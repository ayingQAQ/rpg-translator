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
import chardet # type: ignore


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
        for i, item in enumerate(data):
            if i >= 5:
                break
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


def _extract_rpgm_commands(cmd_list: List[Dict[str, Any]], prefix: str, text_entries: Dict[str, str]):
    """Helper to extract RPG Maker event commands."""
    cmd_idx = 0
    while cmd_idx < len(cmd_list):
        command = cmd_list[cmd_idx]
        if not command:
            cmd_idx += 1
            continue
        
        code = command.get('code')
        
        if code == 401:
            # Text data - merge consecutive 401s
            text_lines = []
            start_cmd_idx = cmd_idx
            
            while cmd_idx < len(cmd_list):
                cmd = cmd_list[cmd_idx] # type: ignore
                if cmd and cmd.get('code') == 401:
                    params = cmd.get('parameters', [])
                    if params and len(params) > 0:
                        text_lines.append(str(params[0]))
                    else:
                        text_lines.append("")
                    cmd_idx += 1
                else:
                    break
            
            if text_lines:
                key = f"{prefix}_cmd401_{start_cmd_idx}"
                text_entries[key] = "\n".join(text_lines)
            
            continue # already incremented cmd_idx
            
        elif code == 102:
            # Show Choices
            params = command.get('parameters', [])
            if params and len(params) > 0 and isinstance(params[0], list):
                for choice_idx, choice_text in enumerate(params[0]):
                    key = f"{prefix}_cmd102_{cmd_idx}_choice_{choice_idx}"
                    text_entries[key] = str(choice_text)
                    
        elif code == 402:
            # When [Choice]
            params = command.get('parameters', [])
            if params and len(params) > 1:
                key = f"{prefix}_cmd402_{cmd_idx}_when_{params[0]}"
                text_entries[key] = str(params[1])
                
        cmd_idx += 1

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
                # Process map events
                events = content.get('events', [])
                for event_idx, event in enumerate(events):
                    if event and isinstance(event, dict):
                        for page_idx, page in enumerate(event.get('pages', [])):
                            if isinstance(page, dict) and 'list' in page and isinstance(page['list'], list):
                                prefix = f"events_{event_idx}_pages_{page_idx}_list"
                                _extract_rpgm_commands(page['list'], prefix, text_entries)
                                
            elif isinstance(content, list):
                # Process database files - content is a list
                for idx, entry in enumerate(content):
                    if isinstance(entry, dict):
                        # Extract common text fields
                        for field in ['name', 'description', 'message1', 'message2', 'message3', 'message4', 'note', 'profile']:
                            if field in entry and entry[field] and isinstance(entry[field], str):
                                text_entries[f"{idx}_{field}"] = entry[field]
                        
                        # Extract commands if present (CommonEvents.json, Troops.json)
                        if 'list' in entry and isinstance(entry['list'], list):
                            prefix = f"{idx}_list"
                            _extract_rpgm_commands(entry['list'], prefix, text_entries)
                        elif 'pages' in entry and isinstance(entry['pages'], list):
                            for page_idx, page in enumerate(entry['pages']):
                                if isinstance(page, dict) and 'list' in page and isinstance(page['list'], list):
                                    prefix = f"{idx}_pages_{page_idx}_list"
                                    _extract_rpgm_commands(page['list'], prefix, text_entries)
            
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
                for row_idx, row in enumerate(content[1:], 1): # type: ignore
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
    for i in range(len(parts) - 1):
        part = parts[i]
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

def _apply_rpgm_command_translation(data: Any, path: str, translated_value: str):
    """Apply translation specifically to RPG Maker command blocks."""
    parts = path.split('_')
    current = data
    
    # Navigate to the 'list' array
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.startswith('cmd'):
            break
            
        if part.isdigit():
            idx = int(part)
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return # Invalid path
        else:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return # Invalid path
        i += 1
        
    if not isinstance(current, list):
        return
        
    commands = current
    cmd_type = parts[i] # e.g. "cmd401"
    
    if cmd_type == 'cmd401':
        start_idx = int(parts[i+1])
        if start_idx >= len(commands): return
        
        # We need to replace the 401 commands starting at start_idx with translated_value
        translated_lines = translated_value.split('\n')
        
        # Find how many 401s there are currently
        old_401_count = 0
        idx = start_idx
        while idx < len(commands):
            cmd = commands[idx]
            if cmd and cmd.get('code') == 401:
                old_401_count += 1
                idx += 1
            else:
                break
                
        new_401_count = len(translated_lines)
        
        # Modify existing 401s
        for j in range(min(old_401_count, new_401_count)):
            commands[start_idx + j]['parameters'][0] = translated_lines[j]
            
        if new_401_count > old_401_count:
            # Insert additional 401s
            for j in range(old_401_count, new_401_count):
                new_cmd = {'code': 401, 'indent': commands[start_idx]['indent'], 'parameters': [translated_lines[j]]}
                commands.insert(start_idx + j, new_cmd)
        elif new_401_count < old_401_count:
            # Delete excess 401s
            for _ in range(old_401_count - new_401_count):
                commands.pop(start_idx + new_401_count)
                
    elif cmd_type == 'cmd102':
        cmd_idx = int(parts[i+1])
        if len(parts) > i+3:
            choice_idx = int(parts[i+3])
            if cmd_idx < len(commands):
                cmd = commands[cmd_idx]
                if cmd and cmd.get('code') == 102:
                    params = cmd.get('parameters', [])
                    if params and len(params) > 0 and isinstance(params[0], list) and choice_idx < len(params[0]):
                        params[0][choice_idx] = translated_value
                        
    elif cmd_type == 'cmd402':
        cmd_idx = int(parts[i+1])
        if cmd_idx < len(commands):
            cmd = commands[cmd_idx]
            if cmd and cmd.get('code') == 402:
                params = cmd.get('parameters', [])
                if params and len(params) > 1:
                    params[1] = translated_value


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
    # Group RPG Maker command updates to process them out of array shifting order
    rpgm_command_updates = []
    
    for key, translated_value in translated_data.items():
        if "cmd401_" in key or "cmd102_" in key or "cmd402_" in key:
            rpgm_command_updates.append((key, translated_value))
        elif '_' in key and any(part.isdigit() for part in key.split('_')):
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
                original_data[key] = translated_value # type: ignore
                
    # Sort RPGM updates by command index descending to avoid shifting issues when inserting/deleting items
    def get_cmd_idx(path):
        parts = path.split('_')
        for i, part in enumerate(parts):
            if part.startswith('cmd'):
                return int(parts[i+1])
        return 0

    rpgm_command_updates.sort(key=lambda x: get_cmd_idx(x[0]), reverse=True)
    
    for key, translated_value in rpgm_command_updates:
        _apply_rpgm_command_translation(original_data, key, translated_value)
    
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
