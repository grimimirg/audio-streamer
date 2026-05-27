import os
import sys
from pathlib import Path

import pyaudio
from dotenv import load_dotenv

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
    STREAM_BITRATES = [
        int(bitrate.strip())
        for bitrate in os.getenv('AUDIO_STREAM_BITRATES', '128').split(',')
    ]
    FFMPEG_OUTPUT_QUEUE_SIZE = int(os.getenv('FFMPEG_OUTPUT_QUEUE_SIZE', '50'))
    FFMPEG_QUEUE_TIMEOUT = float(os.getenv('FFMPEG_QUEUE_TIMEOUT', '0.1'))

    for bitrate in STREAM_BITRATES:
        if bitrate < 64 or bitrate > 320:
            raise ValueError(
                f"Bitrate {bitrate} is out of valid range (64-320)"
            )
except ValueError as e:
    print(f"\nERROR: Invalid streaming configuration in .env file: {e}")
    print("Please check AUDIO_STREAMER_MAX_CLIENTS, AUDIO_STREAMER_QUEUE_SIZE, AUDIO_STREAM_BITRATES, FFMPEG_OUTPUT_QUEUE_SIZE, and FFMPEG_QUEUE_TIMEOUT values.")
    sys.exit(1)
