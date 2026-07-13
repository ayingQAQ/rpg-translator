"""
JSON Parser - Parse and reconstruct JSON/JSON5 files
"""

import json
import re
import hashlib
from typing import Iterable, List, Tuple, Any, Dict, Optional
from .base_parser import BaseParser, TextSegment
try:
    from ..core.text_candidates import evaluate_candidate
except ImportError:
    from core.text_candidates import evaluate_candidate


class JSONParser(BaseParser):
    """Parser for JSON and JSON5 files."""
    
    RPG_TEXT_FIELDS = {
        'name', 'nickname', 'description', 'message1', 'message2', 'message3',
        'message4', 'profile', 'displayName', 'gameTitle', 'currencyUnit',
    }
    RPG_COMMAND_TEXT_INDEXES = {
        101: (4,),   # Show Text speaker name (MZ style)
        401: (0,),   # Show Text
        402: (1,),   # When Choice
        405: (0,),   # Scroll Text
        320: (1,),   # Change Actor Name
        324: (1,),   # Change Actor Nickname
        325: (1,),   # Change Actor Profile
    }
    RPG_COMMAND_NAMES = {
        101: 'Show Text speaker', 102: 'Show Choices', 401: 'Show Text',
        402: 'When Choice', 405: 'Scroll Text', 320: 'Change Actor Name',
        324: 'Change Actor Nickname', 325: 'Change Actor Profile',
    }
    RPG_DEFAULT_COMMAND_CODES = {101, 102, 401, 405, 320, 324, 325}
    RPG_RESOURCE_CONTAINERS = {
        'sounds', 'titleBgm', 'battleBgm', 'victoryMe', 'defeatMe',
        'boat', 'ship', 'airship',
    }

    def __init__(
        self,
        file_path: str,
        preserve_keys: bool = False,
        rpg_safe: bool = False,
        rpg_command_codes: Optional[Iterable[int]] = None,
        include_rpg_notes: bool = False,
        **kwargs,
    ):
        """
        Initialize JSON parser.
        
        Args:
            file_path: Path to JSON file
            preserve_keys: Whether to preserve JSON keys (not translate them)
            **kwargs: Additional options
        """
        super().__init__(file_path, **kwargs)
        self.preserve_keys = preserve_keys
        self.rpg_safe = rpg_safe
        command_codes = self.RPG_DEFAULT_COMMAND_CODES if rpg_command_codes is None else rpg_command_codes
        self.rpg_command_codes = {int(code) for code in command_codes}
        self.include_rpg_notes = include_rpg_notes
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

    def _append_segment(self, text: str, location: str, metadata: Dict, segments: List[TextSegment]) -> None:
        if not self.should_skip_text(text):
            metadata = dict(metadata)
            if self.rpg_safe:
                evaluation = evaluate_candidate(
                    text,
                    source_type=metadata.get('source_type', 'database'),
                    field=metadata.get('field'),
                )
                if evaluation.decision == 'reject':
                    return
                metadata.update({
                    'decision': evaluation.decision,
                    'score': evaluation.score,
                    'analysis_text': evaluation.analysis_text,
                })
            metadata['source_hash'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
            metadata['path'] = location
            segments.append(TextSegment(
                text=text,
                location=location,
                context=self._build_context(location, metadata),
                metadata=metadata,
            ))

    def _build_context(self, location: str, metadata: Dict) -> str:
        """Produce a stable human-readable context without changing the source."""
        command_code = metadata.get('code')
        if command_code is not None:
            command_name = self.RPG_COMMAND_NAMES.get(command_code, f'Event command {command_code}')
            return f'RPG Maker {command_name} · {location}'
        field = metadata.get('field')
        if field:
            return f'RPG Maker field {field} · {location}'
        return f'JSON value · {location}'

    def _is_rpg_field_translatable(self, key: str, parent_path: str) -> bool:
        """Reject known metadata/resource locations in RPG Maker database JSON."""
        if key == 'note':
            return self.include_rpg_notes
        if key not in self.RPG_TEXT_FIELDS:
            return False
        if key == 'name' and any(container in parent_path for container in self.RPG_RESOURCE_CONTAINERS):
            return False
        return True

    def _extract_rpg_command_parameters(
        self, parameters: List[Any], code: Any, path: str, segments: List[TextSegment]
    ) -> None:
        """Extract only player-facing RPG Maker command parameters."""
        if code not in self.rpg_command_codes:
            return

        if code == 102 and parameters and isinstance(parameters[0], list):
            for index, text in enumerate(parameters[0]):
                if isinstance(text, str):
                    self._append_segment(
                        text,
                        f"{path}[0][{index}]",
                        {'type': 'rpg_command', 'source_type': 'event', 'code': code, 'field': 'choice'},
                        segments,
                    )
            return

        for index in self.RPG_COMMAND_TEXT_INDEXES.get(code, ()):
            if index < len(parameters) and isinstance(parameters[index], str):
                self._append_segment(
                    parameters[index],
                    f"{path}[{index}]",
                    {'type': 'rpg_command', 'source_type': 'event', 'code': code, 'field': 'message'},
                    segments,
                )

    def _extract_rpg_command_list(
        self, commands: List[Any], path: str, segments: List[TextSegment]
    ) -> None:
        """Extract event commands, merging consecutive 401 lines into dialogue units."""
        index = 0
        while index < len(commands):
            command = commands[index]
            if not isinstance(command, dict):
                index += 1
                continue

            code = command.get('code')
            if code == 401 and code in self.rpg_command_codes:
                start_index = index
                lines: List[str] = []
                locations: List[str] = []
                while index < len(commands):
                    line_command = commands[index]
                    if not isinstance(line_command, dict) or line_command.get('code') != 401:
                        break
                    parameters = line_command.get('parameters', [])
                    if isinstance(parameters, list) and parameters and isinstance(parameters[0], str):
                        lines.append(parameters[0])
                        locations.append(f"{path}[{index}].parameters[0]")
                    index += 1

                if lines:
                    self._append_segment(
                        "\n".join(lines),
                        locations[0],
                        {
                            'type': 'rpg_dialogue_block',
                            'source_type': 'event',
                            'code': 401,
                            'field': 'message',
                            'list_path': path,
                            'start_index': start_index,
                            'locations': locations,
                        },
                        segments,
                    )
                continue

            parameters = command.get('parameters', [])
            if isinstance(parameters, list):
                self._extract_rpg_command_parameters(
                    parameters,
                    code,
                    f"{path}[{index}].parameters",
                    segments,
                )
            index += 1
    
    def _extract_texts(self, data: Any, path: str, segments: List[TextSegment]) -> None:
        """Recursively extract text values from JSON data."""
        
        if isinstance(data, dict):
            command_code = data.get('code') if self.rpg_safe else None
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key

                if self.rpg_safe and key == 'parameters' and isinstance(value, list):
                    self._extract_rpg_command_parameters(value, command_code, new_path, segments)
                elif isinstance(value, str):
                    if not self.rpg_safe or self._is_rpg_field_translatable(key, path):
                        self._append_segment(
                            value,
                            new_path,
                            {
                                'type': 'value',
                                'source_type': 'database' if self.rpg_safe else 'generic',
                                'field': key,
                            },
                            segments,
                        )
                else:
                    self._extract_texts(value, new_path, segments)
        
        elif isinstance(data, list):
            if self.rpg_safe and path.endswith('.list'):
                self._extract_rpg_command_list(data, path, segments)
                return
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                
                if isinstance(item, str):
                    self._append_segment(
                        item,
                        new_path,
                        {
                            'type': 'array_value',
                            'source_type': 'database' if self.rpg_safe else 'generic',
                            'index': i,
                        },
                        segments,
                    )
                else:
                    self._extract_texts(item, new_path, segments)
        
        elif isinstance(data, str):
            self._append_segment(data, path, {'type': 'root_value'}, segments)
    
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
        
        dialogue_blocks = []

        # Apply normal translations using precise path assignment.
        for segment in translated_segments:
            if segment.translated_text:
                if segment.metadata and segment.metadata.get('type') == 'rpg_dialogue_block':
                    dialogue_blocks.append(segment)
                else:
                    self._set_value_by_path(result, segment.location, segment.translated_text)

        # A translation can gain or lose line breaks. Apply blocks in reverse
        # command order so inserted/removed 401 commands do not shift the path
        # of an earlier block in the same event list.
        dialogue_blocks.sort(
            key=lambda segment: (
                str(segment.metadata.get('list_path', '')),
                int(segment.metadata.get('start_index', 0)),
            ),
            reverse=True,
        )
        for segment in dialogue_blocks:
            self._apply_rpg_dialogue_block(result, segment)
        
        return result

    def _get_value_by_path(self, data: Any, path: str) -> Any:
        current = data
        for component in re.findall(r'[^.\[\]]+', path):
            if component.isdigit():
                if not isinstance(current, list) or int(component) >= len(current):
                    return None
                current = current[int(component)]
            else:
                if not isinstance(current, dict) or component not in current:
                    return None
                current = current[component]
        return current

    def _apply_rpg_dialogue_block(self, data: Any, segment: TextSegment) -> None:
        metadata = segment.metadata or {}
        commands = self._get_value_by_path(data, str(metadata.get('list_path', '')))
        start_index = metadata.get('start_index')
        if not isinstance(commands, list) or not isinstance(start_index, int) or start_index >= len(commands):
            return

        translated_lines = segment.translated_text.split('\n')
        old_count = 0
        while start_index + old_count < len(commands):
            command = commands[start_index + old_count]
            if not isinstance(command, dict) or command.get('code') != 401:
                break
            old_count += 1
        if old_count == 0:
            return

        for offset, line in enumerate(translated_lines[:old_count]):
            parameters = commands[start_index + offset].setdefault('parameters', [])
            if not isinstance(parameters, list):
                parameters = []
                commands[start_index + offset]['parameters'] = parameters
            if parameters:
                parameters[0] = line
            else:
                parameters.append(line)

        if len(translated_lines) > old_count:
            import copy

            template = commands[start_index]
            for offset, line in enumerate(translated_lines[old_count:], old_count):
                new_command = copy.deepcopy(template)
                new_command['parameters'] = [line]
                commands.insert(start_index + offset, new_command)
        elif len(translated_lines) < old_count:
            for _ in range(old_count - len(translated_lines)):
                commands.pop(start_index + len(translated_lines))
    
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
