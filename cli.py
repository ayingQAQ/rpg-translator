#!/usr/bin/env python3
"""
RPG Game Translator - Command Line Interface
=============================================

Usage:
    python cli.py translate <input> [options]
    python cli.py batch <directory> [options]
    python cli.py info
"""

import argparse
import sys
import os
from pathlib import Path

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import modules directly
from core.translator import GameTranslator
from parsers import get_supported_formats
from translators import get_available_engines


def create_parser():
    """Create command line argument parser."""
    
    parser = argparse.ArgumentParser(
        description='RPG Game Translator - Universal translation tool for RPG games',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate a single JSON file
  python cli.py translate dialogue.json --engine google --target zh-CN

  # Translate with DeepL
  python cli.py translate dialogue.json --engine deepl --target zh-CN

  # Batch translate all JSON files in a directory
  python cli.py batch ./data --extensions .json .csv --recursive

  # Use local AI model
  python cli.py translate dialogue.json --engine local --source en --target zh

  # Show supported formats and engines
  python cli.py info
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # ========== Translate Command ==========
    translate_parser = subparsers.add_parser(
        'translate',
        help='Translate a single file'
    )
    translate_parser.add_argument(
        'input',
        help='Input file path'
    )
    translate_parser.add_argument(
        '-o', '--output',
        help='Output file path (auto-generate if not specified)'
    )
    translate_parser.add_argument(
        '-e', '--engine',
        choices=get_available_engines(),
        default='google',
        help='Translation engine (default: google)'
    )
    translate_parser.add_argument(
        '-s', '--source',
        default='auto',
        help='Source language code (default: auto-detect)'
    )
    translate_parser.add_argument(
        '-t', '--target',
        default='zh-CN',
        help='Target language code (default: zh-CN)'
    )
    translate_parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )
    translate_parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Texts per batch (default: 50)'
    )
    translate_parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup of original file'
    )
    translate_parser.add_argument(
        '--output-dir',
        default='./output',
        help='Output directory (default: ./output)'
    )
    
    # ========== Batch Command ==========
    batch_parser = subparsers.add_parser(
        'batch',
        help='Translate multiple files in a directory'
    )
    batch_parser.add_argument(
        'directory',
        help='Input directory'
    )
    batch_parser.add_argument(
        '-o', '--output-dir',
        help='Output directory (default: ./output)'
    )
    batch_parser.add_argument(
        '-e', '--engine',
        choices=get_available_engines(),
        default='google',
        help='Translation engine (default: google)'
    )
    batch_parser.add_argument(
        '-s', '--source',
        default='auto',
        help='Source language code (default: auto-detect)'
    )
    batch_parser.add_argument(
        '-t', '--target',
        default='zh-CN',
        help='Target language code (default: zh-CN)'
    )
    batch_parser.add_argument(
        '--extensions',
        nargs='+',
        help='File extensions to process (default: all supported formats)'
    )
    batch_parser.add_argument(
        '--recursive',
        action='store_true',
        default=True,
        help='Process subdirectories (default: True)'
    )
    batch_parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not process subdirectories'
    )
    batch_parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )
    batch_parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup of original files'
    )
    
    # ========== Info Command ==========
    info_parser = subparsers.add_parser(
        'info',
        help='Show supported formats and engines'
    )
    
    # ========== Config Command ==========
    config_parser = subparsers.add_parser(
        'config',
        help='Show or create configuration'
    )
    config_parser.add_argument(
        '--init',
        action='store_true',
        help='Create default configuration file'
    )
    config_parser.add_argument(
        '--show',
        action='store_true',
        help='Show current configuration'
    )
    
    return parser


def cmd_translate(args):
    """Handle translate command."""
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        return 1
    
    # Create translator
    translator = GameTranslator(
        engine=args.engine,
        source_lang=args.source,
        target_lang=args.target,
        delay=args.delay,
        batch_size=args.batch_size,
        output_dir=args.output_dir,
        backup=not args.no_backup
    )
    
    # Translate
    try:
        output_path = translator.translate_file(
            args.input,
            args.output
        )
        print(f"\n[OK] Translation completed: {output_path}")
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Translation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_batch(args):
    """Handle batch command."""
    
    # Check if directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: Directory not found: {args.directory}")
        return 1
    
    # Determine recursive mode
    recursive = not args.no_recursive if args.no_recursive else args.recursive
    
    # Create translator
    translator = GameTranslator(
        engine=args.engine,
        source_lang=args.source,
        target_lang=args.target,
        delay=args.delay,
        output_dir=args.output_dir or './output',
        backup=not args.no_backup
    )
    
    # Batch translate
    try:
        output_paths = translator.translate_directory(
            args.directory,
            args.output_dir,
            extensions=args.extensions,
            recursive=recursive
        )
        
        print(f"\n{'='*60}")
        print(f"✓ Batch translation completed")
        print(f"  Total files processed: {len(output_paths)}")
        print(f"{'='*60}")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Batch translation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_info(args):
    """Handle info command."""
    
    print("\n" + "="*60)
    print("RPG Game Translator - Supported Formats & Engines")
    print("="*60)
    
    # Supported formats
    print("\n[Supported File Formats]")
    formats = get_supported_formats()
    for i, fmt in enumerate(formats, 1):
        print(f"  {i:2}. {fmt}")
    
    # Supported engines
    print("\n[Supported Translation Engines]")
    engines = get_available_engines()
    engine_info = {
        'google': 'Google Translate (Free, no API key required)',
        'deepl': 'DeepL (Requires API key, high quality)',
        'baidu': 'Baidu Translate (Requires API credentials)',
        'local': 'Local AI Models (Offline, requires model download)',
    }
    for i, engine in enumerate(engines, 1):
        info = engine_info.get(engine, '')
        print(f"  {i}. {engine:8} - {info}")
    
    # Language codes
    print("\n[Common Language Codes]")
    languages = [
        ('auto', 'Auto-detect'),
        ('en', 'English'),
        ('zh-CN', 'Chinese Simplified'),
        ('zh-TW', 'Chinese Traditional'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
    ]
    for code, name in languages:
        print(f"  {code:8} - {name}")
    
    print("\n" + "="*60 + "\n")
    
    return 0


def cmd_config(args):
    """Handle config command."""
    
    config_file = 'config.yaml'
    
    if args.init:
        # Create default config
        import shutil
        
        template = os.path.join(
            os.path.dirname(__file__),
            'config.yaml'
        )
        
        if os.path.exists(template):
            shutil.copy(template, config_file)
            print(f"✓ Configuration file created: {config_file}")
        else:
            print(f"✗ Template not found: {template}")
            return 1
    
    elif args.show:
        # Show current config
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                print(f.read())
        else:
            print(f"No configuration file found at: {config_file}")
            print("Run 'python cli.py config --init' to create one")
    
    else:
        print("Usage: python cli.py config --init OR --show")
        return 1
    
    return 0


def main():
    """Main entry point."""
    
    parser = create_parser()
    args = parser.parse_args()
    
    # No command specified
    if not args.command:
        parser.print_help()
        return 0
    
    # Route to command handler
    commands = {
        'translate': cmd_translate,
        'batch': cmd_batch,
        'info': cmd_info,
        'config': cmd_config,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
