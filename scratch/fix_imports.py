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
        
    if "QShortcut" in content and "from PyQt6.QtGui import" not in content and "import QShortcut" not in content:
        content = content.replace("from PyQt6.QtCore import Qt\n", "from PyQt6.QtCore import Qt\nfrom PyQt6.QtGui import QKeySequence, QShortcut\n")
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"Fixed imports in {f}")
    elif "QShortcut" in content and "import QShortcut" not in content:
        # Just in case they had QtGui but missing QShortcut
        if "from PyQt6.QtGui import QColor, QIntValidator" in content:
            content = content.replace("from PyQt6.QtGui import QColor, QIntValidator", "from PyQt6.QtGui import QColor, QIntValidator, QKeySequence, QShortcut")
            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
            print(f"Fixed imports in {f} (appended)")
