"""
SpectraSoft — Page 6: Matrix Element Correction

This page defines correction coefficients for inter-element interference.
It allows correction for:
- Type L: Overlap correction (spectral line interference)
- Type D: Absorption/Excitation correction (matrix effect)

Columns:
- Target: The element being corrected (dropdown from Page 3 elements)
- Type: Correction type (L = Overlap, D = Absorption/Excitation)
- Interfering: The element causing the interference (dropdown from Page 3 elements)
- Coeff: Correction coefficient (editable float)

Rules:
- A single target can have multiple interfering elements
- Type L corrections are additive (subtract interfering contribution)
- Type D corrections are multiplicative (scale the result)
- Coefficients are typically auto-calculated by Regression module

Saved JSON example:
{
    "corrections": [
        {"target": "MN", "type": "L", "interfering": "CR", "coeff": 0.00123456},
        {"target": "MN", "type": "L", "interfering": "MO", "coeff": 0.00098765},
        {"target": "SI", "type": "D", "interfering": "AL", "coeff": 0.00056789}
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
from core.json_export import export_page06_matrix

MAX_CORRECTIONS = 100  # Maximum number of correction rows


class CorrectionPage(QWidget):

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
        bar = QLabel(f"Matrix Correction - {self.group_name}")
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
        title = QLabel("MATRIX ELEMENT CORRECTION")
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

        btn_add = QPushButton("Add Row")
        btn_add.setStyleSheet(btn_style)
        btn_add.clicked.connect(self._on_add)

        btn_delete = QPushButton("Delete Row")
        btn_delete.setStyleSheet(btn_style)
        btn_delete.clicked.connect(self._on_delete)

        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(btn_style)
        btn_clear.clicked.connect(self._on_clear)

        ctrl_layout.addWidget(btn_add)
        ctrl_layout.addWidget(btn_delete)
        ctrl_layout.addWidget(btn_clear)
        ctrl_layout.addStretch()

        info_lbl = QLabel("L = Overlap (subtractive) | D = Absorption/Excitation (multiplicative)")
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
        """Create a table with 4 columns: Target, Type, Interfering, Coeff."""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Target", "Type", "Interfering", "Coeff"])

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
        table.setColumnWidth(0, 100)  # Target
        table.setColumnWidth(1, 80)   # Type
        table.setColumnWidth(2, 100)  # Interfering
        table.setColumnWidth(3, 120)  # Coeff

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Row height
        table.verticalHeader().setDefaultSectionSize(27)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Set initial row count to 0 (user adds rows)
        table.setRowCount(0)
        table.setFixedWidth(440)  # 100 + 80 + 100 + 120 + borders

        return table

    def _get_element_list(self) -> list:
        """Get list of elements from Page 3 data."""
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_03_channel:
                page3_data = g.page_03_channel
                if isinstance(page3_data, list):
                    elements = []
                    for entry in page3_data:
                        ele = entry.get("ele", "").strip()
                        name = entry.get("name", "").strip()
                        if ele:
                            display = f"{ele}" if not name or name == ele else f"{ele} ({name})"
                            elements.append((display, ele))
                    return elements
        finally:
            session.close()
        return []

    def _create_combo(self, items: list, current_value: str = ""):
        """Create a combobox with the given items."""
        combo = QComboBox()
        combo.addItem("")  # Empty option
        for display, value in items:
            combo.addItem(display, value)
        combo.setStyleSheet(
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
        # Set current value if found
        if current_value:
            index = combo.findData(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _add_row(self, data: dict = None):
        """Add a new row to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Get element list
        elements = self._get_element_list()

        # Target column - dropdown
        target_combo = self._create_combo(
            elements,
            data.get("target", "") if data else ""
        )
        self.table.setCellWidget(row, 0, target_combo)

        # Type column - dropdown (L or D)
        type_combo = QComboBox()
        type_combo.addItems(["", "L", "D"])
        type_combo.setStyleSheet(
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
        if data and data.get("type"):
            idx = type_combo.findText(data.get("type", ""))
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 1, type_combo)

        # Interfering column - dropdown
        inter_combo = self._create_combo(
            elements,
            data.get("interfering", "") if data else ""
        )
        self.table.setCellWidget(row, 2, inter_combo)

        # Coeff column - editable float
        coeff_edit = QLineEdit()
        coeff_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        validator = QDoubleValidator(-100.0, 100.0, 8, coeff_edit)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        coeff_edit.setValidator(validator)
        coeff_edit.setStyleSheet(
            "QLineEdit{"
            "background:white;"
            "color:black;"
            "border:1px solid #888888;"
            "font:9pt Arial;"
            "padding:0px 2px;"
            "}"
        )
        if data and data.get("coeff") is not None:
            coeff_edit.setText(f"{data.get('coeff', 0.0):.8f}")
        else:
            coeff_edit.setText("0.00000000")
        self.table.setCellWidget(row, 3, coeff_edit)

        # Update table height
        self._update_table_height()

    def _update_table_height(self):
        """Update table height based on row count."""
        row_count = self.table.rowCount()
        if row_count == 0:
            row_count = 1  # At least show header
        table_height = (row_count * 27) + 27 + 3
        self.table.setFixedHeight(table_height)

    def _populate_from_data(self, data: list):
        """Populate table from saved data."""
        self.table.setRowCount(0)
        for entry in data:
            self._add_row(entry)
        self._update_table_height()

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _collect(self) -> dict:
        """Collect data from table into a dict."""
        corrections = []
        for row in range(self.table.rowCount()):
            target_combo = self.table.cellWidget(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            inter_combo = self.table.cellWidget(row, 2)
            coeff_edit = self.table.cellWidget(row, 3)

            target = target_combo.currentData() if target_combo else ""
            corr_type = type_combo.currentText().strip() if type_combo else ""
            interfering = inter_combo.currentData() if inter_combo else ""
            coeff = 0.0
            if coeff_edit:
                try:
                    coeff = float(coeff_edit.text().strip()) if coeff_edit.text().strip() else 0.0
                except ValueError:
                    coeff = 0.0

            # Only save rows with a target
            if target:
                corrections.append({
                    "target": target,
                    "type": corr_type,
                    "interfering": interfering,
                    "coeff": coeff
                })

        return {"corrections": corrections}

    def _load(self):
        """Load saved corrections from database."""
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_06_matrix:
                data = g.page_06_matrix
                if isinstance(data, dict):
                    corrections = data.get("corrections", [])
                    if corrections:
                        self._populate_from_data(corrections)
                        return
        finally:
            session.close()

        # No data - empty table
        self.table.setRowCount(0)
        self._update_table_height()

    def _save(self):
        """Save corrections to database and mirror to import_data/page_06_matrix.json."""
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_06_matrix = data
                session.commit()
                # ── Mirror to import_data/page_06_matrix.json ──────────
                export_page06_matrix(data)
        finally:
            session.close()

    # =========================================================================
    # Button Actions
    # =========================================================================

    def _on_add(self):
        """Add a new correction row."""
        # Check if we have elements in Page 3
        elements = self._get_element_list()
        if not elements:
            QMessageBox.warning(
                self,
                "No Elements",
                "Please configure Page 3 (Element Information) first.\n"
                "You need at least one element to create corrections."
            )
            return

        # Check if we've reached the maximum
        if self.table.rowCount() >= MAX_CORRECTIONS:
            QMessageBox.warning(
                self,
                "Limit Reached",
                f"Maximum {MAX_CORRECTIONS} corrections allowed."
            )
            return

        self._add_row()

    def _on_delete(self):
        """Delete selected row."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a row to delete.")
            return

        if self.table.rowCount() <= 1:
            self.table.removeRow(current_row)
            self._update_table_height()
            return

        self.table.removeRow(current_row)
        self._update_table_height()

    def _on_clear(self):
        """Clear all rows."""
        if QMessageBox.question(
            self,
            "Clear All",
            "Remove all corrections?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self._update_table_height()

    def _on_ok(self):
        self._save()
        self._show_msg("Saved", "Matrix correction data saved successfully.")

    def _on_next(self):
        self._save()
        try:
            from ui.anainf.page_07_master import MasterCurvePage
            self.main_window.set_right_widget(
                MasterCurvePage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            self._show_msg("Next Page", "Page 7 (Master Curve) is not built yet.")

    def _on_pre(self):
        self._save()
        try:
            from ui.anainf.page_05_working_curve import WorkingCurvePage
            self.main_window.set_right_widget(
                WorkingCurvePage(self.main_window, self.group_id, self.group_name)
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