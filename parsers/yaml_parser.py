"""
YAML Parser - Parse and reconstruct YAML files
"""

import yaml
from typing import List, Tuple, Any, Dict
from .base_parser import BaseParser, TextSegment


class YAMLParser(BaseParser):
    """Parser for YAML files."""
    
    def __init__(self, file_path: str, preserve_keys: bool = False, **kwargs):
        """
        Initialize YAML parser.
        
        Args:
            file_path: Path to YAML file
            preserve_keys: Whether to preserve YAML keys (not translate them)
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.preserve_keys = preserve_keys
    
    def parse(self) -> List[TextSegment]:
        """Parse YAML and extract text values."""
        
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            self.original_data = yaml.safe_load(f)
        
        segments = []
        self._extract_texts(self.original_data, "", segments)
        
        return segments
    
    def _extract_texts(self, data: Any, path: str, segments: List[TextSegment]) -> None:
        """Recursively extract text values from YAML data."""
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                
                if isinstance(value, str):
                    if not self.should_skip_text(value):
                        segments.append(TextSegment(
                            text=value,
                            location=new_path,
                            metadata={'type': 'value'}
                        ))
                else:
                    self._extract_texts(value, new_path, segments)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                
                if isinstance(item, str):
                    if not self.should_skip_text(item):
                        segments.append(TextSegment(
                            text=item,
                            location=new_path,
                            metadata={'type': 'array_value', 'index': i}
                        ))
                else:
                    self._extract_texts(item, new_path, segments)
        
        elif isinstance(data, str):
            if not self.should_skip_text(data):
                segments.append(TextSegment(
                    text=data,
                    location=path,
                    metadata={'type': 'root_value'}
                ))
    
    def reconstruct(self, translated_segments: List[Tuple[str, str]]) -> Any:
        """
        Reconstruct YAML with translations.
        
        Args:
            translated_segments: List of (original, translated) tuples
        """
        if self.original_data is None:
            raise ValueError("No original data. Call parse() first.")
        
        # Create translation mapping
        translation_map = {orig: trans for orig, trans in translated_segments}
        
        # Deep copy original data
        import copy
        result = copy.deepcopy(self.original_data)
        
        # Apply translations
        self._apply_translations(result, translation_map)
        
        return result
    
    def _apply_translations(self, data: Any, translation_map: Dict[str, str]) -> Any:
        """Recursively apply translations to data."""
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value in translation_map:
                    data[key] = translation_map[value]
                else:
                    self._apply_translations(value, translation_map)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, str) and item in translation_map:
                    data[i] = translation_map[item]
                else:
                    self._apply_translations(item, translation_map)
        
        elif isinstance(data, str) and data in translation_map:
            return translation_map[data]
    
    def save(self, data: Any, output_path: str) -> None:
        """Save data to YAML file."""
        import os
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
