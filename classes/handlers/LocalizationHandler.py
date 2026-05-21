import os
import yaml
from flask import jsonify

from utilities.Logger import Logger


class LocalizationHandler:
    """Handles translation files and localization."""

    def __init__(self, locales_dir: str):
        """Initialize the localization handler.
        
        Args:
            locales_dir: Directory path containing translation YAML files
        """
        self.locales_dir = locales_dir

    def get_locale(self, lang: str):
        """Serve translation files as JSON.
        
        Args:
            lang: Language code (it, en, de)
            
        Returns:
            dict: Translation data as JSON, or error response
        """
        try:
            locale_file = os.path.join(self.locales_dir, f'{lang}.yaml')
            if not os.path.exists(locale_file):
                return jsonify({'error': 'Language not found'}), 404

            with open(locale_file, 'r', encoding='utf-8') as f:
                translations = yaml.safe_load(f)

            return jsonify(translations)
        except Exception as e:
            Logger.error(f"Error loading locale {lang}: {e}")
            return jsonify({'error': 'Failed to load translations'}), 500
