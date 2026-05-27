# Audio Streamer - User Manual

Welcome to Audio Streamer! This manual will guide you through everything you need to know, whether you're just getting started or diving into advanced integration.

## Table of Contents
- [Getting Started](#getting-started)
- [Technical Overview](#technical-overview)
- [Streaming Modes](#streaming-modes)
  - [Microphone Mode](#1-microphone-mode-microphoneaudiostreamer)
  - [Audio Interface Mode](#2-audio-interface-mode-cardaudiostreamer)
  - [Liquid Music Mode](#3-liquid-music-mode-liquidmusicstreamer)
  - [Bitrate-Based Streaming](#4-bitrate-based-streaming)
- [Configuration](#configuration)
- [Audio Engine Details](#audio-engine-details)
- [Liquid Music Mode](#liquid-music-mode)
- [Security Implementation](#security-implementation)
- [API Reference](#api-reference)
  - [Streaming Endpoints](#streaming-endpoints)
  - [Statistics API](#statistics-api)
  - [Liquid Music Endpoints](#liquid-music-endpoints)
  - [WebSocket Events](#websocket-events)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
  - [Audio Device Issues](#audio-device-issues)
  - [Streaming Issues](#streaming-issues)
  - [File Upload Issues](#file-upload-issues)
  - [Network Issues](#network-issues)
  - [Liquid Music Issues](#liquid-music-issues)
  - [Bitrate Streaming Issues](#bitrate-streaming-issues)

---

## Getting Started

### What is Audio Streamer?

Audio Streamer is a flexible audio broadcasting system that lets you stream audio over your network. Think of it as your personal radio station - you can broadcast live audio from a microphone, play music files from your computer, or mix audio from professional equipment, and multiple listeners can tune in simultaneously.

### What Can You Do With It?

Whether you're a radio enthusiast, a podcaster, or just want to share music with friends across different devices, Audio Streamer has you covered:

- **Stream live audio** from microphones or audio interfaces - perfect for live shows, podcasts, or DJ sets
- **Play music files** from your computer with automatic playlist management - great for background music or automated radio
- **Support multiple listeners** simultaneously over the network - share your stream with anyone on your network
- **Work with various audio formats** (MP3, WAV, FLAC, OGG, M4A) - no need to convert your files
- **Control everything from a web dashboard** - easy to use, no technical knowledge required
- **Choose streaming quality** - offer multiple bitrates (64-320 kbps) to accommodate different bandwidth constraints
- **Automatic quality adaptation** - listeners can select appropriate quality based on their connection

### Quick Start Guide

If you just want to get up and running quickly, here's what you need to do:

1. **Install the application** - follow the installation instructions for your system (including FFmpeg for bitrate-based streaming)
2. **Configure basic settings** - edit the `.env` file to set your server port, station name, and desired streaming bitrates
3. **Choose how you want to stream**:
   - **For music files**: Use the "Liquid Music" mode. You can either upload files directly or select a folder from your computer - the app will scan it asynchronously and you'll see files appear in your playlist in real-time
   - **For live audio**: Connect a microphone or audio interface to your computer
4. **Open the dashboard** - point your browser to `http://your-server:4986/dashboard` (or `http://your-server:4986/dashboard_liquid` for music mode)
5. **Start streaming** - click the play button in the dashboard
6. **Share the stream** - give your listeners the appropriate stream URL:
   - `/stream` for high-quality WAV (best for local networks)
   - `/stream/128` for standard quality MP3 (good for most connections)
   - `/stream/320` for highest quality MP3
   - Other bitrates as configured in your `.env` file

That's really all there is to it! The application handles all the technical details behind the scenes - audio encoding, network streaming, playlist management, metadata extraction - so you can focus on the content.

### For Developers and Technical Users

If you're interested in how things work under the hood, want to integrate Audio Streamer with other systems, or need to customize it for your needs, check out the [Technical Overview](#technical-overview) and [API Reference](#api-reference) sections below. We've documented the architecture, endpoints, and WebSocket events to help you integrate Audio Streamer into your projects.

---

## Technical Overview

### Architecture

Audio Streamer is built with a modular, maintainable architecture that separates concerns and makes it easy to extend or modify functionality. Here's how the pieces fit together:

**Core Components:**

- **ApplicationController**: Think of this as the main conductor that orchestrates everything. It manages the application lifecycle, coordinates between different components, and ensures smooth startup and shutdown.

- **AudioStreamerFactory**: This is like a factory that creates the right type of audio streamer based on your needs. Whether you're using a microphone, professional audio interface, or playing music files, this factory instantiates the appropriate streamer for you.

- **Audio Streamers**: These are the engines that handle different audio sources:
  - `MicrophoneAudioStreamer`: Captures audio from microphones or line-in using Linux's ALSA system via `arecord`. Great for simple setups - just plug in a microphone and go.
  - `CardAudioStreamer`: Uses PyAudio for professional audio interfaces. Supports multiple devices simultaneously and provides detailed statistics. Ideal for broadcast studios or when you need professional-grade audio.
  - `LiquidMusicStreamer`: Plays music files from your computer with automatic playlist management. Perfect for automated radio stations, background music systems, or when you just want to stream your music library.

- **AudioHttpFacade**: This handles all web communication - both HTTP requests for the dashboard and API endpoints, and WebSocket connections for real-time updates. It's the bridge between your browser and the audio streaming engine.

- **Handler Classes**: Modular components that handle specific functionalities:
  - `AuthHandler`: Manages authentication to protect your dashboard
  - `CoverUploadHandler`: Handles album cover image uploads
  - `LocalizationHandler`: Provides multi-language support
  - `LiquidMusicHandler`: Manages music file operations and directory scanning
  - `StreamHandler`: Handles core streaming and dashboard routes

This modular design means you can easily add new streaming modes, authentication methods, or features without disrupting existing functionality. If you're a developer looking to extend the system, this architecture makes it straightforward.

### Technology Stack

Audio Streamer uses modern, well-maintained technologies to ensure reliability and performance:

- **Backend**: Python 3.9+ - chosen for its readability, extensive library ecosystem, and excellent audio processing capabilities
- **Web Framework**: Flask 3.0.0 - lightweight yet powerful, perfect for building the web interface and API
- **Real-time Communication**: Flask-SocketIO 5.3.6 - enables live updates to the dashboard (like real-time playlist updates during scanning)
- **Audio Processing**:
  - PyAudio 0.2.14 - for direct audio device access
  - FFmpeg - for converting audio files to the streaming format
- **Metadata Extraction**: Mutagen 1.47.0 - automatically reads song information (title, artist, album) from your music files
- **File Validation**: python-magic 0.4.27 - ensures uploaded files are actually audio files (security measure)
- **Configuration**: python-dotenv 1.0.0 - makes configuration easy with a simple `.env` file
- **Localization**: PyYAML 6.0.1 - supports multiple languages through YAML configuration files


---

## Streaming Modes

Audio Streamer supports three different streaming modes, each designed for specific use cases:

### 1. Microphone Mode (MicrophoneAudioStreamer)

**Best for**: Simple setups, podcasts, voice broadcasts

This mode captures audio from your computer's built-in microphone or line-in jack. It's the simplest way to get started if you just want to broadcast voice or audio from a basic source.

**How it works**:
- Uses ALSA (Advanced Linux Sound Architecture) via the `arecord` command
- Supports built-in microphones and line-in jacks (3.5mm)
- Captures audio at CD quality: 44.1kHz, 16-bit, stereo
- Buffer size is configurable via the `AUDIO_CHUNK` environment variable (default: 1024)

**Device Selection**:
- Uses ALSA device selection (e.g., 'default' for built-in microphone, 'hw:0,2' for line-in)
- Device selection is based on ALSA hardware notation
- You can select devices via ALSA device indices for more control

**Pros**:
- Stable system audio capture
- Low CPU overhead
- Compatible with most Linux audio systems
- Easy to set up

**Cons**:
- Linux only (depends on ALSA)
- Limited to 2 channels (stereo)
- Fixed sample rate (44.1kHz)

### 2. Audio Interface Mode (CardAudioStreamer)

**Best for**: Professional audio setups, broadcast studios, multiple audio sources

This mode uses PyAudio to work with professional audio interfaces. If you have a USB audio interface, a mixing console, or need to capture audio from multiple sources simultaneously, this is the mode for you.

**How it works**:
- Uses PyAudio (PortAudio wrapper) for direct audio device access
- Supports multiple audio devices simultaneously
- Captures at 44.1kHz, 16-bit, stereo
- Configurable buffer size for fine-tuning

**Device Selection**:
- Lists all available PyAudio devices on startup
- Supports multiple device indices (e.g., "0 1 2" to use 3 devices)
- Note: PyAudio only supports single device per stream, so the first device from the list is used

**Pros**:
- Professional audio interface support
- Cross-platform (works on Windows, Linux, and macOS)
- Peak listener tracking
- Detailed statistics (data transferred, chunks processed)

**Cons**:
- Higher CPU overhead
- Requires PortAudio installation
- May have latency issues with certain interfaces

### 3. Liquid Music Mode (LiquidMusicStreamer)

**Best for**: Music streaming, automated radio stations, background music

This mode plays music files from your computer with automatic playlist management. It's perfect for when you want to stream your music library or create an automated radio station.

**How it works**:
- Uses FFmpeg for audio conversion and streaming
- Supports MP3, WAV, FLAC, OGG, M4A formats
- Automatically extracts metadata (title, artist, album, year) from your files
- Thread-safe playlist management
- Playback state management (playing, paused, stopped)

**Features**:
- **Manual track upload** via dashboard - upload individual files
- **Local directory loading with async scanning** - select a folder and watch as files appear in your playlist in real-time
- **Real-time playlist updates** via WebSocket - see the playlist populate as files are scanned
- **Directory listing** - browse common directories on your server to select music folders
- **Scan interruption** - stop scanning at any time if you change your mind
- **Playlist management** - add, remove, skip tracks
- **Playback controls** - play, pause, resume, stop, skip forward/backward
- **Automatic metadata extraction** - no manual entry needed
- **Playback stack** - history of played tracks
- **Security validation** - uploaded files are validated to ensure they're actually audio

**Pros**:
- No audio hardware required
- Perfect for automated broadcasting
- Metadata extraction eliminates manual entry
- Secure file validation
- Automatic cleanup of uploaded files
- Async scanning means you can start streaming immediately while files are still being loaded

**Cons**:
- File-based only (no live audio)
- Requires disk space for uploaded files
- FFmpeg dependency

### 4. Bitrate-Based Streaming

**Best for**: Bandwidth-constrained environments, mobile listeners, quality control

Audio Streamer supports multiple quality streams simultaneously, allowing listeners to choose the appropriate bitrate based on their bandwidth and quality preferences.

**How it works**:
- Uses FFmpeg to re-encode audio to MP3 at specified bitrates
- Creates separate streaming endpoints for each bitrate (e.g., `/stream/128`, `/stream/192`, `/stream/320`)
- Original `/stream` endpoint continues to provide WAV format without re-encoding
- Threading-based architecture prevents blocking during re-encoding
- Configurable queue sizes and timeouts for optimal performance
- FFmpeg stderr monitoring for error detection

**Available Endpoints**:
- `/stream` - Original WAV stream (no re-encoding, highest quality)
- `/stream/64` - 64 kbps MP3 (lowest bandwidth, lowest quality)
- `/stream/128` - 128 kbps MP3 (standard quality, good for most connections)
- `/stream/192` - 192 kbps MP3 (high quality)
- `/stream/256` - 256 kbps MP3 (very high quality)
- `/stream/320` - 320 kbps MP3 (maximum MP3 quality)

**Configuration**:
- `AUDIO_STREAM_BITRATES` - Comma-separated list of bitrates to enable (e.g., `128,192,320`)
- `FFMPEG_OUTPUT_QUEUE_SIZE` - Buffer size for encoded MP3 data (default: 50)
- `FFMPEG_QUEUE_TIMEOUT` - Timeout for waiting for encoded data (default: 0.1s)

**Requirements**:
- FFmpeg must be installed on the system
- FFmpeg is used for real-time audio re-encoding
- Higher bitrates require more CPU resources

**Performance Considerations**:
- Higher bitrates = better audio quality but more bandwidth and CPU usage
- Lower bitrates = less bandwidth but lower audio quality
- Queue size affects memory usage and drop resistance
- Larger queues reduce audio drops during network slowdowns

**Use Cases**:
- Mobile listeners with limited data plans can use lower bitrates
- High-bandwidth listeners can use higher bitrates for better quality
- Automatic quality selection based on connection conditions
- Bandwidth-constrained networks can still access the stream

---

## Configuration

All configuration is done through the `.env` file. It's simple - just copy `.env.example` to `.env` and edit the values you need.

### Environment Variables

```bash
# Audio Configuration
AUDIO_CHUNK=512               # Buffer size in samples (512-2048, default: 512)
AUDIO_CHANNELS=2               # 1=mono, 2=stereo (default: 2)
AUDIO_RATE=44100               # Sample rate in Hz (22050, 44100, 48000, default: 44100)

# Network Configuration
AUDIO_STREAMER_HOST=0.0.0.0    # Bind address (default: 0.0.0.0)
AUDIO_STREAMER_PORT=4986       # Server port (default: 4986)
AUDIO_STREAMER_DEBUG=False     # Debug mode (default: False)

# Streaming Configuration
AUDIO_STREAMER_MAX_CLIENTS=10  # Maximum concurrent listeners (default: 10)
AUDIO_STREAMER_QUEUE_SIZE=100 # Buffer queue size per client (default: 100)
AUDIO_STREAM_BITRATES=128,192,320  # Available bitrates in kbps (default: 128,192,320)

# Bitrate Streaming Configuration (FFmpeg-based)
FFMPEG_OUTPUT_QUEUE_SIZE=50   # FFmpeg output queue size (default: 50)
FFMPEG_QUEUE_TIMEOUT=0.1      # FFmpeg queue timeout in seconds (default: 0.1)

# Station Configuration
RADIO_STATION_NAME=My Streamer  # Custom station name (default: My Streamer)

# Dashboard Authentication (Optional)
DASHBOARD_USERNAME=admin        # Dashboard username (default: admin)
DASHBOARD_PASSWORD=admin123     # Dashboard password (default: admin123)
```

### Audio Quality Tuning

Depending on your use case, you might want to tune the audio quality settings:

**Lower Latency (for live performances)**:
```bash
AUDIO_CHUNK=512
AUDIO_RATE=44100
```
Smaller buffer size reduces latency but may cause interruptions if your system can't keep up.

**Higher Quality (for music streaming)**:
```bash
AUDIO_CHUNK=2048
AUDIO_RATE=48000
```
Larger buffer size and higher sample rate improve quality but increase latency.

**Lower Bandwidth (for limited connections)**:
```bash
AUDIO_CHUNK=1024
AUDIO_RATE=22050
AUDIO_CHANNELS=1
```
Lower sample rate and mono audio reduce bandwidth usage at the cost of audio quality.


---

## Audio Engine Details

### Audio Processing

**Audio Quality Settings**:
- Sample Rate: 44.1kHz (CD quality)
- Bit Depth: 16-bit
- Channels: Stereo (2 channels)
- Format: Raw PCM (s16le)

**Buffer Management**:
- Chunk size is configurable via `AUDIO_CHUNK`
- Default: 1024 samples per chunk
- **Larger chunks** = higher latency but better continuity (less likely to have dropouts)
- **Smaller chunks** = lower latency but may cause interruptions if system can't keep up

### Thread Safety

Audio Streamer is designed to handle multiple listeners safely:

**Client Management**:
- Each connected client gets its own thread-safe queue
- RLock (reentrant lock) for playlist and client management
- Atomic operations for adding/removing clients

**Playlist Management**:
- Thread-safe playlist access in LiquidMusicStreamer
- Lock-protected metadata dictionary
- Atomic track index updates

### Error Recovery

The application is designed to handle errors gracefully:

**Audio Device Issues**:
- Automatic retry on device access errors
- Graceful degradation on device disconnection
- All audio errors are logged for troubleshooting

**Network Issues**:
- Auto-reconnect on client side (WebSocket)
- Connection timeout handling
- Buffer underrun protection

---

## Liquid Music Mode

This section dives deeper into the Liquid Music mode, which is perfect for music streaming and automated radio stations.

### Metadata Extraction

**How it works**:
- Uses the Mutagen library to extract metadata from audio files
- Reads from file headers (ID3, Vorbis comments, etc.)
- Supports multiple audio formats

**What gets extracted**:
- Title (from TIT2 / title fields)
- Artist (from TPE1 / artist fields)
- Album (from TALB / album fields)
- Year (from TDRC / date fields)

**Fallback behavior**:
- If metadata is missing, fields are left empty (no fake values)
- Filename is used as fallback for display only if needed
- The system doesn't guess - if it can't find the metadata, it shows nothing rather than incorrect information

### File Upload Security

Audio Streamer takes file security seriously. All uploaded files go through multiple validation layers:

**Validation Pipeline**:
1. **Extension Check**: First-level filter for allowed extensions (.mp3, .wav, .flac, .ogg, .m4a)
2. **MIME Type Check**: Magic bytes validation using python-magic - checks the actual file signature, not just the extension
3. **Mutagen Validation**: Confirms the file is valid audio with proper structure
4. **Suspicious Content Check**: Detects executable headers (MZ, ELF, shebangs)
5. **File Size Limit**: Maximum 50MB to prevent DoS attacks

**Allowed MIME Types**:
- audio/mpeg, audio/mp3
- audio/wav, audio/wave, audio/x-wav
- audio/flac, audio/x-flac
- audio/ogg, audio/x-ogg
- audio/x-m4a, audio/mp4, audio/x-m4p

**Security Features**:
- Invalid files are automatically deleted
- Validation errors are logged
- No execution of uploaded files
- Size limits prevent resource exhaustion

### Playlist Management

**Data Structures**:
```python
self.playlist = []  # List of file paths in order
self.playlistMetadata = {}  # Dictionary mapping paths to metadata
self.currentTrackIndex = 0  # Index of current track
self.playbackStack = []  # History of played tracks
```

**Operations**:
- **Add Track**: Extracts metadata and appends to playlist
- **Remove Track**: Removes by index, updates metadata
- **Skip Forward**: Increments index, wraps around to beginning
- **Skip Backward**: Decrements index, wraps around to end
- **Clear**: Empties playlist and metadata

**State Management**:
- `isPlaying`: Playback active state
- `isPaused`: Playback paused state
- `onAir`: Streaming active state
- `isScanning`: Directory scanning in progress
- Thread-safe state transitions

### Automatic Cleanup

**Startup Behavior**:
- All uploaded tracks are deleted on application startup
- Upload folder (`uploads/music`) is cleared
- This prevents disk space accumulation
- Maintains clean state between sessions

---

## Security Implementation

### HTTP Basic Authentication

The dashboard is protected by HTTP Basic Authentication to prevent unauthorized access.

**What's Protected**:
- All dashboard routes require authentication
- Credentials are configured via environment variables
- Default: admin/admin123 (change this in production!)
- Applied to:
  - `/dashboard`
  - `/dashboard_liquid`
  - `/upload_cover`
  - All `/liquid/*` endpoints

**Implementation**:
- AuthHandler class manages authentication
- Decorator pattern for route protection
- Credentials are stored in environment variables (not in code)

### File Upload Security

**Validation Pipeline**:
1. File size check (max 50MB)
2. Empty file detection
3. MIME type verification (magic bytes)
4. Mutagen audio validation
5. Executable header detection
6. Script shebang detection

**Threat Mitigation**:
- Prevents executable file uploads
- Blocks script uploads
- Validates audio file structure
- Limits file size to prevent DoS attacks
- Automatic deletion of invalid files

### Network Security

**Recommended Practices**:
- Use a reverse proxy with SSL/TLS for production
- Implement rate limiting
- Restrict access via firewall
- Disable debug mode in production
- Use strong dashboard credentials
- Keep the application updated


---

## API Reference

This section is for developers who want to integrate Audio Streamer with other systems or build custom applications on top of it.

### Streaming Endpoints

**Default Stream**: `GET /stream`
- Streams audio in WAV format without re-encoding
- Highest quality, no compression
- Best for local networks or high-bandwidth connections

**Bitrate-Based Streams**: `GET /stream/{bitrate}`
- Streams audio re-encoded to MP3 at specified bitrate
- Bitrate options: 64, 128, 192, 256, 320 kbps
- Lower bitrates use less bandwidth but lower quality
- Requires FFmpeg to be installed
- Valid range: 64-320 kbps

**Example Usage**:
```bash
# Default WAV stream
curl http://localhost:4986/stream

# 128 kbps MP3 stream
curl http://localhost:4986/stream/128

# 320 kbps MP3 stream (highest quality MP3)
curl http://localhost:4986/stream/320
```

**Player Integration**:
```html
<!-- Default stream -->
<audio src="http://your-server:4986/stream" autoplay></audio>

<!-- Low bitrate for mobile -->
<audio src="http://your-server:4986/stream/128"></audio>

<!-- High bitrate for desktop -->
<audio src="http://your-server:4986/stream/320"></audio>
```

### Statistics API

**Endpoint**: `GET /stats`

Get real-time statistics about the streaming server.

**Response**:
```json
{
  "on_air": true,
  "is_playing": false,
  "is_paused": false,
  "listeners": 5,
  "sample_rate": 44100,
  "channels": 2,
  "uptime_seconds": 3600,
  "uptime_formatted": "1h 0m 0s",
  "start_time": 1234567890,
  "current_track": "song.mp3",
  "track_title": "Song Title",
  "artist": "Artist Name",
  "album_name": "Album Name",
  "track_year": "2023",
  "playlist_length": 10,
  "current_track_index": 3,
  "playback_stack_length": 5,
  "local_music_path": "/path/to/music",
  "is_scanning": false
}
```

**CardAudioStreamer Additional Fields**:
```json
{
  "peak_listeners": 42,
  "total_data_mb": 1024.5,
  "chunks_processed": 1000000,
  "avg_chunk_size": 2048
}
```

**Use Cases**:
- Monitor server health
- Display current status in custom dashboards
- Track listener counts over time
- Integrate with monitoring systems

### Liquid Music Endpoints

These endpoints control the Liquid Music (file playback) mode.

**Upload Track**: `POST /liquid/upload_track`
- Upload a single audio file
- Content-Type: multipart/form-data
- Parameter: `track` (file)
- Response: `{"success": true, "filename": "...", "path": "..."}`

**Play**: `POST /liquid/play`
- Start playback
- Response: `{"success": true}`

**Stop**: `POST /liquid/stop`
- Stop playback
- Response: `{"success": true}`

**Pause**: `POST /liquid/pause`
- Pause playback
- Response: `{"success": true}`

**Resume**: `POST /liquid/resume`
- Resume paused playback
- Response: `{"success": true}`

**Skip Forward**: `POST /liquid/skip_forward`
- Skip to next track
- Response: `{"success": true}`

**Skip Backward**: `POST /liquid/skip_backward`
- Skip to previous track
- Response: `{"success": true}`

**Set Local Path**: `POST /liquid/set_local_path`
- Set a local directory to scan for music files
- Content-Type: application/json
- Body: `{"path": "/path/to/music"}`
- Response: `{"success": true}`
- Note: Starts async scanning; playlist updates in real-time via WebSocket. You can start streaming immediately while files are being scanned.

**Stop Scan**: `POST /liquid/stop_scan`
- Interrupt an ongoing directory scan
- Response: `{"success": true}`
- Note: Stops the scanning process; the playlist will contain all files that were scanned before stopping.

**List Directories**: `POST /liquid/list_directories`
- List directories in a given path (for folder browser UI)
- Content-Type: application/json
- Body: `{"path": "/path/to/list"}` (empty string for root directories)
- Response: `{"directories": [{"name": "...", "path": "...", "is_root": false}], "current_path": "..."}`
- Note: Lists only directories (no files) from the server's filesystem. Use this to build folder selection UIs.

**Get Playlist**: `GET /liquid/playlist`
- Get the current playlist with metadata
- Response: `{"playlist": [...], "current_index": 0}`

**Get Stack**: `GET /liquid/stack`
- Get the playback stack (history)
- Response: `{"stack": [...]}`

**Remove Track**: `POST /liquid/remove_track`
- Remove a track from the playlist
- Content-Type: application/json
- Body: `{"index": 0}`
- Response: `{"success": true}`

### WebSocket Events

Audio Streamer uses WebSocket for real-time updates. This is perfect for building responsive interfaces that react to changes immediately.

**Client → Server**:
- `connect`: Client connection
- `disconnect`: Client disconnection

**Server → Client**:
- `stats`: Real-time statistics update
  - Includes `is_scanning` state to track directory scanning progress
  - Use this to update your dashboard in real-time
- `track_info`: Track information update
  - Sent when the current track changes
- `file_scanned`: Emitted when a file is scanned during async directory scanning
  - Data: `{"filename": "...", "path": "...", "title": "...", "artist": "...", "album": "...", "year": "...", "index": 1, "total": 100}`
  - Use this to show real-time progress as files are added to the playlist

**Integration Example**:
```javascript
const socket = io();

socket.on('stats', (data) => {
    console.log('Listeners:', data.listeners);
    console.log('On air:', data.on_air);
    console.log('Scanning:', data.is_scanning);
});

socket.on('file_scanned', (data) => {
    console.log(`Scanned ${data.index}/${data.total}: ${data.filename}`);
    // Update your playlist UI in real-time
});
```


---

## Advanced Configuration

### System Dependencies

**Linux (Debian/Ubuntu)**:
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev libmagic1 ffmpeg
```

**Linux (Fedora/RHEL)**:
```bash
sudo dnf install python3-devel portaudio-devel file-libs ffmpeg
```

**macOS**:
```bash
brew install portaudio libmagic ffmpeg
```

**Windows**:
- Install PortAudio from http://www.portaudio.com/
- Install python-magic binary from https://github.com/ahupp/python-magic
- Install FFmpeg from https://ffmpeg.org/download.html

**FFmpeg Requirement**:
- FFmpeg is required for bitrate-based streaming features
- Also required for Liquid Music mode (file playback)
- Install via your system package manager or download from ffmpeg.org

### Process Management

**PM2** (recommended for production):
```bash
npm install -g pm2
pm2 start app.py --name "radio-station" --interpreter python3
pm2 startup
pm2 save
```

**Systemd** (alternative for production):
```ini
[Unit]
Description=Audio Streamer Radio Station
After=network.target sound.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/audio-streamer
Environment="AUDIO_STREAMER_DEBUG=false"
ExecStart=/usr/bin/python3 /path/to/audio-streamer/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Nginx)

For production deployments, use Nginx as a reverse proxy with SSL/TLS:

```nginx
server {
    listen 443 ssl;
    server_name radio.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:4986;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### Audio Device Issues

**No devices detected**:
```bash
# Check ALSA devices
arecord -l

# Check PyAudio devices
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(i, p.get_device_info_by_index(i)['name']) for i in range(p.get_device_count())]"
```

**Permission denied**:
```bash
# Add user to audio group
sudo usermod -a -G audio $USER

# Check device permissions
ls -l /dev/snd/*
```

### Streaming Issues

**Audio interruptions**:
- Decrease `AUDIO_CHUNK` to 512 or 256
- Check CPU usage: `htop`
- Close other audio applications
- Verify sample rate compatibility

**High latency**:
- Decrease `AUDIO_CHUNK` to 512
- Check network latency
- Verify buffer settings

### File Upload Issues

**Invalid file type**:
- Verify file has correct extension
- Check file is not corrupted
- Ensure file is actual audio (not renamed executable)

**Upload fails**:
- Check file size (< 50MB)
- Verify disk space available
- Check upload folder permissions

### Network Issues

**Listeners cannot connect**:
```bash
# Check firewall
sudo ufw status
sudo ufw allow 4986

# Check if port is listening
netstat -tlnp | grep 4986

# Test local connection
curl http://localhost:4986/stats
```

**Connection drops**:
- Check internet stability
- Verify audio device not in use
- Monitor system resources
- Check logs for errors

### Liquid Music Issues

**Playlist not loading**:
- Check file paths are valid
- Verify file permissions
- Check FFmpeg is installed: `ffmpeg -version`

### Bitrate Streaming Issues

**FFmpeg not found**:
```bash
# Check if FFmpeg is installed
ffmpeg -version

# Install FFmpeg on Debian/Ubuntu
sudo apt update
sudo apt install -y ffmpeg

# Install FFmpeg on Fedora/RHEL
sudo dnf install -y ffmpeg

# Install FFmpeg on macOS
brew install ffmpeg
```

**Bitrate stream not working**:
- Verify FFmpeg is installed and accessible
- Check that the bitrate is in valid range (64-320 kbps)
- Review logs for FFmpeg errors
- Ensure `AUDIO_STREAM_BITRATES` includes the desired bitrate

**Audio drops during bitrate streaming**:
- Increase `FFMPEG_OUTPUT_QUEUE_SIZE` (try 100 instead of 50)
- Increase `FFMPEG_QUEUE_TIMEOUT` (try 0.2 instead of 0.1)
- Check CPU usage - re-encoding requires CPU resources
- Try lower bitrates to reduce CPU load

**High CPU usage with bitrate streaming**:
- Reduce number of enabled bitrates
- Use lower bitrates
- Increase `FFMPEG_QUEUE_TIMEOUT` to reduce CPU usage
- Consider using default `/stream` endpoint (no re-encoding) if acceptable

**Metadata not extracting**:
- Verify Mutagen is installed: `pip show mutagen`
- Check file has embedded metadata
- Check logs for extraction errors

**Playback not starting**:
- Verify playlist is not empty
- Check FFmpeg can play file: `ffmpeg -i file.mp3 -f null -`
- Check playback state in logs


---

## Performance Tuning

### CPU Optimization

**Reduce CPU usage**:
- Increase `AUDIO_CHUNK` to 2048 or 4096
- Use Microphone mode instead of Audio Interface
- Close unnecessary applications

**Reduce latency**:
- Decrease `AUDIO_CHUNK` to 512
- Use Audio Interface mode
- Ensure sufficient CPU resources

### Memory Optimization

**Reduce memory usage**:
- Decrease `AUDIO_STREAMER_QUEUE_SIZE`
- Limit concurrent listeners
- Monitor memory usage: `free -h`

### Network Optimization

**Reduce bandwidth**:
- Decrease sample rate to 22050
- Use mono (1 channel)
- Decrease `AUDIO_CHUNK`

**Improve quality**:
- Increase sample rate to 48000
- Use stereo (2 channels)
- Ensure stable network connection

---

## Logging and Monitoring

### Log Files

**Application logs**:
- Console output (stdout/stderr)
- Can be redirected to file for production

**PM2 logs**:
```bash
pm2 logs radio-station
```

**Systemd logs**:
```bash
sudo journalctl -u audio-streamer -f
```

### Monitoring Metrics

**Key metrics to monitor**:
- CPU usage
- Memory usage
- Network bandwidth
- Listener count
- Error rate
- Audio buffer underruns

### Health Checks

**Statistics endpoint**:
```bash
curl http://localhost:4986/stats
```

**Expected response**: JSON with `on_air: true` when streaming

---

## Development

### Code Structure

```
audio-streamer/
├── app.py                      # Main application entry point
├── classes/
│   ├── ApplicationController.py # Main controller
│   ├── AudioHttpFacade.py     # HTTP server and WebSocket
│   ├── streamer/
│   │   ├── AudioStreamerFactory.py
│   │   └── streamers/
│   │       ├── MicrophoneAudioStreamer.py
│   │       ├── CardAudioStreamer.py
│   │       └── LiquidMusicStreamer.py
│   └── handlers/
│       ├── AuthHandler.py
│       ├── CoverUploadHandler.py
│       ├── LocalizationHandler.py
│       ├── LiquidMusicHandler.py
│       └── StreamHandler.py
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   └── dashboard_liquid.html
├── static/
│   ├── css/
│   └── js/
├── locales/
│   ├── en.yaml
│   ├── it.yaml
│   └── de.yaml
└── uploads/
    ├── covers/
    └── music/
```

### Adding New Streamers

To add a new streamer type:

1. Create new streamer class in `classes/streamer/streamers/`
2. Implement required methods:
   - `listAvailableDevices()`
   - `startAudioStream()`
   - `stopAudioStream()`
   - `addClient()`
   - `removeClient()`
   - `getStats()`
3. Add to `AudioStreamerFactory.py`
4. Update `ApplicationController.py` to include new option
5. Update documentation

### Adding New Endpoints

To add new HTTP endpoints:

1. Create or update handler in `classes/handlers/`
2. Add route in `AudioHttpFacade._add_routes()`
3. Apply authentication if needed with `_requires_auth()`
4. Update documentation

---

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3).

For the complete license text, see [LICENSE](LICENSE) or visit:
https://www.gnu.org/licenses/gpl-3.0.html
