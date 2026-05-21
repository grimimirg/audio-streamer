# Audio Streamer - User Manual

## Table of Contents
- [Technical Overview](#technical-overview)
- [Streaming Modes](#streaming-modes)
- [Configuration](#configuration)
- [Audio Engine Details](#audio-engine-details)
- [Liquid Music Mode](#liquid-music-mode)
- [Security Implementation](#security-implementation)
- [API Reference](#api-reference)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

---

## Technical Overview

### Architecture

Audio Streamer is built on a modular architecture with the following components:

- **ApplicationController**: Main controller managing the application lifecycle
- **AudioStreamerFactory**: Factory pattern for creating appropriate streamer instances
- **Audio Streamers**:
  - `MicrophoneAudioStreamer`: Uses `arecord` for microphone/line-in capture
  - `CardAudioStreamer`: Uses `PyAudio` for professional audio interfaces
  - `LiquidMusicStreamer`: File-based music playback with playlist management
- **AudioHttpFacade**: HTTP server and WebSocket communication handler
- **Handler Classes**: Modular route handlers for different functionalities
  - `AuthHandler`: HTTP Basic Authentication
  - `CoverUploadHandler`: Album cover image management
  - `LocalizationHandler`: Multi-language support
  - `LiquidMusicHandler`: Liquid Music specific endpoints
  - `StreamHandler**: Core streaming and dashboard routes

### Technology Stack

- **Backend**: Python 3.9+
- **Web Framework**: Flask 3.0.0
- **Real-time Communication**: Flask-SocketIO 5.3.6
- **Audio Processing**: PyAudio 0.2.14, FFmpeg
- **Metadata Extraction**: Mutagen 1.47.0
- **File Validation**: python-magic 0.4.27
- **Configuration**: python-dotenv 1.0.0
- **Localization**: PyYAML 6.0.1

---

## Streaming Modes

### 1. Microphone Mode (MicrophoneAudioStreamer)

**Purpose**: Capture audio from system audio devices using `arecord`

**Technical Implementation**:
- Uses ALSA (Advanced Linux Sound Architecture) via `arecord` command
- Supports built-in microphones and line-in jacks
- Sample rate: 44.1kHz, 16-bit, stereo
- Buffer size: Configurable via `AUDIO_CHUNK` environment variable (default: 1024)

**Device Selection**:
- Device 1: Built-in microphone (default)
- Device 2: Line-in jack (3.5mm)
- Device selection via ALSA device indices

**Audio Pipeline**:
```
Audio Source → ALSA → arecord → PCM Buffer → Client Queues → HTTP Stream
```

**Advantages**:
- Stable system audio capture
- Low CPU overhead
- Compatible with most Linux audio systems

**Limitations**:
- Linux only (ALSA dependency)
- Limited to 2 channels (stereo)
- Fixed sample rate (44.1kHz)

### 2. Audio Interface Mode (CardAudioStreamer)

**Purpose**: Professional audio interface support using PyAudio

**Technical Implementation**:
- Uses PyAudio (PortAudio wrapper) for direct audio device access
- Supports multiple audio devices simultaneously
- Sample rate: 44.1kHz, 16-bit, stereo
- Configurable buffer size

**Device Selection**:
- Lists all available PyAudio devices
- Supports multiple device indices (e.g., "0 1 2" for 3 devices)
- Automatic device mixing

**Audio Pipeline**:
```
Audio Interface → PyAudio → PCM Buffer → Client Queues → HTTP Stream
```

**Advantages**:
- Professional audio interface support
- Multi-device mixing
- Cross-platform (Windows, Linux, macOS)
- Peak listener tracking
- Detailed statistics (data transferred, chunks processed)

**Limitations**:
- Higher CPU overhead
- Requires PortAudio installation
- May have latency issues with certain interfaces

### 3. Liquid Music Mode (LiquidMusicStreamer)

**Purpose**: File-based music playback with playlist management

**Technical Implementation**:
- Uses FFmpeg for audio conversion and streaming
- Supports MP3, WAV, FLAC, OGG, M4A formats
- Automatic metadata extraction via Mutagen
- Thread-safe playlist management
- Playback state management (playing, paused, stopped)

**Audio Pipeline**:
```
Audio File → FFmpeg → PCM Buffer → Client Queues → HTTP Stream
```

**Features**:
- Manual track upload via dashboard
- Local directory loading with **async scanning**
- **Real-time playlist updates** during scanning via WebSocket
- **Folder browser** for visual directory selection (server filesystem)
- **Scan interruption** - stop scanning at any time
- Playlist management (add, remove, skip)
- Playback controls (play, pause, resume, stop, skip forward/backward)
- Automatic metadata extraction (title, artist, album, year)
- Playback stack (history of played tracks)
- Security validation for uploaded files

**Advantages**:
- No audio hardware required
- Perfect for automated broadcasting
- Metadata extraction eliminates manual entry
- Secure file validation
- Automatic cleanup of uploaded files

**Limitations**:
- File-based only (no live audio)
- Requires disk space for uploaded files
- FFmpeg dependency

---

## Configuration

### Environment Variables

All configuration is done via the `.env` file. Copy `.env.example` to `.env` and configure:

```bash
# Audio Configuration
AUDIO_CHUNK=1024              # Buffer size (512-4096, default: 1024)
AUDIO_CHANNELS=2              # 1=mono, 2=stereo (default: 2)
AUDIO_RATE=44100              # Sample rate (22050, 44100, 48000, default: 44100)

# Network Configuration
AUDIO_STREAMER_HOST=0.0.0.0   # Bind address (default: 0.0.0.0)
AUDIO_STREAMER_PORT=4986      # Server port (default: 4986)
AUDIO_STREAMER_DEBUG=False    # Debug mode (default: False)

# Station Configuration
RADIO_STATION_NAME=My Radio Station  # Custom station name

# Streaming Configuration
AUDIO_STREAMER_MAX_CLIENTS=10      # Max concurrent listeners (default: 10)
AUDIO_STREAMER_QUEUE_SIZE=100      # Buffer queue size (default: 100)

# Dashboard Authentication (Optional)
DASHBOARD_USERNAME=admin           # Dashboard username (default: admin)
DASHBOARD_PASSWORD=admin123        # Dashboard password (default: admin123)
```

### Audio Quality Tuning

**Lower Latency (for live performances)**:
```bash
AUDIO_CHUNK=512
AUDIO_RATE=44100
```

**Higher Quality (for music streaming)**:
```bash
AUDIO_CHUNK=2048
AUDIO_RATE=48000
```

**Lower Bandwidth (for limited connections)**:
```bash
AUDIO_CHUNK=1024
AUDIO_RATE=22050
AUDIO_CHANNELS=1
```

---

## Audio Engine Details

### Audio Processing

**Sample Rate**: 44.1kHz (CD quality)
**Bit Depth**: 16-bit
**Channels**: Stereo (2 channels)
**Format**: Raw PCM (s16le)

**Buffer Management**:
- Configurable chunk size via `AUDIO_CHUNK`
- Default: 1024 samples per chunk
- Larger chunks = higher latency, better continuity
- Smaller chunks = lower latency, may cause interruptions

### Thread Safety

**Client Management**:
- Thread-safe queue for each connected client
- RLock (reentrant lock) for playlist and client management
- Atomic operations for adding/removing clients

**Playlist Management**:
- Thread-safe playlist access in LiquidMusicStreamer
- Lock-protected metadata dictionary
- Atomic track index updates

### Error Recovery

**Audio Device Issues**:
- Automatic retry on device access errors
- Graceful degradation on device disconnection
- Logging of all audio errors

**Network Issues**:
- Auto-reconnect on client side (WebSocket)
- Connection timeout handling
- Buffer underrun protection

---

## Liquid Music Mode

### Metadata Extraction

**Implementation**:
- Uses Mutagen library for metadata extraction
- Extracts from file headers (ID3, Vorbis comments, etc.)
- Supports multiple audio formats

**Extracted Fields**:
- Title (TIT2 / title)
- Artist (TPE1 / artist)
- Album (TALB / album)
- Year (TDRC / date)

**Fallback Behavior**:
- If metadata is missing, fields are left empty
- No default values or placeholders
- Filename is used as fallback for display only if needed

### File Upload Security

**Validation Layers**:
1. **Extension Check**: First-level filter for allowed extensions (.mp3, .wav, .flac, .ogg, .m4a)
2. **MIME Type Check**: Magic bytes validation using python-magic
3. **Mutagen Validation**: Confirms file is valid audio with proper structure
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
- **Skip Forward**: Increments index, wraps around
- **Skip Backward**: Decrements index, wraps around
- **Clear**: Empties playlist and metadata

**State Management**:
- `isPlaying`: Playback active state
- `isPaused`: Playback paused state
- `onAir`: Streaming active state
- Thread-safe state transitions

### Automatic Cleanup

**Startup Behavior**:
- All uploaded tracks are deleted on application startup
- Upload folder (`uploads/music`) is cleared
- Prevents disk space accumulation
- Maintains clean state between sessions

**Implementation**:
```python
def clear_upload_folder(self):
    if os.path.exists(self.upload_dir):
        for filename in os.listdir(self.upload_dir):
            file_path = os.path.join(self.upload_dir, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
```

---

## Security Implementation

### HTTP Basic Authentication

**Dashboard Protection**:
- All dashboard routes require authentication
- Credentials configured via environment variables
- Default: admin/admin123
- Applied to:
  - `/dashboard`
  - `/dashboard_liquid`
  - `/upload_cover`
  - All `/liquid/*` endpoints

**Implementation**:
- AuthHandler class manages authentication
- Decorator pattern for route protection
- Secure credential storage in environment variables

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
- Limits file size to prevent DoS
- Automatic deletion of invalid files

### Network Security

**Recommended Practices**:
- Use reverse proxy with SSL/TLS
- Implement rate limiting
- Restrict access via firewall
- Disable debug mode in production
- Use strong dashboard credentials

---

## API Reference

### Statistics API

**Endpoint**: `GET /stats`

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

### Liquid Music Endpoints

**Upload Track**: `POST /liquid/upload_track`
- Content-Type: multipart/form-data
- Parameter: `track` (file)
- Response: `{"success": true, "filename": "...", "path": "..."}`

**Play**: `POST /liquid/play`
- Response: `{"success": true}`

**Stop**: `POST /liquid/stop`
- Response: `{"success": true}`

**Pause**: `POST /liquid/pause`
- Response: `{"success": true}`

**Resume**: `POST /liquid/resume`
- Response: `{"success": true}`

**Skip Forward**: `POST /liquid/skip_forward`
- Response: `{"success": true}`

**Skip Backward**: `POST /liquid/skip_backward`
- Response: `{"success": true}`

**Set Local Path**: `POST /liquid/set_local_path`
- Content-Type: application/json
- Body: `{"path": "/path/to/music"}`
- Response: `{"success": true}`
- Note: Starts async scanning; playlist updates in real-time via WebSocket

**Stop Scan**: `POST /liquid/stop_scan`
- Response: `{"success": true}`
- Note: Interrupts ongoing directory scan; playlist contains files scanned so far

**List Directories**: `POST /liquid/list_directories`
- Content-Type: application/json
- Body: `{"path": "/path/to/list"}` (empty for root directories)
- Response: `{"directories": [{"name": "...", "path": "...", "is_root": false}], "current_path": "..."}`
- Note: Lists only directories (no files) from server filesystem

**Get Playlist**: `GET /liquid/playlist`
- Response: `{"playlist": [...], "current_index": 0}`

**Get Stack**: `GET /liquid/stack`
- Response: `{"stack": [...]}`

**Remove Track**: `POST /liquid/remove_track`
- Content-Type: application/json
- Body: `{"index": 0}`
- Response: `{"success": true}`

### WebSocket Events

**Client → Server**:
- `connect`: Client connection
- `disconnect`: Client disconnection

**Server → Client**:
- `stats`: Real-time statistics update (includes `is_scanning` state)
- `track_info`: Track information update
- `file_scanned`: Emitted when a file is scanned during async directory scanning
  - Data: `{"filename": "...", "path": "...", "title": "...", "artist": "...", "album": "...", "year": "...", "index": 1, "total": 100}`

---

## Advanced Configuration

### System Dependencies

**Linux (Debian/Ubuntu)**:
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev libmagic1
```

**Linux (Fedora/RHEL)**:
```bash
sudo dnf install python3-devel portaudio-devel file-libs
```

**macOS**:
```bash
brew install portaudio libmagic
```

**Windows**:
- Install PortAudio from http://www.portaudio.com/
- Install python-magic binary from https://github.com/ahupp/python-magic

### Process Management

**PM2**:
```bash
npm install -g pm2
pm2 start app.py --name "radio-station" --interpreter python3
pm2 startup
pm2 save
```

**Systemd**:
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
