import logging
import queue
import threading
import subprocess
from typing import List, Optional

from utilities.Constants import CHANNELS, RATE, CHUNK


class MicrophoneAudioStreamer:
    """Alternative audio streaming engine using arecord instead of PyAudio.
    
    This version uses subprocess to call arecord for audio capture,
    which is more stable on Linux systems.
    """

    def __init__(self):
        """Initialize the alternative audio streaming system."""
        self.recording_process = None
        self.onAir = False
        self.listeningClients = []
        self._lock = threading.RLock()

    def listAvailableDevices(self):
        """List available audio devices using arecord."""
        logging.info("=== Available audio devices (arecord) ===")
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                logging.info(result.stdout)
            else:
                logging.error("Failed to list devices with arecord")
        except Exception as e:
            logging.error(f"Error listing devices: {e}")
        logging.info("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]]):
        """Start capturing audio using arecord.
        
        Args:
            listeningDeviceIndexes: List of device indexes (not used with arecord,
                                    we use device names instead)
        """
        if self.onAir:
            logging.info("Stream already onAir")
            return

        try:
            # Build arecord command
            cmd = [
                'arecord',
                '-D', 'pulse',  # Use PulseAudio
                '-f', 'cd',     # CD quality (16-bit, 44100 Hz, stereo)
                '-c', str(CHANNELS),
                '-r', str(RATE),
                '--buffer-size', str(CHUNK),
                '-t', 'raw',    # Raw PCM output
                '-'             # Output to stdout
            ]
            
            logging.info(f"Starting arecord with command: {' '.join(cmd)}")
            
            # Start arecord process
            self.recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )
            
            # Start the audio capture thread
            self.onAir = True
            threading.Thread(target=self._captureAudioFromProcess, daemon=True).start()
            
            logging.info("Audio streaming started with arecord")
            
        except Exception as e:
            logging.error(f"Failed to start arecord: {e}")
            return

    def stopAudioStream(self):
        """Stop audio streaming and clean up."""
        self.onAir = False
        
        if self.recording_process:
            try:
                self.recording_process.terminate()
                self.recording_process.wait(timeout=5)
                logging.info("arecord process terminated")
            except Exception as e:
                logging.error(f"Error terminating arecord: {e}")
                self.recording_process.kill()
            
            self.recording_process = None

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

    def _captureAudioFromProcess(self):
        """Read audio data from arecord process and distribute to clients."""
        logging.info("Audio capture thread started - reading from arecord")
        
        try:
            while self.onAir and self.recording_process:
                # Read audio chunk from arecord
                data = self.recording_process.stdout.read(CHUNK * 2)  # 2 bytes per sample for 16-bit
                
                if not data:
                    # Check if process ended
                    if self.recording_process.poll() is not None:
                        stderr = self.recording_process.stderr.read().decode()
                        stdout = self.recording_process.stdout.read().decode()
                        logging.error(f"arecord process ended with code {self.recording_process.returncode}")
                        logging.error(f"arecord stderr: {stderr}")
                        logging.error(f"arecord stdout: {stdout}")
                        break
                    else:
                        # Process still running but no data, wait a bit
                        import time
                        time.sleep(0.01)
                        continue
                
                # Log first few chunks for debugging
                if not hasattr(self, '_chunk_count'):
                    self._chunk_count = 0
                self._chunk_count += 1
                if self._chunk_count <= 5:
                    logging.info(f"Read chunk {self._chunk_count}: {len(data)} bytes")
                
                # Distribute to clients
                with self._lock:
                    clients_copy = self.listeningClients.copy()
                
                for client in clients_copy:
                    try:
                        client.put_nowait(data)
                    except queue.Full:
                        logging.warning("Client queue full, dropping audio chunk")
                        
        except Exception as e:
            logging.error(f"Error in audio capture thread: {e}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            self.onAir = False
            logging.info("Audio capture thread ended")
