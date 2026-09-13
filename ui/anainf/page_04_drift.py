"""
SpectraSoft — Page 4: Drift Correction Target Values

This page stores the "Gold Standard" target intensities for recalibration
samples, as well as the drift correction coefficients (α, β, k).

Fields:
- H_Name: One-character name for the High standard (e.g., "A")
- H_Target: Target intensity for the High standard (0.0000)
- L_Name: One-character name for the Low standard (e.g., "B")
- L_Target: Target intensity for the Low standard (0.0000)
- K_Name: One-character name for the 1-point standard (e.g., "C")
- K_Target: Target intensity for the 1-point standard (0.0000)
- α (Alpha): Drift correction slope (1.0 = no correction)
- β (Beta): Drift correction intercept (0.0 = no correction)
- k (K-coeff): 1-point correction factor (1.0 = no correction)

Rules:
- Sample names must be a single character (A-Z)
- Targets are initially 0.0; set via Job 8 (INT.2 for Target) or manual entry
- α, β, k are calculated during recalibration (Job 3) and auto-filed
- All coefficients default to no correction (α=1, β=0, k=1)

Saved JSON example:
{
    "h_sample": "A",
    "l_sample": "B",
    "k_sample": "C",
    "h_target": 0.8500,
    "l_target": 0.1500,
    "k_target": 0.5000,
    "alpha": 1.0,
    "beta": 0.0,
    "k_coeff": 1.0
}
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFrame,
    QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QDoubleValidator

from core.database import get_session
from core.models import AnalyticalGroup
from core.json_export import export_page04_drift


class DriftCorrectionPage(QWidget):

    def __init__(self, main_window, group_id: int, group_name: str):
        super().__init__()
        self.main_window = main_window
        self.group_id = group_id
        self.group_name = group_name

        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.lightGray)
        self.setPalette(p)

        self._build_ui()
        self._load()

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title Bar ──────────────────────────────────────────────────────
        bar = QLabel(f"Drift Correction - {self.group_name}")
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
        title = QLabel("DRIFT CORRECTION TARGET VALUES")
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
        table = QFrame()
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

        # ==================================================================
        # Column Sizes
        # ==================================================================
        col_label = 70       # "Sample" / "H (High)" etc.
        col_name = 80        # Name field
        col_target = 100     # Target
        col_coeff = 100      # α, β, k
        row_h = 27

        # ==================================================================
        # Helper: Blue Header Label
        # ==================================================================
        def hdr(text, w=col_label):
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

        # ==================================================================
        # Helper: Blue Top-Left Corner
        # ==================================================================
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

        # ==================================================================
        # Helper: Row Label
        # ==================================================================
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

        # ==================================================================
        # Helper: Editable Cell (with validator)
        # ==================================================================
        def make_edit(default="", width=col_name, align=Qt.AlignmentFlag.AlignCenter):
            e = QLineEdit(str(default))
            e.setFixedSize(width, row_h)
            e.setAlignment(align)
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

        # ==================================================================
        # Helper: Read-Only Cell
        # ==================================================================
        def ro(width=col_name):
            e = QLineEdit("")
            e.setFixedSize(width, row_h)
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

        # ==================================================================
        # ROW 0: Headers (all blue)
        # ==================================================================
        grid.addWidget(corner(), 0, 0)
        grid.addWidget(hdr("Name", col_name), 0, 1)
        grid.addWidget(hdr("Target", col_target), 0, 2)
        grid.addWidget(hdr("α (Alpha)", col_coeff), 0, 3)
        grid.addWidget(hdr("β (Beta)", col_coeff), 0, 4)
        grid.addWidget(hdr("k", col_coeff), 0, 5)

        # ==================================================================
        # ROW 1: H (High)
        # ==================================================================
        grid.addWidget(row_lbl("H (High)"), 1, 0)
        self.h_name = make_edit("", col_name)
        self.h_target = make_edit("0.0000", col_target)
        self.h_alpha = make_edit("1.0000", col_coeff)
        self.h_beta = make_edit("0.0000", col_coeff)
        self.h_k = make_edit("1.0000", col_coeff)
        grid.addWidget(self.h_name, 1, 1)
        grid.addWidget(self.h_target, 1, 2)
        grid.addWidget(self.h_alpha, 1, 3)
        grid.addWidget(self.h_beta, 1, 4)
        grid.addWidget(self.h_k, 1, 5)

        # ==================================================================
        # ROW 2: L (Low)
        # ==================================================================
        grid.addWidget(row_lbl("L (Low)"), 2, 0)
        self.l_name = make_edit("", col_name)
        self.l_target = make_edit("0.0000", col_target)
        self.l_alpha = ro(col_coeff)
        self.l_beta = ro(col_coeff)
        self.l_k = ro(col_coeff)
        grid.addWidget(self.l_name, 2, 1)
        grid.addWidget(self.l_target, 2, 2)
        grid.addWidget(self.l_alpha, 2, 3)
        grid.addWidget(self.l_beta, 2, 4)
        grid.addWidget(self.l_k, 2, 5)

        # ==================================================================
        # ROW 3: K (1-Point)
        # ==================================================================
        grid.addWidget(row_lbl("K (1-pt)"), 3, 0)
        self.k_name = make_edit("", col_name)
        self.k_target = make_edit("0.0000", col_target)
        self.k_alpha = ro(col_coeff)
        self.k_beta = ro(col_coeff)
        self.k_k = ro(col_coeff)
        grid.addWidget(self.k_name, 3, 1)
        grid.addWidget(self.k_target, 3, 2)
        grid.addWidget(self.k_alpha, 3, 3)
        grid.addWidget(self.k_beta, 3, 4)
        grid.addWidget(self.k_k, 3, 5)

        # ==================================================================
        # ROW 4: Informational notes
        # ==================================================================
        note = QLabel(
            "Note: H and L are for 2-point recalibration; K is for 1-point recalibration.\n"
            "Targets are set via Job 8 (INT.2 for Target). α, β, k are calculated during recalibration (Job 3)."
        )
        note.setWordWrap(True)
        note.setFixedHeight(50)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(
            "QLabel{"
            "background:#f0ece4;"
            "color:#555555;"
            "font:9pt Arial;"
            "border:1px solid #888888;"
            "padding:4px 6px;"
            "}"
        )
        grid.addWidget(note, 4, 0, 1, 6)

        ml.addWidget(table)
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

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _collect(self) -> dict:
        return {
            "h_sample": self.h_name.text().strip(),
            "l_sample": self.l_name.text().strip(),
            "k_sample": self.k_name.text().strip(),
            "h_target": self._to_float(self.h_target.text()),
            "l_target": self._to_float(self.l_target.text()),
            "k_target": self._to_float(self.k_target.text()),
            "alpha": self._to_float(self.h_alpha.text()),
            "beta": self._to_float(self.h_beta.text()),
            "k_coeff": self._to_float(self.h_k.text()),
        }

    def _apply(self, d: dict):
        if not d:
            d = {}
        self.h_name.setText(d.get("h_sample", ""))
        self.l_name.setText(d.get("l_sample", ""))
        self.k_name.setText(d.get("k_sample", ""))
        self.h_target.setText(f"{d.get('h_target', 0.0):.4f}")
        self.l_target.setText(f"{d.get('l_target', 0.0):.4f}")
        self.k_target.setText(f"{d.get('k_target', 0.0):.4f}")
        self.h_alpha.setText(f"{d.get('alpha', 1.0):.4f}")
        self.h_beta.setText(f"{d.get('beta', 0.0):.4f}")
        self.h_k.setText(f"{d.get('k_coeff', 1.0):.4f}")

    def _to_float(self, text: str) -> float:
        try:
            return float(text.strip()) if text.strip() else 0.0
        except ValueError:
            return 0.0

    def _save(self):
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_04_drift = data
                session.commit()
                # ── Mirror to import_data/page_04_drift.json ────────────
                export_page04_drift(data)
        finally:
            session.close()

    def _load(self):
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_04_drift:
                self._apply(g.page_04_drift)
            else:
                self._apply({})
        finally:
            session.close()

    # =========================================================================
    # Message Box Helper
    # =========================================================================

    def _show_msg(self, title, text, icon=QMessageBox.Icon.Information):
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStyleSheet(
            "QLabel{color:black;font:9pt Arial;}"
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
        msg.exec()

    def _show_question(self, title, text):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setStyleSheet(
            "QLabel{color:black;font:9pt Arial;}"
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
        return msg.exec()

    # =========================================================================
    # Buttons
    # =========================================================================

    def _on_ok(self):
        self._save()
        self._show_msg("Saved", "Drift correction data saved successfully.")

    def _on_next(self):
        self._save()
        try:
            from ui.anainf.page_05_working_curve import WorkingCurvePage
            self.main_window.set_right_widget(
                WorkingCurvePage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            self._show_msg("Next Page", "Page 5 (Working Curve) is not built yet.")

    def _on_pre(self):
        self._save()
        try:
            from ui.anainf.page_03_channel import ChannelPage
            self.main_window.set_right_widget(
                ChannelPage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            pass

    def _on_print(self):
        self._show_msg("Print", "Print coming soon.")

    def _on_cancel(self):
        if self._show_question("Cancel", "Discard changes?") == QMessageBox.StandardButton.Yes:
            self._load()
            self.main_window._show_home_content()