from typing import Optional, List
import time

from classes.streamer.AudioStreamerFactory import AudioStreamerFactory
from classes.streamer.streamers.IcecastStreamer import IcecastStreamer
from classes.streamer.streamers.ShoutcastStreamer import ShoutcastStreamer
from .AudioHttpFacade import AudioHttpFacade
from utilities.Constants import ICECAST_ENABLED, SHOUTCAST_ENABLED
from utilities.FfmpegCapabilities import log_encoding_capabilities
from utilities.Logger import Logger


class ApplicationController:
    """Main application controller that orchestrates audio streaming and HTTP server.
    
    Handles device selection, audio streaming setup, and server lifecycle management.
    """

    # The relays that can be offered at startup, in menu order. Each entry maps
    # the relay class to the attribute holding it and the facade setter that
    # publishes its state, so adding a protocol is a one-line change here.
    _RELAYS = (
        (IcecastStreamer, 'icecastStreamer', 'set_icecast_streamer'),
        (ShoutcastStreamer, 'shoutcastStreamer', 'set_shoutcast_streamer'),
    )

    def __init__(self):
        """Initialize the application with audio streaming and HTTP components."""
        # We'll choose the best streamer based on device selection
        self.audioStreamer = None
        self.audioHttpFacade = None
        self.icecastStreamer = None
        self.shoutcastStreamer = None
        # Always at least the direct stream; the startup menu may add relays
        self.protocols = ['direct']
        self._setupSuccessful = False
        self.startTime = time.time()  # Application start time

    def _askForInputMethod(self):
        """Ask user to choose between microphone, audio interface, or liquid music."""
        while True:
            try:
                print("\n" + "=" * 50)
                print("Choose your audio input method:")
                print("1. Microphone (built-in or USB mic)")
                print("2. Audio Interface (external sound card, line-in)")
                print("3. Liquid Music (file-based music playback)")
                print("=" * 50)

                choice = input("Enter your choice (1, 2, or 3): ").strip()

                if choice == "1":
                    Logger.info("User selected: Microphone input")
                    return "microphone"
                elif choice == "2":
                    Logger.info("User selected: Audio interface input")
                    return "interface"
                elif choice == "3":
                    Logger.info("User selected: Liquid Music")
                    return "liquid_music"
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
                    continue

            except (EOFError, KeyboardInterrupt):
                Logger.info("User interrupted, defaulting to microphone")
                return "microphone"

    def _createStreamer(self, input_method):
        """Create the appropriate audio streamer based on user choice using the factory.
        
        Args:
            input_method: The selected input method (microphone, interface, or liquid_music)
            
        Returns:
            An instance of the appropriate audio streamer class
        """
        return AudioStreamerFactory.create(input_method)

    def setup(self):
        """Setup audio streaming by selecting devices and starting capture.
        
        Returns:
            self: Returns self for method chaining, or None if setup fails
        """
        try:
            # Record what the host's ffmpeg can do before any encoding starts
            log_encoding_capabilities()

            # First, ask user for input method
            input_method = self._askForInputMethod()

            # Create the appropriate streamer
            self.audioStreamer = self._createStreamer(input_method)
            self.audioStreamer.startTime = self.startTime  # Set application start time
            self.audioHttpFacade = AudioHttpFacade(self.audioStreamer, input_method)

            # For liquid music, skip device selection and don't auto-start streaming
            if input_method == "liquid_music":
                Logger.info("Liquid Music mode: streaming will start when play is pressed")
                self.audioStreamer.listAvailableDevices()
            else:
                # List available devices and ask for selection
                self.audioStreamer.listAvailableDevices()
                deviceIndex = self._askForDeviceIndex()

                if deviceIndex is None:
                    Logger.warning("No device selected, using default")

                # Start audio streaming
                self.audioStreamer.startAudioStream(deviceIndex)

                # Verify streaming started successfully
                if not self.audioStreamer.onAir:
                    Logger.error("Failed to start audio streaming")
                    return None

            self._startSelectedRelays()
            self.audioHttpFacade.set_protocols(self.protocols)

            self._setupSuccessful = True
            Logger.info("Application setup completed successfully")
            return self

        except Exception as e:
            Logger.error(f"Setup failed: {e}")
            return None

    def run(self, host: str, port: int, debug: bool):
        """Run the HTTP server if setup was successful.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            debug: Enable Flask debug mode
        """
        if not self._setupSuccessful:
            Logger.error("Cannot start server: setup was not successful")
            return

        try:
            self.audioHttpFacade.run(host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            Logger.info("Received interrupt signal, shutting down")
            self.shutdown()
        except Exception as e:
            Logger.error(f"Server error: {e}")
            self.shutdown()

    def shutdown(self):
        """Cleanly shutdown the application by stopping audio streaming."""
        Logger.info("Shutting down application...")
        try:
            if self.icecastStreamer:
                self.icecastStreamer.stop()
            if self.shoutcastStreamer:
                self.shoutcastStreamer.stop()
            if self.audioHttpFacade:
                self.audioHttpFacade.shutdown()
            self.audioStreamer.stopAudioStream()
            Logger.info("Application shutdown completed")
        except Exception as e:
            Logger.error(f"Error during shutdown: {e}")

    def __del__(self):
        """Destructor to ensure proper cleanup."""
        try:
            if hasattr(self, 'audioStreamer') and self.audioStreamer:
                self.audioStreamer.stopAudioStream()
        except Exception:
            pass  # Ignore errors during cleanup

    # -- PRIVATES --

    def _configuredRelays(self):
        """List the relays whose configuration is filled in.

        Being configured is what makes a relay selectable: the .env block
        carries the host and password, and Constants only validates it when the
        relay is enabled. A relay the operator never configured is therefore
        never offered, so the menu cannot start a server without credentials.

        Returns:
            list: The configured relay entries, in menu order
        """
        enabled = {
            IcecastStreamer: ICECAST_ENABLED,
            ShoutcastStreamer: SHOUTCAST_ENABLED,
        }
        return [entry for entry in self._RELAYS if enabled[entry[0]]]

    def _askForProtocol(self, relays, prompt=input):
        """Ask which of the configured relays to use for this run.

        The protocol is chosen per run rather than per configuration, so
        restarting the station is how an operator switches protocols.

        Args:
            relays: The configured relay entries to offer
            prompt: Input function, injectable for testing

        Returns:
            list: The relay entries to start, empty for the direct stream only
        """
        # "all" is only meaningful with more than one relay to combine
        offer_all = len(relays) > 1
        last = len(relays) + (2 if offer_all else 1)

        while True:
            try:
                print("\n" + "=" * 50)
                print("Choose your streaming protocol:")
                print("1. Direct only (listeners connect to this server)")
                for index, (relay_class, _, _) in enumerate(relays, start=2):
                    label = self._relayLabel(relay_class)
                    print(f"{index}. Direct + {label}")
                if offer_all:
                    print(f"{last}. Direct + all configured relays")
                print("=" * 50)

                choice = prompt(f"Enter your choice (1-{last}): ").strip()

                if choice == "1":
                    Logger.info("User selected: direct streaming only")
                    return []
                if offer_all and choice == str(last):
                    Logger.info("User selected: direct streaming plus all configured relays")
                    return list(relays)

                index = int(choice) - 2
                if 0 <= index < len(relays):
                    selected = relays[index]
                    Logger.info(f"User selected: direct streaming plus {self._relayLabel(selected[0])}")
                    return [selected]

                raise ValueError(choice)

            except ValueError:
                print(f"Invalid choice. Please enter a number between 1 and {last}.")
                continue

            except (EOFError, KeyboardInterrupt):
                # No console to answer on - systemd units and containers run
                # without stdin. Falling back to every configured relay keeps
                # unattended deployments behaving exactly as their .env says.
                Logger.info("No protocol selected, using all configured relays")
                return list(relays)

    def _startSelectedRelays(self):
        """Start the relays chosen at startup and publish their state."""
        relays = self._configuredRelays()

        if not relays:
            # Nothing is configured, so there is nothing to choose between and
            # a direct-only station is never asked a question it cannot answer
            Logger.info("No relay configured, streaming directly only")
            return

        for relay_class, attribute, setter in self._askForProtocol(relays):
            relay = self._startRelay(relay_class)
            setattr(self, attribute, relay)
            getattr(self.audioHttpFacade, setter)(relay)

            # A relay that could not start is not an active protocol, so the
            # dashboard does not claim the station is relaying to it
            if relay is not None:
                self.protocols.append(self._relayLabel(relay_class).lower())

    @staticmethod
    def _relayLabel(relay_class) -> str:
        """Name a relay the way the manual does, e.g. "IcecastStreamer" -> "Icecast".

        Args:
            relay_class: The relay class to name

        Returns:
            str: The human-readable relay name
        """
        return relay_class.__name__.removesuffix('Streamer')

    def _startRelay(self, relay_class):
        """Start one relay, reporting rather than raising when it cannot run.

        A failure is logged but does not abort startup, and one relay failing
        leaves the other untouched: the local stream is the primary service, and
        losing a relay should not take the station off the air.

        Args:
            relay_class: The relay class to instantiate

        Returns:
            The started relay, or None if it could not be started
        """
        # Reachability is checked first so an unreachable server is reported as
        # such, rather than surfacing as an opaque mount failure.
        relay_class.test_connection()

        label = self._relayLabel(relay_class)

        try:
            relay = relay_class(self.audioStreamer)
            relay.start()
            return relay
        except RuntimeError as e:
            Logger.error(f"{label} relay disabled: {e}")
            return None

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
                    Logger.info("Using default audio device")
                    return None

                # Parse and validate device indexes
                device_indexes = []
                for part in choice.split():
                    try:
                        device_idx = int(part)
                        if device_idx < 0:
                            Logger.error("Device index cannot be negative")
                            raise ValueError
                        device_indexes.append(device_idx)
                    except ValueError:
                        Logger.error(f"Invalid device index: {part}")
                        raise ValueError

                Logger.info(f"Selected devices: {device_indexes}")
                return device_indexes

            except ValueError:
                Logger.error(
                    "Invalid input format. Please enter numbers separated by spaces, or press ENTER for default.")
                # Continue the loop to ask again
                continue
            except (EOFError, KeyboardInterrupt):
                Logger.info("No device selected, using default")
                return None
