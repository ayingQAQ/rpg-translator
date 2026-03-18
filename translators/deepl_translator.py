"""
DeepL Translator - Professional translation API
"""

import os
import requests
from typing import Optional
from .base_translator import BaseTranslator


class DeepLTranslator(BaseTranslator):
    """
    DeepL translation engine.
    
    Requires DeepL API key. Offers free and pro tiers.
    Free tier: 500,000 characters/month
    Pro tier: Unlimited (paid)
    """
    
    # API endpoints
    FREE_API_URL = "https://api-free.deepl.com/v2/translate"
    PRO_API_URL = "https://api.deepl.com/v2/translate"
    
    def __init__(
        self,
        api_key: str = None,
        free_mode: bool = True,
        **kwargs
    ):
        """
        Initialize DeepL translator.
        
        Args:
            api_key: DeepL API key
            free_mode: Use free API endpoint
            **kwargs: Base translator arguments
        """
        super().__init__(**kwargs)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv('DEEPL_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "DeepL API key is required.\n"
                "Set it in config or DEEPL_API_KEY environment variable.\n"
                "Get your API key at: https://www.deepl.com/pro-api"
            )
        
        self.free_mode = free_mode
        self.api_url = self.FREE_API_URL if free_mode else self.PRO_API_URL
    
    def translate(self, text: str) -> str:
        """
        Translate text using DeepL API.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # Prepare request
        params = {
            'auth_key': self.api_key,
            'text': text,
            'target_lang': self._map_language(self.target_lang),
        }
        
        # Add source language if specified
        if self.source_lang != 'auto':
            params['source_lang'] = self._map_language(self.source_lang)
        
        # Make request
        response = requests.post(self.api_url, data=params, timeout=30)
        
        # Check response
        if response.status_code != 200:
            raise RuntimeError(
                f"DeepL API error: {response.status_code}\n"
                f"Response: {response.text}"
            )
        
        # Parse response
        result = response.json()
        return result['translations'][0]['text']
    
    def _map_language(self, lang: str) -> str:
        """
        Map language code to DeepL format.
        
        DeepL uses uppercase codes with hyphens.
        """
        mapping = {
            'zh-CN': 'ZH',
            'zh-TW': 'ZH',
            'zh': 'ZH',
            'en': 'EN',
            'ja': 'JA',
            'ko': 'KO',
            'de': 'DE',
            'fr': 'FR',
            'es': 'ES',
            'it': 'IT',
            'pt': 'PT-PT',
            'pt-BR': 'PT-BR',
            'ru': 'RU',
        }
        return mapping.get(lang, lang.upper())
    
    def get_usage(self) -> dict:
        """
        Get API usage statistics.
        
        Returns:
            Dictionary with usage info
        """
        usage_url = (
            "https://api-free.deepl.com/v2/usage"
            if self.free_mode
            else "https://api.deepl.com/v2/usage"
        )
        
        response = requests.post(
            usage_url,
            data={'auth_key': self.api_key},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    
    @staticmethod
    def get_supported_languages() -> list:
        """Get list of supported languages."""
        return [
            'en', 'zh', 'ja', 'ko',
            'de', 'fr', 'es', 'it', 'pt', 'pt-BR',
            'ru', 'nl', 'pl', 'bg', 'cs', 'da',
            'et', 'fi', 'el', 'hu', 'lv', 'lt',
            'ro', 'sk', 'sl', 'sv'
        ]
