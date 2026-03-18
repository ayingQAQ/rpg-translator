"""
Binary Parser - Parse and reconstruct custom binary formats

This is a template for parsing custom binary formats.
Users can extend this class or define custom format specifications.
"""

from typing import List, Tuple, Any, Dict, Optional
from .base_parser import BaseParser, TextSegment


class BinaryParser(BaseParser):
    """
    Parser for custom binary formats.
    
    This is a flexible parser that can be configured to handle various
    binary formats used by RPG games.
    """
    
    def __init__(
        self,
        file_path: str,
        format_spec: Dict = None,
        **kwargs
    ):
        """
        Initialize binary parser.
        
        Args:
            file_path: Path to binary file
            format_spec: Format specification dictionary
                Example:
                {
                    'header_size': 16,
                    'text_table_offset': 0x1000,
                    'text_table_count': 100,
                    'text_entry_size': 256,
                    'text_encoding': 'utf-8',
                    'pointer_table': True,
                }
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.format_spec = format_spec or {}
        self.binary_data = None
        self.text_entries = []
    
    def parse(self) -> List[TextSegment]:
        """
        Parse binary file and extract text.
        
        This is a template implementation. Override this method
        for specific binary formats.
        """
        
        with open(self.file_path, 'rb') as f:
            self.binary_data = f.read()
        
        # Get format specification
        text_offset = self.format_spec.get('text_table_offset', 0)
        text_count = self.format_spec.get('text_table_count', 0)
        entry_size = self.format_spec.get('text_entry_size', 256)
        encoding = self.format_spec.get('text_encoding', 'utf-8')
        null_terminated = self.format_spec.get('null_terminated', True)
        
        segments = []
        
        # If format spec is provided, parse accordingly
        if text_count > 0 and entry_size > 0:
            for i in range(text_count):
                offset = text_offset + i * entry_size
                entry_data = self.binary_data[offset:offset + entry_size]
                
                try:
                    if null_terminated:
                        # Find null terminator
                        null_pos = entry_data.find(b'\x00')
                        if null_pos != -1:
                            text = entry_data[:null_pos].decode(encoding)
                        else:
                            text = entry_data.decode(encoding).rstrip('\x00')
                    else:
                        text = entry_data.decode(encoding).rstrip('\x00')
                    
                    if text and not self.should_skip_text(text):
                        segments.append(TextSegment(
                            text=text,
                            location=f"offset_{offset:08X}",
                            metadata={
                                'offset': offset,
                                'entry_index': i,
                                'entry_size': entry_size
                            }
                        ))
                except Exception as e:
                    # Skip invalid entries
                    continue
        
        return segments
    
    def reconstruct(self, translated_segments: List[Tuple[str, str]]) -> bytes:
        """
        Reconstruct binary file with translations.
        
        Args:
            translated_segments: List of (original, translated) tuples
        
        Returns:
            Modified binary data
        """
        if self.binary_data is None:
            raise ValueError("No original data. Call parse() first.")
        
        # Create translation mapping
        translation_map = {orig: trans for orig, trans in translated_segments}
        
        # Create mutable copy
        result = bytearray(self.binary_data)
        
        # Apply translations
        encoding = self.format_spec.get('text_encoding', 'utf-8')
        entry_size = self.format_spec.get('text_entry_size', 256)
        
        for segment in self.text_entries:
            if segment.text in translation_map:
                translated = translation_map[segment.text]
                offset = segment.metadata['offset']
                
                # Encode translated text
                encoded = translated.encode(encoding)
                
                # Ensure it fits in the entry
                if len(encoded) > entry_size - 1:
                    # Truncate if too long
                    encoded = encoded[:entry_size - 1]
                
                # Write to result
                result[offset:offset + len(encoded)] = encoded
                # Add null terminator
                result[offset + len(encoded)] = 0
        
        return bytes(result)
    
    def save(self, data: bytes, output_path: str) -> None:
        """Save binary data to file."""
        import os
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(data)
    
    @staticmethod
    def analyze_format(file_path: str, sample_text: List[str] = None) -> Dict:
        """
        Analyze binary file to detect format patterns.
        
        This is a helper method to assist in reverse engineering
        binary formats.
        
        Args:
            file_path: Path to binary file
            sample_text: Known text strings in the file (for searching)
        
        Returns:
            Detected format information
        """
        import re
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        results = {
            'file_size': len(data),
            'potential_offsets': [],
            'encodings': []
        }
        
        # Try to find text patterns
        encodings_to_try = ['utf-8', 'utf-16', 'utf-16-le', 'shift-jis', 'gbk', 'euc-jp']
        
        for encoding in encodings_to_try:
            try:
                decoded = data.decode(encoding, errors='ignore')
                
                # Find sequences of printable characters
                printable_sequences = re.findall(
                    r'[\x20-\x7E\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]{4,}',
                    decoded
                )
                
                if printable_sequences:
                    results['encodings'].append({
                        'encoding': encoding,
                        'sequences_found': len(printable_sequences),
                        'sample': printable_sequences[:5]
                    })
            except Exception:
                continue
        
        # Search for known text
        if sample_text:
            for text in sample_text:
                for encoding in encodings_to_try:
                    try:
                        encoded = text.encode(encoding)
                        offset = data.find(encoded)
                        if offset != -1:
                            results['potential_offsets'].append({
                                'text': text,
                                'offset': offset,
                                'encoding': encoding
                            })
                    except Exception:
                        continue
        
        return results


# Example format specifications for common RPG game formats
FORMAT_TEMPLATES = {
    'rpg_maker_xp': {
        'text_table_offset': 0x1000,
        'text_encoding': 'utf-8',
        'null_terminated': True,
    },
    'renpy_save': {
        'text_encoding': 'utf-8',
        'null_terminated': False,
    },
    # Add more templates as needed
}
