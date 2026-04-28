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

// Cambia lingua
async function changeLanguage(lang) {
    const success = await i18n.loadTranslations(lang);
    if (success) {
        // Aggiorna tutti gli elementi con data-i18n
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = i18n.t(key);
        });
        
        // Aggiorna dropdown lingua
        const langSelect = document.getElementById('languageDropdown');
        if (langSelect) {
            langSelect.value = i18n.getCurrentLang();
        }
        
        // Aggiorna anche lo stato corrente se presente
        if (window.updateCurrentStatus) {
            window.updateCurrentStatus();
        }
    }
}
