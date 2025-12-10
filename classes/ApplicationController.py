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
            choice = input("Choose a device index to stream from (multiple indexes allowed, and separate by a space)").strip()
            if choice == "":
                print("Using default")
                return None
            else:
                return list(map(int, choice))
        except ValueError:
            print("Invalid input")
            return None
