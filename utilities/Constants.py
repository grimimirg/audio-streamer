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

# Icecast source configuration
# Only validated when the relay is enabled, so a station that never streams to
# Icecast is not forced to fill these in.
try:
    ICECAST_ENABLED = os.getenv('ICECAST_ENABLED', 'False').lower() in ('true', '1', 'yes')
    ICECAST_HOST = os.getenv('ICECAST_HOST', 'localhost')
    ICECAST_PORT = int(os.getenv('ICECAST_PORT', '8000'))
    ICECAST_MOUNT = os.getenv('ICECAST_MOUNT', '/stream')
    ICECAST_USER = os.getenv('ICECAST_USER', 'source')
    ICECAST_PASSWORD = os.getenv('ICECAST_PASSWORD', '')
    ICECAST_BITRATE = int(os.getenv('ICECAST_BITRATE', '128'))
    ICECAST_PROTOCOL = os.getenv('ICECAST_PROTOCOL', 'http').strip().lower()
    ICECAST_RECONNECT_DELAY = float(os.getenv('ICECAST_RECONNECT_DELAY', '2.0'))
    ICECAST_RECONNECT_MAX_DELAY = float(os.getenv('ICECAST_RECONNECT_MAX_DELAY', '60.0'))
    ICECAST_TEST_TIMEOUT = float(os.getenv('ICECAST_TEST_TIMEOUT', '5.0'))

    if not ICECAST_MOUNT.startswith('/'):
        ICECAST_MOUNT = f"/{ICECAST_MOUNT}"

    if ICECAST_ENABLED:
        if not 0 < ICECAST_PORT < 65536:
            raise ValueError(f"ICECAST_PORT {ICECAST_PORT} is out of valid range (1-65535)")
        if not ICECAST_PASSWORD:
            raise ValueError("ICECAST_PASSWORD is required when ICECAST_ENABLED is true")
        if ICECAST_BITRATE < 64 or ICECAST_BITRATE > 320:
            raise ValueError(f"ICECAST_BITRATE {ICECAST_BITRATE} is out of valid range (64-320)")
        if ICECAST_PROTOCOL not in ('http', 'icy', 'xaudiocast'):
            raise ValueError(
                f"ICECAST_PROTOCOL '{ICECAST_PROTOCOL}' is not one of http, icy, xaudiocast"
            )
        if ICECAST_RECONNECT_DELAY <= 0:
            raise ValueError("ICECAST_RECONNECT_DELAY must be greater than zero")
        if ICECAST_RECONNECT_MAX_DELAY < ICECAST_RECONNECT_DELAY:
            raise ValueError(
                "ICECAST_RECONNECT_MAX_DELAY cannot be smaller than ICECAST_RECONNECT_DELAY"
            )
        if ICECAST_TEST_TIMEOUT <= 0:
            raise ValueError("ICECAST_TEST_TIMEOUT must be greater than zero")
except ValueError as e:
    print(f"\nERROR: Invalid Icecast configuration in .env file: {e}")
    print("Please check ICECAST_PORT, ICECAST_PASSWORD, ICECAST_BITRATE, ICECAST_PROTOCOL, "
          "ICECAST_RECONNECT_DELAY, and ICECAST_RECONNECT_MAX_DELAY values.")
    sys.exit(1)

# Shoutcast source configuration
# libshout speaks the ICY source protocol, which is Shoutcast v1; DNAS 2 servers
# accept it on their legacy source port. Only validated when enabled.
try:
    SHOUTCAST_ENABLED = os.getenv('SHOUTCAST_ENABLED', 'False').lower() in ('true', '1', 'yes')
    SHOUTCAST_HOST = os.getenv('SHOUTCAST_HOST', 'localhost')
    SHOUTCAST_PORT = int(os.getenv('SHOUTCAST_PORT', '8000'))
    SHOUTCAST_MOUNT = os.getenv('SHOUTCAST_MOUNT', '/stream')
    SHOUTCAST_USER = os.getenv('SHOUTCAST_USER', 'source')
    SHOUTCAST_PASSWORD = os.getenv('SHOUTCAST_PASSWORD', '')
    SHOUTCAST_BITRATE = int(os.getenv('SHOUTCAST_BITRATE', '128'))
    SHOUTCAST_RECONNECT_DELAY = float(os.getenv('SHOUTCAST_RECONNECT_DELAY', '2.0'))
    SHOUTCAST_RECONNECT_MAX_DELAY = float(os.getenv('SHOUTCAST_RECONNECT_MAX_DELAY', '60.0'))
    SHOUTCAST_TEST_TIMEOUT = float(os.getenv('SHOUTCAST_TEST_TIMEOUT', '5.0'))

    if not SHOUTCAST_MOUNT.startswith('/'):
        SHOUTCAST_MOUNT = f"/{SHOUTCAST_MOUNT}"

    if SHOUTCAST_ENABLED:
        if not 0 < SHOUTCAST_PORT < 65536:
            raise ValueError(f"SHOUTCAST_PORT {SHOUTCAST_PORT} is out of valid range (1-65535)")
        if not SHOUTCAST_PASSWORD:
            raise ValueError("SHOUTCAST_PASSWORD is required when SHOUTCAST_ENABLED is true")
        if SHOUTCAST_BITRATE < 64 or SHOUTCAST_BITRATE > 320:
            raise ValueError(
                f"SHOUTCAST_BITRATE {SHOUTCAST_BITRATE} is out of valid range (64-320)"
            )
        if SHOUTCAST_RECONNECT_DELAY <= 0:
            raise ValueError("SHOUTCAST_RECONNECT_DELAY must be greater than zero")
        if SHOUTCAST_RECONNECT_MAX_DELAY < SHOUTCAST_RECONNECT_DELAY:
            raise ValueError(
                "SHOUTCAST_RECONNECT_MAX_DELAY cannot be smaller than SHOUTCAST_RECONNECT_DELAY"
            )
        if SHOUTCAST_TEST_TIMEOUT <= 0:
            raise ValueError("SHOUTCAST_TEST_TIMEOUT must be greater than zero")
except ValueError as e:
    print(f"\nERROR: Invalid Shoutcast configuration in .env file: {e}")
    print("Please check SHOUTCAST_PORT, SHOUTCAST_PASSWORD, SHOUTCAST_BITRATE, "
          "SHOUTCAST_RECONNECT_DELAY, SHOUTCAST_RECONNECT_MAX_DELAY, and "
          "SHOUTCAST_TEST_TIMEOUT values.")
    sys.exit(1)

# Station identity, shared by the web interface and the relay mount metadata
RADIO_STATION_NAME = os.getenv('RADIO_STATION_NAME', 'My Radio Station')
