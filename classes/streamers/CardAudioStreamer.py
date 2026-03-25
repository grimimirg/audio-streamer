import logging
import queue
import threading
from typing import List, Optional

import pyaudio

from utilities.Constants import FORMAT, CHANNELS, RATE, CHUNK


def get_supported_sample_rate(device_index, default_rate=44100):
    """Try to find a supported sample rate for the given device."""
    common_rates = [44100, 48000, 22050, 16000, 8000]
    
    # Try the default rate first
    try:
        audio = pyaudio.PyAudio()
        device_info = audio.get_device_info_by_index(device_index)
        audio.terminate()
        
        # If device reports a specific rate, try that first
        if 'defaultSampleRate' in device_info:
            suggested_rate = int(device_info['defaultSampleRate'])
            if suggested_rate in common_rates:
                common_rates.insert(0, suggested_rate)
    except:
        pass
    
    # Test each rate
    for rate in common_rates:
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK
            )
            stream.close()
            audio.terminate()
            logging.info(f"Device {device_index} supports sample rate: {rate}")
            return rate
        except Exception:
            continue
    
    return default_rate  # Fallback to default


class CardAudioStreamer:
    """Core audio streaming engine that captures audio from input devices
    and distributes it to connected clients via thread-safe queues."""

    def __init__(self):
        """Initialize the audio streaming system.
        
        Sets up PyAudio interface, streaming state, client management,
        and thread synchronization primitives.
        """
        self.audioInterface = pyaudio.PyAudio()
        self.currentStream = None  # Active PyAudio stream object
        self.onAir = False  # Streaming state flag
        self.listeningClients = []  # List of client queues for audio distribution
        self._lock = threading.RLock()  # Thread-safe lock for client management

    def listAvailableDevices(self):
        """Print all available audio input devices to the console.
        
        Iterates through system audio devices and displays only those
        with input channels (microphones, line-in, etc.).
        """
        logging.info("=== Available audio devices ===")
        for i in range(self.audioInterface.get_device_count()):
            info = self.audioInterface.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                logging.info(f"{i}: {info['name']} - Input channels: {info['maxInputChannels']}")
        logging.info("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]]):
        """Start capturing audio from specified input devices.
        
        Args:
            listeningDeviceIndexes: List of device indexes to capture from.
                                    If None, uses the system default device.
                                    
        Note: PyAudio only supports single device per stream, so we use
              the first device from the list if multiple are provided.
        """
        if self.onAir:
            logging.info(f"Stream on {listeningDeviceIndexes} already OnAir")
            return

        # Validate device indexes to prevent crashes
        if listeningDeviceIndexes is not None:
            for device_idx in listeningDeviceIndexes:
                if device_idx >= self.audioInterface.get_device_count() or device_idx < 0:
                    logging.error(f"Invalid device index: {device_idx}")
                    return

        # Open audio stream with error handling
        try:
            # Find supported sample rate for this device
            device_idx = listeningDeviceIndexes[0] if listeningDeviceIndexes else None
            if device_idx is not None:
                supported_rate = get_supported_sample_rate(device_idx, RATE)
                logging.info(f"Using sample rate: {supported_rate} Hz for device {device_idx}")
            else:
                supported_rate = RATE
                
            self.currentStream = self.audioInterface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=supported_rate,
                input=True,
                input_device_index=device_idx,
                frames_per_buffer=CHUNK
            )
        except Exception as e:
            logging.error(f"Failed to open audio stream: {e}")
            return

        # Start the audio capture thread
        logging.info("Starting audio capture thread...")
        self.onAir = True
        capture_thread = threading.Thread(target=self._captureAudioFromStream, daemon=True)
        capture_thread.start()
        logging.info("Audio capture thread started successfully")

        logging.info(f"Audio streaming on {listeningDeviceIndexes} started")

    def stopAudioStream(self):
        """Stop audio streaming and clean up resources safely.
        
        Sets the onAir flag to False to stop the capture thread,
        then properly closes and cleans up the audio stream.
        """
        self.onAir = False  # Signal capture thread to stop

        # Safely close the audio stream if it exists
        if self.currentStream is not None:
            try:
                self.currentStream.stop_stream()
                self.currentStream.close()
            except Exception as e:
                logging.error(f"Error closing stream: {e}")
            finally:
                self.currentStream = None  # Prevent dangling references

        # Note: PyAudio interface is kept alive for potential restart
        logging.info("Audio streaming stopped")

    def addClient(self, clientQueue: queue.Queue):
        """Add a new client queue to receive audio data.
        
        Args:
            clientQueue: Thread-safe queue for sending audio chunks to this client
        """
        logging.info(f"Client connected")
        with self._lock:  # Thread-safe client list modification
            self.listeningClients.append(clientQueue)
            logging.info(f"New connected client. Number of connected clients: {len(self.listeningClients)}")

    def removeClient(self, clientQueue: queue.Queue):
        """Remove a client queue from the distribution list.
        
        Args:
            clientQueue: The queue to remove from active clients
        """
        with self._lock:  # Thread-safe client list modification
            if clientQueue in self.listeningClients:
                self.listeningClients.remove(clientQueue)
                logging.info("Client disconnected")

    def getStats(self):
        """Get current streaming statistics.
        
        Returns:
            dict: Contains streaming status, listener count, and audio parameters
        """
        logging.info(f"Current stats: {self.onAir}, {len(self.listeningClients)}, {RATE}, {CHANNELS}")
        with self._lock:  # Thread-safe access to client count
            return {
                'on_air': self.onAir,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS
            }

    # -- PRIVATES --

    def _captureAudioFromStream(self):
        """Background thread: Continuously capture audio and distribute to clients.
        
        This method runs in a daemon thread and:
        1. Reads audio chunks from the input stream
        2. Creates a thread-safe copy of current clients
        3. Distributes audio data to each client queue
        4. Handles queue overflow and stream errors gracefully
        """
        logging.info("Audio capture thread started - beginning capture loop")
        
        while self.onAir:
            try:
                if self.currentStream is None:
                    break

                # Read audio data from the input device
                data = self.currentStream.read(CHUNK, exception_on_overflow=False)

                # Create a thread-safe snapshot of current clients
                with self._lock:
                    clients_copy = self.listeningClients.copy()

                # Distribute audio data to all connected clients
                for client in clients_copy:
                    try:
                        client.put_nowait(data)  # Non-blocking put
                    except queue.Full:
                        # Client queue is full, drop this chunk to prevent blocking
                        logging.warning("Client queue full, dropping audio chunk")

            except OSError as e:
                # Handle stream errors (device disconnect, etc.)
                if self.onAir:  # Only log if we're supposed to be streaming
                    logging.error(f"Audio device error: {e}")
                    logging.error(f"Device info: {self.currentStream}")
                break  # Exit the loop on device error
            except Exception as e:
                # Handle other unexpected errors
                if self.onAir:  # Only log if we're supposed to be streaming
                    logging.error(f"Unexpected error in audio capture: {type(e).__name__}: {e}")
                    import traceback
                    logging.error(f"Full traceback: {traceback.format_exc()}")
                break  # Exit the loop on error
