#!/usr/bin/env python3
"""
RPG Game Translator - GUI Launcher
===================================
Simple launcher for the GUI application.
"""

import sys
import os

# Ensure we're in the correct directory
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# Check for PyQt5
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    print("=" * 60)
    print("PyQt5 is not installed!")
    print("=" * 60)
    print("\nTo install the required GUI dependencies, run:")
    print("  pip install PyQt5")
    print("\nOr install all requirements:")
    print("  pip install -r requirements.txt")
    print("\n" + "=" * 60)
    sys.exit(1)

# Import and run the GUI
try:
    from gui_main import main
    main()
except Exception as e:
    print(f"Error starting GUI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
