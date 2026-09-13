"""
SpectraSoft — Master Elements Settings Page

Fixed table of 45 hardware channels (ITG 1-45).
User can edit Element Name and Wavelength for each channel.
ITG No. is read-only and serves as the primary key.

Columns:
- ITG No.: Integrator number (1-45, fixed, read-only)
- Ele. Name: Element symbol (editable, must be unique)
- Wavelength: Wavelength in nm (editable)

Rules:
- Exactly 45 rows, ITG No. cannot be changed
- Ele. Name must be unique (case-insensitive)
- Ele. Name is required (cannot be empty)
"""

import json
from core.json_export import export_master_elements
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.database import get_session
from core.models import MasterElement

NUM_ROWS = 45  # ITG 1 to 45


class MasterElementsPage(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

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
        bar = QLabel("Master Elements")
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

        # ── Excel-Style Table (Scrollable) ──────────────────────────────
        table_frame = QFrame()
        table_frame.setStyleSheet(
            "QFrame{"
            "background:white;"
            "border:1px solid #888888;"
            "}"
        )
        # Fixed height for table frame to allow scrolling without taking too much space
        table_frame.setFixedHeight(465)

        self.table = QTableWidget(NUM_ROWS, 3)
        self.table.setHorizontalHeaderLabels(["ITG No.", "Ele. Name", "Wavelength"])

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

        # Column widths – fixed, no resizing
        self.table.setColumnWidth(0, 80)   # ITG No.
        self.table.setColumnWidth(1, 100)  # Ele. Name
        self.table.setColumnWidth(2, 100)  # Wavelength

        # Disable column resizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )

        # Row height - 27px consistent
        self.table.verticalHeader().setDefaultSectionSize(27)
        # Enable vertical scrollbar (it will appear when needed)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # ── Fill rows with fixed ITG numbers ──────────────────────────
        for row in range(NUM_ROWS):
            itg_no = row + 1

            # ITG No. column (read-only, gray)
            itg_item = QTableWidgetItem(str(itg_no))
            itg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            itg_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            itg_item.setBackground(QColor("#e8e8e8"))
            itg_item.setForeground(QColor("black"))
            self.table.setItem(row, 0, itg_item)

            # Ele. Name column (editable)
            name_item = QTableWidgetItem("")
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_item.setForeground(QColor("black"))
            self.table.setItem(row, 1, name_item)

            # Wavelength column (editable)
            wl_item = QTableWidgetItem("")
            wl_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            wl_item.setForeground(QColor("black"))
            self.table.setItem(row, 2, wl_item)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table)

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

    # =========================================================================
    # Data
    # =========================================================================

    def _load(self):
        """Load element names and wavelengths from DB into the table."""
        session = get_session()
        try:
            rows = session.query(MasterElement).order_by(MasterElement.itg_no).all()
            # Clear existing cells
            for row in range(NUM_ROWS):
                self.table.item(row, 1).setText("")
                self.table.item(row, 2).setText("")
            # Fill from DB
            for r in rows:
                if 1 <= r.itg_no <= NUM_ROWS:
                    row = r.itg_no - 1
                    self.table.item(row, 1).setText(r.ele_name or "")
                    self.table.item(row, 2).setText(r.wavelength or "")
        finally:
            session.close()

    def _collect(self) -> list:
        """Collect data from table into a list of dicts."""
        rows = []
        for row in range(NUM_ROWS):
            name_item = self.table.item(row, 1)
            wl_item = self.table.item(row, 2)
            name = name_item.text().strip() if name_item else ""
            wavelength = wl_item.text().strip() if wl_item else ""
            rows.append({
                "itg_no": row + 1,
                "ele_name": name,
                "wavelength": wavelength,
            })
        return rows

    def _validate_names(self, rows) -> bool:
        """Check for duplicate element names (case-insensitive) and empty names."""
        names = {}
        for r in rows:
            name = r["ele_name"].strip()
            if not name:
                QMessageBox.warning(
                    self,
                    "Invalid Element Name",
                    f"ITG {r['itg_no']} has an empty element name.\n\n"
                    "All elements must have a name."
                )
                return False
            name_upper = name.upper()
            if name_upper in names:
                QMessageBox.warning(
                    self,
                    "Duplicate Element Name",
                    f"Element name '{name}' (ITG {r['itg_no']}) duplicates '{names[name_upper]}'.\n\n"
                    "All element names must be unique (case-insensitive)."
                )
                return False
            names[name_upper] = f"ITG {r['itg_no']}"
        return True

    # =========================================================================
    # Actions
    # =========================================================================

    def _on_save(self):
        rows = self._collect()

        if not self._validate_names(rows):
            return

        session = get_session()
        try:
            # Clear all existing entries
            session.query(MasterElement).delete()

            # Insert all 45 rows (no display_order)
            for r in rows:
                session.add(MasterElement(
                    itg_no=r["itg_no"],
                    ele_name=r["ele_name"],
                    wavelength=r["wavelength"],
                ))
            session.commit()
            # ── Mirror to import_data/master_elements.json ────────────────
            export_master_elements(rows)
            QMessageBox.information(self, "Saved",
                f"Master elements saved successfully.\n"
                f"{len(rows)} channels configured.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Save Failed", str(e))
        finally:
            session.close()

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Master Elements",
            "master_elements.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump({"master_elements": self._collect()}, f, indent=2)
            QMessageBox.information(self, "Exported",
                f"Master elements exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Master Elements", "",
            "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            rows = data.get("master_elements", [])
            if not rows:
                QMessageBox.warning(self, "Import Failed",
                    "No master_elements found in file.")
                return

            # Validate and apply
            itg_map = {}
            for r in rows:
                try:
                    itg = int(r.get("itg_no", 0))
                except (ValueError, TypeError):
                    itg = 0
                if itg < 1 or itg > NUM_ROWS:
                    QMessageBox.warning(self, "Import Failed",
                        f"Invalid ITG No. '{itg}' – must be between 1 and {NUM_ROWS}.")
                    return
                name = r.get("ele_name", "").strip()
                if not name:
                    QMessageBox.warning(self, "Import Failed",
                        f"ITG {itg} has empty element name in file.")
                    return
                # Check duplicate names in import file
                if name.upper() in [v[0].upper() for v in itg_map.values()]:
                    QMessageBox.warning(self, "Import Failed",
                        f"Duplicate element name '{name}' in import file.")
                    return
                wavelength = r.get("wavelength", "").strip()
                itg_map[itg] = (name, wavelength)

            # Apply to table
            for itg, (name, wl) in itg_map.items():
                row = itg - 1
                self.table.item(row, 1).setText(name)
                self.table.item(row, 2).setText(wl)

            QMessageBox.information(self, "Imported",
                f"Imported {len(itg_map)} element entries.")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    # =========================================================================
    # Fullscreen mode
    # =========================================================================

    def wants_fullscreen(self) -> bool:
        return True