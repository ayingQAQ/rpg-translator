"""
Google Translator - Free Google Translate API
"""

from typing import Optional
from .base_translator import BaseTranslator


class GoogleTranslator(BaseTranslator):
    """
    Google Translate engine using deep_translator library.
    
    This is a free option but may have rate limits.
    """
    
    def __init__(self, **kwargs):
        """Initialize Google translator."""
        super().__init__(**kwargs)
        self._translator = None
    
    def _get_translator(self):
        """Lazy load translator to avoid initialization overhead."""
        if self._translator is None:
            try:
                from deep_translator import GoogleTranslator as GT
                self._translator = GT(
                    source='auto' if self.source_lang == 'auto' else self._map_language(self.source_lang),
                    target=self._map_language(self.target_lang)
                )
            except ImportError:
                raise ImportError(
                    "deep_translator is required for Google Translate.\n"
                    "Install it with: pip install deep-translator"
                )
        return self._translator
    
    def translate(self, text: str) -> str:
        """
        Translate text using Google Translate.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        translator = self._get_translator()
        
        try:
            result = translator.translate(text)
            return result
        except Exception as e:
            raise RuntimeError(f"Google Translate failed: {e}")
    
    def _map_language(self, lang: str) -> str:
        """
        Map language code to Google Translate format.
        
        Args:
            lang: Language code
        
        Returns:
            Google Translate language code
        """
        mapping = {
            'zh-CN': 'zh-CN',
            'zh-TW': 'zh-TW',
            'zh': 'zh-CN',
            'en': 'en',
            'ja': 'ja',
            'ko': 'ko',
            'auto': 'auto',
        }
        return mapping.get(lang, lang.lower())
    
    @staticmethod
    def get_supported_languages() -> list:
        """Get list of supported languages."""
        return [
            'auto', 'en', 'zh-CN', 'zh-TW', 'ja', 'ko',
            'es', 'fr', 'de', 'it', 'pt', 'ru', 'ar',
            'th', 'vi', 'id', 'ms', 'fil'
        ]
