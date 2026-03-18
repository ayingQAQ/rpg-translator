"""
Baidu Translator - Baidu Translation API
"""

import os
import hashlib
import random
import requests
from typing import Optional
from .base_translator import BaseTranslator


class BaiduTranslator(BaseTranslator):
    """
    Baidu translation engine.
    
    Requires Baidu API credentials (App ID and Secret Key).
    Offers free tier: 2,000,000 characters/month for standard translation.
    """
    
    API_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    
    def __init__(
        self,
        app_id: str = None,
        secret_key: str = None,
        **kwargs
    ):
        """
        Initialize Baidu translator.
        
        Args:
            app_id: Baidu App ID
            secret_key: Baidu Secret Key
            **kwargs: Base translator arguments
        """
        super().__init__(**kwargs)
        
        # Get credentials from parameter or environment
        self.app_id = app_id or os.getenv('BAIDU_APP_ID')
        self.secret_key = secret_key or os.getenv('BAIDU_SECRET_KEY')
        
        if not self.app_id or not self.secret_key:
            raise ValueError(
                "Baidu API credentials are required.\n"
                "Set them in config or BAIDU_APP_ID and BAIDU_SECRET_KEY environment variables.\n"
                "Get your credentials at: https://fanyi-api.baidu.com/"
            )
    
    def translate(self, text: str) -> str:
        """
        Translate text using Baidu API.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # Generate salt and sign
        salt = str(random.randint(32768, 65536))
        sign = self._generate_sign(text, salt)
        
        # Prepare request
        params = {
            'q': text,
            'from': self._map_language(self.source_lang),
            'to': self._map_language(self.target_lang),
            'appid': self.app_id,
            'salt': salt,
            'sign': sign,
        }
        
        # Make request
        response = requests.get(self.API_URL, params=params, timeout=30)
        
        # Check response
        if response.status_code != 200:
            raise RuntimeError(
                f"Baidu API error: {response.status_code}\n"
                f"Response: {response.text}"
            )
        
        # Parse response
        result = response.json()
        
        # Check for errors
        if 'error_code' in result:
            raise RuntimeError(
                f"Baidu API error: {result.get('error_code')}\n"
                f"Message: {result.get('error_msg')}"
            )
        
        # Extract translation
        if 'trans_result' in result:
            return result['trans_result'][0]['dst']
        
        return text
    
    def _generate_sign(self, text: str, salt: str) -> str:
        """
        Generate API signature.
        
        Args:
            text: Text to translate
            salt: Random salt
        
        Returns:
            MD5 signature
        """
        # Sign = MD5(appid + q + salt + secret_key)
        sign_str = f"{self.app_id}{text}{salt}{self.secret_key}"
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    def _map_language(self, lang: str) -> str:
        """
        Map language code to Baidu format.
        """
        mapping = {
            'auto': 'auto',
            'zh-CN': 'zh',
            'zh-TW': 'cht',
            'zh': 'zh',
            'en': 'en',
            'ja': 'jp',
            'ko': 'kor',
            'es': 'spa',
            'fr': 'fra',
            'de': 'de',
            'it': 'it',
            'pt': 'pt',
            'ru': 'ru',
            'ar': 'ara',
        }
        return mapping.get(lang, lang)
    
    @staticmethod
    def get_supported_languages() -> list:
        """Get list of supported languages."""
        return [
            'auto', 'zh', 'en', 'ja', 'ko',
            'es', 'fr', 'de', 'it', 'pt', 'ru', 'ar',
            'th', 'vi', 'id', 'ms'
        ]
