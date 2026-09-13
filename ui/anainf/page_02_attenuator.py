"""
SpectraSoft — Page 2: Attenuator Settings

This page sets the sensitivity (ATT) for each element channel.
ATT values range from 0 to 63 and control the gain of each PMT detector.

Columns:
- Element: Element name (read-only, from master table)
- ITG: Integrator number (read-only, from master table)
- W.L.: Wavelength (read-only, from master table)
- ATT: Attenuator value (0-63, editable)

Rules:
- ATT values must be between 0 and 63
- Values are saved per element per group, keyed by ITG No.
- Each element can have only one ATT value

Saved JSON example:
{
    "rows": [
        {"itg_no": 1, "element": "FE", "wavelength": "271.4", "att_value": 45},
        {"itg_no": 2, "element": "C", "wavelength": "193.0", "att_value": 12},
        {"itg_no": 3, "element": "SI", "wavelength": "212.4", "att_value": 30},
        ...
    ]
}
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIntValidator, QKeySequence, QShortcut

from core.database import get_session
from core.models import AnalyticalGroup, MasterElement
from core.json_export import export_attenuator


class AttenuatorPage(QWidget):

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
        bar = QLabel(f"Attenuator Settings - {self.group_name}")
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
        title = QLabel("ATTENUATOR SETTINGS")
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

        # ── Get Elements ──────────────────────────────────────────────────
        session = get_session()
        try:
            # Order by itg_no (primary key)
            elements = session.query(MasterElement).order_by(MasterElement.itg_no).all()
            element_count = len(elements)
        finally:
            session.close()

        # If no elements exist, show empty tables
        if element_count == 0:
            elements = []

        # Split into two halves
        half = (element_count + 1) // 2
        left_elements = elements[:half]
        right_elements = elements[half:]

        # Pad to ensure both tables have same number of rows
        max_rows = max(len(left_elements), len(right_elements))
        if max_rows == 0:
            max_rows = 1  # At least one empty row to show the table
        if len(left_elements) < max_rows:
            left_elements = left_elements + [None] * (max_rows - len(left_elements))
        if len(right_elements) < max_rows:
            right_elements = right_elements + [None] * (max_rows - len(right_elements))

        # ── Tables Container ─────────────────────────────────────────────
        tables_container = QHBoxLayout()
        tables_container.setSpacing(20)
        tables_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create left table with correct height
        self._left_table = self._create_table(max_rows)
        self._populate_table(self._left_table, left_elements)

        # Create right table with same height
        self._right_table = self._create_table(max_rows)
        self._populate_table(self._right_table, right_elements)

        tables_container.addWidget(self._left_table)
        tables_container.addWidget(self._right_table)

        # Wrap in a container with stretch for centering
        wrapper = QHBoxLayout()
        wrapper.addStretch()
        wrapper.addLayout(tables_container)
        wrapper.addStretch()

        ml.addLayout(wrapper)
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
    # Table Creation
    # =========================================================================

    def _create_table(self, row_count: int) -> QTableWidget:
        """Create a single Excel-style table with 4 columns."""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Element", "ITG", "W.L.", "ATT"])

        # Excel-style table styling
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
            "QLineEdit{"
            "background:white;"
            "color:black;"
            "}"
        )

        # Column widths
        table.setColumnWidth(0, 70)   # Element
        table.setColumnWidth(1, 50)   # ITG
        table.setColumnWidth(2, 80)   # Wavelength
        table.setColumnWidth(3, 70)   # ATT

        # Turn off scrollbars to avoid layout shifting
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )

        # Row height - 27px consistent
        table.verticalHeader().setDefaultSectionSize(27)

        # Set row count
        table.setRowCount(row_count)

        # Calculate exact table dimensions: 70 + 50 + 80 + 70 + borders
        table.setFixedWidth(274)  # + 4px for borders

        # Height: rows × 27 + header (27) + borders
        table_height = (row_count * 27) + 27 + 3
        table.setFixedHeight(table_height)

        return table

    # =========================================================================
    # Table Population
    # =========================================================================

    def _populate_table(self, table, elements):
        """Populate a table with element data."""
        session = get_session()
        try:
            saved_values = {}
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_02_attenuator and g.page_02_attenuator.get("rows"):
                for r in g.page_02_attenuator["rows"]:
                    # Use itg_no as the key if present, else fallback to (element, wavelength)
                    itg = r.get("itg_no")
                    if itg is not None:
                        saved_values[itg] = r.get("att_value", 0)
                    else:
                        # old format: fallback to (element, wavelength)
                        saved_values[(r["element"], r["wavelength"])] = r.get("att_value", 0)
        finally:
            session.close()

        for row, me in enumerate(elements):
            if me is None:
                # Empty row (padding)
                for col in range(4):
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    if col < 3:
                        item.setBackground(QColor("#e8e8e8"))
                    else:
                        item.setBackground(QColor("white"))
                    table.setItem(row, col, item)
                continue

            # Handle both model objects and dicts
            if hasattr(me, 'ele_name'):
                ele = me.ele_name or ""
                itg = me.itg_no
                wl = me.wavelength or ""
            else:
                ele = me.get("ele_name", "")
                itg = me.get("itg_no", 0)
                wl = me.get("wavelength", "")

            # Element (read-only, grayish)
            ele_item = QTableWidgetItem(ele)
            ele_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ele_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            ele_item.setBackground(QColor("#e8e8e8"))
            ele_item.setForeground(QColor("black"))
            table.setItem(row, 0, ele_item)

            # ITG (read-only, grayish)
            itg_item = QTableWidgetItem(str(itg))
            itg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            itg_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            itg_item.setBackground(QColor("#e8e8e8"))
            itg_item.setForeground(QColor("black"))
            table.setItem(row, 1, itg_item)

            # Wavelength (read-only, grayish)
            wl_item = QTableWidgetItem(wl)
            wl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            wl_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            wl_item.setBackground(QColor("#e8e8e8"))
            wl_item.setForeground(QColor("black"))
            table.setItem(row, 2, wl_item)

            # ATT value (editable, white)
            # Try to get saved value using itg_no first, then fallback
            att = 0
            if itg in saved_values:
                att = saved_values[itg]
            else:
                # fallback to old key format
                att = saved_values.get((ele, wl), 0)
            att_item = QTableWidgetItem(str(att))
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            att_item.setForeground(QColor("black"))
            table.setItem(row, 3, att_item)

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _collect(self) -> dict:
        """Collect data from both tables into a single dict."""
        rows = []
        for table in [self._left_table, self._right_table]:
            for row in range(table.rowCount()):
                ele_item = table.item(row, 0)
                itg_item = table.item(row, 1)
                wl_item = table.item(row, 2)
                att_item = table.item(row, 3)

                if ele_item and itg_item and wl_item and att_item:
                    ele = ele_item.text().strip()
                    itg_str = itg_item.text().strip()
                    wl = wl_item.text().strip()
                    if ele and itg_str:  # only save non-empty
                        try:
                            itg_no = int(itg_str)
                        except ValueError:
                            continue
                        try:
                            att_val = int(att_item.text()) if att_item.text() else 0
                        except ValueError:
                            att_val = 0
                        rows.append({
                            "itg_no": itg_no,
                            "element": ele,
                            "wavelength": wl,
                            "att_value": att_val,
                        })

        return {"rows": rows}

    def _save(self):
        """Save data to database and mirror to import_data/attenuator.json."""
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_02_attenuator = data
                session.commit()
                # ── Mirror to import_data/attenuator.json ───────────────
                export_attenuator(data.get("rows", []))
        finally:
            session.close()

    def _load(self):
        """Reload both tables with current data."""
        session = get_session()
        try:
            # Order by itg_no (primary key)
            elements = session.query(MasterElement).order_by(MasterElement.itg_no).all()

            if not elements:
                # No elements – show empty tables
                self._left_table.setRowCount(1)
                self._right_table.setRowCount(1)
                self._populate_table(self._left_table, [None])
                self._populate_table(self._right_table, [None])
                return

            half = (len(elements) + 1) // 2
            left_elements = elements[:half]
            right_elements = elements[half:]

            # Pad to same length
            max_rows = max(len(left_elements), len(right_elements))
            if len(left_elements) < max_rows:
                left_elements = left_elements + [None] * (max_rows - len(left_elements))
            if len(right_elements) < max_rows:
                right_elements = right_elements + [None] * (max_rows - len(right_elements))

            # Save current ATT values (from DB)
            saved_values = {}
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_02_attenuator and g.page_02_attenuator.get("rows"):
                for r in g.page_02_attenuator["rows"]:
                    itg = r.get("itg_no")
                    if itg is not None:
                        saved_values[itg] = r.get("att_value", 0)
                    else:
                        saved_values[(r["element"], r["wavelength"])] = r.get("att_value", 0)

            # Update table heights based on new row count
            self._left_table.setRowCount(max_rows)
            self._right_table.setRowCount(max_rows)

            # Recalculate table height
            table_height = (max_rows * 27) + 27 + 3
            self._left_table.setFixedHeight(table_height)
            self._right_table.setFixedHeight(table_height)

            # Repopulate
            self._repopulate_table(self._left_table, left_elements, saved_values)
            self._repopulate_table(self._right_table, right_elements, saved_values)

        finally:
            session.close()

    def _repopulate_table(self, table, elements, saved_values):
        """Repopulate a table with saved data."""
        for row, me in enumerate(elements):
            if me is None:
                for col in range(4):
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    if col < 3:
                        item.setBackground(QColor("#e8e8e8"))
                    else:
                        item.setBackground(QColor("white"))
                    table.setItem(row, col, item)
                continue

            if hasattr(me, 'ele_name'):
                ele = me.ele_name or ""
                itg = me.itg_no
                wl = me.wavelength or ""
            else:
                ele = me.get("ele_name", "")
                itg = me.get("itg_no", 0)
                wl = me.get("wavelength", "")

            # Element (read-only, grayish)
            ele_item = QTableWidgetItem(ele)
            ele_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ele_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            ele_item.setBackground(QColor("#e8e8e8"))
            ele_item.setForeground(QColor("black"))
            table.setItem(row, 0, ele_item)

            # ITG (read-only, grayish)
            itg_item = QTableWidgetItem(str(itg))
            itg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            itg_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            itg_item.setBackground(QColor("#e8e8e8"))
            itg_item.setForeground(QColor("black"))
            table.setItem(row, 1, itg_item)

            # Wavelength (read-only, grayish)
            wl_item = QTableWidgetItem(wl)
            wl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            wl_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            wl_item.setBackground(QColor("#e8e8e8"))
            wl_item.setForeground(QColor("black"))
            table.setItem(row, 2, wl_item)

            # ATT value (editable, white)
            att = saved_values.get(itg, 0) if itg in saved_values else saved_values.get((ele, wl), 0)
            att_item = QTableWidgetItem(str(att))
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            att_item.setForeground(QColor("black"))
            table.setItem(row, 3, att_item)

    # =========================================================================
    # Message Box Helper
    # =========================================================================

    def _show_msg(self, title, text, icon=QMessageBox.Icon.Information):
        """Show a styled message box."""
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
        """Show a styled question dialog."""
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
        self._show_msg("Saved", "Attenuator settings saved successfully.")

    def _on_next(self):
        self._save()
        from ui.anainf.page_03_channel import ChannelPage
        self.main_window.set_right_widget(
            ChannelPage(self.main_window, self.group_id, self.group_name)
        )

    def _on_pre(self):
        self._save()
        from ui.anainf.page_01_source import SourceConditionPage
        self.main_window.set_right_widget(
            SourceConditionPage(self.main_window, self.group_id, self.group_name)
        )

    def _on_print(self):
        self._show_msg("Print", "Print coming soon.")

    def _on_cancel(self):
        if self._show_question("Cancel", "Discard changes?") == QMessageBox.StandardButton.Yes:
            from ui.anainf.page_01_source import AnalyticalConditionPage
            self.main_window.set_right_widget(
                AnalyticalConditionPage(self.main_window, self.group_id, self.group_name)
            )