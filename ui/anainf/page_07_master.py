"""
SpectraSoft — Page 7: Master Curve Correction

This page defines master curve correction parameters for fine-tuning results
using a known standard sample.

Columns (one row per element from Page 3):
- ELE: Element name (read‑only, from Page 3)
- NAME: Custom name (read‑only, from Page 3)
- Sample: One-character sample name (editable)
- Target: Target concentration (editable)
- D1: Correction not required if result within target ± D1 (editable)
- D2: Correction required if outside D1 but within D2 (editable)
- AC: Additive correction (auto‑calculated or manual)
- MC: Multiplicative correction (auto‑calculated or manual)

Rules:
- D1 and D2 are control limits
- If result is within ±D1: no correction (AC=0, MC=1)
- If outside D1 but within ±D2: apply correction
- If outside ±D2: error display
- AC and MC are typically auto‑calculated during Job 4

Saved JSON example:
{
    "corrections": [
        {"element": "C", "name": "C", "sample": "M", "target": 3.5000, "d1": 0.1000, "d2": 0.2000, "ac": 0.0, "mc": 1.0},
        ...
    ]
}
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QDoubleValidator

from core.database import get_session
from core.models import AnalyticalGroup
from core.json_export import export_page07_master

MAX_ELEMENTS = 32


class MasterCurvePage(QWidget):

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
        bar = QLabel(f"Master Curve - {self.group_name}")
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
        title = QLabel("MASTER CURVE CORRECTION")
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

        # ── Info Text ────────────────────────────────────────────────────
        info = QLabel(
            "D1 = No correction if result within target ± D1\n"
            "D2 = Apply correction if outside D1 but within D2\n"
            "AC = Additive correction | MC = Multiplicative correction"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(
            "QLabel{"
            "background:#f0ece4;"
            "color:#555555;"
            "font:9pt Arial;"
            "border:1px solid #888888;"
            "padding:4px 6px;"
            "}"
        )
        ml.addWidget(info)

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

        info_lbl = QLabel("AC and MC are auto‑calculated during Master Curve Recalibration (Job 4)")
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
        """Create a table with 8 columns: ELE, NAME, Sample, Target, D1, D2, AC, MC."""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            ["ELE", "NAME", "Sample", "Target", "D1", "D2", "AC", "MC"]
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
        col_widths = [50, 70, 60, 80, 70, 70, 80, 80]
        for i, w in enumerate(col_widths):
            table.setColumnWidth(i, w)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Row height
        table.verticalHeader().setDefaultSectionSize(27)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Set rows
        table.setRowCount(MAX_ELEMENTS)
        self._populate_empty_rows(table)

        # Calculate table height
        table_height = (MAX_ELEMENTS * 27) + 27 + 3
        table.setFixedHeight(table_height)

        return table

    def _populate_empty_rows(self, table):
        """Fill rows with default widgets."""
        validator = QDoubleValidator(-1000.0, 1000.0, 4, None)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

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

            # Sample (editable, max 1 char)
            sample_edit = QLineEdit("")
            sample_edit.setMaxLength(1)
            sample_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sample_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 2, sample_edit)

            # Target, D1, D2, AC, MC (editable floats)
            for col, default in [(3, "0.0000"), (4, "0.0000"), (5, "0.0000"), (6, "0.0000"), (7, "1.0000")]:
                edit = QLineEdit(default)
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def _populate_from_page3(self, data: list):
        """Populate table using Page 3 data."""
        # Clear all rows
        for row in range(MAX_ELEMENTS):
            ele_item = self.table.item(row, 0)
            if ele_item:
                ele_item.setText("")
            name_item = self.table.item(row, 1)
            if name_item:
                name_item.setText("")
            sample_edit = self.table.cellWidget(row, 2)
            if sample_edit:
                sample_edit.setText("")
            for col in range(3, 8):
                edit = self.table.cellWidget(row, col)
                if edit:
                    edit.setText("0.0000" if col != 7 else "1.0000")

        # Load saved data
        saved_data = {}
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_07_master:
                corrections = g.page_07_master.get("corrections", [])
                for entry in corrections:
                    key = (entry.get("element", ""), entry.get("name", ""))
                    saved_data[key] = entry
        finally:
            session.close()

        # Fill rows with Page 3 data
        for idx, entry in enumerate(data):
            if idx >= MAX_ELEMENTS:
                break
            row = idx
            ele = entry.get("ele", "")
            name = entry.get("name", "")

            ele_item = self.table.item(row, 0)
            if ele_item:
                ele_item.setText(ele)
            name_item = self.table.item(row, 1)
            if name_item:
                name_item.setText(name)

            key = (ele, name)
            if key in saved_data:
                saved = saved_data[key]
                sample_edit = self.table.cellWidget(row, 2)
                if sample_edit:
                    sample_edit.setText(saved.get("sample", ""))
                for col, field in enumerate(["target", "d1", "d2", "ac", "mc"], start=3):
                    edit = self.table.cellWidget(row, col)
                    if edit:
                        val = saved.get(field, 0.0 if field != "mc" else 1.0)
                        if field == "mc":
                            edit.setText(f"{val:.4f}")
                        else:
                            edit.setText(f"{val:.4f}")

    def _collect(self) -> dict:
        """Collect data from table into a dict."""
        corrections = []
        for row in range(MAX_ELEMENTS):
            ele_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if not ele_item or not name_item:
                continue
            ele = ele_item.text().strip()
            name = name_item.text().strip()
            if not ele:
                continue

            sample_edit = self.table.cellWidget(row, 2)
            target_edit = self.table.cellWidget(row, 3)
            d1_edit = self.table.cellWidget(row, 4)
            d2_edit = self.table.cellWidget(row, 5)
            ac_edit = self.table.cellWidget(row, 6)
            mc_edit = self.table.cellWidget(row, 7)

            def get_float(edit, default=0.0):
                try:
                    return float(edit.text().strip()) if edit and edit.text().strip() else default
                except ValueError:
                    return default

            corrections.append({
                "element": ele,
                "name": name,
                "sample": sample_edit.text().strip() if sample_edit else "",
                "target": get_float(target_edit, 0.0),
                "d1": get_float(d1_edit, 0.0),
                "d2": get_float(d2_edit, 0.0),
                "ac": get_float(ac_edit, 0.0),
                "mc": get_float(mc_edit, 1.0),
            })

        return {"corrections": corrections}

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _load(self):
        """Load Page 3 data and saved corrections."""
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                page3_data = g.page_03_channel
                if isinstance(page3_data, list):
                    self._populate_from_page3(page3_data)
        finally:
            session.close()

    def _save(self):
        """Save corrections to database and mirror to import_data/page_07_master.json."""
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_07_master = data
                session.commit()
                # ── Mirror to import_data/page_07_master.json ──────────
                export_page07_master(data)
        finally:
            session.close()

    # =========================================================================
    # Button Actions
    # =========================================================================

    def _on_reset(self):
        if QMessageBox.question(
            self,
            "Reset",
            "Reset all values to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            for row in range(MAX_ELEMENTS):
                sample_edit = self.table.cellWidget(row, 2)
                if sample_edit:
                    sample_edit.setText("")
                for col, default in [(3, "0.0000"), (4, "0.0000"), (5, "0.0000"), (6, "0.0000"), (7, "1.0000")]:
                    edit = self.table.cellWidget(row, col)
                    if edit:
                        edit.setText(default)

    def _on_ok(self):
        self._save()
        self._show_msg("Saved", "Master curve data saved successfully.")

    def _on_next(self):
        self._save()
        try:
            from ui.anainf.page_08_display import DisplayPage
            self.main_window.set_right_widget(
                DisplayPage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            self._show_msg("Next Page", "Page 8 (Display) is not built yet.")

    def _on_pre(self):
        self._save()
        try:
            from ui.anainf.page_06_matrix import CorrectionPage
            self.main_window.set_right_widget(
                CorrectionPage(self.main_window, self.group_id, self.group_name)
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