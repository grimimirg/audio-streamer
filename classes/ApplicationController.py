from classes.AudioHttpFacade import AudioHttpFacade
from classes.AudioStreamer import AudioStreamer


class ApplicationController:

    def __init__(self):
        self.audioStreamer = AudioStreamer()
        self.audioHttpFacade = AudioHttpFacade(self.audioStreamer)

    def setup(self):
        self.audioStreamer.listAvailableDevices()
        deviceIndex = self._askForDeviceIndex()
        self.audioStreamer.startAudioStream(deviceIndex)

        return self

    def run(self, host: str, port: int, debug: bool):
        try:
            self.audioHttpFacade.run(host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        print("Shutting down...")
        self.audioStreamer.stopAudioStream()

    # -- PRIVATES --

    def _askForDeviceIndex(self):
        try:
            choice = input("Choose a device index to stream from (empty = default is used):").strip()
            if choice == "":
                print("Using default")
                return None
            else:
                deviceIndex = int(choice)
                print("Using " + deviceIndex)
                return deviceIndex
        except ValueError:
            print("⚠️  Input non valido, uso dispositivo di default")
            return None
