"""
SpectraSoft — Page 1: Analytical Condition

This page defines the physical parameters for the excitation source and the
sequence of the burn process for an analytical group.

Fields:
- Purge: Argon flush time (in 0.1 sec units)
- SEQ1/SEQ2/SEQ3 Source: Spark type for each sequence (dropdown from Source Codes)
- SEQ1/SEQ2/SEQ3 Preburn: Pre-spark time to homogenize sample (in 0.1 sec units)
- SEQ1/SEQ2/SEQ3 Integ: Integration/measurement window (in 0.1 sec units)
- Clean Source: Spark type for cleaning (dropdown from Source Codes)
- Clean: Cleaning spark time (in 0.1 sec units)

Rules:
- Purge applies only to SEQ1 (SEQ2 and SEQ3 are read-only)
- Clean applies only to Clean column (SEQ1-3 are read-only)
- Preburn and Integ are editable for SEQ1, SEQ2, SEQ3
- Source is editable for SEQ1, SEQ2, SEQ3, and Clean
- All values are stored in the page_01_condition JSON field

Source Types (from Source Codes table):
  - 1: Normal Spark (standard for most elements)
  - 3: Combined Spark (for trace elements like P, S)
  - 4: Oscillation Spark (for gray cast iron)
  - 5: High Power Spark (for carbon in steel)
  - HVS: High Voltage Spark (for aluminum/magnesium alloys)
  - 6: Cleaning Spark (reverse polarity cleaning)

Saved JSON example:
{
    "purge_seq1": "3",
    "source_seq1": "1: Normal Spark",
    "source_seq2": "2: High Power Spark",
    "source_seq3": "0: Fatigue Lamp",
    "source_clean": "5: Cleaning Spark",
    "preburn_seq1": "200",
    "preburn_seq2": "200",
    "preburn_seq3": "0",
    "integ_seq1": "300",
    "integ_seq2": "23",
    "integ_seq3": "0",
    "clean_value": "0"
}
"""


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QFrame, QMessageBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from core.database import get_session
from core.models import AnalyticalGroup, SourceCode
from core.json_export import export_page01_source


def _load_source_options() -> list:
    session = get_session()
    try:
        rows = session.query(SourceCode).order_by(SourceCode.entry_no).all()
        opts = []
        for r in rows:
            if r.name and r.name.strip():
                opts.append(f"{format(r.entry_no, 'X')}: {r.name.strip()}")
        return opts if opts else ["(no sources defined)"]
    finally:
        session.close()


class SourceConditionPage(QWidget):
    def __init__(self, main_window, group_id: int, group_name: str):
        super().__init__()
        self.main_window = main_window
        self.group_id = group_id
        self.group_name = group_name

        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.lightGray)
        self.setPalette(p)

        self._source_opts = _load_source_options()
        self._build_ui()
        self._load()

    # UI Construction
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title Bar ──────────────────────────────────────────────────────
        bar = QLabel(f"Analytical Condition - {self.group_name}")
        bar.setFixedHeight(24)
        bar.setContentsMargins(12, 0, 0, 0)
        bar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        bar.setStyleSheet(
            "background:#5c9bd5;"
            "color:white;"
            "font:bold 10pt Arial;"
        )
        root.addWidget(bar)

        # ── Outer Frame ──────────────────────────────────────────────────
        outer = QFrame()
        outer.setFrameShape(QFrame.Shape.Box)
        outer.setFrameShadow(QFrame.Shadow.Sunken)
        outer.setLineWidth(2)
        outer.setStyleSheet("background:white;")
        root.addWidget(outer, stretch=1)

        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        ol.addWidget(scroll)

        inner = QWidget()
        inner.setAutoFillBackground(True)
        ip = inner.palette()
        ip.setColor(inner.backgroundRole(), Qt.GlobalColor.lightGray)
        inner.setPalette(ip)
        scroll.setWidget(inner)

        ml = QVBoxLayout(inner)
        ml.setContentsMargins(20, 16, 20, 12)
        ml.setSpacing(8)

        # ── Table Title ──────────────────────────────────────────────────
        title = QLabel("SEQUENCE PARAMETERS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "QLabel{"
            "background:#d4d0c8;"
            "color:black;"
            "font:bold 10pt Arial;"
            "border:1px solid #888888;"
            "padding:3px 0px;"
            "}"
        )
        ml.addWidget(title)

        # ── Excel-Style Table ───────────────────────────────────────────
        # Main table frame - flat border
        table = QFrame()
        # Set size policy to prevent the grid from expanding and creating gaps
        table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        table.setStyleSheet(
            "QFrame{"
            "background:white;"
            "border:1px solid #888888;"
            "}"
        )
        table.setFixedHeight(162)

        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # Column Sizes 
        col_label = 60       # Row labels
        col_seq = 140        # Each sequence column
        col_unit = 40        # Unit column
        row_h = 27

        # Helper: Blue Header Label
        def hdr(text, w=col_seq):
            lbl = QLabel(text)
            lbl.setFixedSize(w, row_h)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "QLabel{"
                "background:#0078d7;"
                "color:white;"
                "font:bold 9pt Arial;"
                "border:1px solid #888888;"
                "padding:1px 2px;"
                "}"
            )
            return lbl

        # Helper: Blue Top-Left Corner
        def corner():
            lbl = QLabel("")
            lbl.setFixedSize(col_label, row_h)
            lbl.setStyleSheet(
                "QLabel{"
                "background:#0078d7;"
                "border:1px solid #888888;"
                "}"
            )
            return lbl

        # Helper: Row Label
        def row_lbl(text):
            lbl = QLabel(text)
            lbl.setFixedSize(col_label, row_h)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(
                "QLabel{"
                "background:#d4d0c8;"
                "color:black;"
                "font:9pt Arial;"
                "border:1px solid #888888;"
                "padding:0px 4px;"
                "}"
            )
            return lbl

        # Helper: Unit Label
        def unit(text):
            lbl = QLabel(text)
            lbl.setFixedSize(col_unit, row_h)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(
                "QLabel{"
                "background:#d4d0c8;"
                "color:black;"
                "font:9pt Arial;"
                "border:1px solid #888888;"
                "padding:0px 2px;"
                "}"
            )
            return lbl

        # Helper: Editable Cell
        def edit(default=""):
            e = QLineEdit(str(default))
            e.setFixedSize(col_seq, row_h)
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            e.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            return e

        # Helper: Read-Only Cell
        def ro():
            e = QLineEdit("")
            e.setFixedSize(col_seq, row_h)
            e.setReadOnly(True)
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            e.setStyleSheet(
                "QLineEdit{"
                "background:#f0ece4;"
                "color:#999999;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            return e

        # Helper: Combobox
        def cmb(opts):
            c = QComboBox()
            c.addItems(opts)
            c.setFixedSize(col_seq, row_h)

            # Minimal styling to keep native functionality while enforcing colors
            c.setStyleSheet("""
                QComboBox {
                    background: white;
                    color: black;
                    border: 1px solid #888;
                    padding-left: 4px;
                }
                QComboBox QAbstractItemView {
                    background: white;
                    color: black;
                    selection-background-color: #0078d7;
                    selection-color: white;
                }
            """)
            return c
        
        # ROW 0: Headers (all blue)
        grid.addWidget(corner(), 0, 0)           # Top-left corner - blue
        grid.addWidget(hdr("SEQ1"), 0, 1)
        grid.addWidget(hdr("SEQ2"), 0, 2)
        grid.addWidget(hdr("SEQ3"), 0, 3)
        grid.addWidget(hdr("CLEAN"), 0, 4)
        grid.addWidget(unit(""), 0, 5)

        # ROW 1: Purge
        grid.addWidget(row_lbl("Purge"), 1, 0)
        self._purge = edit("0")
        grid.addWidget(self._purge, 1, 1)
        grid.addWidget(ro(), 1, 2)
        grid.addWidget(ro(), 1, 3)
        grid.addWidget(ro(), 1, 4)
        grid.addWidget(unit("Sec."), 1, 5)

        # ROW 2: Source
        grid.addWidget(row_lbl("Source"), 2, 0)
        self._src1 = cmb(self._source_opts)
        self._src2 = cmb(self._source_opts)
        self._src3 = cmb(self._source_opts)
        self._srcc = cmb(self._source_opts)
        grid.addWidget(self._src1, 2, 1)
        grid.addWidget(self._src2, 2, 2)
        grid.addWidget(self._src3, 2, 3)
        grid.addWidget(self._srcc, 2, 4)
        grid.addWidget(unit(""), 2, 5)

        # ROW 3: Preburn
        grid.addWidget(row_lbl("Preburn"), 3, 0)
        self._pb1 = edit("0")
        self._pb2 = edit("0")
        self._pb3 = edit("0")
        grid.addWidget(self._pb1, 3, 1)
        grid.addWidget(self._pb2, 3, 2)
        grid.addWidget(self._pb3, 3, 3)
        grid.addWidget(ro(), 3, 4)
        grid.addWidget(unit("Sec."), 3, 5)

        # ROW 4: Integ
        grid.addWidget(row_lbl("Integ."), 4, 0)
        self._ig1 = edit("0")
        self._ig2 = edit("0")
        self._ig3 = edit("0")
        grid.addWidget(self._ig1, 4, 1)
        grid.addWidget(self._ig2, 4, 2)
        grid.addWidget(self._ig3, 4, 3)
        grid.addWidget(ro(), 4, 4)
        grid.addWidget(unit("Sec."), 4, 5)

        # ROW 5: Clean
        grid.addWidget(row_lbl("Clean"), 5, 0)
        grid.addWidget(ro(), 5, 1)
        grid.addWidget(ro(), 5, 2)
        grid.addWidget(ro(), 5, 3)
        self._clean = edit("0")
        grid.addWidget(self._clean, 5, 4)
        grid.addWidget(unit("Sec."), 5, 5)

        # Wrap the table in a horizontal layout to prevent it from stretching
        table_wrapper = QHBoxLayout()
        table_wrapper.addStretch()
        table_wrapper.addWidget(table)
        table_wrapper.addStretch()  
        
        ml.addLayout(table_wrapper)
        ml.addStretch()

        # ── Bottom Nav ──────────────────────────────────────────────────
        btn_bar = QWidget()
        btn_bar.setAutoFillBackground(True)
        bbp = btn_bar.palette()
        bbp.setColor(btn_bar.backgroundRole(), Qt.GlobalColor.lightGray)
        btn_bar.setPalette(bbp)

        bbl = QHBoxLayout(btn_bar)
        bbl.setContentsMargins(12, 4, 12, 8)
        bbl.setSpacing(4)

        btn_style = (
            "QPushButton{"
            "background:#d4d0c8;"
            "color:black;"
            "border:2px outset #aaaaaa;"
            "font:9pt Arial;"
            "padding:4px 12px;"
            "min-width:60px;"
            "}"
            "QPushButton:pressed{"
            "border:2px inset #888888;"
            "}"
        )

        for txt, slot, key in [
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
        QShortcut(QKeySequence("F9"), self).activated.connect(self._on_cancel)
        bbl.addWidget(canc)
        QShortcut(QKeySequence(Qt.KeyboardModifier.KeypadModifier | Qt.Key.Key_9), self).activated.connect(self._on_cancel)

        root.addWidget(btn_bar)

    # Data

    def _collect(self):
        return {
            "purge_seq1": self._purge.text(),
            "source_seq1": self._src1.currentText(),
            "source_seq2": self._src2.currentText(),
            "source_seq3": self._src3.currentText(),
            "source_clean": self._srcc.currentText(),
            "preburn_seq1": self._pb1.text(),
            "preburn_seq2": self._pb2.text(),
            "preburn_seq3": self._pb3.text(),
            "integ_seq1": self._ig1.text(),
            "integ_seq2": self._ig2.text(),
            "integ_seq3": self._ig3.text(),
            "clean_value": self._clean.text(),
        }

    def _apply(self, d):
        if not d:
            return
        self._purge.setText(d.get("purge_seq1", "0"))
        self._pb1.setText(d.get("preburn_seq1", "0"))
        self._pb2.setText(d.get("preburn_seq2", "0"))
        self._pb3.setText(d.get("preburn_seq3", "0"))
        self._ig1.setText(d.get("integ_seq1", "0"))
        self._ig2.setText(d.get("integ_seq2", "0"))
        self._ig3.setText(d.get("integ_seq3", "0"))
        self._clean.setText(d.get("clean_value", "0"))

        for combo_w, key in [
            (self._src1, "source_seq1"),
            (self._src2, "source_seq2"),
            (self._src3, "source_seq3"),
            (self._srcc, "source_clean"),
        ]:
            saved = d.get(key, "")
            for i in range(combo_w.count()):
                if combo_w.itemText(i) == saved:
                    combo_w.setCurrentIndex(i)
                    break

    def _save(self):
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_01_source = data
                session.commit()
                # ── Mirror to import_data/page_01_source.json ────────────
                export_page01_source(data)
        finally:
            session.close()

    def _load(self):
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_01_source:
                self._apply(g.page_01_source)
        finally:
            session.close()

    # Buttons
    def _on_ok(self):
        self._save()
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def _on_next(self):
        self._save()
        from ui.anainf.page_02_attenuator import AttenuatorPage
        self.main_window.set_right_widget(
            AttenuatorPage(self.main_window, self.group_id, self.group_name)
        )

    def _on_pre(self):
        self._save()
        self.main_window._show_home_content()

    def _on_print(self):
        QMessageBox.information(self, "Print", "Print coming soon.")

    def _on_cancel(self):
        if QMessageBox.question(
            self,
            "Cancel",
            "Discard changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.main_window._show_home_content()