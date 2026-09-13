"""
SpectraSoft — Analysis Run Page (Simulation)
Every 10 seconds, a new ST (analysis) is automatically completed.
Stop halts the timer. End Analysis shows averages per channel across all STs.
Includes a countdown display.
"""

import random
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QApplication, QFrame, QGroupBox, QComboBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtGui import QTextDocument, QPageLayout
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

# ----------------------------------------------------------------------
# Channels: (name, base_intensity, sequence_it_belongs_to)
CHANNELS = [
    ("Fe_high", 982000, 2),
    ("Fe_low",   12540, 2),
    ("Cr",       45600, 2),
    ("Ni",       23100, 2),
    ("Mn",       65400, 2),
    ("Si",       89200, 3),
    ("Al",       12300, 3),
]
NUM_SEQS = 3

# ----------------------------------------------------------------------
class AnalysisRunPage(QWidget):
    def __init__(self, main_window, group_id: int, group_name: str):
        super().__init__()
        self.main_window = main_window
        self.group_id = group_id
        self.group_name = group_name

        # State
        self.analysis_count = 0
        self.auto_timer = None
        self.countdown_timer = None
        self.remaining_seconds = 0
        self.st_results = []
        self.current_display_mode = "latest"
        self.current_st_view = None
        self._updating_from_timer = False

        # Build UI
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.lightGray)
        self.setPalette(p)

        self._build_ui()
        self._reset_state()

    # ------------------------------------------------------------------
    # Helper: compute table's total required width
    # ------------------------------------------------------------------
    def _get_table_fixed_width(self) -> int:
        if self.table.columnCount() == 0:
            return 0
        total_col_width = sum(self.table.columnWidth(col) for col in range(self.table.columnCount()))
        frame_width = self.table.frameWidth() * 2
        return total_col_width + frame_width

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        bar = QLabel("Analysis Run (Simulation)")
        bar.setFixedHeight(24)
        bar.setContentsMargins(12, 0, 0, 0)
        bar.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        bar.setStyleSheet(
            "background:#5c9bd5;"
            "color:white;"
            "font:bold 10pt Arial;"
        )
        root.addWidget(bar)

        # Outer frame
        outer = QFrame()
        outer.setFrameShape(QFrame.Shape.Box)
        outer.setFrameShadow(QFrame.Shadow.Sunken)
        outer.setLineWidth(2)
        outer.setStyleSheet("background:white;")
        root.addWidget(outer, stretch=1)

        layout = QVBoxLayout(outer)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # AG Info
        ag_group = QGroupBox("Analytical Group")
        ag_group.setStyleSheet(
            "QGroupBox{"
            "background:#f0f0f0;"
            "border:1px solid #888888;"
            "border-radius:4px;"
            "margin-top:8px;"
            "font:bold 10pt Arial;"
            "}"
            "QGroupBox::title{"
            "subcontrol-origin:margin;"
            "left:8px;"
            "padding:0 5px;"
            "color:black;"
            "background:#f0f0f0;"
            "}"
        )
        ag_layout = QVBoxLayout(ag_group)
        ag_layout.setSpacing(5)

        row1 = QHBoxLayout()
        lbl1 = QLabel("AG No.:")
        lbl1.setStyleSheet("font:bold 9pt Arial; color:black;")
        self.ag_id_label = QLabel(str(self.group_id))
        self.ag_id_label.setStyleSheet("font:bold 10pt Arial; color:black;")
        row1.addWidget(lbl1)
        row1.addWidget(self.ag_id_label)
        row1.addStretch()
        ag_layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl2 = QLabel("Group Name:")
        lbl2.setStyleSheet("font:bold 9pt Arial; color:black;")
        self.ag_name_label = QLabel(self.group_name)
        self.ag_name_label.setStyleSheet("font:bold 10pt Arial; color:black;")
        row2.addWidget(lbl2)
        row2.addWidget(self.ag_name_label)
        row2.addStretch()
        ag_layout.addLayout(row2)
        layout.addWidget(ag_group)

        # ST selection row
        st_row = QHBoxLayout()
        st_left = QHBoxLayout()
        st_label = QLabel("Select ST:")
        st_label.setStyleSheet("color:black; font:9pt Arial;")
        st_left.addWidget(st_label)
        self.st_combo = QComboBox()
        self.st_combo.setStyleSheet(
            "QComboBox{"
            "background:white;"
            "color:black;"
            "border:1px solid #888888;"
            "font:9pt Arial;"
            "padding:1px 4px;"
            "}"
            "QComboBox QAbstractItemView{"
            "background:white;"
            "color:black;"
            "}"
        )
        self.st_combo.currentIndexChanged.connect(self._on_st_selected)
        st_left.addWidget(self.st_combo)
        st_row.addLayout(st_left)

        self.st_number_label = QLabel("ST No.: —")
        self.st_number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.st_number_label.setStyleSheet("font:bold 10pt Arial; color:black;")
        st_row.addWidget(self.st_number_label, stretch=1)

        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.analyses_done_label = QLabel(f"Analyses done: {self.analysis_count}")
        self.analyses_done_label.setStyleSheet("font:bold 9pt Arial; color:#555555;")
        right_layout.addWidget(self.analyses_done_label)
        st_row.addWidget(right_widget)
        layout.addLayout(st_row)

        # Table container
        table_container = QHBoxLayout()
        table_container.addStretch()
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(False)  # <-- Removed alternating row colors
        self.table.setStyleSheet(
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
            "background:white;"   # Ensure all items have white background
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
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._build_empty_table()
        table_container.addWidget(self.table)
        table_container.addStretch()
        layout.addLayout(table_container)

        # Buttons
        btn_layout = QHBoxLayout()
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

        self.btn_start = QPushButton("Start")
        self.btn_start.setStyleSheet(btn_style)
        self.btn_start.clicked.connect(self._on_start)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setStyleSheet(btn_style)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)

        self.btn_end = QPushButton("End Analysis")
        self.btn_end.setStyleSheet(btn_style)
        self.btn_end.clicked.connect(self._on_end_analysis)
        self.btn_end.setEnabled(True)

        self.btn_print = QPushButton("Print")
        self.btn_print.setStyleSheet(btn_style)
        self.btn_print.clicked.connect(self._on_print)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_end)
        btn_layout.addWidget(self.btn_print)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("Ready. Press Start to measure.")
        self.status_label.setStyleSheet("color:black; font:9pt Arial;")
        layout.addWidget(self.status_label)

        # Countdown label
        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet("font:bold 9pt Arial; color:#555555;")
        layout.addWidget(self.countdown_label)

    # ------------------------------------------------------------------
    # Table building
    # ------------------------------------------------------------------
    def _build_empty_table(self):
        self.table.clear()
        self.table.setRowCount(len(CHANNELS))
        self.table.setColumnCount(2 + NUM_SEQS)
        headers = ["Ch. No.", "Channel"] + [f"Seq {i+1}" for i in range(NUM_SEQS)]
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 100)
        seq_width = 180
        for col in range(2, 2 + NUM_SEQS):
            self.table.setColumnWidth(col, seq_width)

        self.table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.table.setFixedWidth(self._get_table_fixed_width())

        for row, (ch_name, _, _) in enumerate(CHANNELS):
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, num_item)
            name_item = QTableWidgetItem(ch_name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, name_item)

        self.table.resizeRowsToContents()

    def _fill_table_with_data(self, data_dict: dict):
        for row, (ch_name, _, seq) in enumerate(CHANNELS):
            for seq_col in range(1, NUM_SEQS + 1):
                col = 1 + seq_col
                if seq == seq_col and ch_name in data_dict:
                    val = data_dict[ch_name]
                    item = QTableWidgetItem(f"{val:,.0f}")
                else:
                    item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

    def _fill_table_with_averages(self, averages: dict):
        for row, (ch_name, _, seq) in enumerate(CHANNELS):
            for seq_col in range(1, NUM_SEQS + 1):
                col = 1 + seq_col
                if seq == seq_col and ch_name in averages:
                    val = averages[ch_name]
                    item = QTableWidgetItem(f"{val:,.0f}")
                else:
                    item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Measurement simulation (one complete ST)
    # ------------------------------------------------------------------
    def _generate_one_st_data(self) -> dict:
        result = {}
        for ch_name, base_int, _ in CHANNELS:
            noise = random.uniform(-0.5, 0.5) / 100.0
            result[ch_name] = int(base_int * (1 + noise))
        return result

    def _add_new_st(self, data: dict):
        self.analysis_count += 1
        self.analyses_done_label.setText(f"Analyses done: {self.analysis_count}")
        self.st_results.append({"st_number": self.analysis_count, "data": data})
        self.st_combo.addItem(f"ST {self.analysis_count}")
        self._fill_table_with_data(data)
        self.current_display_mode = "latest"
        self.current_st_view = self.analysis_count
        self.st_number_label.setText(f"ST No.: {self.analysis_count}")
        self._updating_from_timer = True
        self.st_combo.setCurrentIndex(self.st_combo.count() - 1)
        self._updating_from_timer = False

    # ------------------------------------------------------------------
    # Countdown management
    # ------------------------------------------------------------------
    def _start_countdown(self, seconds: int):
        self.remaining_seconds = seconds
        self._update_countdown_label()
        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)
        self.countdown_timer.start(1000)

    def _on_countdown_tick(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.countdown_timer.stop()
            self.countdown_label.setText("")
        else:
            self._update_countdown_label()

    def _update_countdown_label(self):
        self.countdown_label.setText(f"Next ST in {self.remaining_seconds} seconds...")

    def _stop_countdown(self):
        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()
        self.countdown_label.setText("")

    # ------------------------------------------------------------------
    # Timer and actions
    # ------------------------------------------------------------------
    def _on_start(self):
        if self.auto_timer and self.auto_timer.isActive():
            QMessageBox.warning(self, "Warning", "Measurement already running.")
            return
        if self.current_display_mode == "average":
            if self.st_results:
                self._fill_table_with_data(self.st_results[-1]["data"])
                self.current_display_mode = "latest"
                self.current_st_view = self.st_results[-1]["st_number"]
                self.st_number_label.setText(f"ST No.: {self.current_st_view}")
            else:
                self._build_empty_table()
                self.st_number_label.setText("ST No.: —")
            self.st_combo.setCurrentIndex(-1)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_end.setEnabled(True)
        self.status_label.setText("Measuring... New ST every 10 seconds.")
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(False)
        self.auto_timer.timeout.connect(self._on_timer_tick)
        self.auto_timer.start(10000)
        self._start_countdown(10)

    def _on_timer_tick(self):
        new_data = self._generate_one_st_data()
        self._add_new_st(new_data)
        self.status_label.setText(f"ST {self.analysis_count} completed. Next in 10 sec...")
        self._start_countdown(10)

    def _on_stop(self):
        if self.auto_timer and self.auto_timer.isActive():
            self.auto_timer.stop()
        self._stop_countdown()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_end.setEnabled(True)
        self.status_label.setText("Stopped. Press Start to resume new STs.")

    def _reset_state(self):
        if self.auto_timer and self.auto_timer.isActive():
            self.auto_timer.stop()
        self._stop_countdown()
        self.analysis_count = 0
        self.st_results.clear()
        self.analyses_done_label.setText("Analyses done: 0")
        self.st_combo.clear()
        self._build_empty_table()
        self.current_display_mode = "latest"
        self.current_st_view = None
        self.st_number_label.setText("ST No.: —")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_end.setEnabled(True)
        self.status_label.setText("Ready. Press Start to measure.")

    # ------------------------------------------------------------------
    # ST selection from dropdown
    # ------------------------------------------------------------------
    def _on_st_selected(self, index):
        if index < 0:
            return
        if hasattr(self, '_updating_from_timer') and self._updating_from_timer:
            st_data = self.st_results[index]
            self._fill_table_with_data(st_data["data"])
            self.current_display_mode = "latest"
            self.current_st_view = st_data["st_number"]
            self.st_number_label.setText(f"ST No.: {st_data['st_number']}")
            return

        if self.auto_timer and self.auto_timer.isActive():
            self.auto_timer.stop()
            self._stop_countdown()
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.status_label.setText("Stopped because you selected a previous ST.")
        st_data = self.st_results[index]
        self._fill_table_with_data(st_data["data"])
        self.current_display_mode = "stored"
        self.current_st_view = st_data["st_number"]
        self.st_number_label.setText(f"ST No.: {st_data['st_number']}")

    # ------------------------------------------------------------------
    # End Analysis: average across all stored STs
    # ------------------------------------------------------------------
    def _on_end_analysis(self):
        if not self.st_results:
            QMessageBox.information(self, "No Data", "No STs have been measured yet.")
            return
        if self.auto_timer and self.auto_timer.isActive():
            self.auto_timer.stop()
            self._stop_countdown()
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
        averages = {ch_name: 0.0 for ch_name, _, _ in CHANNELS}
        count = len(self.st_results)
        for st in self.st_results:
            for ch_name in averages:
                averages[ch_name] += st["data"][ch_name]
        for ch_name in averages:
            averages[ch_name] /= count

        self._fill_table_with_averages(averages)
        self.current_display_mode = "average"
        self.current_st_view = None
        self.st_number_label.setText("Average of all STs")
        self.status_label.setText(f"Showing averages of {count} ST(s). Press Start for new measurements.")

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _on_print(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self._render_print_page)
        preview.exec()

    def _render_print_page(self, printer):
        doc = QTextDocument()
        is_landscape = printer.pageLayout().orientation() == QPageLayout.Orientation.Landscape
        orientation_str = "landscape" if is_landscape else "portrait"
        html = self._generate_html_report(orientation_str)
        doc.setHtml(html)
        doc.print(printer)

    def _generate_html_report(self, orientation: str) -> str:
        if self.current_display_mode == "average":
            report_subtitle = f"Summary Report — Average of all {len(self.st_results)} Stored STs"
        elif self.current_display_mode == "stored":
            report_subtitle = f"Historical Log — Run Detail for ST No. {self.current_st_view}"
        else:
            report_subtitle = f"Live Run View — Latest Measurements (ST No. {self.current_st_view or '—'})"

        title = "SpectraSoft Analysis Report"
        timestamp = QDate.currentDate().toString("dd-MM-yyyy")

        rows = []
        header_cols = "<th>Ch. No.</th><th>Channel Name</th>" + "".join(f"<th>Seq {i+1}</th>" for i in range(NUM_SEQS))
        rows.append(f"<tr class='header-row'>{header_cols}</tr>")

        for row in range(self.table.rowCount()):
            ch_no_item = self.table.item(row, 0)
            ch_name_item = self.table.item(row, 1)
            ch_no = ch_no_item.text() if ch_no_item else ""
            ch_name = ch_name_item.text() if ch_name_item else ""
            row_html = f"<tr><td class='center-text'>{ch_no}</td><td class='left-text'><b>{ch_name}</b></td>"
            for col in range(2, self.table.columnCount()):
                item = self.table.item(row, col)
                val = item.text() if item else "—"
                row_html += f"<td class='right-text'>{val}</td>"
            row_html += "</tr>"
            rows.append(row_html)

        table_html = f"<table class='report-table'>{''.join(rows)}</table>"

        if orientation == "landscape":
            layout_wrapper = f"""
            <div class='flex-container'>
                <div class='flex-column' style='width: 58%;'>
                    <h3 class='section-title'>Primary Dataset</h3>
                    {table_html}
                </div>
                <div class='flex-column' style='width: 38%; margin-left: 4%;'>
                    <h3 class='section-title'>System Diagnosis & Notes</h3>
                    <div style='border: 1pt solid #bdc3c7; padding: 12pt; background-color: #f8f9fa; font-size: 11pt;'>
                        <p><b>Status:</b> Nominal</p>
                        <p><b>Operator Notes:</b> High-resolution structural batch test complete. Calibration settings verified against internal standards.</p>
                    </div>
                </div>
            </div>
            """
        else:
            layout_wrapper = f"""
            <div class='center-wrapper'>
                {table_html}
            </div>
            """

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; margin: 0.25in; }}
                .header-container {{ border-bottom: 2pt solid #2c3e50; padding-bottom: 8pt; margin-bottom: 15pt; }}
                h2 {{ color: #2c3e50; margin: 0 0 4pt 0; font-size: 24pt; }}
                h4 {{ color: #7f8c8d; margin: 0; font-size: 12pt; font-weight: normal; letter-spacing: 1pt; }}
                .section-title {{ color: #34495e; font-size: 14pt; margin-top: 0; border-bottom: 1pt solid #bdc3c7; padding-bottom: 4pt; }}
                .meta-box {{ margin-bottom: 20pt; background-color: #f8f9fa; padding: 12pt; border-left: 4pt solid #34495e; font-size: 11pt; }}
                .meta-table {{ width: 100%; border: none; }}
                .meta-table td {{ border: none; padding: 3pt 5pt; }}
                .center-wrapper {{ width: 95%; margin: 0 auto; }}
                .flex-container {{ width: 100%; display: block; }}
                .flex-column {{ float: left; }}
                .report-table {{ width: 100%; border-collapse: collapse; margin-top: 10pt; font-size: 11pt; }}
                .report-table th, .report-table td {{ border: 1pt solid #bdc3c7; padding: 8pt 10pt; }}
                .header-row {{ background-color: #34495e; color: #ffffff; font-weight: bold; }}
                .left-text {{ text-align: left; }}
                .center-text {{ text-align: center; color: #7f8c8d; }}
                .right-text {{ text-align: right; font-family: 'Courier New', monospace; font-weight: bold; font-size: 11pt; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .clear {{ clear: both; }}
                .footer {{ margin-top: 40pt; border-top: 1px solid #dcdde1; padding-top: 10pt; font-size: 10pt; color: #7f8c8d; text-align: right; }}
            </style>
        </head>
        <body>
            <div class='header-container'>
                <h2>{title}</h2>
                <h4>{report_subtitle}</h4>
            </div>
            <div class='meta-box'>
                <table class='meta-table'>
                    <tr>
                        <td><b>Analytical Group:</b> {self.group_name} (ID: {self.group_id})</td>
                        <td style='text-align: right;'><b>Date Generated:</b> {timestamp}</td>
                    </tr>
                    <tr>
                        <td><b>Total Runs Captured:</b> {self.analysis_count} STs</td>
                        <td style='text-align: right;'><b>Mode:</b> {orientation.capitalize()} View</td>
                    </tr>
                </table>
            </div>
            {layout_wrapper}
            <div class='clear'></div>
            <div class='footer'>
                SpectraSoft Core System Engine • Page 1 of 1
            </div>
        </body>
        </html>
        """

    def wants_fullscreen(self) -> bool:
        return True

# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    class DummyMain:
        def set_right_widget(self, w):
            w.show()
    main = DummyMain()
    page = AnalysisRunPage(main, group_id=1, group_name="Hitesh")
    page.show()
    sys.exit(app.exec())