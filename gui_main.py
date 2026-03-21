#!/usr/bin/env python3
"""
RPG Game Translator - GUI Main Application
===========================================
A visual interface for extracting, translating, and replacing RPG game text.
"""

import sys
import os
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,  # type: ignore
                                 QHBoxLayout, QPushButton, QTextEdit, QTreeView,
                                 QSplitter, QLabel, QProgressBar, QMessageBox,
                                 QGroupBox, QComboBox, QCheckBox, QFileDialog,
                                 QLineEdit, QPlainTextEdit, QTabWidget, QListWidget,
                                 QListWidgetItem, QMenu, QAction, QToolBar, QStatusBar,
                                 QDockWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
                                 QHeaderView, QGraphicsDropShadowEffect)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDir, QModelIndex, QTimer, QSettings  # type: ignore
    from PyQt5.QtGui import QIcon, QFont, QColor, QStandardItemModel, QStandardItem  # type: ignore
except ImportError:
    print("PyQt5 is not installed. Please install it with:")
    print("pip install PyQt5")
    sys.exit(1)

import json
import time
import shutil
import re
from typing import List, Dict, Any, Optional
import threading

# Import project modules
try:
    from core.translator import GameTranslator  # type: ignore
    from parsers import get_supported_formats, BaseParser  # type: ignore
    from translators import get_available_engines  # type: ignore
    from game_extractors import detect_game_engine, extract_game_text, convert_to_translation_format, save_translated_file  # type: ignore
except ImportError:
    # Direct execution
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.translator import GameTranslator  # type: ignore
    from parsers import get_supported_formats, BaseParser  # type: ignore
    from translators import get_available_engines  # type: ignore
    from game_extractors import detect_game_engine, extract_game_text, convert_to_translation_format, save_translated_file  # type: ignore


class TranslationThread(QThread):
    """Worker thread for translation to keep GUI responsive."""
    
    progress = pyqtSignal(int, int)  # current, total
    text_translated = pyqtSignal(str, str)  # original, translated
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    error = pyqtSignal(str)
    
    def __init__(self, translator, input_path, output_path=None):
        super().__init__()
        self.translator = translator
        self.input_path = input_path
        self.output_path = output_path
        self._stop_requested = False
    
    def run(self):
        """Run translation in background."""
        try:
            self.log_message.emit(f"Starting translation of: {self.input_path}")
            
            # Set up progress callbacks
            def progress_callback(current, total):
                self.progress.emit(current, total)
                return not self._stop_requested
            
            def log_callback(message):
                self.log_message.emit(message)
            
            self.translator.set_progress_callback(progress_callback)
            self.translator.set_log_callback(log_callback)
            
            # Perform translation
            output = self.translator.translate_file(self.input_path, self.output_path)
            
            if self._stop_requested:
                self.finished.emit(False, "Translation cancelled")
            else:
                self.finished.emit(True, f"Translation completed: {output}")
                
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, f"Translation failed: {e}")
    
    def stop(self):
        """Request thread to stop."""
        self._stop_requested = True


class OneClickTranslateThread(QThread):
    """One-click translation worker thread."""
    progress = pyqtSignal(int, int)  # current, total
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    error = pyqtSignal(str)

    def __init__(self, game_path, engine, source_lang, target_lang, delay=0.1):
        super().__init__()
        self.game_path = game_path
        self.engine = engine
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.delay = delay
        self.translator = None
        self._stop_requested = False

    def run(self):
        """Run one-click translation in background."""
        try:
            self.log_message.emit('Starting one-click translation workflow...')

            gt = GameTranslator(
                engine=self.engine,
                source_lang=self.source_lang,
                target_lang=self.target_lang,
                delay=self.delay,
            )
            self.translator = gt

            def progress_callback(current, total):
                # Keep cancellation support inside per-file translation.
                return not self._stop_requested

            def log_callback(message):
                self.log_message.emit(message)

            gt.set_progress_callback(progress_callback)
            gt.set_log_callback(log_callback)

            game_path = Path(self.game_path)
            engine_info = detect_game_engine(game_path)
            if not engine_info:
                self.finished.emit(False, 'Could not detect game engine in selected directory.')
                return

            engine_name = str(engine_info.get('engine', 'unknown'))
            self.log_message.emit(f'Detected game engine: {engine_name}')

            # Explicitly log intended engine-specific target ranges.
            if engine_name == 'rpgmv':
                self.log_message.emit('Target scope: data/*.json + Map*.json')
            elif engine_name == 'renpy':
                self.log_message.emit('Target scope: game/**/*.rpy')
            elif engine_name == 'wolf':
                self.log_message.emit('Target scope: CommonEvents.dat + Map*.dat + core dat files')
            else:
                self.log_message.emit('Target scope: generic text-like files in game data roots')

            extracted_files = extract_game_text(game_path, engine_info)
            if not extracted_files:
                self.finished.emit(False, 'No candidate text files found for this game.')
                return

            deduped_paths = []
            seen_paths = set()
            for file_info in extracted_files:
                file_path = Path(file_info['path'])
                try:
                    path_key = str(file_path.resolve()).lower()
                except Exception:
                    path_key = str(file_path).lower()
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                deduped_paths.append(file_path)

            supported_extensions = {ext.lower() for ext in get_supported_formats()}
            translatable_paths = []
            unsupported_paths = []

            for file_path in deduped_paths:
                if file_path.suffix.lower() in supported_extensions:
                    translatable_paths.append(file_path)
                else:
                    unsupported_paths.append(file_path)

            self.log_message.emit(
                f'Candidates: {len(deduped_paths)} files, translatable now: {len(translatable_paths)}'
            )
            if unsupported_paths:
                preview = ', '.join(p.name for p in unsupported_paths[:5])
                self.log_message.emit(
                    f'Skipped unsupported formats: {len(unsupported_paths)} (examples: {preview})'
                )

            if not translatable_paths:
                self.finished.emit(False, 'No parser-supported files found in extracted candidates.')
                return

            output_paths = []
            failed_count = 0
            total_files = len(translatable_paths)
            self.progress.emit(0, total_files)

            for idx, input_file in enumerate(translatable_paths, 1):
                if self._stop_requested:
                    self.finished.emit(False, 'One-click translation cancelled.')
                    return

                self.log_message.emit(f'[{idx}/{total_files}] Translating: {input_file.name}')
                try:
                    result_path = gt.translate_file(str(input_file), str(input_file))
                    output_paths.append(result_path)
                except Exception as file_error:
                    failed_count += 1
                    self.log_message.emit(f'Failed: {input_file.name} -> {file_error}')
                finally:
                    self.progress.emit(idx, total_files)

            if self._stop_requested:
                self.finished.emit(False, 'One-click translation cancelled.')
            else:
                self.finished.emit(
                    True,
                    (
                        f'One-click translation completed. '
                        f'Succeeded: {len(output_paths)}, Failed: {failed_count}, '
                        f'Skipped unsupported: {len(unsupported_paths)}'
                    ),
                )

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, f'One-click translation failed: {str(e)}')

    def stop(self):
        """Request thread to stop."""
        self._stop_requested = True
        if self.translator:
            # Cancellation is checked via progress callback.
            pass

class RestoreThread(QThread):
    """一键恢复后台线程"""
    progress = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, game_path):
        super().__init__()
        self.game_path = Path(game_path)
        self._stop_requested = False

    def run(self):
        try:
            self.log_message.emit("开始扫描备份文件...")
            
            # 查找所有包含 .backup 的文件
            backup_files = []
            for ext in ['*.json', '*.csv', '*.txt', '*.yaml', '*.xml', '*.rpy']:
                for file in self.game_path.rglob(ext):
                    if self._stop_requested:
                        self.finished.emit(False, "恢复已取消。")
                        return
                    if '.backup' in file.name:
                        backup_files.append(file)
            
            if not backup_files:
                self.finished.emit(False, "未在目录中找到任何备份文件。")
                return

            total = len(backup_files)
            restored_count = 0
            
            for i, backup_path in enumerate(backup_files):
                if self._stop_requested:
                    self.finished.emit(False, "恢复已取消。")
                    return
                # 利用正则还原真实文件名
                # 兼容 "name.backup.json" 和 "name.backup_123456.json" 两种命名方式
                original_name = re.sub(r'\.backup(_\d+)?', '', backup_path.name)
                original_path = backup_path.parent / original_name
                
                # 覆盖回原文件（保留备份文件作为后悔药）
                shutil.copy2(backup_path, original_path)
                self.log_message.emit(f"已恢复: {original_name}")
                
                restored_count += 1
                self.progress.emit(i + 1, total)
                
            self.finished.emit(True, f"成功恢复了 {restored_count} 个原版文件。")
            
        except Exception as e:
            self.finished.emit(False, f"恢复过程中出错: {str(e)}")

    def stop(self):
        """Request thread to stop."""
        self._stop_requested = True


class GameTextExtractorThread(QThread):
    """Worker thread for extracting game text."""
    
    progress = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, list)  # success, extracted_files
    error = pyqtSignal(str)
    
    def __init__(self, game_path):
        super().__init__()
        self.game_path = game_path
        self._stop_requested = False
    
    def run(self):
        """Extract game text in background."""
        try:
            self.log_message.emit(f"Detecting game engine in: {self.game_path}")
            if self._stop_requested:
                self.finished.emit(False, [])
                return
            
            # Detect game engine
            engine_info = detect_game_engine(self.game_path)
            if not engine_info:
                self.error.emit("Could not detect game engine")
                self.finished.emit(False, [])
                return
            
            self.log_message.emit(f"Detected: {engine_info['engine']} v{engine_info.get('version', 'unknown')}")
            if self._stop_requested:
                self.finished.emit(False, [])
                return
            
            # Extract text
            self.log_message.emit("Extracting text files...")
            extracted_files = extract_game_text(self.game_path, engine_info)
            if self._stop_requested:
                self.finished.emit(False, [])
                return
            
            self.finished.emit(True, extracted_files)
            
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, [])

    def stop(self):
        """Request thread to stop."""
        self._stop_requested = True


class TextTableWidget(QTableWidget):
    """Custom table widget for displaying text entries."""
    
    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Key", "Original Text", "Translated Text", "Status"])
        header = self.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # type: ignore
            header.setSectionResizeMode(1, QHeaderView.Stretch)  # type: ignore
            header.setSectionResizeMode(2, QHeaderView.Stretch)  # type: ignore
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # type: ignore
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)  # type: ignore
        self.verticalHeader().setDefaultSectionSize(30)  # type: ignore
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSortingEnabled(True)
    
    def load_text_data(self, text_data: List[Dict]):
        """Load text data into table."""
        was_sorting_enabled = self.isSortingEnabled()
        if was_sorting_enabled:
            self.setSortingEnabled(False)
        self.setRowCount(len(text_data))
        
        for row, item in enumerate(text_data):
            # Key
            key_item = QTableWidgetItem(item.get('key', ''))
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)  # type: ignore
            self.setItem(row, 0, key_item)
            
            # Original text
            orig_item = QTableWidgetItem(item.get('original', ''))
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemIsEditable)  # type: ignore
            self.setItem(row, 1, orig_item)
            
            # Translated text (editable)
            trans_item = QTableWidgetItem(item.get('translated', ''))
            self.setItem(row, 2, trans_item)
            
            # Status
            status = item.get('status', 'pending')
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)  # type: ignore
            
            # Color code status
            if status == 'translated':
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            elif status == 'pending':
                status_item.setBackground(QColor(255, 255, 200))  # Light yellow
            elif status == 'error':
                status_item.setBackground(QColor(255, 200, 200))  # Light red
            
            self.setItem(row, 3, status_item)
        if was_sorting_enabled:
            self.setSortingEnabled(True)
    
    def get_text_data(self) -> List[Dict]:
        """Get text data from table."""
        data = []
        for row in range(self.rowCount()):
            item0 = self.item(row, 0)
            item1 = self.item(row, 1)
            item2 = self.item(row, 2)
            item3 = self.item(row, 3)
            data.append({
                'key': item0.text() if item0 else '',
                'original': item1.text() if item1 else '',
                'translated': item2.text() if item2 else '',
                'status': item3.text() if item3 else 'pending'
            })
        return data


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPG Game Translator")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1080, 720)
        self.settings = QSettings("RPGTranslator", "RPG Game Translator")
        
        # Initialize data
        self.current_project: Optional[Any] = None
        self.text_data: List[Dict[str, Any]] = []
        self.game_path: Optional[Path] = None
        self.current_file: Optional[Path] = None
        self.main_splitter: Optional[QSplitter] = None
        self.last_open_dir = str(self.settings.value("last_game_dir", "", type=str))
        self.translator_thread: Optional[TranslationThread] = None
        self.extractor_thread: Optional[GameTextExtractorThread] = None
        self.one_click_thread: Optional[OneClickTranslateThread] = None
        self.restore_thread: Optional[RestoreThread] = None
        self.current_parser: Optional[BaseParser] = None
        self.status_engine_label: Optional[QLabel] = None
        self.status_files_label: Optional[QLabel] = None
        
        # Setup UI
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.apply_visual_theme()
        self.restore_window_state()
        
        # Update UI state
        self.update_ui_state()
    
    def setup_ui(self):
        """Setup the main UI."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 12)
        main_layout.setSpacing(10)

        # Top banner
        hero_banner = self.create_hero_banner()
        main_layout.addWidget(hero_banner)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)  # type: ignore
        splitter.setHandleWidth(8)
        self.main_splitter = splitter
        
        # Left panel - Project/Files
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Text editor
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("mainProgress")
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Processing %p%")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def create_hero_banner(self):
        """Create a compact header banner."""
        banner = QWidget()
        banner.setObjectName("heroBanner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_layout.setSpacing(10)

        left_wrap = QWidget()
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        title = QLabel("RPG 翻译工作台")
        title.setObjectName("heroTitle")
        subtitle = QLabel("引擎感知提取 + 精准批量翻译流程")
        subtitle.setObjectName("heroSubtitle")
        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)

        hint = QLabel("提示：一键汉化只处理引擎命中的候选文件")
        hint.setObjectName("heroHint")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore

        banner_layout.addWidget(left_wrap, 1)
        banner_layout.addWidget(hint, 1)
        return banner
    
    def create_left_panel(self):
        """Create left panel with project/file management."""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # Project info group
        project_group = QGroupBox("Project")
        project_group.setObjectName("panelCard")
        project_layout = QVBoxLayout()
        project_layout.setSpacing(8)
        
        self.project_label = QLabel("No project loaded")
        self.project_label.setObjectName("projectLabel")
        self.project_label.setWordWrap(True)
        project_layout.addWidget(self.project_label)
        
        self.load_game_btn = QPushButton("Load Game Directory")
        self.load_game_btn.setMinimumHeight(36)
        self.load_game_btn.clicked.connect(self.load_game_directory)
        project_layout.addWidget(self.load_game_btn)
        
        # One-click translation action
        self.one_click_btn = QPushButton("一键汉化 (Mtool 模式)")
        self.one_click_btn.setMinimumHeight(48)
        self.one_click_btn.setObjectName("primaryActionBtn")
        self.one_click_btn.clicked.connect(self.start_one_click_translation)
        self.one_click_btn.setEnabled(False)
        project_layout.addWidget(self.one_click_btn)
        
        # Restore action
        self.restore_btn = QPushButton("一键恢复 (还原原版)")
        self.restore_btn.setMinimumHeight(40)
        self.restore_btn.setObjectName("dangerActionBtn")
        self.restore_btn.clicked.connect(self.start_restore)
        self.restore_btn.setEnabled(False) 
        project_layout.addWidget(self.restore_btn)
        
        project_group.setLayout(project_layout)
        self.apply_card_shadow(project_group)
        left_layout.addWidget(project_group)
        
        # Extracted files list
        files_group = QGroupBox("Extracted Files")
        files_group.setObjectName("panelCard")
        files_layout = QVBoxLayout()
        files_layout.setSpacing(8)

        self.file_filter_input = QLineEdit()
        self.file_filter_input.setPlaceholderText("Filter files by name or type...")
        self.file_filter_input.textChanged.connect(self.filter_extracted_files)
        files_layout.addWidget(self.file_filter_input)
        
        self.files_list = QListWidget()
        self.files_list.setObjectName("filesList")
        self.files_list.setAlternatingRowColors(True)
        self.files_list.setUniformItemSizes(True)
        self.files_list.setToolTip("Double-click a file to load extracted text")
        self.files_list.itemDoubleClicked.connect(self.load_file_for_translation)
        files_layout.addWidget(self.files_list)
        
        self.extract_text_btn = QPushButton("Extract Game Text")
        self.extract_text_btn.setMinimumHeight(34)
        self.extract_text_btn.clicked.connect(self.extract_game_text)
        self.extract_text_btn.setEnabled(False)
        files_layout.addWidget(self.extract_text_btn)
        
        files_group.setLayout(files_layout)
        self.apply_card_shadow(files_group)
        left_layout.addWidget(files_group)
        
        return left_widget
    
    def create_right_panel(self):
        """Create right panel with translation interface."""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # File info
        self.file_label = QLabel("No file loaded")
        self.file_label.setObjectName("fileInfoLabel")
        self.file_label.setMinimumHeight(34)
        right_layout.addWidget(self.file_label)
        
        # Text table
        self.text_table = TextTableWidget()
        right_layout.addWidget(self.text_table)
        
        # Translation controls
        controls_group = QGroupBox("Translation Settings")
        controls_group.setObjectName("panelCard")
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Translation engine
        controls_layout.addWidget(QLabel("Engine:"))
        self.engine_combo = QComboBox()
        engines = get_available_engines()
        for engine in engines:
            self.engine_combo.addItem(engine.title(), engine)
        controls_layout.addWidget(self.engine_combo)
        
        # Source language
        controls_layout.addWidget(QLabel("From:"))
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(['auto', 'en', 'ja', 'ko'])
        controls_layout.addWidget(self.source_lang_combo)
        
        # Target language
        controls_layout.addWidget(QLabel("To:"))
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(['zh-CN', 'zh-TW', 'en', 'ja', 'ko'])
        controls_layout.addWidget(self.target_lang_combo)
        
        # Buttons
        self.translate_btn = QPushButton("Translate All")
        self.translate_btn.clicked.connect(self.translate_all)
        self.translate_btn.setEnabled(False)
        controls_layout.addWidget(self.translate_btn)
        
        self.translate_selected_btn = QPushButton("Translate Selected")
        self.translate_selected_btn.clicked.connect(self.translate_selected)
        self.translate_selected_btn.setEnabled(False)
        controls_layout.addWidget(self.translate_selected_btn)
        
        controls_group.setLayout(controls_layout)
        self.apply_card_shadow(controls_group)
        right_layout.addWidget(controls_group)
        
        # Log output
        log_group = QGroupBox("Log")
        log_group.setObjectName("panelCard")
        log_layout = QVBoxLayout()
        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("logPanel")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Runtime logs appear here...")
        self.log_text.setMaximumBlockCount(1500)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        self.apply_card_shadow(log_group)
        right_layout.addWidget(log_group)
        
        return right_widget
    
    def setup_menus(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        if menubar is None:
            return
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Project", self)
        new_action.triggered.connect(self.new_project)  # type: ignore
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Project", self)
        open_action.triggered.connect(self.open_project)  # type: ignore
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        load_file_action = QAction("Load Translation File", self)
        load_file_action.triggered.connect(self.load_translation_file)  # type: ignore
        file_menu.addAction(load_file_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)  # type: ignore
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self.save_file_as)  # type: ignore
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)  # type: ignore
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)  # type: ignore
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)  # type: ignore
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(toolbar.iconSize())
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)  # type: ignore
        self.addToolBar(toolbar)
        
        # Add actions
        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_project)
        toolbar.addAction(new_action)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_project)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)
    
    def setup_statusbar(self):
        """Setup status bar."""
        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.showMessage("Ready")

        self.status_engine_label = QLabel("Engine: --")
        self.status_files_label = QLabel("Files: 0")
        self.status_engine_label.setObjectName("statusPill")
        self.status_files_label.setObjectName("statusPill")
        status_bar.addPermanentWidget(self.status_engine_label)
        status_bar.addPermanentWidget(self.status_files_label)

    def restore_window_state(self):
        """Restore persisted window geometry and splitter sizes."""
        geometry = self.settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        splitter_sizes = self.settings.value("splitter_sizes")
        if self.main_splitter is not None and isinstance(splitter_sizes, list):
            try:
                sizes = [int(v) for v in splitter_sizes]
                if sizes:
                    self.main_splitter.setSizes(sizes)
            except (TypeError, ValueError):
                pass

    def save_window_state(self):
        """Persist window geometry and splitter sizes."""
        self.settings.setValue("window_geometry", self.saveGeometry())
        if self.main_splitter is not None:
            self.settings.setValue("splitter_sizes", self.main_splitter.sizes())

    def visible_file_count(self) -> int:
        """Return visible item count in file list."""
        visible = 0
        for i in range(self.files_list.count()):
            if not self.files_list.item(i).isHidden():
                visible += 1
        return visible

    def refresh_file_status_count(self):
        """Update status bar with visible/total file count."""
        if self.status_files_label is None:
            return
        total = self.files_list.count()
        visible = self.visible_file_count()
        if visible != total:
            self.status_files_label.setText(f"Files: {visible}/{total}")
        else:
            self.status_files_label.setText(f"Files: {total}")

    def apply_card_shadow(self, widget):
        """Apply subtle depth to card-like panels."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(29, 52, 84, 35))
        widget.setGraphicsEffect(shadow)

    def apply_visual_theme(self):
        """Apply an intentional, high-contrast desktop theme."""
        app_font = QFont("Microsoft YaHei UI", 10)
        self.setFont(app_font)
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f2f6fb;
            }
            QMenuBar {
                background: #ffffff;
                border-bottom: 1px solid #cfdae8;
                padding: 4px 6px;
                color: #1a4169;
            }
            QMenuBar::item {
                background: transparent;
                border-radius: 6px;
                padding: 5px 10px;
                margin: 0 2px;
            }
            QMenuBar::item:selected {
                background: #e9f2ff;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #cfdae8;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 12px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: #e9f2ff;
            }
            QWidget#heroBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #173a63, stop:1 #1f5f8b);
                border: 1px solid #2f6f9a;
                border-radius: 12px;
            }
            QLabel#heroTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#heroSubtitle {
                color: #dceeff;
                font-size: 11px;
            }
            QLabel#heroHint {
                color: #ffecc5;
                font-size: 11px;
                font-weight: 600;
            }
            QToolBar {
                background: #ffffff;
                border: 1px solid #cfdae8;
                border-radius: 10px;
                spacing: 6px;
                padding: 6px 8px;
            }
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 6px 10px;
                color: #173a63;
                font-weight: 600;
            }
            QToolButton:hover {
                background: #e9f2ff;
                border-color: #c8daff;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #cfdae8;
                color: #35526f;
            }
            QLabel#statusPill {
                background: #edf4ff;
                border: 1px solid #d0e1ff;
                border-radius: 10px;
                padding: 3px 8px;
                color: #1a4169;
                font-weight: 600;
            }
            QGroupBox#panelCard {
                background: #ffffff;
                border: 1px solid #cfdae8;
                border-radius: 12px;
                margin-top: 14px;
                font-weight: 600;
                color: #1e2a3a;
            }
            QGroupBox#panelCard::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #2f597e;
            }
            QLabel#projectLabel, QLabel#fileInfoLabel {
                background: #f3f8ff;
                border: 1px solid #d5e4f8;
                border-radius: 8px;
                padding: 8px 10px;
                color: #1e2a3a;
                font-weight: 600;
            }
            QPushButton {
                background: #2b71a8;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #245f8e;
            }
            QPushButton:pressed {
                background: #1f4f75;
            }
            QPushButton:disabled {
                background: #b9c6dd;
                color: #edf1f8;
            }
            QPushButton#primaryActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e8f4f, stop:1 #2fa267);
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#primaryActionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #197843, stop:1 #288d58);
            }
            QPushButton#dangerActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c64a34, stop:1 #e35a3f);
                font-weight: 700;
            }
            QPushButton#dangerActionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a73f2d, stop:1 #c44c35);
            }
            QLineEdit, QComboBox, QListWidget, QPlainTextEdit, QTableWidget {
                background: #ffffff;
                border: 1px solid #d3dfef;
                border-radius: 8px;
                padding: 5px 8px;
                selection-background-color: #d6ebff;
                selection-color: #183655;
            }
            QComboBox {
                min-height: 30px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QLineEdit:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus, QTableWidget:focus {
                border: 1px solid #4f87be;
            }
            QTableWidget {
                alternate-background-color: #f8fbff;
            }
            QListWidget#filesList::item {
                border-radius: 6px;
                padding: 5px 6px;
                margin: 1px 0;
            }
            QListWidget#filesList::item:selected {
                background: #d6ebff;
                color: #133252;
            }
            QHeaderView::section {
                background: #e8f1fd;
                color: #244561;
                border: none;
                border-right: 1px solid #d0dff2;
                border-bottom: 1px solid #d0dff2;
                padding: 6px 8px;
                font-weight: 600;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background: #d6ebff;
                color: #0f2d4a;
            }
            QPlainTextEdit#logPanel {
                font-family: Consolas, "Courier New";
                font-size: 11px;
                background: #f8fbff;
            }
            QProgressBar#mainProgress {
                border: 1px solid #cfd9ec;
                border-radius: 8px;
                background: #ebf0f8;
                text-align: center;
                color: #1f3554;
                font-weight: 600;
            }
            QProgressBar#mainProgress::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2f7bb8, stop:1 #2aa38c);
                border-radius: 7px;
            }
            QSplitter::handle {
                background: #e2ebf7;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background: #cfdcf0;
            }
            """
        )
    
    def update_ui_state(self):
        """Update UI state based on current data."""
        has_project = self.game_path is not None
        has_text = len(self.text_data) > 0
        
        self.extract_text_btn.setEnabled(has_project)
        self.one_click_btn.setEnabled(has_project)
        self.restore_btn.setEnabled(has_project)
        self.translate_btn.setEnabled(has_text)
        self.translate_selected_btn.setEnabled(has_text)
        if has_project:
            self.statusBar().showMessage("Game loaded. Ready to extract or translate.")
        else:
            self.statusBar().showMessage("Ready")
        self.refresh_file_status_count()
    
    def load_game_directory(self):
        """Load game directory."""
        start_dir = ""
        if self.last_open_dir and Path(self.last_open_dir).exists():
            start_dir = self.last_open_dir
        directory = QFileDialog.getExistingDirectory(
            self, "Select Game Directory", start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.load_game_directory_from_path(directory)

    def load_game_directory_from_path(self, directory: str):
        """Load game directory from a specific path."""
        game_path = Path(directory)
        self.game_path = game_path
        self.current_file = None
        self.text_data = []
        self.files_list.clear()
        self.file_filter_input.clear()
        self.text_table.setRowCount(0)
        self.file_label.setText("No file loaded")
        self.last_open_dir = str(game_path)
        self.settings.setValue("last_game_dir", self.last_open_dir)
        self.project_label.setText(f"Game: {game_path.name}")
        
        # Try to auto-detect engine
        try:
            engine_info = detect_game_engine(game_path)
            if engine_info:
                self.log(f"Detected game engine: {engine_info['engine']}")
                if self.status_engine_label is not None:
                    self.status_engine_label.setText(f"Engine: {engine_info['engine']}")
            else:
                self.log("Could not auto-detect game engine")
                if self.status_engine_label is not None:
                    self.status_engine_label.setText("Engine: unknown")
        except Exception as e:
            self.log(f"Error detecting game engine: {e}")
            if self.status_engine_label is not None:
                self.status_engine_label.setText("Engine: error")
        
        self.update_ui_state()
    
    def extract_game_text(self):
        """Extract game text in background thread."""
        if not self.game_path:
            QMessageBox.warning(self, "Warning", "No game directory loaded!")
            return
        
        self.extract_text_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log("Starting text extraction...")
        
        # Create and start extraction thread
        game_path = self.game_path
        if game_path is None:
            return
        ext_thread = GameTextExtractorThread(game_path)
        self.extractor_thread = ext_thread
        ext_thread.progress.connect(self.update_progress)
        ext_thread.log_message.connect(self.log)
        ext_thread.finished.connect(self.extraction_finished)
        ext_thread.error.connect(self.log_error)
        ext_thread.start()
    
    def extraction_finished(self, success, extracted_files):
        """Handle extraction completion."""
        self.extractor_thread = None
        self.extract_text_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.log(f"Extraction completed. Found {len(extracted_files)} files.")
            
            # Update files list
            self.files_list.clear()
            for file_info in extracted_files:
                item = QListWidgetItem(f"{file_info['type']}: {file_info['path'].name}")
                item.setData(Qt.UserRole, file_info)  # type: ignore
                item.setToolTip(str(file_info.get('path', '')))
                self.files_list.addItem(item)
            self.filter_extracted_files(self.file_filter_input.text())
        else:
            QMessageBox.critical(self, "Error", "Text extraction failed!")
        
        self.update_ui_state()

    def filter_extracted_files(self, keyword: str):
        """Filter extracted file list by name/type/path."""
        query = keyword.strip().lower()
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            file_info = item.data(Qt.UserRole)  # type: ignore
            path_text = ""
            if isinstance(file_info, dict):
                path_text = str(file_info.get('path', '')).lower()
            item_text = item.text().lower()
            visible = not query or query in item_text or query in path_text
            item.setHidden(not visible)
        self.refresh_file_status_count()
    
    def start_one_click_translation(self):
        """触发一键汉化"""
        if not self.game_path:
            QMessageBox.warning(self, "Warning", "No game directory loaded!")
            return
            
        reply = QMessageBox.question(self, '一键汉化', 
                                     '此操作将按游戏引擎规则自动筛选目标文件并翻译覆盖。\n'
                                     '系统会自动创建 .backup 备份文件。\n\n是否继续？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        
        if reply == QMessageBox.No:
            return

        # 禁用界面
        self.one_click_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        engine = self.engine_combo.currentData()
        source_lang = self.source_lang_combo.currentText()
        target_lang = self.target_lang_combo.currentText()
        
        # 启动一键汉化线程
        self.log("开始一键汉化...")
        game_path = self.game_path
        if game_path is None:
            return
        oc_thread = OneClickTranslateThread(
            game_path, engine, source_lang, target_lang
        )
        self.one_click_thread = oc_thread
        oc_thread.progress.connect(self.update_progress)
        oc_thread.log_message.connect(self.log)
        oc_thread.finished.connect(self.one_click_finished)
        oc_thread.error.connect(self.log_error)
        oc_thread.start()
    
    def one_click_finished(self, success, message):
        """一键汉化结束回调"""
        self.one_click_thread = None
        self.one_click_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            QMessageBox.information(self, "汉化成功", message)
            # 重新加载一遍文件列表，让用户看到翻译好的文件
            self.extract_game_text()
        else:
            QMessageBox.critical(self, "汉化出错", message)
    
    def start_restore(self):
        """触发一键恢复"""
        if not self.game_path:
            QMessageBox.warning(self, "Warning", "No game directory loaded!")
            return
            
        reply = QMessageBox.warning(self, '警告: 一键恢复', 
                                     '此操作将使用系统中的备份文件（.backup）覆盖现有的游戏文本。\n当前已翻译的内容将被还原为原版（或上一次备份的状态）。\n\n确定要继续吗？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.No:
            return

        # 禁用按钮，防止重复点击
        self.restore_btn.setEnabled(False)
        self.one_click_btn.setEnabled(False)
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动恢复线程
        game_path = self.game_path
        if game_path is None:
            return
        rst_thread = RestoreThread(game_path)
        self.restore_thread = rst_thread
        rst_thread.progress.connect(self.update_progress)
        rst_thread.log_message.connect(self.log)
        rst_thread.finished.connect(self.restore_finished)
        rst_thread.start()

    def restore_finished(self, success, message):
        """恢复结束回调"""
        self.restore_thread = None
        self.restore_btn.setEnabled(True)
        self.one_click_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            QMessageBox.information(self, "恢复成功", message)
            # 如果右侧正打开着某个文件，最好刷新一下或者清空，防止数据不一致
            self.text_table.setRowCount(0)
            self.file_label.setText("No file loaded")
            self.text_data = []
            self.current_file = None
        else:
            QMessageBox.warning(self, "恢复提示", message)
        self.update_ui_state()
    
    def load_file_for_translation(self, item):
        """Load file for translation using Parser system."""
        file_info = item.data(Qt.UserRole)  # type: ignore
        file_path = file_info['path']
        
        if not file_path.exists():
            QMessageBox.warning(self, "Warning", f"File not found: {file_path}")
            return
        
        try:
            self.log(f"Loading file: {file_path}")
            
            # Use Parser system instead of manual JSON loading
            from parsers import get_parser  # type: ignore
            
            parser = get_parser(str(file_path))
            segments = parser.parse()
            
            self.text_data = []
            for segment in segments:
                self.text_data.append({
                    'key': segment.location,  # Use precise location as key!
                    'original': segment.text,
                    'translated': segment.translated_text or '',
                    'status': 'pending' if not segment.translated_text else 'translated'
                })
            
            self.current_file = file_path
            self.current_parser: Optional[BaseParser] = parser  # type: ignore  # Store parser for save operation
            self.file_label.setText(f"File: {file_path.name} ({len(self.text_data)} entries)")
            
            # Load into table
            self.text_table.load_text_data(self.text_data)
            
            self.log(f"Successfully loaded {len(self.text_data)} text entries via Parser")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
            self.log_error(f"Error loading file: {e}")
            import traceback
            traceback.print_exc()
        
        self.update_ui_state()
    
    def translate_all(self):
        """Translate all text."""
        if not self.text_data:
            return
        
        engine = self.engine_combo.currentData()
        source_lang = self.source_lang_combo.currentText()
        target_lang = self.target_lang_combo.currentText()
        
        self.translate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # Create translator
        translator = GameTranslator(
            engine=engine,
            source_lang=source_lang,
            target_lang=target_lang,
            delay=0.2
        )
        
        # Create and start translation thread
        current_file = self.current_file
        if current_file is None:
            return
        tr_thread = TranslationThread(
            translator,
            str(current_file),
            str(current_file.parent / f"{current_file.stem}_{target_lang}.json")
        )
        self.translator_thread = tr_thread
        tr_thread.progress.connect(self.update_progress)
        tr_thread.log_message.connect(self.log)
        tr_thread.finished.connect(self.translation_finished)
        tr_thread.error.connect(self.log_error)
        tr_thread.start()
    
    def translate_selected(self):
        """Translate selected text entries."""
        selected_rows = self.text_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Please select rows to translate")
            return
        
        engine = self.engine_combo.currentData()
        source_lang = self.source_lang_combo.currentText()
        target_lang = self.target_lang_combo.currentText()
        
        # Create translator
        translator = GameTranslator(
            engine=engine,
            source_lang=source_lang,
            target_lang=target_lang,
            delay=0.2
        )
        
        # Translate selected rows
        total = len(selected_rows)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        
        for i, row_idx in enumerate(selected_rows):
            row = row_idx.row()
            item1 = self.text_table.item(row, 1)
            item2 = self.text_table.item(row, 2)
            item3 = self.text_table.item(row, 3)
            if item1 is None or item2 is None or item3 is None:
                continue
            original = item1.text()

            if original.strip():
                try:
                    translated = translator.translate(original)
                    item2.setText(translated)
                    item3.setText('translated')
                    item3.setBackground(QColor(200, 255, 200))
                except Exception as e:
                    item3.setText('error')
                    item3.setBackground(QColor(255, 200, 200))
                    self.log_error(f"Error translating '{original}': {e}")
            
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
        
        self.progress_bar.setVisible(False)
        self.log(f"Translated {total} entries")
    
    def update_progress(self, current, total):
        """Update progress bar."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(f"Processing... {current}/{total}")
    
    def translation_finished(self, success, message):
        """Handle translation completion."""
        self.translator_thread = None
        self.translate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.log(f"Translation completed: {message}")
            QMessageBox.information(self, "Success", message)
            
            # Reload current file to show new translations
            if self.current_file:
                for i in range(self.files_list.count()):
                    item = self.files_list.item(i)
                    file_info = item.data(Qt.UserRole)  # type: ignore
                    if file_info and file_info['path'] == self.current_file:
                        self.load_file_for_translation(item)
                        break
        else:
            self.log_error(f"Translation failed: {message}")
            QMessageBox.critical(self, "Error", message)
    
    def save_file(self):
        """Save current translation using Parser system."""
        current_file = self.current_file
        parser = self.current_parser
        if current_file is None or parser is None:
            return
        
        # Get current data from table
        self.text_data = self.text_table.get_text_data()
        
        # Save to original file path
        try:
            # Update segments with translations from table
            segments = []
            for item in self.text_data:
                from parsers.base_parser import TextSegment  # type: ignore
                segment = TextSegment(
                    text=item['original'],
                    location=item['key'],
                    translated_text=item['translated'] or item['original']
                )
                segments.append(segment)
            
            # Use Parser's reconstruct method to preserve nested structure
            # This ensures RPG Maker and other complex formats are saved correctly
            reconstructed = parser.reconstruct(segments)  # type: ignore[attr-defined]
            
            # Create backup
            backup_path = parser.create_backup()  # type: ignore[attr-defined]
            
            # Save using parser
            parser.save(reconstructed, str(current_file))  # type: ignore[attr-defined]
            
            self.log(f"File saved successfully with backup: {os.path.basename(str(backup_path))}")
            QMessageBox.information(self, "Success", f"File saved successfully!\nBackup created: {os.path.basename(str(backup_path))}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
            self.log_error(f"Save error: {e}")
            import traceback
            traceback.print_exc()
    
    def save_file_as(self):
        """Save as new file."""
        if not self.text_data:
            return
        start_dir = self.last_open_dir if self.last_open_dir and Path(self.last_open_dir).exists() else ""
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Translation File", start_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_name:
            try:
                # Get current data from table
                self.text_data = self.text_table.get_text_data()
                
                # Convert from table format to translation format
                translated_data = {}
                for item in self.text_data:
                    translated_data[item['key']] = item['translated'] or item['original']
                
                # For "Save As", we need the original file to preserve structure
                current_file = self.current_file
                if current_file is None:
                    QMessageBox.warning(self, "Warning", "No source file loaded.")
                    return
                from game_extractors import detect_file_encoding  # type: ignore
                encoding = detect_file_encoding(current_file)

                with open(current_file, 'r', encoding=encoding) as f:
                    original_data = json.load(f)  # noqa: F841

                # Apply translations to original structure
                # This ensures we maintain the proper nested format
                output_path = Path(file_name)
                backup_path = save_translated_file(
                    current_file,
                    translated_data,
                    output_path=output_path
                )
                
                self.log(f"File saved as: {file_name}")
                if backup_path:
                    self.log(f"Original backup created: {backup_path}")
                QMessageBox.information(self, "Success", f"File saved successfully!\n{file_name}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
                self.log_error(f"Save error: {e}")
                import traceback
                traceback.print_exc()
    
    def load_translation_file(self):
        """Load a translation file directly."""
        start_dir = self.last_open_dir if self.last_open_dir and Path(self.last_open_dir).exists() else ""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Translation File", start_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_name:
            self.last_open_dir = str(Path(file_name).parent)
            self.settings.setValue("last_game_dir", self.last_open_dir)
            file_info = {
                'path': Path(file_name),
                'type': 'Translation File'
            }
            
            # Create fake list item
            item = QListWidgetItem(f"File: {Path(file_name).name}")
            item.setData(Qt.UserRole, file_info)  # type: ignore
            
            self.load_file_for_translation(item)
    
    def new_project(self):
        """Create new project."""
        self.current_project = None
        self.text_data = []
        self.game_path = None
        self.current_file = None
        
        self.project_label.setText("No project loaded")
        self.file_label.setText("No file loaded")
        self.files_list.clear()
        self.file_filter_input.clear()
        self.text_table.setRowCount(0)
        self.log_text.clear()
        if self.status_engine_label is not None:
            self.status_engine_label.setText("Engine: --")
        
        self.update_ui_state()
    
    def open_project(self):
        """Open existing project."""
        start_dir = ""
        if self.last_open_dir and Path(self.last_open_dir).exists():
            start_dir = self.last_open_dir
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.load_game_directory_from_path(directory)
    
    def show_settings(self):
        """Show settings dialog."""
        QMessageBox.information(self, "Settings", "Settings dialog coming soon!")
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About RPG Game Translator",
            "RPG Game Translator\n\n"
            "A tool for extracting, translating, and replacing RPG game text.\n\n"
            "Features:\n"
            "- Support for multiple game engines\n"
            "- Multiple translation engines (Google, DeepL, etc.)\n"
            "- Visual editing interface\n"
            "- Batch processing\n\n"
            "Version: 1.0.0"
        )
    
    def log(self, message):
        """Add log message."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def log_error(self, error):
        """Add error log message."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] ERROR: {error}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.save_window_state()

        threads = [
            ("translation", self.translator_thread),
            ("extract", self.extractor_thread),
            ("one-click", self.one_click_thread),
            ("restore", self.restore_thread),
        ]

        running_threads = []
        for name, thread in threads:
            if thread is not None and thread.isRunning():
                running_threads.append((name, thread))

        for _, thread in running_threads:
            stop_fn = getattr(thread, "stop", None)
            if callable(stop_fn):
                stop_fn()

        for _, thread in running_threads:
            thread.wait(1200)

        still_running = [(name, thread) for name, thread in running_threads if thread.isRunning()]
        if still_running:
            reply = QMessageBox.question(
                self,
                "Background tasks still running",
                "Some background tasks are still running. Force close now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return

            for _, thread in still_running:
                thread.terminate()
                thread.wait(600)

        event.accept()


def main():
    """Main entry point."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("RPG Game Translator")
    app.setOrganizationName("RPGTranslator")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
