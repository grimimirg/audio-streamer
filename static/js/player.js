const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const vinyl = document.getElementById('vinyl');
const visualizer = document.getElementById('visualizer');
const connectionStatus = document.getElementById('connectionStatus');
let isPlaying = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;
let currentStatusKey = 'status.ready'; // Track current status for translation

function changeTheme(themeName) {
    document.getElementById('mainBody').className = themeName;
    localStorage.setItem('theme', themeName);
}

function updateStatus(messageKey, type = 'loading') {
    currentStatusKey = messageKey;
    connectionStatus.textContent = i18n.t(messageKey);
    connectionStatus.className = type;
    
    // Store current status key for re-translation on language change
    window.updateCurrentStatus = () => {
        connectionStatus.textContent = i18n.t(messageKey);
    };
}

function togglePlay() {
    if (!isPlaying) {
        startStreaming();
    } else {
        stopStreaming();
    }
}

function startStreaming() {
    updateStatus('status.connecting', 'loading');
    playBtn.disabled = true;
    playBtn.textContent = `⏳ ${i18n.t('controls.connecting')}`;

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

    playBtn.textContent = `▶️ ${i18n.t('controls.play')}`;
    playBtn.style.background = '#667eea';
    playBtn.disabled = false;
    vinyl.style.animationPlayState = 'paused';
    isPlaying = false;
    reconnectAttempts = 0;
    updateStatus('status.ready', 'loading');
}

function onLoadStart() {
    updateStatus('status.buffering', 'loading');
}

function onCanPlay() {
    playBtn.textContent = `⏸️ ${i18n.t('controls.pause')}`;
    playBtn.style.background = '#f43f5e';
    playBtn.disabled = false;
    vinyl.style.animationPlayState = 'running';
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
                updateStatus('status.server_stopped', 'error');
                stopStreaming();
            }
        })
        .catch(error => {
            console.error('Stats error:', error);
            if (isPlaying) {
                updateStatus('status.connection_lost', 'error');
            }
        });
}, 5000);

audio.volume = 0.7;

// Funzione per aggiornare i testi statici dell'interfaccia
function updateStaticTexts() {
    // Aggiorna tutti gli elementi con attributo data-i18n
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        element.textContent = i18n.t(key);
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    // Carica le traduzioni iniziali
    await i18n.loadTranslations(i18n.getCurrentLang());
    
    // Aggiorna i testi statici
    updateStaticTexts();
    
    // Ripristina tema salvato
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.getElementById('mainBody').className = savedTheme;
        document.getElementById('themeDropdown').value = savedTheme;
    }
    
    // Ripristina lingua salvata
    const savedLang = localStorage.getItem('language');
    if (savedLang) {
        document.getElementById('languageDropdown').value = savedLang;
    }
    
    // Aggiorna lo stato iniziale
    updateStatus('status.ready', 'loading');
});

// Aggiorna funzione changeLanguage per aggiornare anche i testi statici
const originalChangeLanguage = changeLanguage;
changeLanguage = async function(lang) {
    const success = await originalChangeLanguage(lang);
    if (success) {
        updateStaticTexts();
        // Aggiorna anche il testo del bottone play se non sta suonando
        if (!isPlaying) {
            playBtn.textContent = `▶️ ${i18n.t('controls.play')}`;
        }
    }
};
