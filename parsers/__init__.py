"""
File Format Parsers
====================

Support for various game text file formats.
"""

from .base_parser import BaseParser
from .json_parser import JSONParser
from .csv_parser import CSVParser
from .xml_parser import XMLParser
from .yaml_parser import YAMLParser
from .excel_parser import ExcelParser
from .binary_parser import BinaryParser

# Format to parser mapping
PARSERS = {
    '.json': JSONParser,
    '.json5': JSONParser,
    '.csv': CSVParser,
    '.tsv': CSVParser,
    '.xml': XMLParser,
    '.yaml': YAMLParser,
    '.yml': YAMLParser,
    '.xlsx': ExcelParser,
    '.xls': ExcelParser,
    # Binary formats can be added here
    # '.dat': BinaryParser,
}


def get_parser(file_path: str, **kwargs) -> BaseParser:
    """
    Get appropriate parser for a file based on its extension.
    
    Args:
        file_path: Path to the file
        **kwargs: Additional parser arguments
    
    Returns:
        Parser instance
    
    Raises:
        ValueError: If file format is not supported
    """
    import os
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext not in PARSERS:
        raise ValueError(
            f"Unsupported file format: {ext}\n"
            f"Supported formats: {', '.join(PARSERS.keys())}"
        )
    
    return PARSERS[ext](file_path, **kwargs)


def get_supported_formats() -> list:
    """Return list of supported file formats."""
    return list(PARSERS.keys())


__all__ = [
    "BaseParser",
    "JSONParser",
    "CSVParser",
    "XMLParser",
    "YAMLParser",
    "ExcelParser",
    "TextSegment",
    "BinaryParser",
    "get_parser",
    "get_supported_formats",
]
