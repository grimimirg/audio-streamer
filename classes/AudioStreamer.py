import queue
import threading
import logging
from typing import List, Optional

import pyaudio

from utilities.Constants import FORMAT, CHANNELS, RATE, CHUNK


class AudioStreamer:

    def __init__(self):
        self.audioInterface = pyaudio.PyAudio()
        self.currentStream = None
        self.onAir = False
        self.listeningClients = []
        self._lock = threading.RLock()
        logging.basicConfig(level=logging.INFO)

    def listAvailableDevices(self):
        logging.info("=== Available audio devices ===")
        for i in range(self.audioInterface.get_device_count()):
            info = self.audioInterface.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                logging.info(f"{i}: {info['name']} - Input channels: {info['maxInputChannels']}")
        logging.info("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: Optional[List[int]]):
        if self.onAir:
            logging.info(f"Stream on {listeningDeviceIndexes} already OnAir")
            return

        # Validate device indexes
        if listeningDeviceIndexes is not None:
            for device_idx in listeningDeviceIndexes:
                if device_idx >= self.audioInterface.get_device_count() or device_idx < 0:
                    logging.error(f"Invalid device index: {device_idx}")
                    return

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

        self.onAir = True
        threading.Thread(target=self._captureAudioFromStream, daemon=True).start()

        logging.info(f"Audio streaming on {listeningDeviceIndexes} started")

    def stopAudioStream(self):
        self.onAir = False
        
        if self.currentStream is not None:
            try:
                self.currentStream.stop_stream()
                self.currentStream.close()
            except Exception as e:
                logging.error(f"Error closing stream: {e}")
            finally:
                self.currentStream = None

        try:
            self.audioInterface.terminate()
        except Exception as e:
            logging.error(f"Error terminating audio interface: {e}")

    def addClient(self, clientQueue: queue.Queue):
        with self._lock:
            self.listeningClients.append(clientQueue)
            logging.info("New connected client")

    def removeClient(self, clientQueue: queue.Queue):
        with self._lock:
            if clientQueue in self.listeningClients:
                self.listeningClients.remove(clientQueue)
                logging.info("Client disconnected")

    def getStats(self):
        with self._lock:
            return {
                'on_air': self.onAir,
                'listeners': len(self.listeningClients),
                'sample_rate': RATE,
                'channels': CHANNELS
            }

    # -- PRIVATES --

    def _captureAudioFromStream(self):
        while self.onAir:
            try:
                data = self.currentStream.read(CHUNK)
                with self._lock:
                    clients_copy = self.listeningClients.copy()
                
                for client in clients_copy:
                    try:
                        client.put_nowait(data)
                    except queue.Full:
                        logging.warning("Client queue full, dropping audio chunk")
            except Exception as e:
                if self.onAir:  # Only log if we're supposed to be streaming
                    logging.error(f"Error reading from audio stream: {e}")
                break
