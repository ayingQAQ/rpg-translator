"""
Game Translator - Main translation workflow
"""

import os
import sys
import json
import time
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Handle imports for both package and direct execution
try:
    from ..parsers import get_parser, BaseParser, TextSegment, get_supported_formats
    from ..translators import get_translator, BaseTranslator
except ImportError:
    # Direct execution
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parsers import get_parser, BaseParser, TextSegment, get_supported_formats
    from translators import get_translator, BaseTranslator


class GameTranslator:
    """
    Main class for translating RPG game text files.
    
    Handles the complete workflow:
    1. Parse input file
    2. Extract text segments
    3. Translate texts
    4. Reconstruct and save output
    """
    
    def __init__(
        self,
        engine: str = 'google',
        source_lang: str = 'auto',
        target_lang: str = 'zh-CN',
        config: Dict = None,
        **kwargs
    ):
        """
        Initialize game translator.
        
        Args:
            engine: Translation engine ('google', 'deepl', 'baidu', 'local')
            source_lang: Source language code
            target_lang: Target language code
            config: Configuration dictionary
            **kwargs: Additional options
        """
        self.config = config or {}
        self.engine_name = engine
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        # Translation settings
        self.batch_size = kwargs.get('batch_size', 50)
        self.delay = kwargs.get('delay', 0.5)
        self.preserve_patterns = kwargs.get('preserve_patterns', [])
        self.skip_patterns = kwargs.get('skip_patterns', [])
        
        # Output settings
        self.output_dir = kwargs.get('output_dir', './output')
        self.create_backup = kwargs.get('backup', True)
        self.log_file = kwargs.get('log_file', 'translation_log.json')
        
        # Initialize translator
        self.translator = get_translator(
            engine,
            source_lang=source_lang,
            target_lang=target_lang,
            **kwargs
        )
        
        # Translation statistics
        self.stats = {
            'total_texts': 0,
            'translated_texts': 0,
            'skipped_texts': 0,
            'failed_texts': 0,
            'start_time': None,
            'end_time': None,
        }
        
        # Translation log
        self.translation_log = []
        
        # Progress callback
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """
        Set progress callback for GUI updates.
        
        Args:
            callback: Function(current, total) -> bool, return False to cancel
        """
        self.progress_callback = callback
    
    def set_log_callback(self, callback):
        """
        Set log callback for GUI log updates.
        
        Args:
            callback: Function(message)
        """
        self.log_callback = callback
    
    def _log(self, message: str):
        """Log message with callback."""
        if hasattr(self, 'log_callback') and self.log_callback:
            self.log_callback(message)
        # Always print to console for debugging
        print(message)
    
    def translate_file(
        self,
        input_path: str,
        output_path: str = None,
        **parser_kwargs
    ) -> str:
        """
        Translate a single file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file (auto-generate if None)
            **parser_kwargs: Parser-specific options
        
        Returns:
            Path to translated file
        """
        print(f"\n{'='*60}")
        print(f"Translating: {input_path}")
        print(f"{'='*60}")
        
        # Start timer
        self.stats['start_time'] = datetime.now()
        
        # Generate output path if not provided
        if output_path is None:
            output_path = self._generate_output_path(input_path)
        
        # Create output directory
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        # Parse file
        print(f"\n[1/4] Parsing file...")
        parser = get_parser(input_path, **parser_kwargs)
        
        # Create backup
        if self.create_backup:
            backup_path = parser.create_backup()
            print(f"  Backup created: {backup_path}")
        
        # Extract texts
        print(f"\n[2/4] Extracting text segments...")
        segments = parser.parse()
        self.stats['total_texts'] = len(segments)
        print(f"  Found {len(segments)} text segments")
        
        # Translate texts
        print(f"\n[3/4] Translating texts...")
        translated_segments = self._translate_segments(segments)
        
        # Reconstruct and save
        print(f"\n[4/4] Saving translated file...")
        reconstructed = parser.reconstruct(translated_segments)
        parser.save(reconstructed, output_path)
        print(f"  Saved to: {output_path}")
        
        # End timer
        self.stats['end_time'] = datetime.now()
        
        # Print summary
        self._print_summary()
        
        # Save log
        if self.log_file:
            self._save_translation_log(input_path, output_path)
        
        return output_path
    
    def translate_directory(
        self,
        input_dir: str,
        output_dir: str = None,
        extensions: List[str] = None,
        recursive: bool = True,
        **parser_kwargs
    ) -> List[str]:
        """
        Translate all supported files in a directory.
        
        Args:
            input_dir: Input directory
            output_dir: Output directory
            extensions: File extensions to process
            recursive: Process subdirectories
            **parser_kwargs: Parser-specific options
        
        Returns:
            List of output file paths
        """
        # Use all supported formats if not specified
        if extensions is None:
            extensions = get_supported_formats()
        
        # Set output directory
        if output_dir is None:
            output_dir = self.output_dir
        
        # Find all files
        input_files = self._find_files(input_dir, extensions, recursive)
        
        print(f"\nFound {len(input_files)} files to translate")
        
        # Translate each file
        output_paths = []
        for i, input_path in enumerate(input_files, 1):
            print(f"\n[{i}/{len(input_files)}] Processing: {input_path}")
            
            try:
                # Generate output path maintaining directory structure
                rel_path = os.path.relpath(input_path, input_dir)
                output_path = os.path.join(output_dir, rel_path)
                
                # Translate
                result_path = self.translate_file(
                    input_path,
                    output_path,
                    **parser_kwargs
                )
                output_paths.append(result_path)
                
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        return output_paths
    
    def _translate_segments(self, segments: List) -> List[TextSegment]:
        """
        Translate all text segments using multi-threading for performance.
        
        Args:
            segments: List of TextSegment objects
        
        Returns:
            List of TextSegment objects with translated_text populated
        """
        from tqdm import tqdm
        import threading
        
        translated = []
        failed = []
        total = len(segments)
        completed = 0
        
        # Thread-safe lock for updating shared variables
        lock = threading.Lock()
        
        def process_segment(segment):
            """Process a single segment (thread-safe)."""
            nonlocal completed
            
            # Skip empty texts
            if not segment or not segment.text or not segment.text.strip():
                segment.translated_text = segment.text
                with lock:
                    completed += 1
                return segment, None
            
            # Check if should skip
            if self._should_skip(segment.text):
                segment.translated_text = segment.text
                with lock:
                    self.stats['skipped_texts'] += 1
                    completed += 1
                
                with lock:
                    self.translation_log.append({
                        'original': segment.text,
                        'translated': segment.text,
                        'location': segment.location,
                        'success': True,
                        'status': 'skipped'
                    })
                return segment, None
            
            # Preserve placeholders
            preserved_text, placeholder_map = self._preserve_placeholders(segment.text)
            
            # Translate
            try:
                translated_text = self.translator.translate_with_retry(preserved_text)
                
                # Restore placeholders
                translated_text = self._restore_placeholders(translated_text, placeholder_map)
                
                segment.translated_text = translated_text
                with lock:
                    self.stats['translated_texts'] += 1
                    completed += 1
                
                # Log translation
                with lock:
                    self.translation_log.append({
                        'original': segment.text,
                        'translated': translated_text,
                        'location': segment.location,
                        'success': True,
                        'status': 'translated'
                    })
                
                return segment, None
                
            except Exception as e:
                segment.translated_text = segment.text
                with lock:
                    self.stats['failed_texts'] += 1
                    completed += 1
                
                # Log failure
                with lock:
                    self.translation_log.append({
                        'original': segment.text,
                        'translated': segment.text,
                        'location': segment.location,
                        'success': False,
                        'error': str(e),
                        'status': 'failed'
                    })
                
                return segment, str(e)
        
        # 🚀 使用线程池，同时发起多个翻译请求
        # 免费 Google 接口开太大容易被封 IP，5-10 比较安全
        # 如果是付费API如DeepL可以开到20-50
        max_workers = 10
        
        # Create progress display (优雅降级处理)
        use_pbar = not self.progress_callback
        pbar = None
        if use_pbar:
            try:
                from tqdm import tqdm
                pbar = tqdm(
                    total=total,
                    desc="Translating",
                    unit="texts",
                    ncols=80
                )
            except ImportError:
                print("\n[提示] 未检测到 tqdm 库，终端进度条已隐藏。如需显示请执行: pip install tqdm")
                use_pbar = False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_segment = {executor.submit(process_segment, seg): seg for seg in segments}
            
            # 处理完成的任务
            for future in concurrent.futures.as_completed(future_to_segment):
                segment, err = future.result()
                translated.append(segment)
                
                # Update progress
                if use_pbar:
                    pbar.update(1)
                    pbar.set_description(f"Translating ({completed}/{total})")
                elif self.progress_callback:
                    with lock:
                        current_completed = completed
                    should_continue = self.progress_callback(current_completed, total)
                    if not should_continue:
                        print("Translation cancelled by user.")
                        # Cancel remaining futures
                        for f in future_to_segment:
                            f.cancel()
                        break
                
                # Collect failed translations
                if err:
                    failed.append((segment.text, err))
        
      # 直接把多余的嵌套 if 去掉，并保持正确的缩进
        if use_pbar and pbar:  # 防止 pbar 未定义时报错
            pbar.close()
        
        # Report failures
        if failed:
            print(f"\n  {len(failed)} translations failed:")
            for orig, err in failed[:5]:  # Show first 5 failures
                print(f"    - '{orig[:50]}...': {err}")
            if len(failed) > 5:
                print(f"    ... and {len(failed) - 5} more")
        
        return translated
    
    def _should_skip(self, text: str) -> bool:
        """Check if text should be skipped."""
        import re
        
        if not text or not text.strip():
            return True
        
        for pattern in self.skip_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _preserve_placeholders(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Preserve placeholders in text."""
        import re
        
        if not self.preserve_patterns:
            return text, {}
        
        placeholders = {}
        result = text
        
        for pattern in self.preserve_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                token = f"__PH_{len(placeholders)}__"
                placeholders[token] = match
                result = result.replace(match, token, 1)
        
        return result, placeholders
    
    def _restore_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """Restore placeholders in translated text."""
        result = text
        for token, original in placeholder_map.items():
            result = result.replace(token, original)
        return result
    
    def _generate_output_path(self, input_path: str) -> str:
        """Generate output file path."""
        name = os.path.basename(input_path)
        base, ext = os.path.splitext(name)
        
        new_name = f"{base}_{self.target_lang}{ext}"
        return os.path.join(self.output_dir, new_name)
    
    def _find_files(
        self,
        directory: str,
        extensions: List[str],
        recursive: bool
    ) -> List[str]:
        """Find all files with specified extensions with basic safety filtering."""
        files = []
        skip_dirs = {'img', 'images', 'graphics', 'audio', 'sound', 'music', 'movies', 'video', 'save', 'saves'}
        
        for root, dirs, filenames in os.walk(directory):
            # Modify dirs in-place to skip irrelevant directories early
            dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
            
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, filename)
                    try:
                        # Skip files that are > 10MB to avoid parsing huge assets
                        if os.path.getsize(file_path) <= 10 * 1024 * 1024:
                            files.append(file_path)
                    except OSError:
                        pass
            
            if not recursive:
                break
        
        return files
    
    def _print_summary(self):
        """Print translation summary."""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*60}")
        print("Translation Summary")
        print(f"{'='*60}")
        print(f"  Total texts:     {self.stats['total_texts']}")
        print(f"  Translated:      {self.stats['translated_texts']}")
        print(f"  Skipped:         {self.stats['skipped_texts']}")
        print(f"  Failed:          {self.stats['failed_texts']}")
        print(f"  Duration:        {duration:.2f} seconds")
        print(f"{'='*60}\n")
    
    def _save_translation_log(self, input_path: str, output_path: str):
        """Save translation log to file."""
        
        # Convert datetime objects to strings
        stats_serializable = self.stats.copy()
        if stats_serializable.get('start_time'):
            stats_serializable['start_time'] = stats_serializable['start_time'].isoformat()
        if stats_serializable.get('end_time'):
            stats_serializable['end_time'] = stats_serializable['end_time'].isoformat()
        
        log_data = {
            'input_file': input_path,
            'output_file': output_path,
            'engine': self.engine_name,
            'source_lang': self.source_lang,
            'target_lang': self.target_lang,
            'timestamp': datetime.now().isoformat(),
            'statistics': stats_serializable,
            'translations': self.translation_log
        }
        
        log_path = os.path.join(
            os.path.dirname(output_path) or '.',
            self.log_file
        )
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"  Translation log saved: {log_path}")
