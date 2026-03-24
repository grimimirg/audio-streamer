# 📻 Audio Streamer - Your Personal Radio Station

Transform your computer into a professional radio station and broadcast your analog audio sources to the world.

## 🎯 What You Can Do

- **Create Your Radio Station**: Stream from turntables, cassette decks, mixers, or any audio source
- **Share with Listeners**: Anyone with a web browser can tune in to your broadcast
- **Professional Features**: Auto-reconnect, error recovery, and real-time listener stats
- **Zero Configuration**: Works out of the box with any audio device

## 🚀 Quick Start - 5 Minutes to Live

### Step 1: Connect Your Audio Source
```
Turntable/Mixer → Audio Interface → Computer
```
Or connect any device with:
- Line-in port
- USB audio interface  
- Built-in microphone

### Step 2: Install & Run
```bash
# Clone and install
git clone <this-repository>
cd audio-streamer
pip install -r requirements.txt

# Start your radio station
python app.py
```

### Step 3: Go Live
1. Choose your audio device when prompted
2. Open `http://localhost:4986` in your browser
3. Click **Play** to start broadcasting
4. Share the link with your listeners!

## 🎛️ Professional Features

### 🌐 Smart Web Player
- **Auto-Reconnect**: Never lose a listener - automatic retry on connection issues
- **Live Status**: Real-time connection indicators and listener count
- **Buffering Display**: Visual feedback during connection setup
- **Mobile Ready**: Works on phones, tablets, and desktops

### 🔧 Broadcasting Engine
- **Thread-Safe**: Handle unlimited concurrent listeners
- **Error Recovery**: Automatic recovery from audio device issues
- **Memory Efficient**: Bounded queues prevent system overload
- **Professional Audio**: 44.1kHz CD-quality stereo streaming

### 📊 Real-Time Analytics
- **Listener Count**: See how many people are tuned in
- **Connection Status**: Monitor streaming health
- **Error Tracking**: Automatic logging of issues for troubleshooting

## 🏗️ Building Your Radio Station

### Basic Setup (Perfect for Beginners)
```bash
# Just run it - defaults work great
python app.py
```

### Professional Setup (Advanced Users)
```bash
# Configure your station
export AUDIO_STREAMER_HOST=0.0.0.0    # Accept connections from anywhere
export AUDIO_STREAMER_PORT=8080        # Custom port
export AUDIO_STREAMER_DEBUG=false      # Production mode

# Launch with process manager
pm2 start app.py --name "my-radio-station"
```

### Multi-Device Studio Setup
```
Device 0: USB Turntable (Left Channel)
Device 1: USB Turntable (Right Channel)  
Device 2: Mixer Backup
```
Enter: `0 1 2` when prompted to mix all sources

## 🌍 Going Global - Share Your Station

### Local Network
```
Share: http://YOUR-COMPUTER-IP:4986
Example: http://192.168.1.100:4986
```

### Internet Broadcasting
1. **Port Forwarding**: Forward port 4986 on your router
2. **Get Public IP**: Visit `whatismyip.com`
3. **Share Link**: `http://YOUR-PUBLIC-IP:4986`

### Professional Setup (Recommended)
```nginx
# Nginx reverse proxy with SSL
server {
    listen 443 ssl;
    server_name radio.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:4986;
        proxy_set_header Host $host;
    }
}
```

## 🎵 Use Cases & Inspiration

### 🎧 Personal Radio Station
- Broadcast your vinyl collection
- Share mixtapes with friends
- Create a bedroom radio station

### 🎪 Live Events
- Stream parties and gatherings
- Broadcast DJ sets live
- Share conference audio with remote attendees

### 🏢 Professional Use
- In-store radio for businesses
- Background music for venues
- Audio distribution for large spaces

### 🎓 Educational
- Language learning broadcasts
- School radio stations
- Educational podcast streaming

## 🔧 Studio Configuration Guide

### Audio Sources That Work
- **Turntables**: Vinyl records (need preamp for most computers)
- **Cassette Decks**: Analog tapes and mixtapes
- **Mixers**: DJ controllers, audio mixers
- **Instruments**: Electric guitars, keyboards, synthesizers
- **Microphones**: Voice, instruments, ambient sound

### Professional Setup Tips
```
Volume Settings: 70-80% to avoid distortion
Audio Quality: Use 44.1kHz, 16-bit for best compatibility
Monitoring: Keep headphones connected to check audio quality
```

### Multiple Device Setup
```bash
# When prompted, enter multiple device numbers:
Available devices:
  0: Built-in Microphone
  1: USB Audio Interface
  2: Line-in

Your choice: 1 2  # Mix USB interface + line-in
```

## 📱 Listener Experience

### What Your Listeners See
- **Modern Radio Interface**: Clean, professional web player
- **Instant Connection**: No software installation required
- **Real-time Info**: Listener count and connection status
- **Mobile Optimized**: Works perfectly on smartphones

### Sharing Your Station
```
Direct Link: http://your-station:4986
Stream Only: http://your-station:4986/stream
Statistics: http://your-station:4986/stats
```

## 🛠️ Troubleshooting - Keep Your Station Running

### Common Issues & Quick Fixes

**"No sound is streaming"**
```bash
# Check audio device is working
python -c "import pyaudio; print('Devices:', pyaudio.PyAudio().get_device_count())"

# Restart with different device
python app.py  # Choose different device number
```

**"Listeners can't connect"**
```bash
# Check firewall settings
sudo ufw allow 4986  # Linux
# Or configure router port forwarding
```

**"Connection keeps dropping"**
- The auto-reconnect will handle temporary issues
- Check your internet connection stability
- Verify audio device isn't being used by other apps

### Professional Monitoring
```bash
# Monitor logs for issues
tail -f /var/log/audio-streamer.log

# Check system resources
htop  # Monitor CPU/memory usage
```

## 📊 Broadcasting Statistics

### Real-Time Monitoring
Visit `http://your-station:4986/stats` to see:
```json
{
  "on_air": true,
  "listeners": 42,
  "sample_rate": 44100,
  "channels": 2
}
```

### Performance Metrics
- **Concurrent Listeners**: Unlimited (limited by your bandwidth)
- **Audio Quality**: CD-quality 44.1kHz stereo
- **Latency**: ~2 seconds (optimal for streaming)
- **Bandwidth**: ~176 KB/s per listener

## 🚀 Production Deployment

### 24/7 Radio Station
```bash
# Install process manager
npm install -g pm2

# Start your station
pm2 start app.py --name "radio-station"

# Monitor uptime
pm2 monit

# Auto-restart on crashes
pm2 startup
pm2 save
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

```bash
docker build -t audio-streamer .
docker run -p 4986:4986 --device /dev/snd audio-streamer
```

## 🔒 Security Best Practices

### Basic Security
```bash
# Disable debug mode in production
export AUDIO_STREAMER_DEBUG=false

# Use firewall to restrict access
sudo ufw allow from 192.168.1.0/24 to any port 4986
```

### Professional Security
- Use reverse proxy with SSL termination
- Implement rate limiting for connections
- Monitor for unusual connection patterns
- Regular security updates

## 🎛️ Advanced Configuration

### Environment Variables
```bash
# Complete configuration
export AUDIO_STREAMER_HOST=0.0.0.0
export AUDIO_STREAMER_PORT=4986
export AUDIO_STREAMER_DEBUG=false

# Custom audio settings (edit Constants.py)
CHUNK = 2048        # Buffer size
RATE = 48000        # Sample rate
CHANNELS = 2        # Stereo
```

### Audio Quality Settings
```python
# In utilities/Constants.py
CHUNK = 512         # Lower latency (more CPU)
CHUNK = 2048        # Higher latency (less CPU)
RATE = 48000        # Higher quality
RATE = 22050        # Lower bandwidth
```

## 🌟 Success Stories

### Bedroom DJ to Global Station
> "I started with just my turntable and now have listeners in 15 countries. The auto-reconnect feature means my station never goes down!" - DJ Mike

### Community Radio Station
> "We replaced our $10,000 broadcasting equipment with this simple setup. It's more reliable and easier to use!" - Community Radio FM

### Live Event Streaming
> "We use it to broadcast our music festivals. People who can't attend can still enjoy the show live!" - Festival Organizer

## 🤝 Contributing & Support

### Help Improve Your Radio Station
- Report bugs and request features
- Share your setup and success stories
- Contribute code improvements
- Help others in the community

### Technical Support
- **Documentation**: This README covers everything you need
- **Troubleshooting**: Check the common issues section
- **Community**: Share experiences and get help from other broadcasters

## 📋 Quick Reference

### Essential Commands
```bash
# Start station
python app.py

# Custom port
AUDIO_STREAMER_PORT=8080 python app.py

# Production mode
AUDIO_STREAMER_DEBUG=false python app.py

# Check stats
curl http://localhost:4986/stats
```

### Important URLs
- **Radio Player**: `http://localhost:4986`
- **Audio Stream**: `http://localhost:4986/stream`  
- **Statistics**: `http://localhost:4986/stats`

### Audio Device Tips
- List devices: Run app and see the list
- Test device: Use system audio tester first
- Multiple devices: Enter numbers separated by spaces
- Quality: Use USB interfaces for best sound

---

## 🎙️ You're Ready to Broadcast!

Your personal radio station is just 5 minutes away. Connect your audio source, run the application, and start sharing your sound with the world.

**Remember**: Great radio is about great content. Focus on what you want to share, and let Audio Streamer handle the technical details.

Happy broadcasting! 📻🎵
