"""
Game Text Extractors
===================
Extract translatable text from various RPG game engines.
"""

import os
import sys
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import xml.etree.ElementTree as ET

# Add support for additional encodings
import chardet


def detect_file_encoding(file_path: Path) -> str:
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as f:
        raw_data = f.read(100000)  # Read first 100KB
        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'
        
        # Ensure we have a valid encoding
        try:
            'test'.encode(encoding)
        except (LookupError, ValueError):
            encoding = 'utf-8'
        
        return encoding


def detect_game_engine(game_path: Path) -> Optional[Dict[str, Any]]:
    """
    Detect game engine type from directory structure.
    
    Args:
        game_path: Path to game directory
    
    Returns:
        Dictionary with engine info or None if unknown
    """
    if not game_path.is_dir():
        return None
    
    # Check for RPG Maker MV/MZ
    if (game_path / "www" / "data").exists() or (game_path / "data").exists():
        # Check for RPG Maker specific files
        data_dir = game_path / "www" / "data" if (game_path / "www").exists() else game_path / "data"
        
        if (data_dir / "Actors.json").exists() or (data_dir / "Map001.json").exists():
            return {
                'engine': 'rpgmv',
                'version': 'mv',
                'data_dir': data_dir,
                'text_patterns': ['name', 'message', 'description', 'note', 'terms']
            }
    
    # Check for RPG Maker VX Ace
    if (game_path / "Game.rvproj2").exists() or (game_path / "Data" / "Actors.rvdata2").exists():
        return {
            'engine': 'rpgvxace',
            'version': 'vxace',
            'data_dir': game_path / "Data" if (game_path / "Data").exists() else game_path,
            'text_patterns': ['name', 'description', 'message', 'note']
        }
    
    # Check for Wolf RPG Editor
    wolf_files = list(game_path.glob("*.wolf")) + list(game_path.glob("Data.wolf"))
    if wolf_files or (game_path / "Game.wolf").exists():
        return {
            'engine': 'wolf',
            'version': 'wolf',
            'data_dir': game_path,
            'text_patterns': ['name', 'message', 'description']
        }
    
    # Check for Unity games (common patterns)
    if (game_path / "*.assets").exists() or (game_path / "Managed").exists():
        return {
            'engine': 'unity',
            'version': 'unity',
            'data_dir': game_path,
            'text_patterns': ['text', 'message', 'name', 'description']
        }
    
    # Check for Ren'Py
    if (game_path / "game").exists() and (game_path / "renpy").exists():
        return {
            'engine': 'renpy',
            'version': 'renpy',
            'data_dir': game_path / "game",
            'text_patterns': ['text', 'dialogue', 'menu', 'prompt']
        }
    
    # Check for general text files
    json_files = list(game_path.glob("**/*.json"))
    csv_files = list(game_path.glob("**/*.csv"))
    txt_files = list(game_path.glob("**/*.txt"))
    
    if json_files or csv_files or txt_files:
        return {
            'engine': 'generic',
            'version': 'generic',
            'data_dir': game_path,
            'text_patterns': ['text', 'message', 'dialogue', 'name', 'description', 'note', 'terms']
        }
    
    return None


def extract_rpgmv_text(data_dir: Path, engine_info: Dict) -> List[Dict[str, Any]]:
    """Extract text from RPG Maker MV/MZ game."""
    extracted_files = []
    
    # Define files to extract from
    extract_files = [
        'Actors.json', 'Classes.json', 'Skills.json', 'Items.json',
        'Weapons.json', 'Armors.json', 'Enemies.json', 'Troops.json',
        'States.json', 'System.json', 'MapInfos.json'
    ]
    
    for file_name in extract_files:
        file_path = data_dir / file_name
        if file_path.exists():
            try:
                encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=encoding) as f:
                    data = json.load(f)
                
                if data:
                    extracted_files.append({
                        'path': file_path,
                        'type': 'Data File',
                        'engine': 'rpgmv',
                        'content': None
                    })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    # Extract map files
    map_files = list(data_dir.glob("Map*.json"))
    for map_file in map_files:
        try:
            encoding = detect_file_encoding(map_file)
            with open(map_file, 'r', encoding=encoding) as f:
                map_data = json.load(f)
            
            if map_data and 'events' in map_data:
                extracted_files.append({
                    'path': map_file,
                    'type': 'Map',
                    'engine': 'rpgmv',
                    'content': None
                })
        except Exception as e:
            print(f"Error reading map {map_file}: {e}")
    
    return extracted_files


def extract_generic_text(game_path: Path, engine_info: Dict) -> List[Dict[str, Any]]:
    """Extract text from generic JSON/CSV/TXT files."""
    extracted_files = []
    
    # Supported extensions
    extensions = ['*.json', '*.csv', '*.txt', '*.xml', '*.yaml', '*.yml']
    
    for ext in extensions:
        for file_path in game_path.rglob(ext):
            try:
                file_size = file_path.stat().st_size
                
                # Skip files that are too large (> 10MB)
                if file_size > 10 * 1024 * 1024:
                    continue
                
                # Skip files in obvious non-text directories
                skip_dirs = ['img', 'images', 'graphics', 'audio', 'sound', 'music', 'movies', 'video', 'movies']
                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                    continue
                
                if ext == '*.json':
                    encoding = detect_file_encoding(file_path)
                    with open(file_path, 'r', encoding=encoding) as f:
                        data = json.load(f)
                    
                    # Check if it's likely a text data file
                    if is_text_data_file(data):
                        extracted_files.append({
                            'path': file_path,
                            'type': 'JSON Data',
                            'engine': 'generic',
                            'content': None
                        })
                
                elif ext == '*.csv':
                    import csv
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        if len(rows) > 1:  # Has data
                            extracted_files.append({
                                'path': file_path,
                                'type': 'CSV Data',
                                'engine': 'generic',
                                'content': None
                            })
                
                elif ext == '*.txt':
                    encoding = detect_file_encoding(file_path)
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read(100) # Only peek to see if not empty
                        if len(content.strip()) > 0:
                            extracted_files.append({
                                'path': file_path,
                                'type': 'Text File',
                                'engine': 'generic',
                                'content': None
                            })
            
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
    
    return extracted_files


def is_text_data_file(data: Any) -> bool:
    """
    Check if JSON data is likely a text data file.
    """
    if not isinstance(data, (dict, list)):
        return False
    
    # Check for common text patterns
    text_patterns = ['name', 'text', 'message', 'dialogue', 'description', 'note', 'terms', 'title']
    
    if isinstance(data, dict):
        # Check keys
        for key in data.keys():
            if isinstance(key, str) and any(pattern in key.lower() for pattern in text_patterns):
                return True
        
        # Check values
        for value in data.values():
            if isinstance(value, str) and len(value) > 0 and not value.startswith('data:'):
                return True
    
    elif isinstance(data, list) and len(data) > 0:
        # Check first few items
        for item in data[:5]:
            if isinstance(item, dict):
                for key in item.keys():
                    if isinstance(key, str) and any(pattern in key.lower() for pattern in text_patterns):
                        return True
    
    return False


def extract_wolf_text(game_path: Path, engine_info: Dict) -> List[Dict[str, Any]]:
    """Extract text from Wolf RPG Editor game."""
    extracted_files = []
    
    # Wolf RPG typically uses .wolf archive files or extracted data files
    # Look for CommonEvents.dat, Map*.dat, etc.
    data_files = [
        'CommonEvents.dat',
        'MapInfos.dat',
        'Troops.dat',
        'Enemies.dat',
        'Actors.dat',
        'Classes.dat',
        'Skills.dat',
        'Items.dat',
        'Weapons.dat',
        'Armors.dat'
    ]
    
    data_dir = engine_info.get('data_dir', game_path)
    
    for file_name in data_files:
        file_path = data_dir / file_name
        if file_path.exists():
            try:
                encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    content = f.read(100) # Only peek
                    if content.strip():
                        # Wolf files are often binary or custom format
                        # Try to extract text strings
                        extracted_files.append({
                            'path': file_path,
                            'type': 'Wolf Data',
                            'engine': 'wolf',
                            'content': None
                        })
            except Exception as e:
                print(f"Error reading Wolf file {file_path}: {e}")
    
    # Also check for extracted map files (Map####.dat)
    map_files = list(data_dir.glob("Map*.dat"))
    for map_file in map_files:
        try:
            encoding = detect_file_encoding(map_file)
            with open(map_file, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read(100)
                if content.strip():
                    extracted_files.append({
                        'path': map_file,
                        'type': 'Wolf Map',
                        'engine': 'wolf',
                        'content': None
                    })
        except Exception as e:
            print(f"Error reading Wolf map {map_file}: {e}")
    
    return extracted_files


def extract_renpy_text(game_path: Path, engine_info: Dict) -> List[Dict[str, Any]]:
    """Extract text from Ren'Py game."""
    extracted_files = []
    
    # Ren'Py script files are in the 'game' directory with .rpy extension
    game_dir = engine_info.get('data_dir', game_path)
    
    if not game_dir.exists():
        return extracted_files
    
    # Find all .rpy files
    rpy_files = list(game_dir.rglob("*.rpy"))
    
    for rpy_file in rpy_files:
        try:
            encoding = detect_file_encoding(rpy_file)
            with open(rpy_file, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read(100)
                
                if content.strip():
                    extracted_files.append({
                        'path': rpy_file,
                        'type': 'Ren\'Py Script',
                        'engine': 'renpy',
                        'content': None
                    })
        except Exception as e:
            print(f"Error reading Ren'Py file {rpy_file}: {e}")
    
    # Also check for common Ren'Py data files
    data_files = ['script.rpy', 'screens.rpy', 'options.rpy', 'gui.rpy']
    for data_file in data_files:
        file_path = game_dir / data_file
        if file_path.exists():
            try:
                encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read(100)
                    if content.strip():
                        extracted_files.append({
                            'path': file_path,
                            'type': 'Ren\'Py Data',
                            'engine': 'renpy',
                            'content': None
                        })
            except Exception as e:
                print(f"Error reading Ren'Py data file {file_path}: {e}")
    
    return extracted_files


def extract_game_text(game_path: Path, engine_info: Dict) -> List[Dict[str, Any]]:
    """
    Extract translatable text from game files.
    
    Args:
        game_path: Path to game directory
        engine_info: Engine information from detect_game_engine
    
    Returns:
        List of extracted files with content
    """
    engine = engine_info['engine']
    data_dir = engine_info.get('data_dir', game_path)
    
    if engine == 'rpgmv':
        return extract_rpgmv_text(data_dir, engine_info)
    elif engine == 'wolf':
        return extract_wolf_text(data_dir, engine_info)
    elif engine == 'renpy':
        return extract_renpy_text(data_dir, engine_info)
    else:
        # For unity, generic, and other engines, use generic extraction
        return extract_generic_text(data_dir, engine_info)


def convert_to_translation_format(extracted_files: List[Dict]) -> Dict[Path, Dict]:
    """
    Convert extracted files to translation format.
    
    Args:
        extracted_files: List of extracted file info
    
    Returns:
        Dictionary mapping file paths to translation-ready data
    """
    translation_files = {}
    
    for file_info in extracted_files:
        file_path = file_info['path']
        content = file_info['content']
        
        if file_info['engine'] == 'rpgmv':
            # Process RPG Maker MV data
            text_entries = {}
            
            if 'Map' in file_info['type'] and isinstance(content, dict):
                # Process map events - content is a dict with 'events' key
                events = content.get('events', [])
                for event_idx, event in enumerate(events):
                    if event:
                        for page_idx, page in enumerate(event.get('pages', [])):
                            for cmd_idx, command in enumerate(page.get('list', [])):
                                if command and command.get('code') in [101, 401]:  # Show Text
                                    parameters = command.get('parameters', [])
                                    if parameters and len(parameters) > 0:
                                        key = f"event_{event_idx}_page_{page_idx}_cmd_{cmd_idx}"
                                        text_entries[key] = parameters[0] if isinstance(parameters[0], str) else str(parameters[0])
            elif isinstance(content, list):
                # Process database files - content is a list
                for idx, entry in enumerate(content):
                    if isinstance(entry, dict):
                        # Extract common text fields
                        if 'name' in entry and entry['name']:
                            text_entries[f"{idx}_name"] = entry['name']
                        if 'description' in entry and entry['description']:
                            text_entries[f"{idx}_description"] = entry['description']
                        if 'message1' in entry and entry['message1']:
                            text_entries[f"{idx}_message1"] = entry['message1']
                        if 'message2' in entry and entry['message2']:
                            text_entries[f"{idx}_message2"] = entry['message2']
                        if 'note' in entry and entry['note']:
                            text_entries[f"{idx}_note"] = entry['note']
            
            if text_entries:
                translation_files[file_path] = text_entries
        
        elif isinstance(content, dict):
            # Simple key-value JSON
            text_entries = {}
            for key, value in content.items():
                if isinstance(value, str) and len(value.strip()) > 0:
                    text_entries[key] = value
            
            if text_entries:
                translation_files[file_path] = text_entries
        
        elif isinstance(content, list) and len(content) > 0:
            # CSV or list data
            if all(isinstance(row, list) for row in content):
                # CSV format
                text_entries = {}
                headers = content[0] if content else []
                for row_idx, row in enumerate(content[1:], 1):
                    for col_idx, cell in enumerate(row):
                        if isinstance(cell, str) and len(cell.strip()) > 0:
                            key = f"row_{row_idx}_col_{col_idx}"
                            text_entries[key] = cell
                
                if text_entries:
                    translation_files[file_path] = text_entries
            elif all(isinstance(item, dict) for item in content):
                # List of objects
                text_entries = {}
                for item_idx, item in enumerate(content):
                    for key, value in item.items():
                        if isinstance(value, str) and len(value.strip()) > 0:
                            entry_key = f"{item_idx}_{key}"
                            text_entries[entry_key] = value
                
                if text_entries:
                    translation_files[file_path] = text_entries
    
    return translation_files


def _apply_nested_translation(data: Any, path: str, translated_value: str):
    """
    Apply translation to nested path like "events_1_pages_0_list_1_parameters_0".
    
    Args:
        data: The data structure to modify
        path: Path string with underscores (e.g., "events_1_pages_0_list_1_parameters_0")
        translated_value: The translated text to apply
    """
    parts = path.split('_')
    current = data
    
    # Navigate to the parent of the target
    for part in parts[:-1]:
        if part.isdigit():
            idx = int(part)
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return  # Path invalid
        else:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return  # Path invalid
    
    # Apply translation to final element
    last_part = parts[-1]
    if last_part.isdigit():
        idx = int(last_part)
        if isinstance(current, list) and idx < len(current):
            current[idx] = translated_value
    else:
        if isinstance(current, dict):
            current[last_part] = translated_value


def save_translated_file(original_path: Path, translated_data: Dict, output_path: Optional[Path] = None):
    """
    Save translated data back to file format.
    
    Args:
        original_path: Original file path
        translated_data: Dictionary of translated text
        output_path: Output file path (optional, defaults to overwrite original)
    """
    if output_path is None:
        output_path = original_path
    
    # Detect encoding
    encoding = detect_file_encoding(original_path)
    
    # Load original file
    with open(original_path, 'r', encoding=encoding) as f:
        original_data = json.load(f)
    
    # Apply translations
    for key, translated_value in translated_data.items():
        if '_' in key and any(part.isdigit() for part in key.split('_')):
            # Complex nested path (e.g., "events_1_pages_0_list_1_parameters_0")
            _apply_nested_translation(original_data, key, translated_value)
        elif isinstance(original_data, list):
            # Simple array format (e.g., "1_name")
            for idx, entry in enumerate(original_data):
                if isinstance(entry, dict):
                    if key.startswith(f"{idx}_"):
                        field = key.replace(f"{idx}_", "")
                        if field in entry:
                            entry[field] = translated_value
        elif isinstance(original_data, dict):
            # Simple key-value
            if key in original_data:
                original_data[key] = translated_value
    
    # Save with backup
    backup_path = original_path.with_suffix(f".backup_{int(time.time())}.json")
    original_path.rename(backup_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(original_data, f, ensure_ascii=False, indent=2)
    
    return backup_path


if __name__ == "__main__":
    # Test functions
    test_path = Path(".")
    engine = detect_game_engine(test_path)
    if engine:
        print(f"Detected engine: {engine}")
        extracted = extract_game_text(test_path, engine)
        print(f"Extracted {len(extracted)} files")
    else:
        print("No game engine detected")
