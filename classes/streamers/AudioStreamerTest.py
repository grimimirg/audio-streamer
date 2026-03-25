import logging
import queue
import threading
import time
from typing import List, Optional

from utilities.Constants import CHANNELS, RATE, CHUNK


class AudioStreamerTest:
    """Test audio streaming engine that generates sine wave instead of capturing audio.
    
    This version generates a test tone to verify the streaming pipeline works.
    """

    def __init__(self):
        """Initialize the test audio streaming system."""
        self.onAir = False
        self.listeningClients = []
        self._lock = threading.RLock()

    def listAvailableDevices(self):
        """List available audio devices (mock for test)."""
        logging.info("=== TEST MODE - Generating sine wave ===")
        logging.info("No real audio devices needed")
        logging.info("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]]):
        """Start generating test tone."""
        if self.onAir:
            logging.info("Stream already onAir")
            return

        try:
            # Start the test tone generation thread
            self.onAir = True
            threading.Thread(target=self._generateTestTone, daemon=True).start()
            
            logging.info("Test tone streaming started")
            
        except Exception as e:
            logging.error(f"Failed to start test tone: {e}")
            return

    def stopAudioStream(self):
        """Stop test tone streaming."""
        self.onAir = False
        logging.info("Test tone streaming stopped")

    def addClient(self, clientQueue: queue.Queue):
        """Add a client queue for audio distribution."""
        logging.info("Client connected")
        with self._lock:
            self.listeningClients.append(clientQueue)
            logging.info(f"New connected client. Number of connected clients: {len(self.listeningClients)}")

    def removeClient(self, clientQueue: queue.Queue):
        """Remove a client queue from distribution list."""
        with self._lock:
            if clientQueue in self.listeningClients:
                self.listeningClients.remove(clientQueue)
                logging.info(f"Client disconnected. Number of connected clients: {len(self.listeningClients)}")

    def getStats(self):
        """Get current streaming statistics."""
        with self._lock:
            return {
                'on_air': self.onAir,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS
            }

    def _generateTestTone(self):
        """Generate a 440 Hz sine wave test tone."""
        logging.info("Test tone generation started")
        
        import math
        
        frequency = 440  # A4 note
        amplitude = 0.3  # 30% of max volume
        phase = 0
        
        try:
            while self.onAir:
                # Generate one chunk of sine wave
                chunk_data = bytearray()
                
                for i in range(CHUNK):
                    # Generate sine wave sample
                    sample_value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * phase / RATE))
                    
                    # Convert to 16-bit little-endian
                    chunk_data.extend(sample_value.to_bytes(2, byteorder='little', signed=True))
                    
                    phase += 1
                
                # Distribute to clients
                with self._lock:
                    clients_copy = self.listeningClients.copy()
                
                for client in clients_copy:
                    try:
                        client.put_nowait(bytes(chunk_data))
                    except queue.Full:
                        logging.warning("Client queue full, dropping audio chunk")
                
                # Small delay to control timing
                time.sleep(CHUNK / RATE / 2)  # Half the chunk duration for smooth playback
                
        except Exception as e:
            logging.error(f"Error in test tone generation: {e}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            self.onAir = False
            logging.info("Test tone generation ended")
