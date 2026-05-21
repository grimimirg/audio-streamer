// Dashboard JavaScript for Liquid Music streaming mode

// Global variables
let socket;
let errorCount = 0;
let startTime = null;
let uptimeInterval = null;
const MAX_ERRORS = 3;
let playlist = [];
let playbackStack = [];

// Initialization
document.addEventListener('DOMContentLoaded', async function () {
    await i18n.loadTranslations(i18n.getCurrentLang());
    updateStaticTexts();

    // Connect to WebSocket
    connectWebSocket();

    // Load initial playlist and stack
    loadPlaylist();
    loadPlaybackStack();
});

// Update static texts with i18n
function updateStaticTexts() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        element.textContent = i18n.t(key);
    });
}

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

        // Update scanning state in UI
        updateScanningState(data.is_scanning);
    });

    socket.on('file_scanned', (data) => {
        // Add scanned file to playlist in real-time
        playlist.push({
            index: playlist.length,
            filename: data.filename,
            path: data.path,
            title: data.title,
            artist: data.artist,
            album: data.album,
            year: data.year
        });
        renderPlaylist(0);
        updatePlaylistCount();
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

function changeLanguage(lang) {
    i18n.loadTranslations(lang).then(() => {
        localStorage.setItem('language', lang);
        updateStaticTexts();
    });
}

function showError(message) {
    console.error(message);
}

function updateUI(stats) {
    // Main metrics
    document.getElementById('listenersCount').textContent = stats.listeners;
    document.getElementById('sampleRate').textContent = (stats.sample_rate / 1000).toFixed(1) + 'k';
    document.getElementById('channels').textContent = stats.channels + (stats.channels === 2 ? ' (Stereo)' : ' (Mono)');

    // Audio info
    document.getElementById('streamStatus').textContent = stats.on_air ? i18n.t('dashboard.active') : i18n.t('dashboard.inactive');
    document.getElementById('currentTrack').textContent = stats.current_track || '---';

    // Playback state
    let stateText = '---';
    if (stats.is_playing && !stats.is_paused) {
        stateText = i18n.t('dashboard.playing');
    } else if (stats.is_paused) {
        stateText = i18n.t('dashboard.paused');
    } else {
        stateText = i18n.t('dashboard.stopped');
    }
    document.getElementById('playbackState').textContent = stateText;

    // Playlist info
    document.getElementById('playlistLength').textContent = stats.playlist_length || 0;

    // Reload playlist and stack if they changed
    if (stats.playlist_length !== playlist.length) {
        loadPlaylist();
    }
    if (stats.playback_stack_length !== playbackStack.length) {
        loadPlaybackStack();
    }
}

function openPlayer() {
    window.location.href = '/';
}

// Upload tracks
async function uploadTracks() {
    const fileInput = document.getElementById('trackUpload');
    const files = fileInput.files;

    if (files.length === 0) {
        const statusDiv = document.getElementById('uploadStatus');
        statusDiv.textContent = 'Please select files';
        statusDiv.style.color = '#facc15'; // Yellow warning color
        return;
    }

    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = `Uploading ${files.length} file(s)...`;
    statusDiv.style.color = '#4ade80'; // Green for success

    for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append('track', files[i]);

        try {
            const response = await fetch('/liquid/upload_track', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`Uploaded: ${data.filename}`);
            } else {
                const error = await response.json();
                console.error(`Upload failed: ${error.error}`);
            }
        } catch (error) {
            console.error('Upload error:', error);
        }
    }

    statusDiv.textContent = `Uploaded ${files.length} file(s) successfully`;
    fileInput.value = '';

    // Reload playlist
    setTimeout(loadPlaylist, 500);
}

// Load playlist
async function loadPlaylist() {
    try {
        const response = await fetch('/liquid/playlist');
        if (response.ok) {
            const data = await response.json();
            playlist = data.playlist;
            renderPlaylist(data.current_index);
            document.getElementById('playlistCount').textContent = playlist.length;
            document.getElementById('playlistCountLocal').textContent = playlist.length;
        }
    } catch (error) {
        console.error('Error loading playlist:', error);
    }
}

// Render playlist
function renderPlaylist(currentIndex) {
    const container = document.getElementById('playlistContainer');
    const containerLocal = document.getElementById('playlistContainerLocal');

    if (playlist.length === 0) {
        const emptyHtml = '<div class="history-empty" data-i18n="dashboard.playlist_empty"></div>';
        container.innerHTML = emptyHtml;
        containerLocal.innerHTML = emptyHtml;
        updateStaticTexts();
        return;
    }

    const playlistHtml = playlist.map((track, index) => {
        const isCurrent = index === currentIndex;
        const currentClass = isCurrent ? 'current-track' : '';
        const displayTitle = track.title || '';
        const displayArtist = track.artist || '';
        const displayAlbum = track.album || '';
        const displayYear = track.year || '';
        
        return `
                <div class="history-card ${currentClass}">
                    <div class="history-card-cover-placeholder">🎵</div>
                    <div class="history-card-info">
                        <div class="history-card-title">${displayTitle}</div>
                        <div class="history-card-artist">${displayArtist}</div>
                        ${displayAlbum ? `<div class="history-card-album">${displayAlbum}${displayYear ? ` (${displayYear})` : ''}</div>` : ''}
                        ${isCurrent ? '<div class="history-card-album">▶️ Currently Playing</div>' : ''}
                    </div>
                    <button onclick="removeTrack(${index})" style="background: rgba(255,0,0,0.3); border: none; color: white; padding: 5px 10px; border-radius: 4px; cursor: pointer; float: right;">✕</button>
                    <div style="clear: both;"></div>
                </div>
            `;
    }).join('');

    container.innerHTML = playlistHtml;
    containerLocal.innerHTML = playlistHtml;
}

// Remove track from playlist
async function removeTrack(index) {
    try {
        const response = await fetch('/liquid/remove_track', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({index: index})
        });

        if (response.ok) {
            loadPlaylist();
        }
    } catch (error) {
        console.error('Error removing track:', error);
    }
}

// Load playback stack
async function loadPlaybackStack() {
    try {
        const response = await fetch('/liquid/stack');
        if (response.ok) {
            const data = await response.json();
            playbackStack = data.stack;
            renderPlaybackStack();
        }
    } catch (error) {
        console.error('Error loading playback stack:', error);
    }
}

// Render playback stack
function renderPlaybackStack() {
    const container = document.getElementById('playbackStackContainer');

    if (playbackStack.length === 0) {
        container.innerHTML = '<div class="history-empty" data-i18n="dashboard.stack_empty"></div>';
        updateStaticTexts();
        return;
    }

    container.innerHTML = playbackStack.map(track => `
            <div class="history-card">
                <div class="history-card-cover-placeholder">🎵</div>
                <div class="history-card-info">
                    <div class="history-card-title">${track.filename}</div>
                    <div class="history-card-artist">Played</div>
                </div>
                <div style="clear: both;"></div>
            </div>
        `).join('');
}

// Playback controls
async function startPlayback() {
    if (playlist.length === 0) {
        document.getElementById('playbackStatus').textContent = '⚠️ ' + i18n.t('dashboard.playlist_empty_warning');
        setTimeout(() => {
            document.getElementById('playbackStatus').textContent = '';
        }, 2000);
        return;
    }
    try {
        const response = await fetch('/liquid/play', {method: 'POST'});
        if (response.ok) {
            document.getElementById('playbackStatus').textContent = '▶️ Playing';
            setTimeout(() => {
                document.getElementById('playbackStatus').textContent = '';
            }, 2000);
        }
    } catch (error) {
        console.error('Error starting playback:', error);
    }
}

async function stopPlayback() {
    if (playlist.length === 0) {
        return;
    }
    try {
        const response = await fetch('/liquid/stop', {method: 'POST'});
        if (response.ok) {
            document.getElementById('playbackStatus').textContent = '⏹️ Stopped';
            setTimeout(() => {
                document.getElementById('playbackStatus').textContent = '';
            }, 2000);
        }
    } catch (error) {
        console.error('Error stopping playback:', error);
    }
}

async function pausePlayback() {
    if (playlist.length === 0) {
        return;
    }
    try {
        const response = await fetch('/liquid/pause', {method: 'POST'});
        if (response.ok) {
            document.getElementById('playbackStatus').textContent = '⏸️ Paused';
            setTimeout(() => {
                document.getElementById('playbackStatus').textContent = '';
            }, 2000);
        }
    } catch (error) {
        console.error('Error pausing playback:', error);
    }
}

async function resumePlayback() {
    if (playlist.length === 0) {
        return;
    }
    try {
        const response = await fetch('/liquid/resume', {method: 'POST'});
        if (response.ok) {
            document.getElementById('playbackStatus').textContent = '▶️ Resumed';
            setTimeout(() => {
                document.getElementById('playbackStatus').textContent = '';
            }, 2000);
        }
    } catch (error) {
        console.error('Error resuming playback:', error);
    }
}

async function skipForward() {
    if (playlist.length === 0) {
        return;
    }
    try {
        const response = await fetch('/liquid/skip_forward', {method: 'POST'});
        if (response.ok) {
            loadPlaylist();
            loadPlaybackStack();
        }
    } catch (error) {
        console.error('Error skipping forward:', error);
    }
}

async function skipBackward() {
    if (playlist.length === 0) {
        return;
    }
    try {
        const response = await fetch('/liquid/skip_backward', {method: 'POST'});
        if (response.ok) {
            loadPlaylist();
        }
    } catch (error) {
        console.error('Error skipping backward:', error);
    }
}

// Update playlist count
function updatePlaylistCount() {
    document.getElementById('playlistCountLocal').textContent = playlist.length;
}

// Folder selector
let currentFolderPath = '';
let selectedFolderPath = '';

async function openFolderSelector() {
    document.getElementById('folderSelectorModal').style.display = 'flex';
    currentFolderPath = '';
    await loadDirectories('');
}

function closeFolderSelector() {
    document.getElementById('folderSelectorModal').style.display = 'none';
}

async function loadDirectories(path) {
    try {
        const response = await fetch('/liquid/list_directories', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: path})
        });

        if (response.ok) {
            const data = await response.json();
            currentFolderPath = data.current_path;
            renderDirectories(data.directories, data.current_path);
        } else {
            const error = await response.json();
            console.error('Error loading directories:', error.error);
        }
    } catch (error) {
        console.error('Error loading directories:', error);
    }
}

function renderDirectories(directories, currentPath) {
    const folderList = document.getElementById('folderList');
    const breadcrumb = document.getElementById('folderBreadcrumb');

    // Update breadcrumb
    if (currentPath) {
        breadcrumb.innerHTML = `<span style="cursor: pointer; color: #4ade80;" onclick="loadDirectories('')">Root</span>`;
        const parts = currentPath.split('/').filter(p => p);
        let buildPath = '';
        parts.forEach((part, index) => {
            buildPath += '/' + part;
            breadcrumb.innerHTML += ` / <span style="cursor: pointer; color: #4ade80;" onclick="loadDirectories('${buildPath}')">${part}</span>`;
        });
    } else {
        breadcrumb.innerHTML = 'Root';
    }

    // Render directory list
    if (directories.length === 0) {
        folderList.innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">No directories found</div>';
        return;
    }

    folderList.innerHTML = directories.map(dir => `
            <div class="folder-item" style="padding: 12px; cursor: pointer; border-radius: 6px; display: flex; align-items: center; gap: 10px; transition: background 0.2s;"
                 onclick="navigateToDirectory('${dir.path}')"
                 onmouseover="this.style.background='rgba(255,255,255,0.1)'"
                 onmouseout="this.style.background='transparent'">
                <span style="font-size: 1.2rem;">📁</span>
                <span style="color: white; flex: 1;">${dir.name}</span>
                ${dir.is_root ? '<span style="color: #9ca3af; font-size: 0.8rem;">Root</span>' : ''}
            </div>
        `).join('');
}

async function navigateToDirectory(path) {
    selectedFolderPath = path;
    await loadDirectories(path);
}

function selectFolder() {
    if (selectedFolderPath) {
        document.getElementById('localPathInput').value = selectedFolderPath;
        closeFolderSelector();
    } else if (currentFolderPath) {
        document.getElementById('localPathInput').value = currentFolderPath;
        closeFolderSelector();
    } else {
        alert('Please select a folder');
    }
}

// Update scanning state in UI
function updateScanningState(isScanning) {
    const pathInput = document.getElementById('localPathInput');
    const loadBtn = document.getElementById('loadLocalBtn');
    const stopBtn = document.getElementById('stopScanBtn');
    const status = document.getElementById('localPathStatus');

    if (isScanning) {
        pathInput.disabled = true;
        loadBtn.disabled = true;
        stopBtn.style.display = 'inline-block';
        status.textContent = '🔍 Scanning directory...';
    } else {
        pathInput.disabled = false;
        loadBtn.disabled = false;
        stopBtn.style.display = 'none';
        if (status.textContent.includes('Scanning')) {
            status.textContent = '✅ Scan complete';
        }
    }
}

// Stop scan
async function stopScan() {
    try {
        const response = await fetch('/liquid/stop_scan', {method: 'POST'});
        if (response.ok) {
            document.getElementById('localPathStatus').textContent = '🛑 Scan stopped';
        }
    } catch (error) {
        console.error('Error stopping scan:', error);
    }
}

// Set local path
async function setLocalPath() {
    const pathInput = document.getElementById('localPathInput');
    const path = pathInput.value.trim();
    const status = document.getElementById('localPathStatus');

    if (!path) {
        status.textContent = 'Please enter a path';
        status.style.color = '#facc15'; // Yellow warning color
        return;
    }

    try {
        const response = await fetch('/liquid/set_local_path', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: path})
        });

        if (response.ok) {
            status.textContent = `🔍 Scanning: ${path}`;
            status.style.color = '#4ade80'; // Green for success
            // Clear playlist to prepare for new scanned files
            playlist = [];
            renderPlaylist(0);
            updatePlaylistCount();
        } else {
            const error = await response.json();
            status.textContent = `Error: ${error.error}`;
            status.style.color = '#facc15'; // Yellow for error
        }
    } catch (error) {
        console.error('Error setting local path:', error);
        status.textContent = 'Error setting path';
        status.style.color = '#facc15'; // Yellow for error
    }
}
