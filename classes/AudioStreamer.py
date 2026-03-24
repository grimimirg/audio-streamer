import queue
import threading
import logging
from typing import List, Optional

import pyaudio

from utilities.Constants import FORMAT, CHANNELS, RATE, CHUNK


class AudioStreamer:
    """Core audio streaming engine that captures audio from input devices
    and distributes it to connected clients via thread-safe queues."""

    def __init__(self):
        """Initialize the audio streaming system.
        
        Sets up PyAudio interface, streaming state, client management,
        and thread synchronization primitives.
        """
        self.audioInterface = pyaudio.PyAudio()
        self.currentStream = None  # Active PyAudio stream object
        self.onAir = False         # Streaming state flag
        self.listeningClients = []  # List of client queues for audio distribution
        self._lock = threading.RLock()  # Thread-safe lock for client management
        logging.basicConfig(level=logging.INFO)

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
            self.currentStream = self.audioInterface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=listeningDeviceIndexes[0] if listeningDeviceIndexes else None,
                frames_per_buffer=CHUNK
            )
        except Exception as e:
            logging.error(f"Failed to open audio stream: {e}")
            return

        # Start the audio capture thread
        self.onAir = True
        threading.Thread(target=self._captureAudioFromStream, daemon=True).start()

        logging.info(f"Audio streaming on {listeningDeviceIndexes} started")

    def stopAudioStream(self):
        """Stop audio streaming and clean up resources safely.
        
        Sets the onAir flag to False to stop the capture thread,
        then properly closes and cleans up the audio stream and interface.
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

        # Terminate the PyAudio interface
        try:
            self.audioInterface.terminate()
        except Exception as e:
            logging.error(f"Error terminating audio interface: {e}")

    def addClient(self, clientQueue: queue.Queue):
        """Add a new client queue to receive audio data.
        
        Args:
            clientQueue: Thread-safe queue for sending audio chunks to this client
        """
        with self._lock:  # Thread-safe client list modification
            self.listeningClients.append(clientQueue)
            logging.info("New connected client")

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
        while self.onAir:
            try:
                # Read audio data from the input device
                data = self.currentStream.read(CHUNK)
                
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
                        
            except Exception as e:
                # Handle stream errors (device disconnect, etc.)
                if self.onAir:  # Only log if we're supposed to be streaming
                    logging.error(f"Error reading from audio stream: {e}")
                break  # Exit the loop on error
