"""
Base Translator - Abstract base class for translation engines
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import time


class BaseTranslator(ABC):
    """Abstract base class for translation engines."""
    
    def __init__(
        self,
        source_lang: str = 'auto',
        target_lang: str = 'zh-CN',
        delay: float = 0.5,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        **kwargs  # Accept extra kwargs
    ):
        """
        Initialize translator.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            delay: Delay between requests (seconds)
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (seconds)
        """
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.delay = delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._last_request_time = 0
    
    @abstractmethod
    def translate(self, text: str) -> str:
        """
        Translate a single text string.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        pass
    
    def translate_batch(self, texts: List[str]) -> List[Tuple[str, str]]:
        """
        Translate multiple texts.
        
        Args:
            texts: List of texts to translate
        
        Returns:
            List of (original, translated) tuples
        """
        results = []
        
        for text in texts:
            translated = self.translate_with_retry(text)
            results.append((text, translated))
        
        return results
    
    def translate_with_retry(self, text: str) -> str:
        """
        Translate text with retry logic.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting
                self._wait_if_needed()
                
                # Translate
                result = self.translate(text)
                
                # Update last request time
                self._last_request_time = time.time()
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries - 1:
                    # Wait before retry
                    time.sleep(self.retry_delay * (attempt + 1))
        
        # All retries failed, raise exception
        raise RuntimeError(f"Translation failed after {self.max_retries} attempts. Last error: {last_error}")
    
    def _wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
    
    @staticmethod
    def get_supported_languages() -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes
        """
        # Common language codes
        return [
            'auto',    # Auto-detect
            'en',      # English
            'zh-CN',   # Chinese Simplified
            'zh-TW',   # Chinese Traditional
            'ja',      # Japanese
            'ko',      # Korean
            'es',      # Spanish
            'fr',      # French
            'de',      # German
            'it',      # Italian
            'pt',      # Portuguese
            'ru',      # Russian
            'ar',      # Arabic
        ]
