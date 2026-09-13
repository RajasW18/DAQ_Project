import os

files = [
    "page_01_source.py",
    "page_02_attenuator.py",
    "page_03_channel.py",
    "page_04_drift.py",
    "page_05_working_curve.py",
    "page_06_matrix.py",
    "page_07_master.py",
    "page_08_display.py",
    "page_09_purity.py"
]

new_code = """        for txt, slot, key in [
            ("F1:OK", self._on_ok, "F1"),
            ("F2:Next", self._on_next, "F2"),
            ("F3:Pre.", self._on_pre, "F3"),
            ("F4:Print", self._on_print, "F4"),
        ]:
            b = QPushButton(txt)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            bbl.addWidget(b)
            QShortcut(QKeySequence(key), self).activated.connect(slot)

        bbl.addStretch()

        canc = QPushButton("F9:Cancel")
        canc.setStyleSheet(btn_style)
        canc.clicked.connect(self._on_cancel)
        bbl.addWidget(canc)
        QShortcut(QKeySequence("F9"), self).activated.connect(self._on_cancel)"""

import re

for f in files:
    path = os.path.join("ui", "anainf", f)
    if not os.path.exists(path): continue
    
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    
    # Use regex to find the block from "for txt, slot" to "self._on_cancel)"
    pattern = r"        for txt, slot[^\n]*in \[.*?self\._on_cancel\)"
    match = re.search(pattern, content, flags=re.DOTALL)
    
    if match:
        content = content[:match.start()] + new_code + content[match.end():]
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"Updated {f}")
    else:
        print(f"Could not find match in {f}")
