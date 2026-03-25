import os
import pyaudio

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100

# Network configuration
HOST_ADDR = os.getenv('AUDIO_STREAMER_HOST', '0.0.0.0')
PORT = int(os.getenv('AUDIO_STREAMER_PORT', '4986'))
DEBUG = os.getenv('AUDIO_STREAMER_DEBUG', 'False').lower() in ('true', '1', 'yes')

# Streaming configuration
MAX_CLIENTS = int(os.getenv('AUDIO_STREAMER_MAX_CLIENTS', '10'))
CLIENT_QUEUE_SIZE = int(os.getenv('AUDIO_STREAMER_QUEUE_SIZE', '100'))
