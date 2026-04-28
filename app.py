import logging
import sys
import os
from pathlib import Path
from classes.ApplicationController import ApplicationController
from utilities.Constants import HOST_ADDR, PORT, DEBUG


if __name__ == '__main__':
    """Main entry point for the Audio Streamer application.
    
    Initializes the application, performs setup, and starts the server.
    Handles setup failures gracefully with appropriate error codes.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        print("\n" + "="*70)
        print("ERROR: Configuration file '.env' not found!")
        print("="*70)
        print("\nThe .env file is required to run this application.")
        print("\nTo create it, run:")
        print("  cp .env.example .env")
        print("\nThen edit .env with your configuration settings.")
        print("="*70 + "\n")
        sys.exit(1)
    
    try:
        # Initialize application
        app = ApplicationController()
        
        # Perform setup
        if app.setup() is None:
            logging.error("Application setup failed. Exiting.")
            sys.exit(1)
        
        # Start the server
        logging.info(f"Starting server on {HOST_ADDR}:{PORT} (debug={DEBUG})")
        app.run(host=HOST_ADDR, port=PORT, debug=DEBUG)
        
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
