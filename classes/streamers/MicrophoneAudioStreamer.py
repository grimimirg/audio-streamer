import queue
import subprocess
import threading
import time
from typing import Optional, List

from utilities.Constants import CHANNELS, RATE, CHUNK
from utilities.Logger import Logger


class MicrophoneAudioStreamer:
    """Audio streaming engine (arecord) that captures audio from input devices
    and distributes it to connected clients via thread-safe queues."""

    def __init__(self):
        """Initialize the alternative audio streaming system."""
        self.recordingProcess = None
        self.onAir = False
        self.listeningClients = []
        self._lock = threading.RLock()
        self.startTime = None  # Set by ApplicationController

    def listAvailableDevices(self):
        """List available audio devices using arecord."""
        Logger.info("=== Available audio devices (arecord) ===")
        try:
            result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                Logger.info(result.stdout)
                # Parse and show device options
                lines = result.stdout.split('\n')
                device_count = 0
                for line in lines:
                    if 'card 0:' in line and 'device' in line:
                        device_count += 1
                        if 'device 0:' in line:
                            Logger.info(f"Option {device_count}: Built-in Microphone (default)")
                        elif 'device 2:' in line:
                            Logger.info(f"Option {device_count}: Line-in Jack (3.5mm)")
            else:
                Logger.error("Failed to list devices with arecord")
        except Exception as e:
            Logger.error(f"Error listing devices: {e}")
        Logger.info("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]] = None):
        """Start capturing audio using arecord."""
        if self.onAir:
            Logger.info("Stream already onAir")
            return

        try:
            # Determine which device to use
            device = 'default'  # Default to built-in microphone

            if listeningDeviceIndexes and len(listeningDeviceIndexes) > 0:
                device_choice = listeningDeviceIndexes[0]
                if device_choice == 2:  # User chose line-in jack
                    device = 'hw:0,2'
                    Logger.info("Using Line-in Jack (3.5mm)")
                else:
                    device = 'default'
                    Logger.info("Using Built-in Microphone")
            else:
                Logger.info("No device specified, using Built-in Microphone (default)")

            # Build arecord command
            cmd = [
                'arecord',
                '-D', device,
                '-f', 'cd',  # CD quality (16-bit, 44100 Hz, stereo)
                '-c', str(CHANNELS),
                '-r', str(RATE),
                '--buffer-size', str(CHUNK),
                '-t', 'raw',  # Raw PCM output
                '-'  # Output to stdout
            ]

            Logger.info(f"Starting arecord with command: {' '.join(cmd)}")

            # Start arecord process
            self.recordingProcess = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )

            # Start the audio capture thread
            self.onAir = True
            threading.Thread(target=self._captureAudioFromProcess, daemon=True).start()

            Logger.info("Audio streaming started with arecord")

        except Exception as e:
            Logger.error(f"Failed to start arecord: {e}")
            return

    def stopAudioStream(self):
        """Stop audio streaming and clean up."""
        self.onAir = False

        if self.recordingProcess:
            try:
                self.recordingProcess.terminate()
                self.recordingProcess.wait(timeout=5)
                Logger.info("arecord process terminated")
            except Exception as e:
                Logger.error(f"Error terminating arecord: {e}")
                self.recordingProcess.kill()

            self.recordingProcess = None

    def addClient(self, clientQueue: queue.Queue):
        """Add a client queue for audio distribution."""
        Logger.info("Client connected")
        with self._lock:
            self.listeningClients.append(clientQueue)
            Logger.info(f"New connected client. Number of connected clients: {len(self.listeningClients)}")

    def removeClient(self, clientQueue: queue.Queue):
        """Remove a client queue from distribution list."""
        with self._lock:
            if clientQueue in self.listeningClients:
                self.listeningClients.remove(clientQueue)
                Logger.info(f"Client disconnected. Number of connected clients: {len(self.listeningClients)}")

    def getStats(self):
        """Get current streaming statistics."""
        with self._lock:
            # Calculate uptime
            uptime_seconds = 0
            if self.startTime:
                uptime_seconds = int(time.time() - self.startTime)

            return {
                'on_air': self.onAir,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': self._formatUptime(uptime_seconds),
                'start_time': self.startTime
            }

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

    def _captureAudioFromProcess(self):
        """Read audio data from arecord process and distribute to clients."""
        Logger.info("Audio capture thread started - reading from arecord")

        try:
            while self.onAir and self.recordingProcess:
                # Read audio chunk from arecord
                data = self.recordingProcess.stdout.read(CHUNK * 2)  # 2 bytes per sample for 16-bit

                if not data:
                    # Check if process ended
                    if self.recordingProcess.poll() is not None:
                        stderr = self.recordingProcess.stderr.read().decode()
                        stdout = self.recordingProcess.stdout.read().decode()
                        Logger.error(f"arecord process ended with code {self.recordingProcess.returncode}")
                        Logger.error(f"arecord stderr: {stderr}")
                        Logger.error(f"arecord stdout: {stdout}")
                        break
                    else:
                        # Process still running but no data, wait a bit
                        import time
                        time.sleep(0.01)
                        continue

                # Log first few chunks for debugging
                if not hasattr(self, '_chunkCount'):
                    self._chunkCount = 0
                self._chunkCount += 1
                if self._chunkCount <= 5:
                    Logger.info(f"Read chunk {self._chunkCount}: {len(data)} bytes")

                # Distribute to clients
                with self._lock:
                    clientsCopy = self.listeningClients.copy()

                for client in clientsCopy:
                    try:
                        client.put_nowait(data)
                    except queue.Full:
                        Logger.warning("Client queue full, dropping audio chunk")

        except Exception as e:
            Logger.error(f"Error in audio capture thread: {e}")
            import traceback
            Logger.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            self.onAir = False
            Logger.info("Audio capture thread ended")
