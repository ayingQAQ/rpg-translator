"""
RPG Game Translator - Universal Translation Tool for RPG Games
==============================================================

A comprehensive translation tool supporting multiple file formats and translation engines.
"""

__version__ = "1.0.0"
__author__ = "RPG Translator Team"

from .core.translator import GameTranslator
from .parsers import get_parser
from .translators import get_translator

__all__ = [
    "GameTranslator",
    "get_parser", 
    "get_translator",
]
