"""
SpectraSoft — Permanent Left Group Panel
Always visible. Selecting a group loads the page on the right.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QFrame, QInputDialog, QMessageBox, QLineEdit, QDialog, QHBoxLayout)
from PyQt6.QtCore import Qt

from core.database import get_session
from core.models import AnalyticalGroup


class GroupPanel(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        # Background
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.darkGray)
        self.setPalette(p)

        self._all_groups = []  # Store all groups for filtering
        self._build_ui()
        self._load()

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Title - bigger font
        title = QLabel("Analytical Group")
        title.setStyleSheet(
            "QLabel{"
            "background:#d4d0c8;"
            "color:#000000;"
            "border:none;"
            "font:bold 11pt Arial;"
            "}"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search groups...")
        self._search.setStyleSheet(
            "QLineEdit{"
            "background:#ffffff;"
            "color:#000000;"
            "border:1px solid #888888;"
            "font:9pt Arial;"
            "padding:4px 6px;"
            "}"
        )
        self._search.textChanged.connect(self._filter_groups)
        root.addWidget(self._search)

        # Panel frame
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.Box)
        panel.setFrameShadow(QFrame.Shadow.Raised)
        panel.setLineWidth(2)
        panel.setStyleSheet("background:#d4d0c8;")

        pl = QVBoxLayout(panel)
        pl.setContentsMargins(6, 6, 6, 6)
        pl.setSpacing(4)

        # List - no drag and drop, alphabetical order
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{"
            "background:#ffffff;"
            "color:#000000;"
            "border:1px solid #aaaaaa;"
            "font:10pt Arial;"
            "}"
            "QListWidget::item{"
            "padding:4px 6px;"
            "color:#000000;"
            "}"
            "QListWidget::item:selected{"
            "background:#0078d7;"
            "color:#ffffff;"
            "}"
        )
        # No drag-and-drop
        self._list.setDragDropMode(QListWidget.DragDropMode.NoDragDrop)
        self._list.itemDoubleClicked.connect(self._on_open)
        pl.addWidget(self._list)

        # Buttons - bigger font, simpler text
        for label, slot in [
            ("New", self._on_new),
            ("Delete", self._on_delete),
            ("Copy", self._on_wc_copy),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                "QPushButton{"
                "background:#d4d0c8;"
                "color:#000000;"
                "border:2px outset #aaaaaa;"
                "font:9pt Arial;"
                "padding:4px 6px;"
                "min-width:55px;"
                "}"
                "QPushButton:pressed{"
                "border:2px inset #888888;"
                "}"
            )
            btn.clicked.connect(slot)
            pl.addWidget(btn)

        root.addWidget(panel)

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load(self):
        session = get_session()
        try:
            # Sort by name (alphabetical, case-insensitive)
            groups = session.query(AnalyticalGroup).order_by(
                AnalyticalGroup.name
            ).all()

            self._all_groups = groups
            self._populate_list(groups)

            if self._list.count() > 0:
                self._list.setCurrentRow(0)
        finally:
            session.close()

    def _populate_list(self, groups):
        """Populate the list widget with given groups."""
        self._list.clear()
        # Ensure groups are sorted by name before displaying (should already be, but just in case)
        sorted_groups = sorted(groups, key=lambda g: g.name.upper())
        for g in sorted_groups:
            item = QListWidgetItem(g.name)
            item.setData(Qt.ItemDataRole.UserRole, g.id)
            self._list.addItem(item)

    def _filter_groups(self, text):
        """Filter the group list based on search text (case-insensitive)."""
        if not text.strip():
            self._populate_list(self._all_groups)
            return

        search_term = text.strip().upper()
        filtered = [g for g in self._all_groups if search_term in g.name.upper()]
        self._populate_list(filtered)

    def _selected(self):
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole), item.text()
        return None, None

    def highlight(self, group_id: int):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == group_id:
                self._list.setCurrentRow(i)
                break

    # =========================================================================
    # Actions
    # =========================================================================

    def _on_open(self):
        """Double-click opens the group pages."""
        gid, name = self._selected()
        if gid is None:
            return

        from ui.anainf.page_01_source import SourceConditionPage
        self.main_window.set_right_widget(
            SourceConditionPage(self.main_window, gid, name)
        )

    def _on_new(self):
        # Create a custom dialog instead of using QInputDialog
        dialog = QDialog(self)
        dialog.setWindowTitle("New Group")
        dialog.setModal(True)
        dialog.setFixedSize(300, 120)
        # Remove the "?" help button and window icon
        dialog.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint
        )
        dialog.setStyleSheet("background:#d4d0c8;")

        # Layout
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)

        # Label
        label = QLabel("Enter group name:")
        label.setStyleSheet(
            "QLabel{"
            "background:#d4d0c8;"
            "color:#000000;"
            "border:none;"
            "font:9pt Arial;"
            "}"
        )
        layout.addWidget(label)

        # Input field
        input_field = QLineEdit()
        input_field.setStyleSheet(
            "QLineEdit{"
            "background:#ffffff;"
            "color:#000000;"
            "border:1px solid #888888;"
            "font:9pt Arial;"
            "padding:4px 6px;"
            "}"
        )
        input_field.setFocus()
        layout.addWidget(input_field)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(
            "QPushButton{"
            "background:#d4d0c8;"
            "color:#000000;"
            "border:2px outset #aaaaaa;"
            "font:9pt Arial;"
            "padding:4px 12px;"
            "min-width:60px;"
            "}"
            "QPushButton:pressed{"
            "border:2px inset #888888;"
            "}"
        )
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dialog.accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton{"
            "background:#d4d0c8;"
            "color:#000000;"
            "border:2px outset #aaaaaa;"
            "font:9pt Arial;"
            "padding:4px 12px;"
            "min-width:60px;"
            "}"
            "QPushButton:pressed{"
            "border:2px inset #888888;"
            "}"
        )
        cancel_btn.clicked.connect(dialog.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Show dialog and process
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = input_field.text().strip()
        if not name:
            return

        name = name.upper()

        session = get_session()
        try:
            # Check for duplicate
            if session.query(AnalyticalGroup).filter_by(name=name).first():
                QMessageBox.warning(
                    self,
                    "Duplicate",
                    f"'{name}' already exists."
                )
                return

            # Create new group
            g = AnalyticalGroup(
                name=name,
                display_order=0
            )
            session.add(g)
            session.commit()
            session.refresh(g)

            # Add to list and reload sorted
            self._all_groups.append(g)
            self._populate_list(self._all_groups)

            # Select the new item
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == g.id:
                    self._list.setCurrentRow(i)
                    break

            # Clear search
            self._search.clear()

        finally:
            session.close()

    def _on_delete(self):
        gid, name = self._selected()
        if gid is None:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select a group first."
            )
            return

        # Confirm
        if QMessageBox.question(
            self,
            "Delete",
            f"Delete '{name}'? Cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        session = get_session()
        try:
            g = session.get(AnalyticalGroup, gid)
            if g:
                session.delete(g)
                session.commit()

            # Remove from local list
            self._all_groups = [grp for grp in self._all_groups if grp.id != gid]
            self._populate_list(self._all_groups)
            self.main_window._show_home_content()

        finally:
            session.close()

    def _on_wc_copy(self):
        gid, name = self._selected()
        if gid is None:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select a source group first."
            )
            return

        # Get list of other groups (sorted alphabetically)
        session = get_session()
        try:
            dest_names = [
                g.name
                for g in session.query(AnalyticalGroup).order_by(
                    AnalyticalGroup.name
                ).all()
                if g.id != gid
            ]
        finally:
            session.close()

        if not dest_names:
            QMessageBox.information(
                self,
                "Copy",
                "No other groups to copy to."
            )
            return

        # Select destination
        dest_name, ok = QInputDialog.getItem(
            self,
            "Copy",
            f"Copy working curve coefficients FROM '{name}' TO:",
            dest_names,
            0,
            False
        )
        if not ok:
            return

        # Perform copy
        session = get_session()
        try:
            src = session.get(AnalyticalGroup, gid)
            dst = session.query(AnalyticalGroup).filter_by(
                name=dest_name
            ).first()

            if src and dst:
                dst.page_07_working_curve = src.page_07_working_curve
                session.commit()
                QMessageBox.information(
                    self,
                    "Done",
                    f"Copied WC coefficients from '{name}' to '{dest_name}'."
                )
        finally:
            session.close()