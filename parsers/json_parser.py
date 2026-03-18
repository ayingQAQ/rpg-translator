"""
JSON Parser - Parse and reconstruct JSON/JSON5 files
"""

import json
import re
from typing import List, Tuple, Any, Dict
from .base_parser import BaseParser, TextSegment


class JSONParser(BaseParser):
    """Parser for JSON and JSON5 files."""
    
    def __init__(self, file_path: str, preserve_keys: bool = False, **kwargs):
        """
        Initialize JSON parser.
        
        Args:
            file_path: Path to JSON file
            preserve_keys: Whether to preserve JSON keys (not translate them)
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.preserve_keys = preserve_keys
        self.indent = kwargs.get('indent', 2)
    
    def _load_json(self) -> Any:
        """Load JSON file, supporting both standard JSON and JSON5."""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            content = f.read()
        
        # Try standard JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try JSON5 (relaxed JSON with comments, trailing commas)
            try:
                # Simple JSON5 support: remove comments and trailing commas
                # For full JSON5 support, consider using json5 library
                content = self._preprocess_json5(content)
                return json.loads(content)
            except Exception as e:
                raise ValueError(f"Failed to parse JSON file: {self.file_path}\nError: {e}")
    
    def _preprocess_json5(self, content: str) -> str:
        """Preprocess JSON5 content to standard JSON."""
        # Remove single-line comments
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # Remove trailing commas
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        return content
    
    def parse(self) -> List[TextSegment]:
        """Parse JSON and extract all text values."""
        self.original_data = self._load_json()
        segments = []
        
        self._extract_texts(self.original_data, "", segments)
        return segments
    
    def _extract_texts(self, data: Any, path: str, segments: List[TextSegment]) -> None:
        """Recursively extract text values from JSON data."""
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                
                if isinstance(value, str):
                    # Check if this is a key (skip if preserve_keys is True)
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
    
    def reconstruct(self, translated_segments: List[TextSegment]) -> Any:
        """
        Reconstruct JSON with translations using precise path-based assignment.
        
        Args:
            translated_segments: List of TextSegment objects with translated_text
        """
        if self.original_data is None:
            raise ValueError("No original data. Call parse() first.")
        
        # Deep copy original data
        import copy
        result = copy.deepcopy(self.original_data)
        
        # Apply translations using precise path assignment
        for segment in translated_segments:
            if segment.translated_text:
                self._set_value_by_path(result, segment.location, segment.translated_text)
        
        return result
    
    def _set_value_by_path(self, data: Any, path: str, value: str) -> None:
        """
        Set value at precise path using location string.
        
        Args:
            data: Data structure to modify
            path: Location string (e.g., "events[1].pages[0].list[1].parameters[0]")
            value: Value to set
        """
        # Split path into components
        # Handle both dot notation and bracket notation
        import re
        components = re.findall(r'[^.\[\]]+', path)
        
        current = data
        
        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            # Check if component is an array index
            if component.isdigit():
                idx = int(component)
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    # Invalid path, skip
                    return
            else:
                # Object key
                if isinstance(current, dict) and component in current:
                    current = current[component]
                else:
                    # Invalid path, skip
                    return
        
        # Apply translation to final element
        last_component = components[-1]
        if last_component.isdigit():
            idx = int(last_component)
            if isinstance(current, list) and idx < len(current):
                current[idx] = value
        else:
            if isinstance(current, dict):
                current[last_component] = value
        
        return None
    
    def save(self, data: Any, output_path: str) -> None:
        """Save data to JSON file."""
        import os
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=self.indent)
