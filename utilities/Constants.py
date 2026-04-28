import os
import sys
import pyaudio
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('.env')
if not env_path.exists():
    print("\nERROR: .env file not found!")
    print("Please create a .env file from .env.example")
    sys.exit(1)

load_dotenv()

# Audio configuration
try:
    CHUNK = int(os.getenv('AUDIO_CHUNK', '1024'))
    FORMAT = pyaudio.paInt16
    CHANNELS = int(os.getenv('AUDIO_CHANNELS', '2'))
    RATE = int(os.getenv('AUDIO_RATE', '44100'))
except ValueError as e:
    print(f"\nERROR: Invalid audio configuration in .env file: {e}")
    print("Please check AUDIO_CHUNK, AUDIO_CHANNELS, and AUDIO_RATE values.")
    sys.exit(1)

# Network configuration
try:
    HOST_ADDR = os.getenv('AUDIO_STREAMER_HOST', '0.0.0.0')
    PORT = int(os.getenv('AUDIO_STREAMER_PORT', '4986'))
    DEBUG = os.getenv('AUDIO_STREAMER_DEBUG', 'False').lower() in ('true', '1', 'yes')
except ValueError as e:
    print(f"\nERROR: Invalid network configuration in .env file: {e}")
    print("Please check AUDIO_STREAMER_PORT value.")
    sys.exit(1)

# Streaming configuration
try:
    MAX_CLIENTS = int(os.getenv('AUDIO_STREAMER_MAX_CLIENTS', '10'))
    CLIENT_QUEUE_SIZE = int(os.getenv('AUDIO_STREAMER_QUEUE_SIZE', '100'))
except ValueError as e:
    print(f"\nERROR: Invalid streaming configuration in .env file: {e}")
    print("Please check AUDIO_STREAMER_MAX_CLIENTS and AUDIO_STREAMER_QUEUE_SIZE values.")
    sys.exit(1)
