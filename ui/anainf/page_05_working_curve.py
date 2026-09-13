"""
SpectraSoft — Page 5: Working Curve Coefficients & Channel Skip

This page stores the polynomial coefficients (a, b, c, d) used to convert
drift‑corrected intensity (INT.2) into concentration.

Columns (one row per element from Page 3):
- ELE: Element name (read‑only, from Page 3)
- NAME: Custom name (read‑only, from Page 3)
- a: Cubic coefficient (editable)
- b: Quadratic coefficient (editable)
- c: Linear coefficient (editable)
- d: Intercept (editable)
- 100%: Normalization to 100% (Y/N dropdown)
- Skip Point: Channel skip threshold (editable)

Rules:
- Coefficients are typically auto‑filled by Regression module (Section 7)
- User can also enter them manually
- 100% Correction: Y = normalize to 100%, N = no normalization
- Skip Point: concentration where switching between two wavelengths occurs

Saved JSON example:
{
    "coefficients": [
        {"element": "C", "name": "C", "a": 0.0, "b": 0.00037204, "c": 1.04551920, "d": -0.07728757, "norm": "Y", "skip": 0.0},
        ...
    ]
}
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QDoubleValidator

from core.database import get_session
from core.models import AnalyticalGroup
from core.json_export import export_page05_wc

MAX_ELEMENTS = 32


class WorkingCurvePage(QWidget):

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
        bar = QLabel(f"Working Curve - {self.group_name}")
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
        title = QLabel("WORKING CURVE COEFFICIENTS & CHANNEL SKIP")
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

        # ── Single Centered Table ────────────────────────────────────────
        self.table = self._create_table()
        table_container = QHBoxLayout()
        table_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_container.addWidget(self.table)
        ml.addLayout(table_container)

        # ── Control Buttons ──────────────────────────────────────────────
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

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

        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.setStyleSheet(btn_style)
        btn_reset.clicked.connect(self._on_reset)

        ctrl_layout.addWidget(btn_reset)
        ctrl_layout.addStretch()

        info_lbl = QLabel("Coefficients are usually auto‑filled by Regression module.")
        info_lbl.setStyleSheet(
            "QLabel{"
            "color:#666666;"
            "font:9pt Arial;"
            "border:none;"
            "}"
        )
        ctrl_layout.addWidget(info_lbl)

        ml.addLayout(ctrl_layout)

        # ── Bottom Nav ──────────────────────────────────────────────────
        btn_bar = QWidget()
        btn_bar.setAutoFillBackground(True)
        bbp = btn_bar.palette()
        bbp.setColor(btn_bar.backgroundRole(), Qt.GlobalColor.lightGray)
        btn_bar.setPalette(bbp)

        bbl = QHBoxLayout(btn_bar)
        bbl.setContentsMargins(12, 4, 12, 8)
        bbl.setSpacing(4)

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
    # Table Creation
    # =========================================================================

    def _create_table(self) -> QTableWidget:
        """Create a table with 8 columns: ELE, NAME, a, b, c, d, 100%, Skip."""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            ["ELE", "NAME", "a", "b", "c", "d", "100%", "Skip"]
        )

        # Excel-style styling
        table.setStyleSheet(
            "QTableWidget{"
            "background:white;"
            "color:black;"
            "border:1px solid #888888;"
            "gridline-color:#888888;"
            "font:9pt Arial;"
            "}"
            "QTableWidget::item{"
            "border:1px solid #888888;"
            "padding:0px 4px;"
            "color:black;"
            "}"
            "QHeaderView::section{"
            "background:#0078d7;"
            "color:white;"
            "font:bold 9pt Arial;"
            "border:1px solid #888888;"
            "padding:2px 4px;"
            "}"
            "QTableWidget::item:selected{"
            "background:#cce5ff;"
            "color:black;"
            "}"
            "QTableWidget::item:!selected{"
            "color:black;"
            "}"
            "QTableWidget QLineEdit{"
            "background:white;"
            "color:black;"
            "}"
        )

        # Column widths
        col_widths = [50, 70, 90, 90, 90, 90, 60, 70]
        for i, w in enumerate(col_widths):
            table.setColumnWidth(i, w)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Row height
        table.verticalHeader().setDefaultSectionSize(27)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Initially set 32 rows (will be hidden/used based on Page 3 data)
        table.setRowCount(MAX_ELEMENTS)
        self._populate_empty_rows(table)

        # Calculate table height: rows × 27 + header (27) + small margin
        table_height = (MAX_ELEMENTS * 27) + 27 + 3
        table.setFixedHeight(table_height)

        return table

    def _populate_empty_rows(self, table):
        """Fill rows with default widgets (empty or default values)."""
        for row in range(MAX_ELEMENTS):
            # ELE (read-only, gray)
            ele_item = QTableWidgetItem("")
            ele_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ele_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            ele_item.setBackground(QColor("#e8e8e8"))
            ele_item.setForeground(QColor("black"))
            table.setItem(row, 0, ele_item)

            # NAME (read-only, gray)
            name_item = QTableWidgetItem("")
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            name_item.setBackground(QColor("#e8e8e8"))
            name_item.setForeground(QColor("black"))
            table.setItem(row, 1, name_item)

            # a, b, c, d (editable, white) - use QLineEdit widgets for float input
            for col in range(2, 6):
                edit = QLineEdit("0.00000000")
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                validator = QDoubleValidator(-1000.0, 1000.0, 8, edit)
                validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                edit.setValidator(validator)
                edit.setStyleSheet(
                    "QLineEdit{"
                    "background:white;"
                    "color:black;"
                    "border:1px solid #888888;"
                    "font:9pt Arial;"
                    "padding:0px 2px;"
                    "}"
                )
                table.setCellWidget(row, col, edit)

            # 100% Correction (dropdown Y/N)
            norm_combo = QComboBox()
            norm_combo.addItems(["Y", "N"])
            norm_combo.setCurrentIndex(0)  # default Y
            norm_combo.setStyleSheet(
                "QComboBox{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
                "QComboBox::drop-down{"
                "border:none;"
                "width:12px;"
                "}"
                "QComboBox QAbstractItemView{"
                "background:white;"
                "color:black;"
                "}"
            )
            table.setCellWidget(row, 6, norm_combo)

            # Skip Point (editable, float)
            skip_edit = QLineEdit("0.0000")
            skip_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            skip_validator = QDoubleValidator(0.0, 100.0, 4, skip_edit)
            skip_edit.setValidator(skip_validator)
            skip_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 7, skip_edit)

    def _populate_from_page3(self, data: list):
        """Populate table using Page 3 data (list of dicts)."""
        # Clear all rows first
        for row in range(MAX_ELEMENTS):
            # Reset ELE and NAME to empty
            ele_item = self.table.item(row, 0)
            if ele_item:
                ele_item.setText("")
            name_item = self.table.item(row, 1)
            if name_item:
                name_item.setText("")
            # Reset coefficient fields to 0
            for col in range(2, 6):
                edit = self.table.cellWidget(row, col)
                if edit:
                    edit.setText("0.00000000")
            # Reset 100% to Y
            norm_combo = self.table.cellWidget(row, 6)
            if norm_combo:
                norm_combo.setCurrentIndex(0)  # Y
            # Reset Skip to 0
            skip_edit = self.table.cellWidget(row, 7)
            if skip_edit:
                skip_edit.setText("0.0000")

        # Load saved coefficients if any
        saved_coeffs = {}
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_05_wc:
                coeff_list = g.page_05_wc.get("coefficients", [])
                for entry in coeff_list:
                    key = (entry.get("element", ""), entry.get("name", ""))
                    saved_coeffs[key] = entry
        finally:
            session.close()

        # Fill rows with Page 3 data
        for idx, entry in enumerate(data):
            if idx >= MAX_ELEMENTS:
                break
            row = idx
            ele = entry.get("ele", "")
            name = entry.get("name", "")

            # Set ELE and NAME
            ele_item = self.table.item(row, 0)
            if ele_item:
                ele_item.setText(ele)
            name_item = self.table.item(row, 1)
            if name_item:
                name_item.setText(name)

            # Load saved coefficients if available
            key = (ele, name)
            if key in saved_coeffs:
                coeff = saved_coeffs[key]
                # a, b, c, d
                for col, field in enumerate(["a", "b", "c", "d"], start=2):
                    edit = self.table.cellWidget(row, col)
                    if edit:
                        val = coeff.get(field, 0.0)
                        edit.setText(f"{val:.8f}")
                # 100%
                norm_combo = self.table.cellWidget(row, 6)
                if norm_combo:
                    norm = coeff.get("norm", "Y")
                    idx_norm = 0 if norm == "Y" else 1
                    norm_combo.setCurrentIndex(idx_norm)
                # Skip
                skip_edit = self.table.cellWidget(row, 7)
                if skip_edit:
                    skip = coeff.get("skip", 0.0)
                    skip_edit.setText(f"{skip:.4f}")

    def _collect(self) -> dict:
        """Collect coefficients from table into a dict."""
        coefficients = []
        for row in range(MAX_ELEMENTS):
            ele_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if not ele_item or not name_item:
                continue
            ele = ele_item.text().strip()
            name = name_item.text().strip()
            if not ele:  # skip empty rows
                continue

            # Get coefficient values from cell widgets
            a_edit = self.table.cellWidget(row, 2)
            b_edit = self.table.cellWidget(row, 3)
            c_edit = self.table.cellWidget(row, 4)
            d_edit = self.table.cellWidget(row, 5)
            norm_combo = self.table.cellWidget(row, 6)
            skip_edit = self.table.cellWidget(row, 7)

            def get_float(edit):
                try:
                    return float(edit.text().strip()) if edit else 0.0
                except ValueError:
                    return 0.0

            coefficients.append({
                "element": ele,
                "name": name,
                "a": get_float(a_edit),
                "b": get_float(b_edit),
                "c": get_float(c_edit),
                "d": get_float(d_edit),
                "norm": norm_combo.currentText() if norm_combo else "Y",
                "skip": get_float(skip_edit),
            })

        return {"coefficients": coefficients}

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _load(self):
        """Load Page 3 data and saved coefficients."""
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                page3_data = g.page_03_channel
                if isinstance(page3_data, list):
                    self._populate_from_page3(page3_data)
                else:
                    # If no Page 3 data, keep empty rows
                    pass
        finally:
            session.close()

    def _save(self):
        """Save coefficients to database and mirror to import_data/page_05_wc.json."""
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_05_wc = data
                session.commit()
                # ── Mirror to import_data/page_05_wc.json ──────────────
                export_page05_wc(data)
        finally:
            session.close()

    # =========================================================================
    # Button Actions
    # =========================================================================

    def _on_reset(self):
        """Reset all coefficients to default (0 for a,b,c,d; Y for 100%; 0 for skip)."""
        if QMessageBox.question(
            self,
            "Reset",
            "Reset all coefficients to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            for row in range(MAX_ELEMENTS):
                for col in range(2, 6):
                    edit = self.table.cellWidget(row, col)
                    if edit:
                        edit.setText("0.00000000")
                norm_combo = self.table.cellWidget(row, 6)
                if norm_combo:
                    norm_combo.setCurrentIndex(0)  # Y
                skip_edit = self.table.cellWidget(row, 7)
                if skip_edit:
                    skip_edit.setText("0.0000")

    def _on_ok(self):
        self._save()
        self._show_msg("Saved", "Working curve data saved successfully.")

    def _on_next(self):
        self._save()
        try:
            from ui.anainf.page_06_matrix import CorrectionPage
            self.main_window.set_right_widget(
                CorrectionPage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            self._show_msg("Next Page", "Page 6 (Correction) is not built yet.")

    def _on_pre(self):
        self._save()
        try:
            from ui.anainf.page_04_drift import DriftCorrectionPage
            self.main_window.set_right_widget(
                DriftCorrectionPage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            pass

    def _on_print(self):
        self._show_msg("Print", "Print coming soon.")

    def _on_cancel(self):
        if self._show_question("Cancel", "Discard changes?"):
            self._load()
            self.main_window._show_home_content()

    # =========================================================================
    # Message Box Helpers
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
        return msg.exec() == QMessageBox.StandardButton.Yes