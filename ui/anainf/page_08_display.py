"""
SpectraSoft — Page 8: Display & Print Format

This page defines how analysis results are displayed on screen and printed.

Columns (one row per element from Page 3):
- ELE: Element name (read‑only, from Page 3)
- NAME: Custom name (read‑only, from Page 3)
- ORDER: Display order (1 = first)
- FIG: Total number of characters (including decimal)
- DECI: Number of decimal places
- MAGN: Magnification (10^MAGN multiplier)

Rules:
- ORDER = 0 means element is not displayed/printed
- FIG must be between 1 and 6
- DECI must be less than FIG
- MAGN = 0 means no magnification

Saved JSON example:
{
    "display_order": [
        {"element": "C", "name": "C", "order": 1, "fig": 4, "deci": 2, "magn": 0},
        {"element": "SI", "name": "Si", "order": 2, "fig": 4, "deci": 2, "magn": 0},
        ...
    ]
}
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIntValidator, QKeySequence, QShortcut, QKeySequence, QShortcut

from core.database import get_session
from core.models import AnalyticalGroup

MAX_ELEMENTS = 32


class DisplayPage(QWidget):

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
        bar = QLabel(f"Display Format - {self.group_name}")
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
        title = QLabel("DISPLAY & PRINT FORMAT")
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
            "ORDER = Display order (1=first, 0=hidden)\n"
            "FIG = Total characters | DECI = Decimal places | MAGN = ×10^MAGN multiplier"
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

        info_lbl = QLabel("ORDER = 0 hides the element from display/print")
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
        """Create a table with 6 columns: ELE, NAME, ORDER, FIG, DECI, MAGN."""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["ELE", "NAME", "ORDER", "FIG", "DECI", "MAGN"])

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
            "QTableWidget QComboBox{"
            "background:white;"
            "color:black;"
            "border:1px solid #888888;"
            "font:9pt Arial;"
            "}"
        )

        col_widths = [50, 70, 55, 45, 45, 55]
        for i, w in enumerate(col_widths):
            table.setColumnWidth(i, w)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        table.verticalHeader().setDefaultSectionSize(27)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        table.setRowCount(MAX_ELEMENTS)
        self._populate_empty_rows(table)

        table_height = (MAX_ELEMENTS * 27) + 27 + 3
        table.setFixedHeight(table_height)

        return table

    def _populate_empty_rows(self, table):
        """Fill rows with default widgets."""
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

            # ORDER (editable, 0-99)
            order_edit = QLineEdit("0")
            order_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            order_edit.setValidator(QIntValidator(0, 99, order_edit))
            order_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 2, order_edit)

            # FIG (editable, 1-6)
            fig_edit = QLineEdit("0")
            fig_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fig_edit.setValidator(QIntValidator(0, 6, fig_edit))
            fig_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 3, fig_edit)

            # DECI (editable, 0-6)
            deci_edit = QLineEdit("0")
            deci_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            deci_edit.setValidator(QIntValidator(0, 6, deci_edit))
            deci_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 4, deci_edit)

            # MAGN (editable, 0-6)
            magn_edit = QLineEdit("0")
            magn_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            magn_edit.setValidator(QIntValidator(0, 6, magn_edit))
            magn_edit.setStyleSheet(
                "QLineEdit{"
                "background:white;"
                "color:black;"
                "border:1px solid #888888;"
                "font:9pt Arial;"
                "padding:0px 2px;"
                "}"
            )
            table.setCellWidget(row, 5, magn_edit)

    def _populate_from_page3(self, data: list):
        """Populate table using Page 3 data."""
        for row in range(MAX_ELEMENTS):
            ele_item = self.table.item(row, 0)
            if ele_item:
                ele_item.setText("")
            name_item = self.table.item(row, 1)
            if name_item:
                name_item.setText("")
            for col in range(2, 6):
                edit = self.table.cellWidget(row, col)
                if edit:
                    edit.setText("0")

        saved_data = {}
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g and g.page_08_display:
                display_list = g.page_08_display.get("display_order", [])
                for entry in display_list:
                    key = (entry.get("element", ""), entry.get("name", ""))
                    saved_data[key] = entry
        finally:
            session.close()

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
                order_edit = self.table.cellWidget(row, 2)
                if order_edit:
                    order_edit.setText(str(saved.get("order", 0)))
                fig_edit = self.table.cellWidget(row, 3)
                if fig_edit:
                    fig_edit.setText(str(saved.get("fig", 0)))
                deci_edit = self.table.cellWidget(row, 4)
                if deci_edit:
                    deci_edit.setText(str(saved.get("deci", 0)))
                magn_edit = self.table.cellWidget(row, 5)
                if magn_edit:
                    magn_edit.setText(str(saved.get("magn", 0)))

    def _collect(self) -> dict:
        """Collect data from table into a dict."""
        display_order = []
        for row in range(MAX_ELEMENTS):
            ele_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if not ele_item or not name_item:
                continue
            ele = ele_item.text().strip()
            name = name_item.text().strip()
            if not ele:
                continue

            order_edit = self.table.cellWidget(row, 2)
            fig_edit = self.table.cellWidget(row, 3)
            deci_edit = self.table.cellWidget(row, 4)
            magn_edit = self.table.cellWidget(row, 5)

            def get_int(edit, default=0):
                try:
                    return int(edit.text().strip()) if edit and edit.text().strip() else default
                except ValueError:
                    return default

            display_order.append({
                "element": ele,
                "name": name,
                "order": get_int(order_edit, 0),
                "fig": get_int(fig_edit, 0),
                "deci": get_int(deci_edit, 0),
                "magn": get_int(magn_edit, 0),
            })

        return {"display_order": display_order}

    # =========================================================================
    # Data Operations
    # =========================================================================

    def _load(self):
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
        data = self._collect()
        session = get_session()
        try:
            g = session.get(AnalyticalGroup, self.group_id)
            if g:
                g.page_08_display = data
                session.commit()
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
                for col in range(2, 6):
                    edit = self.table.cellWidget(row, col)
                    if edit:
                        edit.setText("0")

    def _on_ok(self):
        self._save()
        self._show_msg("Saved", "Display format saved successfully.")

    def _on_next(self):
        self._save()
        try:
            from ui.anainf.page_09_purity import PurityPage
            self.main_window.set_right_widget(
                PurityPage(self.main_window, self.group_id, self.group_name)
            )
        except ImportError:
            self._show_msg("Next Page", "Page 9 (Purity) is not built yet.")

    def _on_pre(self):
        self._save()
        try:
            from ui.anainf.page_07_master import MasterCurvePage
            self.main_window.set_right_widget(
                MasterCurvePage(self.main_window, self.group_id, self.group_name)
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