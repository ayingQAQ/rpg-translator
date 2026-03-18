#!/usr/bin/env python3
"""
Binary File Analyzer - Help reverse engineer binary formats

This tool helps analyze unknown binary file formats used by games.
"""

import argparse
import os
import sys
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rpg_translator.parsers.binary_parser import BinaryParser


def analyze_binary(file_path: str, sample_texts: List[str] = None):
    """Analyze binary file format."""
    
    print(f"\n{'='*60}")
    print(f"Binary File Analysis: {file_path}")
    print(f"{'='*60}\n")
    
    # Basic file info
    file_size = os.path.getsize(file_path)
    print(f"File size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
    
    # Read file
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Analyze with BinaryParser
    results = BinaryParser.analyze_format(file_path, sample_texts)
    
    # Show potential encodings
    print(f"\n[Detected Encodings]")
    if results['encodings']:
        for enc in results['encodings']:
            print(f"\n  Encoding: {enc['encoding']}")
            print(f"  Text sequences found: {enc['sequences_found']}")
            print(f"  Sample texts:")
            for sample in enc['sample'][:3]:
                print(f"    - {sample[:60]}{'...' if len(sample) > 60 else ''}")
    else:
        print("  No readable text found")
    
    # Show found offsets
    if results['potential_offsets']:
        print(f"\n[Found Text Offsets]")
        for offset_info in results['potential_offsets']:
            print(f"\n  Text: {offset_info['text']}")
            print(f"  Offset: 0x{offset_info['offset']:08X} ({offset_info['offset']})")
            print(f"  Encoding: {offset_info['encoding']}")
    
    # Analyze file structure
    print(f"\n[File Structure Analysis]")
    
    # Check for common headers
    header = data[:16]
    print(f"\n  Header (first 16 bytes):")
    print(f"  Hex: {header.hex()}")
    
    # Try to identify file type
    if data[:4] == b'PK\x03\x04':
        print("  Type: ZIP archive")
    elif data[:4] == b'Rar!':
        print("  Type: RAR archive")
    elif data[:2] == b'MZ':
        print("  Type: Windows executable")
    elif data[:4] == b'\x7fELF':
        print("  Type: Linux executable")
    else:
        print("  Type: Unknown/custom format")
    
    # Look for patterns
    print(f"\n[Pattern Analysis]")
    
    # Find repeated byte sequences
    print("\n  Looking for table structures...")
    
    # Check for potential pointer tables
    # (sequences of 4-byte or 8-byte aligned values)
    potential_pointers = []
    for i in range(0, min(1000, len(data)-4), 4):
        # Read as potential offset
        import struct
        try:
            value = struct.unpack('<I', data[i:i+4])[0]
            if 0 < value < file_size:
                potential_pointers.append((i, value))
        except:
            pass
    
    if potential_pointers:
        print(f"\n  Potential pointer table at offset 0x{potential_pointers[0][0]:08X}")
        print(f"  Found {len(potential_pointers)} potential pointers")
        print(f"  First few entries:")
        for offset, value in potential_pointers[:5]:
            print(f"    0x{offset:08X} -> 0x{value:08X}")
    
    # Generate format specification template
    print(f"\n[Generated Format Spec Template]")
    print("""
  You can use this template in your configuration:

  format_spec:
    text_table_offset: 0x????     # Update this
    text_table_count: ???         # Number of text entries
    text_entry_size: ???          # Size of each entry
    text_encoding: 'utf-8'        # Or detected encoding
    null_terminated: true
    """)
    
    print(f"\n{'='*60}\n")


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description='Analyze binary file format for translation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a binary file
  python analyze.py game.dat

  # Analyze with known text samples
  python analyze.py game.dat --texts "Hello" "World" "Game Over"

  # The tool will search for these texts and report their offsets
        """
    )
    
    parser.add_argument(
        'file',
        help='Binary file to analyze'
    )
    
    parser.add_argument(
        '--texts',
        nargs='+',
        help='Known text strings to search for in the file'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return 1
    
    analyze_binary(args.file, args.texts)
    return 0


if __name__ == '__main__':
    sys.exit(main())
