import logging
from typing import Optional, List

from classes.streamers.CardAudioStreamer import CardAudioStreamer
from classes.streamers.MicrophoneAudioStreamer import MicrophoneAudioStreamer
from .AudioHttpFacade import AudioHttpFacade


class ApplicationController:
    """Main application controller that orchestrates audio streaming and HTTP server.
    
    Handles device selection, audio streaming setup, and server lifecycle management.
    """

    def __init__(self):
        """Initialize the application with audio streaming and HTTP components."""
        # We'll choose the best streamer based on device selection
        self.audioStreamer = None
        self.audioHttpFacade = None
        self._setupSuccessful = False

    def _askForInputMethod(self):
        """Ask user to choose between microphone and audio interface."""
        while True:
            try:
                print("\n" + "=" * 50)
                print("Choose your audio input method:")
                print("1. Microphone (built-in or USB mic)")
                print("2. Audio Interface (external sound card, line-in)")
                print("=" * 50)

                choice = input("Enter your choice (1 or 2): ").strip()

                if choice == "1":
                    logging.info("User selected: Microphone input")
                    return "microphone"
                elif choice == "2":
                    logging.info("User selected: Audio interface input")
                    return "interface"
                else:
                    print("Invalid choice. Please enter 1 or 2.")
                    continue

            except (EOFError, KeyboardInterrupt):
                logging.info("User interrupted, defaulting to microphone")
                return "microphone"

    def _createStreamer(self, input_method):
        """Create the appropriate audio streamer based on user choice."""
        if input_method == "microphone":
            logging.info("Creating AudioStreamerAlternative for microphone input")
            return MicrophoneAudioStreamer()
        elif input_method == "interface":
            logging.info("Creating AudioStreamer for audio interface input")
            return CardAudioStreamer()
        else:
            # Fallback
            logging.warning("Unknown input method, defaulting to microphone")
            return MicrophoneAudioStreamer()

    def setup(self):
        """Setup audio streaming by selecting devices and starting capture.
        
        Returns:
            self: Returns self for method chaining, or None if setup fails
        """
        try:
            # First, ask user for input method
            input_method = self._askForInputMethod()

            # Create the appropriate streamer
            self.audioStreamer = self._createStreamer(input_method)
            self.audioHttpFacade = AudioHttpFacade(self.audioStreamer)

            # List available devices and ask for selection
            self.audioStreamer.listAvailableDevices()
            deviceIndex = self._askForDeviceIndex()

            if deviceIndex is None:
                logging.warning("No device selected, using default")

            # Start audio streaming
            self.audioStreamer.startAudioStream([deviceIndex] if deviceIndex is not None else None)

            # Verify streaming started successfully
            if not self.audioStreamer.onAir:
                logging.error("Failed to start audio streaming")
                return None

            self._setupSuccessful = True
            logging.info("Application setup completed successfully")
            return self

        except Exception as e:
            logging.error(f"Setup failed: {e}")
            return None

    def run(self, host: str, port: int, debug: bool):
        """Run the HTTP server if setup was successful.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            debug: Enable Flask debug mode
        """
        if not self._setupSuccessful:
            logging.error("Cannot start server: setup was not successful")
            return

        try:
            self.audioHttpFacade.run(host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            logging.info("Received interrupt signal, shutting down")
            self.shutdown()
        except Exception as e:
            logging.error(f"Server error: {e}")
            self.shutdown()

    def shutdown(self):
        """Cleanly shutdown the application by stopping audio streaming."""
        logging.info("Shutting down application...")
        try:
            self.audioStreamer.stopAudioStream()
            logging.info("Application shutdown completed")
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")

    def __del__(self):
        """Destructor to ensure proper cleanup."""
        try:
            if hasattr(self, 'audioStreamer') and self.audioStreamer:
                self.audioStreamer.stopAudioStream()
        except Exception:
            pass  # Ignore errors during cleanup

    # -- PRIVATES --

    def _askForDeviceIndex(self) -> Optional[List[int]]:
        """Prompt user to select audio input device indexes.
        
        Returns:
            List[int] or None: List of device indexes, or None for default device
        """
        while True:  # Keep asking until valid input or empty
            try:
                choice = input(
                    "Choose a device index to stream from (multiple indexes allowed, separated by space, or ENTER for default): ").strip()

                if choice == "":
                    logging.info("Using default audio device")
                    return None

                # Parse and validate device indexes
                device_indexes = []
                for part in choice.split():
                    try:
                        device_idx = int(part)
                        if device_idx < 0:
                            logging.error("Device index cannot be negative")
                            raise ValueError
                        device_indexes.append(device_idx)
                    except ValueError:
                        logging.error(f"Invalid device index: {part}")
                        raise ValueError

                logging.info(f"Selected devices: {device_indexes}")
                return device_indexes

            except ValueError:
                logging.error(
                    "Invalid input format. Please enter numbers separated by spaces, or press ENTER for default.")
                # Continue the loop to ask again
                continue
            except (EOFError, KeyboardInterrupt):
                logging.info("No device selected, using default")
                return None
