"""
CSV/TSV Parser - Parse and reconstruct CSV files
"""

import csv
from typing import List, Tuple, Any, Dict, Optional
from .base_parser import BaseParser, TextSegment


class CSVParser(BaseParser):
    """Parser for CSV and TSV files."""
    
    def __init__(
        self,
        file_path: str,
        delimiter: str = None,
        text_columns: List[int] = None,
        header_row: bool = True,
        **kwargs
    ):
        """
        Initialize CSV parser.
        
        Args:
            file_path: Path to CSV file
            delimiter: Column delimiter (auto-detect if None)
            text_columns: Column indices to translate (auto-detect if None)
            header_row: Whether first row is header
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.delimiter = delimiter
        self.text_columns = text_columns
        self.header_row = header_row
        self.original_rows = []
        self.detected_columns = []
    
    def _detect_delimiter(self) -> str:
        """Detect CSV delimiter automatically."""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            first_line = f.readline()
            
            # Count potential delimiters
            delimiters = [',', '\t', ';', '|']
            counts = {d: first_line.count(d) for d in delimiters}
            
            # Return delimiter with highest count
            return max(counts, key=counts.get) if max(counts.values()) > 0 else ','
    
    def _detect_text_columns(self, sample_rows: List[List[str]]) -> List[int]:
        """
        Detect which columns contain translatable text.
        
        Strategy: Columns with longer text and more varied characters
        are likely to be translatable text.
        """
        if not sample_rows:
            return []
        
        num_cols = len(sample_rows[0])
        column_scores = []
        
        for col_idx in range(num_cols):
            texts = [row[col_idx] for row in sample_rows if len(row) > col_idx]
            
            if not texts:
                column_scores.append((col_idx, 0))
                continue
            
            # Calculate score based on:
            # - Average text length
            # - Character variety
            # - Non-numeric content
            total_len = sum(len(t) for t in texts)
            avg_len = total_len / len(texts)
            
            # Check if mostly numeric
            numeric_count = sum(1 for t in texts if t.strip().isdigit())
            numeric_ratio = numeric_count / len(texts)
            
            # Score: higher for longer text, lower for numeric
            score = avg_len * (1 - numeric_ratio)
            
            column_scores.append((col_idx, score))
        
        # Select columns with score above threshold
        # At least include columns with avg length > 5 and < 50% numeric
        text_cols = [
            idx for idx, score in column_scores
            if score > 3
        ]
        
        return text_cols if text_cols else list(range(num_cols))
    
    def parse(self) -> List[TextSegment]:
        """Parse CSV and extract text from specified columns."""
        
        # Detect delimiter if not specified
        if self.delimiter is None:
            self.delimiter = self._detect_delimiter()
        
        # Read all rows
        with open(self.file_path, 'r', encoding=self.encoding, newline='') as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            self.original_rows = list(reader)
        
        if not self.original_rows:
            return []
        
        # Detect text columns if not specified
        if self.text_columns is None:
            sample_rows = self.original_rows[1:] if self.header_row else self.original_rows
            self.detected_columns = self._detect_text_columns(sample_rows[:100])
        else:
            self.detected_columns = self.text_columns
        
        # Extract text segments
        segments = []
        start_row = 1 if self.header_row else 0
        
        for row_idx in range(start_row, len(self.original_rows)):
            row = self.original_rows[row_idx]
            
            for col_idx in self.detected_columns:
                if col_idx < len(row):
                    text = row[col_idx]
                    
                    if not self.should_skip_text(text):
                        segments.append(TextSegment(
                            text=text,
                            location=f"row[{row_idx}].col[{col_idx}]",
                            metadata={
                                'row': row_idx,
                                'column': col_idx,
                                'header': self.original_rows[0][col_idx] if self.header_row and len(self.original_rows[0]) > col_idx else None
                            }
                        ))
        
        return segments
    
    def reconstruct(self, translated_segments: List[Tuple[str, str]]) -> List[List[str]]:
        """
        Reconstruct CSV with translations.
        
        Args:
            translated_segments: List of (original, translated) tuples
        """
        if not self.original_rows:
            raise ValueError("No original data. Call parse() first.")
        
        import copy
        result = copy.deepcopy(self.original_rows)
        
        # Create translation mapping
        translation_map = {orig: trans for orig, trans in translated_segments}
        
        # Apply translations
        start_row = 1 if self.header_row else 0
        
        for row_idx in range(start_row, len(result)):
            for col_idx in self.detected_columns:
                if col_idx < len(result[row_idx]):
                    original_text = result[row_idx][col_idx]
                    if original_text in translation_map:
                        result[row_idx][col_idx] = translation_map[original_text]
        
        return result
    
    def save(self, data: List[List[str]], output_path: str) -> None:
        """Save data to CSV file."""
        import os
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=self.delimiter)
            writer.writerows(data)
