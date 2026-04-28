// Sistema di localizzazione
class I18n {
    constructor() {
        this.currentLang = localStorage.getItem('language') || 'it';
        this.translations = {};
    }

    async loadTranslations(lang) {
        try {
            const response = await fetch(`/locales/${lang}`);
            if (!response.ok) throw new Error('Translation file not found');
            this.translations = await response.json();
            this.currentLang = lang;
            localStorage.setItem('language', lang);
            return true;
        } catch (error) {
            console.error('Error loading translations:', error);
            return false;
        }
    }

    t(key) {
        const keys = key.split('.');
        let value = this.translations;
        
        for (const k of keys) {
            if (value && typeof value === 'object') {
                value = value[k];
            } else {
                return key;
            }
        }
        
        return value || key;
    }

    getCurrentLang() {
        return this.currentLang;
    }
}

// Istanza globale
const i18n = new I18n();

// Funzione per aggiornare tutti i testi tradotti
function updateTranslations() {
    // Titolo e sottotitolo
    document.querySelector('h1').textContent = `📻 ${i18n.t('app.title')}`;
    document.querySelector('.subtitle').textContent = i18n.t('app.subtitle');
    
    // Controlli
    const playBtn = document.getElementById('playBtn');
    if (playBtn.textContent.includes('▶') || playBtn.textContent.includes('Play') || playBtn.textContent.includes('Riproduci') || playBtn.textContent.includes('Abspielen')) {
        playBtn.textContent = `▶️ ${i18n.t('controls.play')}`;
    } else if (playBtn.textContent.includes('⏸') || playBtn.textContent.includes('Pause')) {
        playBtn.textContent = `⏸️ ${i18n.t('controls.pause')}`;
    }
    
    // Volume
    document.querySelector('.volume-control').childNodes[0].textContent = `🔊 ${i18n.t('controls.volume')}: `;
    
    // Listeners
    const statusDiv = document.querySelector('.status');
    const listenersText = statusDiv.childNodes[0];
    listenersText.textContent = `🎧 ${i18n.t('listeners.online')}: `;
    
    // Aggiorna dropdown lingua
    const langSelect = document.getElementById('languageDropdown');
    if (langSelect) {
        langSelect.value = i18n.getCurrentLang();
    }
}

// Cambia lingua
async function changeLanguage(lang) {
    const success = await i18n.loadTranslations(lang);
    if (success) {
        updateTranslations();
        // Aggiorna anche lo stato corrente se presente
        if (window.updateCurrentStatus) {
            window.updateCurrentStatus();
        }
    }
}

// Inizializzazione
document.addEventListener('DOMContentLoaded', async () => {
    await i18n.loadTranslations(i18n.getCurrentLang());
    updateTranslations();
});
