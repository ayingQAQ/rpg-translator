"""
Base Parser - Abstract base class for all parsers
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import os


@dataclass
class TextSegment:
    """Represents a text segment to be translated."""
    text: str
    location: str  # Location in file (e.g., "root.dialogue[0].text")
    context: str = ""  # Additional context (e.g., surrounding text)
    metadata: Dict[str, Any] = None  # Additional metadata
    translated_text: str = ""  # Translated text
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseParser(ABC):
    """Abstract base class for file format parsers."""
    
    def __init__(self, file_path: str, encoding: str = None, **kwargs):
        """
        Initialize parser.
        
        Args:
            file_path: Path to the file
            encoding: File encoding (auto-detect if None)
            **kwargs: Additional parser options
        """
        self.file_path = file_path
        self.encoding = encoding or self._detect_encoding()
        self.options = kwargs
        self.original_data = None
        
    def _detect_encoding(self) -> str:
        """Detect file encoding automatically."""
        try:
            import chardet
            with open(self.file_path, 'rb') as f:
                raw = f.read(10000)  # Read first 10KB
                result = chardet.detect(raw)
                return result.get('encoding', 'utf-8')
        except Exception:
            return 'utf-8'
    
    @abstractmethod
    def parse(self) -> List[TextSegment]:
        """
        Parse file and extract text segments.
        
        Returns:
            List of TextSegment objects
        """
        pass
    
    @abstractmethod
    def reconstruct(self, translated_segments: List[Tuple[str, str]]) -> Any:
        """
        Reconstruct file with translated texts.
        
        Args:
            translated_segments: List of (original_text, translated_text) tuples
        
        Returns:
            Reconstructed data structure
        """
        pass
    
    @abstractmethod
    def save(self, data: Any, output_path: str) -> None:
        """
        Save reconstructed data to file.
        
        Args:
            data: Reconstructed data
            output_path: Output file path
        """
        pass
    
    def get_backup_path(self, output_dir: str = None) -> str:
        """Generate backup file path."""
        if output_dir is None:
            output_dir = os.path.dirname(self.file_path)
        
        base_name = os.path.basename(self.file_path)
        name, ext = os.path.splitext(base_name)
        return os.path.join(output_dir, f"{name}.backup{ext}")
    
    def create_backup(self, backup_path: str = None) -> str:
        """Create backup of original file."""
        import shutil
        
        if backup_path is None:
            backup_path = self.get_backup_path()
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(self.file_path, backup_path)
        return backup_path
    
    def should_skip_text(self, text: str, skip_patterns: List[str] = None) -> bool:
        """
        Check if text should be skipped (not translated).
        
        Args:
            text: Text to check
            skip_patterns: List of regex patterns to skip
        
        Returns:
            True if text should be skipped
        """
        import re
        
        if not text or not text.strip():
            return True
        
        if skip_patterns:
            for pattern in skip_patterns:
                if re.match(pattern, text):
                    return True
        
        return False
    
    def preserve_placeholders(self, text: str, preserve_patterns: List[str] = None) -> Tuple[str, Dict[str, str]]:
        """
        Replace placeholders with tokens to preserve them during translation.
        
        Args:
            text: Original text
            preserve_patterns: Patterns to preserve
        
        Returns:
            (text_with_tokens, placeholder_map)
        """
        import re
        
        if not preserve_patterns:
            return text, {}
        
        placeholders = {}
        result = text
        
        for pattern in preserve_patterns:
            matches = re.findall(pattern, text)
            for i, match in enumerate(matches):
                token = f"__PRESERVE_{len(placeholders)}__"
                placeholders[token] = match
                result = result.replace(match, token, 1)
        
        return result, placeholders
    
    def restore_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """
        Restore preserved placeholders in translated text.
        
        Args:
            text: Translated text with tokens
            placeholder_map: Token to original mapping
        
        Returns:
            Text with restored placeholders
        """
        result = text
        for token, original in placeholder_map.items():
            result = result.replace(token, original)
        return result
