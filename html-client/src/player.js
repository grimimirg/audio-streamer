const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const connectionStatus = document.getElementById('connectionStatus');
let isPlaying = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let currentStatusKey = 'status.ready';
let trackHistory = [];
let historyVisible = false;

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

    // Set up event listeners before assigning src (important for Firefox)
    audio.addEventListener('loadstart', onLoadStart);
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('error', onError);
    audio.addEventListener('stalled', onStalled);

    audio.src = '/stream';

    // Load the audio before playing (Firefox compatibility)
    audio.load();

    // Wait for canplay event before attempting to play
    audio.addEventListener('canplay', function onCanPlayOnce() {
        audio.removeEventListener('canplay', onCanPlayOnce);
        audio.play().catch(onPlayError);
    }, { once: true });

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

// History management functions
function toggleHistory() {
    const historyPanel = document.getElementById('historyPanel');
    historyVisible = !historyVisible;
    
    if (historyVisible) {
        historyPanel.classList.add('open');
    } else {
        historyPanel.classList.remove('open');
    }
}

function isDuplicate(track) {
    return trackHistory.some(existing =>
        existing.artist === track.artist &&
        existing.album_name === track.album_name &&
        existing.track_title === track.track_title
    );
}

function addToHistory(track) {
    if (track.artist && track.track_title && !isDuplicate(track)) {
        trackHistory.unshift(track);
        renderHistory();
    }
}

function renderHistory() {
    const historyStack = document.getElementById('historyStack');
    
    if (trackHistory.length === 0) {
        historyStack.innerHTML = '<div class="history-empty" data-i18n="player.history_empty">Nessun brano nella cronologia</div>';
        return;
    }

    historyStack.innerHTML = trackHistory.map(track => {
        const coverHtml = track.album_cover
            ? `<img src="${track.album_cover}" class="history-card-cover" alt="Cover">`
            : `<div class="history-card-cover-placeholder">🎵</div>`;
        
        const albumYear = track.album_name && track.track_year
            ? `${track.album_name} (${track.track_year})`
            : (track.album_name || track.track_year || '');

        return `
            <div class="history-card">
                ${coverHtml}
                <div class="history-card-info">
                    <div class="history-card-title">${track.track_title}</div>
                    <div class="history-card-artist">${track.artist}</div>
                    <div class="history-card-album">${albumYear}</div>
                </div>
                <div style="clear: both;"></div>
            </div>
        `;
    }).join('');
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

        // Update track info
        const trackInfoContainer = document.getElementById('trackInfoContainer');
        const trackArtist = document.getElementById('trackArtist');
        const trackTitle = document.getElementById('trackTitle');
        const trackAlbum = document.getElementById('trackAlbum');
        const trackCover = document.getElementById('trackCover');
        const trackCoverImg = document.getElementById('trackCoverImg');

        if (data.track_title || data.album_name || data.artist) {
            trackInfoContainer.style.display = 'block';
            trackArtist.textContent = data.artist || '';
            trackTitle.textContent = data.track_title || '';
            trackAlbum.textContent = data.album_name && data.track_year ? `${data.album_name} (${data.track_year})` : (data.album_name || '');

            if (data.album_cover) {
                trackCover.style.display = 'block';
                trackCoverImg.src = data.album_cover;
            } else {
                trackCover.style.display = 'none';
            }

            // Add to history when track info is received
            addToHistory({
                artist: data.artist || '',
                track_title: data.track_title || '',
                album_name: data.album_name || '',
                track_year: data.track_year || '',
                album_cover: data.album_cover || ''
            });
        } else {
            trackInfoContainer.style.display = 'none';
        }

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
