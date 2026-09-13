"""
SpectraSoft — Main Window
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStatusBar, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer
from core.uart_manager import UARTManager

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpectraSoft")
        
        # Fixed size — window cannot be resized
        self.setFixedSize(1100, 680)

        self._current_action = None

        self._build_menu()
        self._build_body()
        self._build_status_bar()
        self.hv_on = False
        self.tan_count = 0
        
    # =========================================================================
    # HV Toggle
    # =========================================================================

    def toggle_hv(self):
        self.hv_on = not self.hv_on
        # TODO: Send command to MCU
        # For simulation, just toggle
        return self.hv_on

    def get_hv_status(self):
        return self.hv_on

    # =========================================================================
    # Menu
    # =========================================================================

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(
            "QMenuBar{"
            "background:#c0b8a8;"
            "color:#000000;"
            "border-bottom:1px solid #888888;"
            "}"
            "QMenuBar::item{"
            "background:#c0b8a8;"
            "color:#000000;"
            "padding:2px 10px;"
            "}"
            "QMenuBar::item:selected{"
            "background:#0078d7;"
            "color:#ffffff;"
            "}"
            "QMenu{"
            "background:#ffffff;"
            "color:#000000;"
            "border:1px solid #888888;"
            "}"
            "QMenu::item:selected{"
            "background:#0078d7;"
            "color:#ffffff;"
            "}"
        )

        # Analytical Group
        group_m = mb.addMenu("Analytical Group")
        self.action_group = QAction("Analytical Group", self)
        self.action_group.setCheckable(True)
        self.action_group.triggered.connect(self._show_home_content)
        group_m.addAction(self.action_group)

        # Master Elements
        master_m = mb.addMenu("Master Elements")
        self.action_master = QAction("Master Elements", self)
        self.action_master.setCheckable(True)
        self.action_master.triggered.connect(self._open_master_elements)
        master_m.addAction(self.action_master)

        # Source Codes
        source_m = mb.addMenu("Source Codes")
        self.action_source = QAction("Source Codes", self)
        self.action_source.setCheckable(True)
        self.action_source.triggered.connect(self._open_source_codes)
        source_m.addAction(self.action_source)

        # ⭐ Analysis Menu with both options
        analysis_m = mb.addMenu("Analysis")
        
        # Option 1: Job Selection (Real Analysis)
        self.action_analysis = QAction("Analysis Jobs", self)
        self.action_analysis.setCheckable(True)
        self.action_analysis.triggered.connect(self._open_job_selection)
        analysis_m.addAction(self.action_analysis)
        
        analysis_m.addSeparator()
        
        # Option 2: Simulation (Test Mode)
        self.action_simulation = QAction("Simulation (Test)", self)
        self.action_simulation.setCheckable(True)
        self.action_simulation.triggered.connect(self._open_simulation)
        analysis_m.addAction(self.action_simulation)

        # Default: Analytical Group checked
        self.action_group.setChecked(True)
        self._current_action = self.action_group

    def _set_active_menu(self, action):
        if self._current_action:
            self._current_action.setChecked(False)
        action.setChecked(True)
        self._current_action = action

    # =========================================================================
    # Body
    # =========================================================================

    def _build_body(self):
        root = QWidget()
        root.setStyleSheet("background:#d4d0c8;")
        self.setCentralWidget(root)

        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        from ui.anainf.group_panel import GroupPanel
        self._group_panel = GroupPanel(self)
        self._group_panel.setFixedWidth(230)
        h.addWidget(self._group_panel)

        self._div = QFrame()
        self._div.setFrameShape(QFrame.Shape.VLine)
        self._div.setFrameShadow(QFrame.Shadow.Sunken)
        self._div.setStyleSheet("color:#aaaaaa;")
        h.addWidget(self._div)

        self._right = QWidget()
        self._right.setStyleSheet("background:#d4d0c8;")
        self._right_layout = QVBoxLayout(self._right)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(0)
        h.addWidget(self._right, stretch=1)

        self._show_home_content()

    # =========================================================================
    # Right Panel Management
    # =========================================================================

    def set_right_widget(self, widget):
        # Clear existing
        while self._right_layout.count():
            item = self._right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._right_layout.addWidget(widget)

        # Fullscreen mode if widget wants it
        if hasattr(widget, 'wants_fullscreen') and callable(widget.wants_fullscreen):
            self.set_fullscreen_mode(widget.wants_fullscreen())
        else:
            self.set_fullscreen_mode(False)

    def set_left_panel_visible(self, visible: bool):
        self._group_panel.setVisible(visible)
        self._div.setVisible(visible)

    def set_fullscreen_mode(self, enabled: bool):
        self.set_left_panel_visible(not enabled)

    # =========================================================================
    # Home / Default View
    # =========================================================================

    def _show_home_content(self):
        self._set_active_menu(self.action_group)
        self.set_fullscreen_mode(False)

        w = QWidget()
        w.setStyleSheet("background:#d4d0c8;")
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(
            "Select a group and double-click to open\n"
            "or use Analysis → Analysis Jobs (real) / Simulation (test)"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            "QLabel{"
            "background:#d4d0c8;"
            "color:#666666;"
            "border:none;"
            "font:9pt Arial;"
            "}"
        )
        v.addWidget(hint)

        self.set_right_widget(w)

    # =========================================================================
    # Status Bar (empty)
    # =========================================================================

    def _build_status_bar(self):
        sb = QStatusBar()
        sb.setStyleSheet("background:#d4d0c8; color:#000000;")
        self.setStatusBar(sb)
        # No text added - status bar is empty

    # =========================================================================
    # Menu Actions
    # =========================================================================

    def _open_source_codes(self):
        from ui.settings.source_codes_page import SourceCodesPage
        self._set_active_menu(self.action_source)
        self.set_right_widget(SourceCodesPage(self))

    def _open_master_elements(self):
        from ui.settings.master_elements_page import MasterElementsPage
        self._set_active_menu(self.action_master)
        self.set_right_widget(MasterElementsPage(self))

    def _get_current_group(self):
        if hasattr(self._group_panel, '_selected'):
            gid, gname = self._group_panel._selected()
            if gid is not None:
                return gid, gname
        return None, None

    def _open_job_selection(self):
        """Open the real analysis job selection page."""
        self._set_active_menu(self.action_analysis)
        from ui.analysis.job_selection import JobSelectionPage
        self.set_right_widget(JobSelectionPage(self))

    def _open_simulation(self):
        """Open the existing simulation page."""
        self._set_active_menu(self.action_simulation)
        from ui.analysis_run_page import AnalysisRunPage
        
        # Get current group (or use a default if none selected)
        gid, gname = self._get_current_group()
        if gid is None:
            gid = 1
            gname = "Demo Group"
        
        run_page = AnalysisRunPage(self, group_id=gid, group_name=gname)
        self.set_right_widget(run_page)

    def _build_status_bar(self):
        sb = QStatusBar()
        sb.setStyleSheet("background:#d4d0c8; color:#000000;")
        self.setStatusBar(sb)
        
        # Connection status label
        self.conn_status_label = QLabel("🔴 Disconnected")
        self.conn_status_label.setStyleSheet("padding: 2px 8px; font: 9pt Arial;")
        sb.addWidget(self.conn_status_label)
        
        # Try to connect after a short delay
        QTimer.singleShot(500, self._check_connection)

    def _check_connection(self):
        """Check hardware connection and update status."""
        uart = UARTManager()
        if uart.connect():
            self.conn_status_label.setText("🟢 Connected")
            self.conn_status_label.setStyleSheet("color: green; padding: 2px 8px; font: 9pt Arial;")
            # Store the connected UART instance for later use?
            # We can store it as an attribute for other methods.
            self._uart = uart
        else:
            self.conn_status_label.setText("🔴 Disconnected")
            self.conn_status_label.setStyleSheet("color: red; padding: 2px 8px; font: 9pt Arial;")
            self._uart = None