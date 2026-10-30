import os
import sys
from pathlib import Path

import pyaudio
from dotenv import load_dotenv

# Load environment variables from .env file.
# The file is optional when the configuration is already present in the process
# environment (systemd units, containers, test runs); it is required otherwise.
env_path = Path('.env')
if env_path.exists():
    load_dotenv()
elif not any(key.startswith('AUDIO_') for key in os.environ):
    print("\nERROR: .env file not found!")
    print("Please create a .env file from .env.example")
    sys.exit(1)

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
    FFMPEG_THREADS = int(os.getenv('FFMPEG_THREADS', '0'))

    if FFMPEG_THREADS < 0:
        raise ValueError(f"FFMPEG_THREADS {FFMPEG_THREADS} cannot be negative")

    for bitrate in STREAM_BITRATES:
        if bitrate < 64 or bitrate > 320:
            raise ValueError(
                f"Bitrate {bitrate} is out of valid range (64-320)"
            )
except ValueError as e:
    print(f"\nERROR: Invalid streaming configuration in .env file: {e}")
    print("Please check AUDIO_STREAMER_MAX_CLIENTS, AUDIO_STREAMER_QUEUE_SIZE, AUDIO_STREAM_BITRATES, FFMPEG_OUTPUT_QUEUE_SIZE, FFMPEG_QUEUE_TIMEOUT, and FFMPEG_THREADS values.")
    sys.exit(1)

# CPU monitoring configuration
try:
    CPU_WARNING_THRESHOLD = float(os.getenv('CPU_WARNING_THRESHOLD', '80'))
    CPU_MONITOR_INTERVAL = float(os.getenv('CPU_MONITOR_INTERVAL', '5.0'))

    if not 0 < CPU_WARNING_THRESHOLD <= 100:
        raise ValueError(
            f"CPU_WARNING_THRESHOLD {CPU_WARNING_THRESHOLD} is out of valid range (0-100)"
        )
    if CPU_MONITOR_INTERVAL <= 0:
        raise ValueError(
            f"CPU_MONITOR_INTERVAL {CPU_MONITOR_INTERVAL} must be greater than zero"
        )
except ValueError as e:
    print(f"\nERROR: Invalid CPU monitoring configuration in .env file: {e}")
    print("Please check CPU_WARNING_THRESHOLD and CPU_MONITOR_INTERVAL values.")
    sys.exit(1)
