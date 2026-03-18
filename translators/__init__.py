"""
Translation Engines
===================

Support for multiple translation backends.
"""

from .base_translator import BaseTranslator
from .google_translator import GoogleTranslator
from .deepl_translator import DeepLTranslator
from .baidu_translator import BaiduTranslator
from .local_translator import LocalTranslator

# Translator registry
TRANSLATORS = {
    'google': GoogleTranslator,
    'deepl': DeepLTranslator,
    'baidu': BaiduTranslator,
    'local': LocalTranslator,
}


def get_translator(engine: str, **kwargs) -> BaseTranslator:
    """
    Get translator instance by engine name.
    
    Args:
        engine: Translator engine name ('google', 'deepl', 'baidu', 'local')
        **kwargs: Translator configuration
    
    Returns:
        Translator instance
    
    Raises:
        ValueError: If engine is not supported
    """
    if engine not in TRANSLATORS:
        raise ValueError(
            f"Unsupported translation engine: {engine}\n"
            f"Supported engines: {', '.join(TRANSLATORS.keys())}"
        )
    
    return TRANSLATORS[engine](**kwargs)


def get_available_engines() -> list:
    """Return list of available translation engines."""
    return list(TRANSLATORS.keys())


__all__ = [
    "BaseTranslator",
    "GoogleTranslator",
    "DeepLTranslator",
    "BaiduTranslator",
    "LocalTranslator",
    "get_translator",
    "get_available_engines",
]
