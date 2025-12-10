import queue
import threading

import pyaudio

from utilities.Constants import FORMAT, CHANNELS, RATE, CHUNK


class AudioStreamer:

    def __init__(self):
        self.audioInterface = pyaudio.PyAudio()
        self.currentStream = None
        self.onAir = False
        self.listeningClients = []

    def listAvailableDevices(self):
        print("=== Available audio devices ===")
        for i in range(self.audioInterface.get_device_count()):
            info = self.audioInterface.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(str(i) + ":" + info['name'] + " - Input channels: " + info['maxInputChannels'])
        print("=" * 10)

    def startAudioStream(self, listeningDeviceIndexes: List[int]):
        if self.onAir:
            print("Stream on " + str(listeningDeviceIndexes) + " already OnAir")
            return

        self.currentStream = self.audioInterface.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=listeningDeviceIndexes,
            frames_per_buffer=CHUNK
        )

        self.onAir = True
        threading.Thread(target=self._captureAudioFromStream(), daemon=True).start()

        print("Audio streaming on " + str(listeningDeviceIndex) + " started")

    def stopAudioStream(self):
        self.onAir = False
        self.currentStream.stop_stream()
        self.currentStream.close()

        self.audioInterface.terminate()

    def addClient(self, clientQueue: queue.Queue):
        self.listeningClients.append(clientQueue)
        print("New connected client")

    def removeClient(self, clientQueue: queue.Queue):
        if clientQueue in self.listeningClients:
            self.listeningClients.remove(clientQueue)
            print("Client disconnected")

    def getStats(self):
        return {
            'on_air': self.onAir,
            'listeners': len(self.listeningClients),
            'sample_rate': RATE,
            'channels': CHANNELS
        }

    # -- PRIVATES --

    def _captureAudioFromStream(self):
        while self.onAir:
            data = self.currentStream.read(CHUNK)
            for client in self.listeningClients:
                client.put_nowait(data)
