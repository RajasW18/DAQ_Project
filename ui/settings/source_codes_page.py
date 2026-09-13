"""
SpectraSoft — Source Codes Settings Page
16 fixed rows (0-F). Name column editable.
"""

import json
from core.json_export import export_source_codes
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import SourceCode

NUM_ROWS = 16


class SourceCodesPage(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.lightGray)
        self.setPalette(p)

        self._build_ui()
        self._load()

    # UI Construction

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title Bar ──────────────────────────────────────────────────────
        bar = QLabel("Source Codes")
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

        inner = QWidget()
        inner.setAutoFillBackground(True)
        ip = inner.palette()
        ip.setColor(inner.backgroundRole(), Qt.GlobalColor.lightGray)
        inner.setPalette(ip)

        ml = QVBoxLayout(inner)
        ml.setContentsMargins(20, 16, 20, 12)
        ml.setSpacing(8)

        # ── Excel-Style Table ───────────────────────────────────────────
        # Height = 16 rows × 27px + header (27px) = 459px
        table_frame = QFrame()
        table_frame.setStyleSheet(
            "QFrame{"
            "background:white;"
            "border:1px solid #888888;"
            "}"
        )
        table_frame.setFixedHeight(465)

        self.table = QTableWidget(NUM_ROWS, 2)
        self.table.setHorizontalHeaderLabels(["HexCode", "Name"])

        # Excel-style table styling
        self.table.setStyleSheet(
            "QTableWidget{"
            "background:white;"
            "color:black;"
            "border:none;"
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
        self.table.setColumnWidth(0, 100)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )

        # Row height - exactly 27px per row
        self.table.verticalHeader().setDefaultSectionSize(27)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table)

        self.table.itemChanged.connect(self._on_table_item_changed)

        ml.addWidget(table_frame)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

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

        for label, slot in [
            ("Save", self._on_save),
            ("Export", self._on_export),
            ("Import", self._on_import),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            btn_row.addWidget(b)

        btn_row.addStretch()
        ml.addLayout(btn_row)

        ol.addWidget(inner)

    # Data

    def _load(self):
        session = get_session()
        try:
            rows = session.query(SourceCode).order_by(
                SourceCode.entry_no).all()

            # Seed 16 empty rows if DB is empty
            if not rows:
                for i in range(NUM_ROWS):
                    session.add(SourceCode(entry_no=i, name=""))
                session.commit()
                rows = session.query(SourceCode).order_by(
                    SourceCode.entry_no).all()

            self.table.blockSignals(True)
            for sc in rows:
                row = sc.entry_no

                # Entry No — read only, beige background
                hex_item = QTableWidgetItem(format(sc.entry_no, 'X'))
                hex_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                hex_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable |
                    Qt.ItemFlag.ItemIsEnabled
                )
                hex_item.setBackground(QColor("#d4d0c8"))
                hex_item.setForeground(QColor("black"))
                self.table.setItem(row, 0, hex_item)

                # Name — editable, text color explicitly set to black
                name_item = QTableWidgetItem(sc.name or "")
                name_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft |
                    Qt.AlignmentFlag.AlignVCenter
                )
                name_item.setForeground(QColor("black"))  # FIX: Text is now black
                self.table.setItem(row, 1, name_item)

            self.table.blockSignals(False)
        finally:
            session.close()

    def _collect(self) -> list:
        rows = []
        for row in range(NUM_ROWS):
            name_item = self.table.item(row, 1)
            rows.append({
                "entry_no": row,
                "name": name_item.text().strip() if name_item else ""
            })
        return rows

    # Actions

    def _persist(self, show_message: bool = True):
        rows = self._collect()
        session = get_session()
        try:
            for r in rows:
                sc = session.get(SourceCode, r["entry_no"])
                if sc:
                    sc.name = r["name"]
                else:
                    session.add(SourceCode(
                        entry_no=r["entry_no"], name=r["name"]))
            session.commit()
            # ── Mirror to import_data/source_codes.json ─────────────────
            export_source_codes(rows)
            if show_message:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setWindowTitle("Saved")
                msg.setText("Source codes saved successfully.")
                msg.setStyleSheet(
                    "QLabel { color: black; }"
                    "QPushButton { color: black; background-color: #d4d0c8; border: 1px solid gray; min-width: 60px; padding: 4px; }"
                )
                msg.exec()
        finally:
            session.close()

    def _on_table_item_changed(self, item):
        if item is None or item.column() != 1:
            return
        if self.table.signalsBlocked():
            return
        self._persist(show_message=False)

    def _on_save(self):
        self._persist(show_message=True)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Source Codes", "source_codes.json",
            "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump({"source_codes": self._collect()}, f, indent=2)
            QMessageBox.information(self, "Exported", f"Source codes exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Source Codes", "",
            "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            rows = data.get("source_codes", [])
            if len(rows) != NUM_ROWS:
                QMessageBox.warning(self, "Import Failed",
                    f"Expected {NUM_ROWS} rows, got {len(rows)}.")
                return
            session = get_session()
            try:
                for r in rows:
                    sc = session.get(SourceCode, r["entry_no"])
                    if sc:
                        sc.name = r.get("name", "")
                    else:
                        session.add(SourceCode(
                            entry_no=r["entry_no"],
                            name=r.get("name", "")))
                session.commit()
            finally:
                session.close()
            self._load()
            QMessageBox.information(self, "Imported", "Source codes imported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    # Fullscreen mode

    def wants_fullscreen(self) -> bool:
        return True