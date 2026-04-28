const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const vinyl = document.getElementById('vinyl');
const visualizer = document.getElementById('visualizer');
const connectionStatus = document.getElementById('connectionStatus');
let isPlaying = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;

function changeTheme(themeName) {
    document.getElementById('mainBody').className = themeName;
    localStorage.setItem('theme', themeName);
}

function updateStatus(message, type = 'loading') {
    connectionStatus.textContent = message;
    connectionStatus.className = type;
}

function togglePlay() {
    if (!isPlaying) {
        startStreaming();
    } else {
        stopStreaming();
    }
}

function startStreaming() {
    updateStatus('🔄 Connecting to stream...', 'loading');
    playBtn.disabled = true;
    playBtn.textContent = '⏳ Connecting...';

    audio.src = '/stream';

    audio.addEventListener('loadstart', onLoadStart);
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('error', onError);
    audio.addEventListener('stalled', onStalled);

    audio.play().catch(onPlayError);
}

function stopStreaming() {
    audio.pause();
    audio.src = '';

    audio.removeEventListener('loadstart', onLoadStart);
    audio.removeEventListener('canplay', onCanPlay);
    audio.removeEventListener('error', onError);
    audio.removeEventListener('stalled', onStalled);

    playBtn.textContent = '▶️ Play';
    playBtn.style.background = '#667eea';
    playBtn.disabled = false;
    vinyl.style.animationPlayState = 'paused';
    isPlaying = false;
    reconnectAttempts = 0;
    updateStatus('🔄 Ready to connect', 'loading');
}

function onLoadStart() {
    updateStatus('🔄 Buffering...', 'loading');
}

function onCanPlay() {
    playBtn.textContent = '⏸️ Pause';
    playBtn.style.background = '#f43f5e';
    playBtn.disabled = false;
    vinyl.style.animationPlayState = 'running';
    isPlaying = true;
    reconnectAttempts = 0;
    updateStatus('🎵 Streaming', 'listeners');
}

function onError(e) {
    console.error('Audio error:', e);

    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        updateStatus(`🔄 Connection failed, retrying... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`, 'error');

        setTimeout(() => {
            if (isPlaying) {
                audio.load();
                audio.play().catch(() => {
                });
            }
        }, 2000);
    } else {
        updateStatus('❌ Connection failed. Check if server is running.', 'error');
        stopStreaming();
    }
}

function onStalled() {
    updateStatus('🔄 Buffering...', 'loading');
}

function onPlayError(error) {
    console.error('Play error:', error);
    updateStatus('❌ Failed to start playback', 'error');
    stopStreaming();
}

function changeVolume(value) {
    audio.volume = value / 100;
    document.getElementById('volumeValue').textContent = value;
}

setInterval(() => {
    fetch('/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error('Stats request failed');
            }
            return response.json();
        })
        .then(data => {
            document.getElementById('listeners').textContent = data.listeners;

            if (isPlaying && !data.on_air) {
                updateStatus('⚠️ Server stopped streaming', 'error');
                stopStreaming();
            }
        })
        .catch(error => {
            console.error('Stats error:', error);
            if (isPlaying) {
                updateStatus('⚠️ Connection to server lost', 'error');
            }
        });
}, 5000);

audio.volume = 0.7;

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.getElementById('mainBody').className = savedTheme;
        document.getElementById('themeDropdown').value = savedTheme;
    }
});
