const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const connectionStatus = document.getElementById('connectionStatus');
let isPlaying = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let currentStatusKey = 'status.ready';

function toggleTheme() {
    const body = document.getElementById('mainBody');
    const themeIcon = document.getElementById('themeIcon');
    const isLight = body.classList.contains('light');
    
    if (isLight) {
        body.classList.remove('light');
        themeIcon.textContent = '☀️';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light');
        themeIcon.textContent = '🌙';
        localStorage.setItem('theme', 'light');
    }
}

function updateStatus(messageKey, type = 'loading') {
    currentStatusKey = messageKey;
    connectionStatus.textContent = i18n.t(messageKey);
    connectionStatus.className = type;
    
    window.updateCurrentStatus = () => {
        connectionStatus.textContent = i18n.t(messageKey);
    };
}

function togglePlay() {
    if (playBtn.disabled) return;
    
    if (!isPlaying) {
        startStreaming();
    } else {
        stopStreaming();
    }
}

function startStreaming() {
    updateStatus('status.connecting', 'loading');
    playBtn.disabled = true;
    playBtn.textContent = i18n.t('controls.connecting');

    audio.src = '/stream';

    audio.addEventListener('loadstart', onLoadStart);
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('error', onError);
    audio.addEventListener('stalled', onStalled);

    audio.play().catch(onPlayError);
    
    audioSpectrum.start();
}

function stopStreaming() {
    playBtn.disabled = true;

    audio.pause();
    audio.src = '';

    audio.removeEventListener('loadstart', onLoadStart);
    audio.removeEventListener('canplay', onCanPlay);
    audio.removeEventListener('error', onError);
    audio.removeEventListener('stalled', onStalled);

    playBtn.textContent = i18n.t('controls.play');
    playBtn.style.background = '';
    playBtn.disabled = false;
    isPlaying = false;
    reconnectAttempts = 0;
    updateStatus('status.ready', 'loading');

    audioSpectrum.stop();
}

function onLoadStart() {
    updateStatus('status.buffering', 'loading');
}

function onCanPlay() {
    playBtn.textContent = i18n.t('controls.pause');
    playBtn.style.background = '#90EE90';
    playBtn.disabled = false;
    isPlaying = true;
    reconnectAttempts = 0;
    updateStatus('status.streaming', 'listeners');
}

function onError(e) {
    console.error('Audio error:', e);

    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const retryMsg = i18n.t('status.connection_failed');
        connectionStatus.textContent = `🔄 ${retryMsg} (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`;
        connectionStatus.className = 'error';

        setTimeout(() => {
            if (isPlaying) {
                audio.load();
                audio.play().catch(() => {});
            }
        }, 2000);
    } else {
        updateStatus('status.error', 'error');
        stopStreaming();
    }
}

function onStalled() {
    updateStatus('status.buffering', 'loading');
}

function onPlayError(error) {
    console.error('Play error:', error);
    updateStatus('status.error', 'error');
    stopStreaming();
}

function changeVolume(value) {
    audio.volume = value / 100;
    document.getElementById('volumeValue').textContent = value;
}

// WebSocket connection for real-time stats
let socket;

function connectWebSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('stats', (data) => {
        document.getElementById('listeners').textContent = data.listeners;

        if (isPlaying && !data.on_air) {
            updateStatus('status.server_stopped', 'error');
            stopStreaming();
        }
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        if (isPlaying) {
            updateStatus('status.connection_lost', 'error');
        }
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        if (isPlaying) {
            updateStatus('status.connection_lost', 'error');
        }
    });
}

audio.volume = 0.7;

function updateStaticTexts() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        element.textContent = i18n.t(key);
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await i18n.loadTranslations(i18n.getCurrentLang());
    updateStaticTexts();

    const savedTheme = localStorage.getItem('theme');
    const body = document.getElementById('mainBody');
    const themeIcon = document.getElementById('themeIcon');

    if (savedTheme === 'light') {
        body.classList.add('light');
        themeIcon.textContent = '🌙';
    } else {
        themeIcon.textContent = '☀️';
    }

    const savedLang = localStorage.getItem('language');
    if (savedLang) {
        document.getElementById('languageDropdown').value = savedLang;
    }

    playBtn.textContent = i18n.t('controls.play');
    updateStatus('status.ready', 'loading');

    // Connect to WebSocket for real-time stats
    connectWebSocket();
});

const originalChangeLanguage = changeLanguage;
changeLanguage = async function(lang) {
    const success = await originalChangeLanguage(lang);
    if (success) {
        updateStaticTexts();
        if (!isPlaying) {
            playBtn.textContent = i18n.t('controls.play');
        }
    }
};
