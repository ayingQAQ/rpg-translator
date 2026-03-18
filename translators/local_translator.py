"""
Local Translator - Local AI model translation
"""

import os
from typing import Optional, List
from .base_translator import BaseTranslator


class LocalTranslator(BaseTranslator):
    """
    Local AI translation engine.
    
    Uses open-source translation models that run locally.
    Supports Helsinki-NLP models and can be extended for other models.
    """
    
    # Common model options
    AVAILABLE_MODELS = {
        'en-zh': 'Helsinki-NLP/opus-mt-en-zh',
        'en-ja': 'Helsinki-NLP/opus-mt-en-ja',
        'en-ko': 'Helsinki-NLP/opus-mt-en-ko',
        'zh-en': 'Helsinki-NLP/opus-mt-zh-en',
        'ja-en': 'Helsinki-NLP/opus-mt-ja-en',
        'ko-en': 'Helsinki-NLP/opus-mt-ko-en',
        # Add more models as needed
    }
    
    def __init__(
        self,
        model_name: str = None,
        device: str = 'auto',
        cache_dir: str = None,
        **kwargs
    ):
        """
        Initialize local translator.
        
        Args:
            model_name: Model name or path (auto-select if None)
            device: Device to use ('auto', 'cpu', 'cuda')
            cache_dir: Directory to cache models
            **kwargs: Base translator arguments
        """
        super().__init__(**kwargs)
        
        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir or os.getenv('TRANSFORMERS_CACHE', './models')
        self._model = None
        self._tokenizer = None
    
    def _get_model_pair(self) -> tuple:
        """
        Get model for language pair.
        
        Returns:
            (model, tokenizer) tuple
        """
        # Auto-select model based on language pair
        if self.model_name is None:
            model_key = f"{self.source_lang}-{self.target_lang}"
            self.model_name = self.AVAILABLE_MODELS.get(
                model_key,
                'Helsinki-NLP/opus-mt-en-zh'  # Default fallback
            )
        
        # Load model
        try:
            from transformers import MarianMTModel, MarianTokenizer
            
            tokenizer = MarianTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            model = MarianMTModel.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            
            # Move to device
            if self.device == 'auto':
                import torch
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            model = model.to(self.device)
            
            return model, tokenizer
            
        except ImportError:
            raise ImportError(
                "transformers is required for local translation.\n"
                "Install it with: pip install transformers torch"
            )
    
    def translate(self, text: str) -> str:
        """
        Translate text using local model.
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # Lazy load model
        if self._model is None:
            self._model, self._tokenizer = self._get_model_pair()
        
        try:
            # Tokenize
            inputs = self._tokenizer(
                text,
                return_tensors='pt',
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate
            outputs = self._model.generate(**inputs)
            
            # Decode
            translated = self._tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            )
            
            return translated
            
        except Exception as e:
            print(f"Local translation error: {e}")
            return text
    
    def translate_batch(self, texts: List[str]) -> List[tuple]:
        """
        Translate multiple texts efficiently.
        
        Args:
            texts: List of texts to translate
        
        Returns:
            List of (original, translated) tuples
        """
        # Lazy load model
        if self._model is None:
            self._model, self._tokenizer = self._get_model_pair()
        
        try:
            # Tokenize all texts
            inputs = self._tokenizer(
                texts,
                return_tensors='pt',
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate in batch
            outputs = self._model.generate(**inputs)
            
            # Decode all
            translated_texts = [
                self._tokenizer.decode(output, skip_special_tokens=True)
                for output in outputs
            ]
            
            return list(zip(texts, translated_texts))
            
        except Exception as e:
            print(f"Batch translation error: {e}")
            return [(text, text) for text in texts]
    
    @staticmethod
    def get_supported_models() -> dict:
        """Get available models."""
        return LocalTranslator.AVAILABLE_MODELS.copy()
    
    @staticmethod
    def is_available() -> bool:
        """Check if local translation is available."""
        try:
            import transformers
            import torch
            return True
        except ImportError:
            return False
