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
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QPushButton, QTextEdit, QTreeView,
                                 QSplitter, QLabel, QProgressBar, QMessageBox,
                                 QGroupBox, QComboBox, QCheckBox, QFileDialog,
                                 QLineEdit, QPlainTextEdit, QTabWidget, QListWidget,
                                 QListWidgetItem, QMenu, QAction, QToolBar, QStatusBar,
                                 QDockWidget, QTableWidget, QTableWidgetItem, QAbstractItemView)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDir, QModelIndex, QTimer
    from PyQt5.QtGui import QIcon, QFont, QColor, QStandardItemModel, QStandardItem
except ImportError:
    print("PyQt5 is not installed. Please install it with:")
    print("pip install PyQt5")
    sys.exit(1)

import json
import time
from typing import List, Dict, Any, Optional
import threading

# Import project modules
try:
    from core.translator import GameTranslator
    from parsers import get_supported_formats
    from translators import get_available_engines
    from game_extractors import detect_game_engine, extract_game_text, convert_to_translation_format, save_translated_file
except ImportError:
    # Direct execution
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.translator import GameTranslator
    from parsers import get_supported_formats
    from translators import get_available_engines
    from game_extractors import detect_game_engine, extract_game_text, convert_to_translation_format, save_translated_file


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


class GameTextExtractorThread(QThread):
    """Worker thread for extracting game text."""
    
    progress = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, list)  # success, extracted_files
    error = pyqtSignal(str)
    
    def __init__(self, game_path):
        super().__init__()
        self.game_path = game_path
    
    def run(self):
        """Extract game text in background."""
        try:
            self.log_message.emit(f"Detecting game engine in: {self.game_path}")
            
            # Detect game engine
            engine_info = detect_game_engine(self.game_path)
            if not engine_info:
                self.error.emit("Could not detect game engine")
                self.finished.emit(False, [])
                return
            
            self.log_message.emit(f"Detected: {engine_info['engine']} v{engine_info.get('version', 'unknown')}")
            
            # Extract text
            self.log_message.emit("Extracting text files...")
            extracted_files = extract_game_text(self.game_path, engine_info)
            
            self.finished.emit(True, extracted_files)
            
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, [])


class TextTableWidget(QTableWidget):
    """Custom table widget for displaying text entries."""
    
    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Key", "Original Text", "Translated Text", "Status"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
    
    def load_text_data(self, text_data: List[Dict]):
        """Load text data into table."""
        self.setRowCount(len(text_data))
        
        for row, item in enumerate(text_data):
            # Key
            key_item = QTableWidgetItem(item.get('key', ''))
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 0, key_item)
            
            # Original text
            orig_item = QTableWidgetItem(item.get('original', ''))
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 1, orig_item)
            
            # Translated text (editable)
            trans_item = QTableWidgetItem(item.get('translated', ''))
            self.setItem(row, 2, trans_item)
            
            # Status
            status = item.get('status', 'pending')
            status_item = QTableWidgetItem(status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            
            # Color code status
            if status == 'translated':
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            elif status == 'pending':
                status_item.setBackground(QColor(255, 255, 200))  # Light yellow
            elif status == 'error':
                status_item.setBackground(QColor(255, 200, 200))  # Light red
            
            self.setItem(row, 3, status_item)
    
    def get_text_data(self) -> List[Dict]:
        """Get text data from table."""
        data = []
        for row in range(self.rowCount()):
            data.append({
                'key': self.item(row, 0).text(),
                'original': self.item(row, 1).text(),
                'translated': self.item(row, 2).text(),
                'status': self.item(row, 3).text()
            })
        return data


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPG Game Translator")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize data
        self.current_project = None
        self.text_data = []
        self.game_path = None
        self.current_file = None
        self.translator_thread = None
        self.extractor_thread = None
        
        # Setup UI
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Update UI state
        self.update_ui_state()
    
    def setup_ui(self):
        """Setup the main UI."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
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
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
    
    def create_left_panel(self):
        """Create left panel with project/file management."""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Project info group
        project_group = QGroupBox("Project")
        project_layout = QVBoxLayout()
        
        self.project_label = QLabel("No project loaded")
        self.project_label.setWordWrap(True)
        project_layout.addWidget(self.project_label)
        
        self.load_game_btn = QPushButton("Load Game Directory")
        self.load_game_btn.clicked.connect(self.load_game_directory)
        project_layout.addWidget(self.load_game_btn)
        
        project_group.setLayout(project_layout)
        left_layout.addWidget(project_group)
        
        # Extracted files list
        files_group = QGroupBox("Extracted Files")
        files_layout = QVBoxLayout()
        
        self.files_list = QListWidget()
        self.files_list.itemDoubleClicked.connect(self.load_file_for_translation)
        files_layout.addWidget(self.files_list)
        
        self.extract_text_btn = QPushButton("Extract Game Text")
        self.extract_text_btn.clicked.connect(self.extract_game_text)
        self.extract_text_btn.setEnabled(False)
        files_layout.addWidget(self.extract_text_btn)
        
        files_group.setLayout(files_layout)
        left_layout.addWidget(files_group)
        
        return left_widget
    
    def create_right_panel(self):
        """Create right panel with translation interface."""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # File info
        self.file_label = QLabel("No file loaded")
        right_layout.addWidget(self.file_label)
        
        # Text table
        self.text_table = TextTableWidget()
        right_layout.addWidget(self.text_table)
        
        # Translation controls
        controls_group = QGroupBox("Translation Settings")
        controls_layout = QHBoxLayout()
        
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
        right_layout.addWidget(controls_group)
        
        # Log output
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        return right_widget
    
    def setup_menus(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Project", self)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Project", self)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        load_file_action = QAction("Load Translation File", self)
        load_file_action.triggered.connect(self.load_translation_file)
        file_menu.addAction(load_file_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
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
        self.statusBar().showMessage("Ready")
    
    def update_ui_state(self):
        """Update UI state based on current data."""
        has_project = self.game_path is not None
        has_file = self.current_file is not None
        has_text = len(self.text_data) > 0
        
        self.extract_text_btn.setEnabled(has_project)
        self.translate_btn.setEnabled(has_text)
        self.translate_selected_btn.setEnabled(has_text)
    
    def load_game_directory(self):
        """Load game directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Game Directory", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.game_path = Path(directory)
            self.project_label.setText(f"Game: {self.game_path.name}")
            
            # Try to auto-detect engine
            try:
                engine_info = detect_game_engine(self.game_path)
                if engine_info:
                    self.log(f"Detected game engine: {engine_info['engine']}")
                else:
                    self.log("Could not auto-detect game engine")
            except Exception as e:
                self.log(f"Error detecting game engine: {e}")
            
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
        self.extractor_thread = GameTextExtractorThread(self.game_path)
        self.extractor_thread.progress.connect(self.update_progress)
        self.extractor_thread.log_message.connect(self.log)
        self.extractor_thread.finished.connect(self.extraction_finished)
        self.extractor_thread.error.connect(self.log_error)
        self.extractor_thread.start()
    
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
                item.setData(Qt.UserRole, file_info)
                self.files_list.addItem(item)
        else:
            QMessageBox.critical(self, "Error", "Text extraction failed!")
        
        self.update_ui_state()
    
    def load_file_for_translation(self, item):
        """Load file for translation using Parser system."""
        file_info = item.data(Qt.UserRole)
        file_path = file_info['path']
        
        if not file_path.exists():
            QMessageBox.warning(self, "Warning", f"File not found: {file_path}")
            return
        
        try:
            self.log(f"Loading file: {file_path}")
            
            # Use Parser system instead of manual JSON loading
            from parsers import get_parser
            
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
            self.current_parser = parser  # Store parser for save operation
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
        self.translator_thread = TranslationThread(
            translator, 
            self.current_file,
            self.current_file.parent / f"{self.current_file.stem}_{target_lang}.json"
        )
        self.translator_thread.progress.connect(self.update_progress)
        self.translator_thread.log_message.connect(self.log)
        self.translator_thread.finished.connect(self.translation_finished)
        self.translator_thread.error.connect(self.log_error)
        self.translator_thread.start()
    
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
            original = self.text_table.item(row, 1).text()
            
            if original.strip():
                try:
                    translated = translator.translate(original)
                    self.text_table.item(row, 2).setText(translated)
                    self.text_table.item(row, 3).setText('translated')
                    self.text_table.item(row, 3).setBackground(QColor(200, 255, 200))
                except Exception as e:
                    self.text_table.item(row, 3).setText('error')
                    self.text_table.item(row, 3).setBackground(QColor(255, 200, 200))
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
        else:
            self.log_error(f"Translation failed: {message}")
            QMessageBox.critical(self, "Error", message)
    
    def save_file(self):
        """Save current translation using Parser system."""
        if not self.current_file or not hasattr(self, 'current_parser'):
            return
        
        # Get current data from table
        self.text_data = self.text_table.get_text_data()
        
        # Save to original file path
        try:
            # Update segments with translations from table
            segments = []
            for item in self.text_data:
                from parsers.base_parser import TextSegment
                segment = TextSegment(
                    text=item['original'],
                    location=item['key'],
                    translated_text=item['translated'] or item['original']
                )
                segments.append(segment)
            
            # Use Parser's reconstruct method to preserve nested structure
            # This ensures RPG Maker and other complex formats are saved correctly
            reconstructed = self.current_parser.reconstruct(segments)
            
            # Create backup
            backup_path = self.current_parser.create_backup()
            
            # Save using parser
            self.current_parser.save(reconstructed, str(self.current_file))
            
            self.log(f"File saved successfully with backup: {backup_path.name}")
            QMessageBox.information(self, "Success", f"File saved successfully!\nBackup created: {backup_path.name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
            self.log_error(f"Save error: {e}")
            import traceback
            traceback.print_exc()
    
    def save_file_as(self):
        """Save as new file."""
        if not self.text_data:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Translation File", "",
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
                
                # For "Save As", we need to preserve the original format structure
                # Load original file first
                from game_extractors import detect_file_encoding
                encoding = detect_file_encoding(self.current_file)
                
                with open(self.current_file, 'r', encoding=encoding) as f:
                    original_data = json.load(f)
                
                # Apply translations to original structure
                # This ensures we maintain the proper nested format
                output_path = Path(file_name)
                backup_path = save_translated_file(
                    self.current_file,
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
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Translation File", "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_name:
            file_info = {
                'path': Path(file_name),
                'type': 'Translation File'
            }
            
            # Create fake list item
            item = QListWidgetItem(f"File: {Path(file_name).name}")
            item.setData(Qt.UserRole, file_info)
            
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
        self.text_table.setRowCount(0)
        self.log_text.clear()
        
        self.update_ui_state()
    
    def open_project(self):
        """Open existing project."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.load_game_directory()
    
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
        # Stop any running threads
        if self.translator_thread and self.translator_thread.isRunning():
            self.translator_thread.stop()
            self.translator_thread.wait()
        
        if self.extractor_thread and self.extractor_thread.isRunning():
            self.extractor_thread.terminate()
            self.extractor_thread.wait()
        
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("RPG Game Translator")
    app.setOrganizationName("RPGTranslator")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
