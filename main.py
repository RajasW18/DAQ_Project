"""
SpectraSoft — Main Entry Point
Run:  python main.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from core.database import init_db
from ui.main_window import MainWindow


def main():
    init_db()

    app = QApplication(sys.argv)
    app.setStyle("Windows")

    # Only set background on the main window — NOT on every widget
    # This prevents text from becoming invisible
    app.setStyleSheet(
        "QMainWindow { background: #d4d0c8; }"
        "QMenuBar { background: #d4d0c8; color: black; }"
        "QMenuBar::item { background: #d4d0c8; color: black; }"
        "QMenuBar::item:selected { background: #0078d7; color: white; }"
        "QMenu { background: #d4d0c8; color: black; }"
        "QMenu::item:selected { background: #0078d7; color: white; }"
        "QStatusBar { background: #d4d0c8; color: black; }"
    )

    app.setFont(QFont("Arial", 9))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()