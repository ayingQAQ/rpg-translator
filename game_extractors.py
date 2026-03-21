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

MAX_TEXT_FILE_SIZE = 10 * 1024 * 1024

# Unified file filtering rules shared by extraction and batch scanning.
DEFAULT_SKIP_DIR_NAMES = {
    'img', 'images', 'graphics', 'audio', 'sound', 'music', 'movies', 'video',
    'save', 'saves', 'output', 'outputs', 'translated', 'translations',
    'backup', 'backups', 'log', 'logs', 'tmp', 'temp', 'cache', '__pycache__',
    '.git', 'docs'
}

SYSTEM_SKIP_FILENAMES = {
    'translation_log.json', 'package.json', 'manifest.json',
    'vk_swiftshader_icd.json', 'jsconfig.json'
}

TRANSLATED_SUFFIX_PATTERN = re.compile(
    r'_(?:zh(?:[-_](?:cn|tw|hans|hant))?|translated)$',
    re.IGNORECASE
)

GENERIC_PRIORITY_DIRS = (
    'data', 'www/data', 'game', 'lang', 'langs', 'locale', 'locales',
    'i18n', 'text', 'texts'
)


def should_skip_dir_name(dir_name: str) -> bool:
    """Return True if a directory name is irrelevant for text extraction."""
    normalized = dir_name.strip().lower()
    if not normalized:
        return False
    return normalized in DEFAULT_SKIP_DIR_NAMES or normalized.startswith('.')


def is_irrelevant_text_file(file_path: Path, scan_root: Optional[Path] = None) -> bool:
    """Return True when file should be ignored by extraction/scan."""
    name = file_path.name
    name_lower = name.lower()

    if name.startswith('.'):
        return True
    if name_lower in SYSTEM_SKIP_FILENAMES:
        return True
    if '.backup' in name_lower:
        return True
    if TRANSLATED_SUFFIX_PATTERN.search(file_path.stem.lower()):
        return True

    if scan_root:
        # Only inspect parts relative to the scan root to avoid false positives
        # from absolute temp/system paths (for example ".../Temp/...").
        try:
            rel_parts = file_path.resolve().relative_to(scan_root.resolve()).parts[:-1]
            for part in rel_parts:
                if should_skip_dir_name(part):
                    return True
        except Exception:
            pass
    else:
        for part in file_path.parts[:-1]:
            if should_skip_dir_name(part):
                return True

    return False


def get_generic_scan_roots(game_path: Path) -> List[Path]:
    """Prefer common game data roots, fallback to whole directory."""
    roots: List[Path] = []
    for rel_dir in GENERIC_PRIORITY_DIRS:
        candidate = game_path / rel_dir
        if candidate.is_dir():
            roots.append(candidate)

    return roots if roots else [game_path]


def dedupe_extracted_files(extracted_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """De-duplicate extracted file list by absolute path while preserving order."""
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for file_info in extracted_files:
        path_obj = Path(file_info['path'])
        try:
            key = str(path_obj.resolve()).lower()
        except Exception:
            key = str(path_obj).lower()

        if key in seen:
            continue

        seen.add(key)
        deduped.append(file_info)

    return deduped


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
    unity_data_dirs = [p for p in game_path.glob("*_Data") if p.is_dir()]
    managed_dirs = [p for p in game_path.rglob("Managed") if p.is_dir()]
    if unity_data_dirs or managed_dirs:
        return {
            'engine': 'unity',
            'version': 'unity',
            'data_dir': unity_data_dirs[0] if unity_data_dirs else game_path,
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
    
    # Check for general text files (respect ignore rules)
    for pattern in ("*.json", "*.csv", "*.txt"):
        for file_path in game_path.rglob(pattern):
            if file_path.is_file() and not is_irrelevant_text_file(file_path, game_path):
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

    def _has_translatable_in_map(map_data: Any) -> bool:
        """Fast check to skip map files without translatable text payload."""
        if not isinstance(map_data, dict):
            return False

        # displayName may be shown to player; note is often metadata tags and is excluded.
        for map_field in ('displayName',):
            value = map_data.get(map_field)
            if isinstance(value, str) and value.strip():
                return True

        events = map_data.get('events', [])
        if not isinstance(events, list):
            return False

        for event in events:
            if not isinstance(event, dict):
                continue
            pages = event.get('pages', [])
            if not isinstance(pages, list):
                continue
            for page in pages:
                if not isinstance(page, dict):
                    continue
                cmd_list = page.get('list', [])
                if not isinstance(cmd_list, list):
                    continue
                for command in cmd_list:
                    if not isinstance(command, dict):
                        continue
                    code = command.get('code')
                    params = command.get('parameters', [])
                    if not isinstance(params, list):
                        params = []

                    # 401: Show Text line
                    if code == 401 and params and isinstance(params[0], str) and params[0].strip():
                        return True
                    # 102: Show Choices (parameters[0] is choice list)
                    if code == 102 and params and isinstance(params[0], list):
                        if any(isinstance(choice, str) and choice.strip() for choice in params[0]):
                            return True
                    # 402: When [Choice]
                    if code == 402 and len(params) > 1 and isinstance(params[1], str) and params[1].strip():
                        return True
                    # 405: Scroll Text line
                    if code == 405 and params and isinstance(params[0], str) and params[0].strip():
                        return True
                    # 101: Show Text header (speaker name in params[4] for MZ-style data)
                    if code == 101 and len(params) > 4 and isinstance(params[4], str) and params[4].strip():
                        return True
                    # 320/324/325: change actor name/nickname/profile
                    if code in {320, 324, 325} and len(params) > 1 and isinstance(params[1], str) and params[1].strip():
                        return True

        return False
    
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
            
            if _has_translatable_in_map(map_data):
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
    """Extract text from generic files using prioritized roots and unified filtering."""
    extracted_files: List[Dict[str, Any]] = []
    seen_files: set[str] = set()

    scan_targets = [
        ('*.json', 'JSON Data'),
        ('*.csv', 'CSV Data'),
        ('*.txt', 'Text File'),
        ('*.xml', 'XML Data'),
        ('*.yaml', 'YAML Data'),
        ('*.yml', 'YAML Data'),
    ]

    for scan_root in get_generic_scan_roots(game_path):
        for pattern, file_type in scan_targets:
            for file_path in scan_root.rglob(pattern):
                if not file_path.is_file():
                    continue

                try:
                    cache_key = str(file_path.resolve()).lower()
                except Exception:
                    cache_key = str(file_path).lower()

                if cache_key in seen_files:
                    continue
                seen_files.add(cache_key)

                try:
                    if is_irrelevant_text_file(file_path, game_path):
                        continue

                    file_size = file_path.stat().st_size
                    if file_size > MAX_TEXT_FILE_SIZE:
                        continue

                    if pattern == '*.json':
                        encoding = detect_file_encoding(file_path)
                        with open(file_path, 'r', encoding=encoding) as f:
                            data = json.load(f)
                        if not is_text_data_file(data):
                            continue
                    elif pattern == '*.csv':
                        import csv
                        encoding = detect_file_encoding(file_path)
                        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                            rows = list(csv.reader(f))
                            if len(rows) <= 1:
                                continue
                    else:
                        encoding = detect_file_encoding(file_path)
                        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                            preview = f.read(200)
                            if not preview.strip():
                                continue

                    extracted_files.append({
                        'path': file_path,
                        'type': file_type,
                        'engine': 'generic',
                        'content': None
                    })
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    continue

    return dedupe_extracted_files(extracted_files)


def is_text_data_file(data: Any) -> bool:
    """
    Check if JSON data is likely a text data file.
    """
    if not isinstance(data, (dict, list)):
        return False
    
    # Check for common text patterns
    text_patterns = ['name', 'text', 'message', 'dialogue', 'description', 'note', 'terms', 'title']
    
    if isinstance(data, dict):
        # Check values, but require them to be mapped to a text-like key if the dictionary has many keys, 
        # or require at least one 'text' pattern key to be present in the dict to classify it as a text data file.
        text_key_found = False
        for key in data.keys():
            if isinstance(key, str) and any(pattern in key.lower() for pattern in text_patterns):
                text_key_found = True
                break
                
        if text_key_found:
            return True
            
        # If no semantic key is found, only consider it text if it has a large number of string values
        # meaning it's likely a purely string-value dictionary (like a localization file)
        str_count = sum(1 for v in data.values() if isinstance(v, str) and len(v) > 1 and not v.startswith('data:'))
        if str_count >= max(2, int(len(data) * 0.3)):  # at least 30% of values are strings
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
    
    return dedupe_extracted_files(extracted_files)


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
        # RPGMV/MZ: core data JSON + Map*.json from data directory.
        print("[Extract] RPGMV/MZ target: data/*.json + Map*.json")
        extracted = extract_rpgmv_text(data_dir, engine_info)
    elif engine == 'wolf':
        # Wolf RPG: CommonEvents/Map*.dat and related data files.
        print("[Extract] Wolf target: CommonEvents.dat + Map*.dat + core dat files")
        extracted = extract_wolf_text(data_dir, engine_info)
    elif engine == 'renpy':
        # Ren'Py: script files under game/*.rpy.
        print("[Extract] Ren'Py target: game/**/*.rpy")
        extracted = extract_renpy_text(data_dir, engine_info)
    else:
        # Generic/Unity fallback: text-like structured files with filters.
        print("[Extract] Generic target: json/csv/txt/xml/yaml in priority data roots")
        extracted = extract_generic_text(data_dir, engine_info)

    return dedupe_extracted_files(extracted)


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
