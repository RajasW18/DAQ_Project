import os

files = [
    "page_01_source.py",
    "page_04_drift.py",
    "page_05_working_curve.py",
    "page_06_matrix.py",
    "page_07_master.py",
    "page_08_display.py",
    "page_09_purity.py"
]

for f in files:
    path = os.path.join("ui", "anainf", f)
    if not os.path.exists(path): continue
    
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
        
    if "QShortcut" not in content:
        if "from PyQt6.QtGui import QColor, QIntValidator" in content:
            content = content.replace("from PyQt6.QtGui import QColor, QIntValidator", "from PyQt6.QtGui import QColor, QIntValidator, QKeySequence, QShortcut")
        elif "from PyQt6.QtGui import QColor" in content:
            content = content.replace("from PyQt6.QtGui import QColor", "from PyQt6.QtGui import QColor, QKeySequence, QShortcut")
        elif "from PyQt6.QtGui import (" in content:
            content = content.replace("from PyQt6.QtGui import (", "from PyQt6.QtGui import (\n    QKeySequence, QShortcut,")
    
    old_loop = """        for txt, slot in [
            ("1:OK", self._on_ok),
            ("2:Next", self._on_next),
            ("3:Pre.", self._on_pre),
            ("4:Print", self._on_print),
        ]:
            b = QPushButton(txt)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            bbl.addWidget(b)"""
            
    new_loop = """        for txt, slot in [
            ("1:OK", self._on_ok),
            ("2:Next", self._on_next),
            ("3:Pre.", self._on_pre),
            ("4:Print", self._on_print),
        ]:
            b = QPushButton(txt)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            bbl.addWidget(b)
            # Map specific Numpad key
            key_val = getattr(Qt.Key, f"Key_{txt[0]}")
            QShortcut(QKeySequence(Qt.KeyboardModifier.KeypadModifier | key_val), self).activated.connect(slot)"""

    content = content.replace(old_loop, new_loop)
    
    old_canc = """        canc = QPushButton("9:Cancel")
        canc.setStyleSheet(btn_style)
        canc.clicked.connect(self._on_cancel)
        bbl.addWidget(canc)"""
        
    new_canc = """        canc = QPushButton("9:Cancel")
        canc.setStyleSheet(btn_style)
        canc.clicked.connect(self._on_cancel)
        bbl.addWidget(canc)
        QShortcut(QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_9), self).activated.connect(self._on_cancel)"""
        
    content = content.replace(old_canc, new_canc)
    
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
    
    print(f"Updated {f}")
