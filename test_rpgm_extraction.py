import os
import sys
from pathlib import Path
import json

# Add current path
sys.path.insert(0, str(Path("e:/clawqwe/翻译脚本/rpg_translator").absolute()))

from game_extractors import _extract_rpgm_commands, convert_to_translation_format, save_translated_file, _apply_rpgm_command_translation # type: ignore

def test_extraction():
    # Simulate a Map event with 101, 102, 401
    commands = [
        {"code": 101, "indent": 0, "parameters": ["Actor1", 0, 0, 2]},
        {"code": 401, "indent": 0, "parameters": ["Hello, this is line 1."]},
        {"code": 401, "indent": 0, "parameters": ["And this is line 2!"]},
        {"code": 102, "indent": 0, "parameters": [["Yes", "No"], 1]},
        {"code": 402, "indent": 0, "parameters": [0, "Yes"]},
        {"code": 401, "indent": 1, "parameters": ["You said yes."]},
        {"code": 0, "indent": 1, "parameters": []},
        {"code": 402, "indent": 0, "parameters": [1, "No"]},
        {"code": 401, "indent": 1, "parameters": ["You said no."]},
        {"code": 0, "indent": 1, "parameters": []},
        {"code": 0, "indent": 0, "parameters": []}
    ]
    
    # Test extraction
    text_entries = {}
    _extract_rpgm_commands(commands, "test", text_entries)
    print("Extracted:")
    for k, v in text_entries.items():
        print(f"  {k}: {repr(v)}")
        
    print("\nSimulating translation...")
    translated_data = {
        "test_cmd401_1": "你好，这是第一行。\n而且这是第二行！\n还有第三行插入！", # 3 lines!
        "test_cmd102_3_choice_0": "行",
        "test_cmd102_3_choice_1": "不行",
        "test_cmd402_4_when_0": "行",
        "test_cmd401_5": "你答应了。",
        "test_cmd402_7_when_1": "不行",
        "test_cmd401_8": "你拒绝了。"
    }
    
    print("\nSimulating Apply translation...")
    # Mock data structure matching what save_translated_file would get
    data = {"test": {"list": list(commands)}}  # Shallow copy
    
    rpgm_command_updates = []
    for key, translated_value in translated_data.items():
        if "cmd401_" in key or "cmd102_" in key or "cmd402_" in key:
            key_path = key.replace("test", "test_list")
            rpgm_command_updates.append((key_path, translated_value))
            
    def get_cmd_idx(path):
        parts = path.split('_')
        for i, part in enumerate(parts):
            if part.startswith('cmd'):
                return int(parts[i+1])
        return 0

    rpgm_command_updates.sort(key=lambda x: get_cmd_idx(x[0]), reverse=True)
    
    print("Application order:")
    for k, v in rpgm_command_updates:
        print(f"  {k} -> {repr(v)}")
        
    for key_path, translated_value in rpgm_command_updates:
        _apply_rpgm_command_translation(data, key_path, translated_value)
        
    print("\nResulting commands:")
    for i, cmd in enumerate(data["test"]["list"]):
        print(f"  {i}: {cmd}")

if __name__ == "__main__":
    test_extraction()
