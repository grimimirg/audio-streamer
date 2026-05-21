// Dashboard JavaScript for standard streaming mode

// Variabili globali
let socket;
let errorCount = 0;
let startTime = null;
let uptimeInterval = null;
const MAX_ERRORS = 3;
let trackHistory = [];

// Inizializzazione
document.addEventListener('DOMContentLoaded', async function () {
    await i18n.loadTranslations(i18n.getCurrentLang());
    updateStaticTexts();

    // Set English as default language
    const savedLang = localStorage.getItem('language') || 'en';
    document.getElementById('languageDropdown').value = savedLang;

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    const body = document.body;
    const themeIcon = document.getElementById('themeIcon');

    if (savedTheme === 'light') {
        body.classList.add('light');
        themeIcon.textContent = '🌙';
    } else {
        themeIcon.textContent = '☀️';
    }

    // Connect to WebSocket
    connectWebSocket();
});

// Update static texts with i18n
function updateStaticTexts() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        element.textContent = i18n.t(key);
    });

    // Update placeholders
    document.getElementById('artistName').placeholder = i18n.t('dashboard.artist_placeholder');
    document.getElementById('trackTitle').placeholder = i18n.t('dashboard.track_title_placeholder');
    document.getElementById('albumName').placeholder = i18n.t('dashboard.album_name_placeholder');
    document.getElementById('trackYear').placeholder = i18n.t('dashboard.track_year_placeholder');
    document.getElementById('albumCover').placeholder = i18n.t('dashboard.album_cover_placeholder');
}

// Update cover preview when URL changes
document.getElementById('albumCover').addEventListener('input', function () {
    const url = this.value;
    const preview = document.getElementById('dashboardCoverPreview');
    const img = document.getElementById('dashboardCoverImg');

    if (url) {
        preview.style.display = 'block';
        img.src = url;
    } else {
        preview.style.display = 'none';
    }
});

// Update cover preview when file is selected
document.getElementById('albumCoverFile').addEventListener('change', function () {
    const file = this.files[0];
    const preview = document.getElementById('dashboardCoverPreview');
    const img = document.getElementById('dashboardCoverImg');

    if (file) {
        preview.style.display = 'block';
        img.src = URL.createObjectURL(file);
    } else {
        preview.style.display = 'none';
    }
});

function connectWebSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('stats', (data) => {
        updateUI(data);
        errorCount = 0;

        // Store start_time and start uptime counter
        if (data.start_time && !startTime) {
            startTime = data.start_time * 1000; // Convert to milliseconds
            startUptimeCounter();
        }
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        if (uptimeInterval) {
            clearInterval(uptimeInterval);
        }
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        errorCount++;
        if (errorCount >= MAX_ERRORS) {
            showError(i18n.t('dashboard.too_many_errors'));
        } else {
            showError(i18n.t('dashboard.connection_error') + ' (' + errorCount + '/' + MAX_ERRORS + ')');
        }
    });
}

function startUptimeCounter() {
    if (uptimeInterval) {
        clearInterval(uptimeInterval);
    }

    uptimeInterval = setInterval(() => {
        if (startTime) {
            const now = Date.now();
            const uptimeSeconds = Math.floor((now - startTime) / 1000);
            document.getElementById('uptime').textContent = formatUptime(uptimeSeconds);
        }
    }, 1000);
}

function formatUptime(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        return `${hours}h ${minutes}m ${secs}s`;
    }
}

function toggleTheme() {
    const body = document.body;
    const themeIcon = document.getElementById('themeIcon');

    if (body.classList.contains('light')) {
        body.classList.remove('light');
        themeIcon.textContent = '☀️';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light');
        themeIcon.textContent = '🌙';
        localStorage.setItem('theme', 'light');
    }
}

// Change language function
async function changeLanguage(lang) {
    await i18n.loadTranslations(lang);
    localStorage.setItem('language', lang);
    updateStaticTexts();
}

// Gestione errori
function showError(message) {
    console.error(message);
}

// Aggiorna l'interfaccia
function updateUI(stats) {
    // Metriche principali
    document.getElementById('listenersCount').textContent = stats.listeners;
    document.getElementById('peakListeners').textContent = stats.peak_listeners || 0;
    document.getElementById('sampleRate').textContent = (stats.sample_rate / 1000).toFixed(1) + 'k';
    document.getElementById('channels').textContent = stats.channels + (stats.channels === 2 ? ' (Stereo)' : ' (Mono)');

    // Info audio
    document.getElementById('streamStatus').textContent = stats.on_air ? i18n.t('dashboard.active') : i18n.t('dashboard.inactive');
    document.getElementById('bitrate').textContent = calculateBitrate(stats.sample_rate, stats.channels);
}

// Calcola il bitrate
function calculateBitrate(sampleRate, channels) {
    const bitrate = sampleRate * channels * 16; // 16-bit
    return (bitrate / 1000).toFixed(0) + ' kbps';
}

// Apri player
function openPlayer() {
    window.open('/', '_blank');
}

// Aggiorna informazioni sul brano
async function updateTrackInfo() {
    const artistName = document.getElementById('artistName').value;
    const trackTitle = document.getElementById('trackTitle').value;
    const albumName = document.getElementById('albumName').value;
    const trackYear = document.getElementById('trackYear').value;
    const albumCover = document.getElementById('albumCover').value;
    const albumCoverFile = document.getElementById('albumCoverFile').files[0];

    let coverUrl = albumCover;

    // Se è stato caricato un file, fai l'upload
    if (albumCoverFile) {
        const formData = new FormData();
        formData.append('cover', albumCoverFile);

        try {
            const response = await fetch('/upload_cover', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                coverUrl = data.url;
            } else {
                console.error('Upload failed');
                return;
            }
        } catch (error) {
            console.error('Upload error:', error);
            return;
        }
    }

    socket.emit('update_track_info', {
        artist: artistName,
        track_title: trackTitle,
        album_name: albumName,
        track_year: trackYear,
        album_cover: coverUrl
    });

    // Add to history
    addToHistory({
        artist: artistName,
        track_title: trackTitle,
        album_name: albumName,
        track_year: trackYear,
        album_cover: coverUrl
    });

    // Mostra messaggio di conferma
    const confirmationMessage = document.getElementById('confirmationMessage');
    confirmationMessage.style.display = 'block';
    setTimeout(() => {
        confirmationMessage.style.display = 'none';
    }, 3000);
}

// Check if track already exists in history (by artist, album, and title)
function isDuplicate(track) {
    return trackHistory.some(existing =>
        existing.artist === track.artist &&
        existing.album_name === track.album_name &&
        existing.track_title === track.track_title
    );
}

// Add track to history
function addToHistory(track) {
    // Only add if all required fields are present and not a duplicate
    if (track.artist && track.track_title && !isDuplicate(track)) {
        trackHistory.unshift(track);
        renderHistory();
    }
}

// Render history stack
function renderHistory() {
    const historyStack = document.getElementById('historyStack');

    if (trackHistory.length === 0) {
        historyStack.innerHTML = '<div class="history-empty" data-i18n="dashboard.history_empty"></div>';
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
