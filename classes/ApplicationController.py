import logging
from typing import Optional, List
from classes.AudioHttpFacade import AudioHttpFacade
from classes.AudioStreamer import AudioStreamer


class ApplicationController:
    """Main application controller that orchestrates audio streaming and HTTP server.
    
    Handles device selection, audio streaming setup, and server lifecycle management.
    """

    def __init__(self):
        """Initialize the application with audio streaming and HTTP components."""
        self.audioStreamer = AudioStreamer()
        self.audioHttpFacade = AudioHttpFacade(self.audioStreamer)
        self._setup_successful = False
        logging.basicConfig(level=logging.INFO)

    def setup(self):
        """Setup audio streaming by selecting devices and starting capture.
        
        Returns:
            self: Returns self for method chaining, or None if setup fails
        """
        try:
            self.audioStreamer.listAvailableDevices()
            deviceIndex = self._askForDeviceIndex()
            
            if deviceIndex is None:
                logging.warning("No device selected, using default")
            
            # Start audio streaming
            self.audioStreamer.startAudioStream(deviceIndex)
            
            # Verify streaming started successfully
            if not self.audioStreamer.onAir:
                logging.error("Failed to start audio streaming")
                return None
                
            self._setup_successful = True
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
        if not self._setup_successful:
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
                logging.error("Invalid input format. Please enter numbers separated by spaces, or press ENTER for default.")
                # Continue the loop to ask again
                continue
            except (EOFError, KeyboardInterrupt):
                logging.info("No device selected, using default")
                return None
