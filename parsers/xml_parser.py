"""
XML Parser - Parse and reconstruct XML files
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple, Any, Dict, Set
from .base_parser import BaseParser, TextSegment


class XMLParser(BaseParser):
    """Parser for XML files."""
    
    def __init__(
        self,
        file_path: str,
        text_tags: List[str] = None,
        preserve_attributes: bool = True,
        **kwargs
    ):
        """
        Initialize XML parser.
        
        Args:
            file_path: Path to XML file
            text_tags: Specific tags to translate (auto-detect if None)
            preserve_attributes: Keep attributes unchanged
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.text_tags = text_tags
        self.preserve_attributes = preserve_attributes
        self.tree = None
        self.root = None
        self.detected_tags = set()
    
    def _clean_xml(self, content: str) -> str:
        """Clean XML content for parsing."""
        # Remove BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]
        return content
    
    def parse(self) -> List[TextSegment]:
        """Parse XML and extract text content."""
        
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            content = self._clean_xml(f.read())
        
        # Parse XML
        self.tree = ET.ElementTree(ET.fromstring(content))
        self.root = self.tree.getroot()
        
        # Auto-detect text tags if not specified
        if self.text_tags is None:
            self._detect_text_tags()
        else:
            self.detected_tags = set(self.text_tags)
        
        # Extract text segments
        segments = []
        self._extract_texts(self.root, "", segments)
        
        return segments
    
    def _detect_text_tags(self) -> None:
        """
        Detect which tags contain translatable text.
        
        Strategy: Tags that frequently contain text with letters
        are likely to be translatable.
        """
        import re
        
        tag_text_count = {}
        
        for elem in self.root.iter():
            tag = elem.tag
            text = elem.text or ""
            text = text.strip()
            
            if text:
                # Check if text contains letters (translatable content)
                if re.search(r'[a-zA-Z\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text):
                    tag_text_count[tag] = tag_text_count.get(tag, 0) + 1
        
        # Select tags that appear multiple times with text
        self.detected_tags = {
            tag for tag, count in tag_text_count.items()
            if count >= 1
        }
    
    def _extract_texts(self, elem: ET.Element, path: str, segments: List[TextSegment]) -> None:
        """Recursively extract text from XML elements."""
        
        # Build current path
        current_path = f"{path}/{elem.tag}" if path else elem.tag
        
        # Extract text content
        if elem.text and elem.text.strip():
            text = elem.text.strip()
            
            # Check if this tag should be translated
            if elem.tag in self.detected_tags and not self.should_skip_text(text):
                segments.append(TextSegment(
                    text=text,
                    location=current_path,
                    context=elem.get('context', ''),
                    metadata={
                        'tag': elem.tag,
                        'attributes': dict(elem.attrib),
                        'type': 'text'
                    }
                ))
        
        # Extract tail text (text after element, before next element)
        if elem.tail and elem.tail.strip():
            tail_text = elem.tail.strip()
            if not self.should_skip_text(tail_text):
                segments.append(TextSegment(
                    text=tail_text,
                    location=f"{current_path}/@tail",
                    metadata={'type': 'tail'}
                ))
        
        # Process children
        for child in elem:
            self._extract_texts(child, current_path, segments)
    
    def reconstruct(self, translated_segments: List[Tuple[str, str]]) -> ET.ElementTree:
        """
        Reconstruct XML with translations.
        
        Args:
            translated_segments: List of (original, translated) tuples
        """
        if self.root is None:
            raise ValueError("No original data. Call parse() first.")
        
        # Create translation mapping
        translation_map = {orig: trans for orig, trans in translated_segments}
        
        # Apply translations
        self._apply_translations(self.root, translation_map)
        
        return self.tree
    
    def _apply_translations(self, elem: ET.Element, translation_map: Dict[str, str]) -> None:
        """Recursively apply translations to elements."""
        
        # Translate text content
        if elem.text:
            text = elem.text.strip()
            if text in translation_map:
                # Preserve original whitespace
                if elem.text.startswith(' ') or elem.text.endswith(' '):
                    elem.text = f" {translation_map[text]} "
                else:
                    elem.text = translation_map[text]
        
        # Translate tail text
        if elem.tail:
            tail_text = elem.tail.strip()
            if tail_text in translation_map:
                if elem.tail.startswith(' ') or elem.tail.endswith(' '):
                    elem.tail = f" {translation_map[tail_text]} "
                else:
                    elem.tail = translation_map[tail_text]
        
        # Process children
        for child in elem:
            self._apply_translations(child, translation_map)
    
    def save(self, tree: ET.ElementTree, output_path: str) -> None:
        """Save XML tree to file."""
        import os
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        # Preserve XML declaration and encoding
        with open(output_path, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
