"""
Core module - Main translation workflow
"""

from .config import load_config
from .translator import GameTranslator

__all__ = ["GameTranslator", "load_config"]
