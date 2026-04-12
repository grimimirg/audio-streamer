import logging
import queue
import threading
import time
from typing import List, Optional

import pyaudio

from utilities.Constants import FORMAT, CHANNELS, RATE, CHUNK


def getSupportedSampleRate(deviceIndex, defaultRate=44100):
    """Try to find a supported sample rate for the given device."""
    commonRates = [44100, 48000, 22050, 16000, 8000]

    # Try the default rate first
    try:
        audio = pyaudio.PyAudio()
        deviceInfo = audio.get_device_info_by_index(deviceIndex)
        audio.terminate()

        # If device reports a specific rate, try that first
        if 'defaultSampleRate' in deviceInfo:
            suggestedRate = int(deviceInfo['defaultSampleRate'])
            if suggestedRate in commonRates:
                commonRates.insert(0, suggestedRate)
    except:
        pass

    # Test each rate
    for rate in commonRates:
        try:
            audio = pyaudio.PyAudio()

            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=rate,
                input=True,
                input_device_index=deviceIndex,
                frames_per_buffer=CHUNK
            )

            stream.close()
            audio.terminate()
            logging.info(f"Device {deviceIndex} supports sample rate: {rate}")

            return rate
        except Exception:
            continue

    return defaultRate  # Fallback to default


class CardAudioStreamer:
    """Audio streaming engine (PyAudio)that captures audio from input devices
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
        
        # Additional metrics
        self.startTime = None  # When streaming started
        self.totalDataTransferred = 0  # Total bytes sent
        self.peakListeners = 0  # Maximum concurrent listeners
        self.chunkCount = 0  # Total audio chunks processed

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
            for deviceIdx in listeningDeviceIndexes:
                if deviceIdx >= self.audioInterface.get_device_count() or deviceIdx < 0:
                    logging.error(f"Invalid device index: {deviceIdx}")
                    return

        # Open audio stream with error handling
        try:
            # Find supported sample rate for this device
            deviceIdx = listeningDeviceIndexes[0] if listeningDeviceIndexes else None
            if deviceIdx is not None:
                supportedRate = getSupportedSampleRate(deviceIdx, RATE)
                logging.info(f"Using sample rate: {supportedRate} Hz for device {deviceIdx}")
            else:
                supportedRate = RATE

            self.currentStream = self.audioInterface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=supportedRate,
                input=True,
                input_device_index=deviceIdx,
                frames_per_buffer=CHUNK
            )
        except Exception as e:
            logging.error(f"Failed to open audio stream: {e}")
            return

        # Start the audio capture thread
        logging.info("Starting audio capture thread...")
        self.onAir = True
        self.startTime = time.time()  # Record start time
        self.totalDataTransferred = 0  # Reset data counter
        self.chunkCount = 0  # Reset chunk counter
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
            # Update peak listeners
            currentListeners = len(self.listeningClients)
            if currentListeners > self.peakListeners:
                self.peakListeners = currentListeners
            logging.info(f"New connected client. Number of connected clients: {currentListeners}")

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
            dict: Contains streaming status, listener count, audio parameters, and additional metrics
        """
        with self._lock:  # Thread-safe access to all metrics
            # Calculate uptime if streaming is active
            uptime_seconds = 0
            if self.startTime and self.onAir:
                uptime_seconds = int(time.time() - self.startTime)
            
            # Format data transferred in human-readable format
            data_mb = self.totalDataTransferred / (1024 * 1024)  # Convert to MB
            
            stats = {
                'on_air': self.onAir,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': self._formatUptime(uptime_seconds),
                'total_data_mb': round(data_mb, 2),
                'peak_listeners': self.peakListeners,
                'chunks_processed': self.chunkCount,
                'avg_chunk_size': round(self.totalDataTransferred / max(1, self.chunkCount), 0) if self.chunkCount > 0 else 0
            }
            
        logging.info(f"Current stats: {stats}")
        return stats
    
    def _formatUptime(self, seconds):
        """Format uptime seconds into human-readable string.
        
        Args:
            seconds: Uptime in seconds
            
        Returns:
            str: Formatted uptime string (e.g., "1h 23m 45s")
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}h {minutes}m {secs}s"

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
                
                # Update metrics
                self.chunkCount += 1
                chunkSize = len(data)
                
                # Create a thread-safe snapshot of current clients
                with self._lock:
                    clientsCopy = self.listeningClients.copy()
                    # Update total data transferred (chunk size * number of clients)
                    self.totalDataTransferred += chunkSize * len(clientsCopy)

                # Distribute audio data to all connected clients
                for client in clientsCopy:
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
