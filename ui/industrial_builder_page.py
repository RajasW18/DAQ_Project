"""User-driven interface for planning, reviewing and running control tasks."""

import os
import json
import csv
import math
import html
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QFileDialog, QListWidget, QTextEdit, QMessageBox, QGroupBox,
    QFormLayout
)

from industrial_control_builder.ai_orchestrator.central_agent import CentralIndustrialOrchestrator
from industrial_control_builder.ai_orchestrator.command_dsl import CommandDSLCompiler
from industrial_control_builder.hal.registry import get_board
from industrial_control_builder.sequence.task_engine import TaskEngine
from industrial_control_builder.driver.firmware_manager import FirmwareManager
from industrial_control_builder.ai_orchestrator.llm_provider import create_provider
from industrial_control_builder.ai_orchestrator.report_generator import SystemReportGenerator
from industrial_control_builder.doc_ingest.ingest_manager import DocumentIngestManager


class BuilderWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, *args):
        super().__init__()
        self.operation, self.args = operation, args

    def run(self):
        try:
            self.completed.emit(self.operation(*self.args))
        except Exception as exc:
            self.failed.emit(str(exc))


class IndustrialBuilderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths = []
        self.conversation = []
        self.worker = None
        self.latest_results = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        heading = QLabel("Industrial Control Builder")
        heading.setStyleSheet("font-size:18pt;font-weight:600;color:#20242a;")
        root.addWidget(heading)
        note = QLabel(
            "The AI drafts a plan. The application validates it, shows the commands, "
            "and asks before execution. Arbitrary model-generated code is never run."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        settings = QGroupBox("Planner and controller")
        form = QFormLayout(settings)
        self.provider = QComboBox()
        self.provider.addItems(["Groq API", "Ollama local"])
        form.addRow("LLM provider", self.provider)
        provider_note = QLabel("Groq sends extracted text to its API. Ollama keeps inference local on this computer.")
        provider_note.setWordWrap(True)
        form.addRow(provider_note)
        self.mode = QComboBox()
        self.mode.addItems(["Simulation (safe default)", "Live serial — Universal SEQ firmware"])
        form.addRow("Execution", self.mode)
        self.port = QLineEdit()
        self.port.setPlaceholderText("e.g. COM4 (required for live mode)")
        form.addRow("Serial port", self.port)
        warning = QLabel(
            "Live mode requires firmware/ running the workspace PIN/W/SEQ_* protocol. "
            "The pasted spectroscopy firmware uses O/A/B/I/T and is not compatible with SEQ_* yet."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#9a4d00;")
        form.addRow(warning)
        root.addWidget(settings)

        docs_row = QHBoxLayout()
        self.add_docs = QPushButton("Add context files")
        self.add_docs.clicked.connect(self._choose_docs)
        docs_row.addWidget(self.add_docs)
        self.remove_docs = QPushButton("Remove selected")
        self.remove_docs.clicked.connect(self._remove_doc)
        docs_row.addWidget(self.remove_docs)
        docs_row.addStretch(1)
        root.addLayout(docs_row)
        self.doc_list = QListWidget()
        self.doc_list.setMaximumHeight(85)
        root.addWidget(self.doc_list)

        root.addWidget(QLabel("Describe the sequence or analysis you want"))
        self.intent = QTextEdit()
        self.intent.setPlaceholderText("Example: Read analog channel A0, then calculate summary statistics.")
        self.intent.setMaximumHeight(90)
        root.addWidget(self.intent)
        data_row = QHBoxLayout()
        data_row.addWidget(QLabel("Analysis Y column (blank = first numeric column)"))
        self.data_column = QLineEdit()
        self.data_column.setPlaceholderText("Y column name")
        data_row.addWidget(self.data_column)
        data_row.addWidget(QLabel("X column (blank = row index)"))
        self.x_column = QLineEdit()
        self.x_column.setPlaceholderText("Optional X column")
        data_row.addWidget(self.x_column)
        root.addLayout(data_row)
        self.plan_button = QPushButton("Draft and validate plan")
        self.plan_button.clicked.connect(self._draft)
        root.addWidget(self.plan_button)

        root.addWidget(QLabel("Plan (editable compact commands)"))
        self.plan = QTextEdit()
        self.plan.setPlaceholderText("The generated plan will appear here for review.")
        root.addWidget(self.plan, stretch=1)

        actions = QHBoxLayout()
        self.run_button = QPushButton("Review and run")
        self.run_button.clicked.connect(self._run)
        actions.addWidget(self.run_button)
        self.report_button = QPushButton("Save build report")
        self.report_button.clicked.connect(self._save_report)
        actions.addWidget(self.report_button)
        self.build_fw_button = QPushButton("Build firmware")
        self.build_fw_button.clicked.connect(self._build_firmware)
        actions.addWidget(self.build_fw_button)
        self.flash_fw_button = QPushButton("Build and flash…")
        self.flash_fw_button.clicked.connect(self._flash_firmware)
        actions.addWidget(self.flash_fw_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Validation, execution and analysis results appear here.")
        self.output.setMinimumHeight(170)
        root.addWidget(self.output)

    def _choose_docs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose reference files", "",
            "Supported files (*.txt *.json *.csv *.xlsx *.xlsm *.docx *.pdf *.png *.jpg *.jpeg *.bmp)")
        for path in paths:
            if path not in self.paths:
                self.paths.append(path)
                self.doc_list.addItem(os.path.basename(path))

    def _remove_doc(self):
        row = self.doc_list.currentRow()
        if row >= 0:
            self.doc_list.takeItem(row)
            self.paths.pop(row)

    def _provider_id(self):
        return "ollama" if self.provider.currentIndex() == 1 else "groq"

    def _set_busy(self, busy):
        self.plan_button.setEnabled(not busy)
        self.run_button.setEnabled(not busy)
        self.add_docs.setEnabled(not busy)
        self.build_fw_button.setEnabled(not busy)
        self.flash_fw_button.setEnabled(not busy)

    def _build_firmware(self):
        self._set_busy(True)
        self.output.setPlainText("Building the fixed PlatformIO ATmega2560 firmware…")
        self.worker = BuilderWorker(FirmwareManager().build)
        self.worker.completed.connect(self._firmware_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _flash_firmware(self):
        port = self.port.text().strip()
        if not port:
            QMessageBox.warning(self, "Serial port required", "Enter the controller's serial port before flashing.")
            return
        answer = QMessageBox.warning(
            self, "Flash controller firmware",
            f"Build and upload the workspace ATmega2560 firmware to {port}?\n\n"
            "This replaces the firmware currently on the connected board. The firmware uses the workspace PIN/W/SEQ_* protocol.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self.output.setPlainText(f"Building firmware and uploading to {port}…")
        self.worker = BuilderWorker(FirmwareManager().build_and_upload, port)
        self.worker.completed.connect(self._firmware_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _firmware_done(self, output):
        self._set_busy(False)
        self.output.setPlainText(output)
        QMessageBox.information(self, "PlatformIO", "Operation completed. Review the output for the firmware result.")

    def _draft(self):
        intent = self.intent.toPlainText().strip()
        if not intent:
            QMessageBox.information(self, "Describe a request", "Enter what you want the controller or analysis to do.")
            return
        self._set_busy(True)
        self.output.setPlainText("Reading selected documents and asking the configured model for a draft…")
        self.worker = BuilderWorker(self._draft_plan, intent, list(self.paths), self._provider_id(), list(self.conversation))
        self.worker.completed.connect(self._draft_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    @staticmethod
    def _draft_plan(intent, paths, provider, conversation):
        docs = [DocumentIngestManager.ingest_file(path) for path in paths]
        context = DocumentIngestManager.build_summary_for_llm(docs)
        agent = CentralIndustrialOrchestrator.__new__(CentralIndustrialOrchestrator)
        agent.hal = get_board("atmega2560")
        agent.provider = create_provider(provider)
        return {"intent": intent, "plan": agent.formulate_sequence_plan(intent, context, conversation)}

    def _draft_done(self, plan):
        self._set_busy(False)
        result = plan["plan"]
        self.plan.setPlainText(result["dsl"])
        self.conversation.extend([
            {"role": "user", "content": plan["intent"]},
            {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)}
        ])
        self.conversation = self.conversation[-8:]
        explanation = result.get("explanation", "Draft ready.")
        if result["dsl"].strip():
            try:
                _, _, logs = self._validate(result["dsl"])
                explanation += "\n\nLocal validation passed.\n" + "\n".join(logs)
            except Exception as exc:
                explanation += f"\n\nValidation needs edits: {exc}"
        self.output.setPlainText(explanation)
        self.latest_results = None

    def _validate(self, dsl):
        class NoopDriver:
            def send_command(self, _command):
                raise RuntimeError("Validation must not send controller commands")
        engine = TaskEngine(get_board("atmega2560"), NoopDriver())
        return CommandDSLCompiler.compile(dsl, engine.hal, engine)

    def _run(self):
        dsl = self.plan.toPlainText().strip()
        try:
            engine, pipeline, logs = self._validate(dsl)
        except Exception as exc:
            QMessageBox.warning(self, "Plan needs changes", str(exc))
            return
        mode = self.mode.currentIndex()
        if not engine.steps:
            table_path = next((p for p in self.paths if p.lower().endswith((".csv", ".xlsx", ".xlsm"))), None)
            if not pipeline.steps or not table_path:
                QMessageBox.information(self, "Analysis data required", "Analysis-only plans need at least one PIPE block and a CSV or Excel file added under context files.")
                return
            self._set_busy(True)
            self.output.setPlainText("Analyzing the selected table with deterministic math blocks…")
            self.worker = BuilderWorker(self._execute_table_analysis, dsl, table_path,
                                        self.data_column.text().strip(), self.x_column.text().strip())
            self.worker.completed.connect(self._analysis_done)
            self.worker.failed.connect(self._failed)
            self.worker.start()
            return
        port = self.port.text().strip()
        if mode == 1 and not port:
            QMessageBox.warning(self, "Serial port required", "Enter the COM port for the live controller.")
            return
        destination = "live controller" if mode == 1 else "simulation"
        confirm = QMessageBox.question(
            self, "Approve execution",
            f"Run {len(engine.steps)} hardware steps on the {destination}?\n\n" + "\n".join(logs[:12]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self.output.setPlainText("Executing approved plan…")
        self.worker = BuilderWorker(self._execute, dsl, mode == 0, port, self._provider_id(), list(self.paths))
        self.worker.completed.connect(self._run_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    @staticmethod
    def _execute(dsl, use_mock, port, provider, paths):
        agent = CentralIndustrialOrchestrator(port=port or None, use_mock=use_mock, provider_name=provider)
        if not agent.driver.is_connected:
            raise RuntimeError("Could not connect to the selected controller. No simulation fallback was used.")
        try:
            if paths:
                agent.ingest_documents(paths)
            result = agent.execute_dsl(dsl, approved=True, timeout_sec=30)
            return {"result": result, "dsl": dsl, "board": agent.hal.get_pinout_summary(),
                    "steps": agent.task_engine.steps, "docs": agent.ingested_docs,
                    "provider": provider, "mode": "simulation" if use_mock else "live"}
        finally:
            agent.shutdown()

    def _run_done(self, value):
        self._set_busy(False)
        self.latest_results = value
        result = value["result"]
        self.output.setHtml(self._format_run_summary(value))

    @staticmethod
    def _format_run_summary(value):
        """Render execution data as a readable run report instead of raw JSON."""
        result = value["result"]
        status = result["run_status"]
        analysis = result["pipeline_results"]
        esc = lambda item: html.escape(str(item))
        mode = value.get("mode", "unknown").replace("_", " ").title()
        state = status.get("status", "UNKNOWN")
        elapsed = status.get("elapsed_s", 0)
        steps = status.get("steps_count", 0)
        readings = status.get("readings", [])
        parts = [
            "<h3 style='margin:0 0 6px 0'>Run complete</h3>",
            f"<p style='margin:0 0 8px 0'><b>{esc(state)}</b> &nbsp;|&nbsp; "
            f"Mode: {esc(mode)} &nbsp;|&nbsp; Steps: {esc(steps)} &nbsp;|&nbsp; "
            f"Elapsed: {esc(f'{float(elapsed):.3f} s')} &nbsp;|&nbsp; "
            f"Readings: {esc(len(readings))}</p>",
        ]
        commands = result.get("logs", [])
        if commands:
            parts.append("<b>Sequence</b><ol style='margin-top:4px'>")
            parts.extend(f"<li>{esc(command)}</li>" for command in commands)
            parts.append("</ol>")
        outputs = analysis.get("step_outputs", {}) if isinstance(analysis, dict) else {}
        if outputs:
            parts.append("<b>Analysis</b><ul style='margin-top:4px'>")
            for name, details in outputs.items():
                rendered = ", ".join(
                    f"{esc(key.replace('_', ' ').title())}: {esc(val)}"
                    for key, val in details.items()
                ) if isinstance(details, dict) else esc(details)
                parts.append(f"<li><b>{esc(name.replace('_', ' ').title())}</b> — {rendered}</li>")
            parts.append("</ul>")
        elif analysis.get("note"):
            parts.append(f"<p style='margin:4px 0'><b>Analysis:</b> {esc(analysis['note'])}</p>")
        if readings:
            parts.append("<b>Readings</b><ul style='margin-top:4px'>")
            parts.extend(
                f"<li>{esc(item.get('channel', 'Reading'))}: {esc(item.get('value'))}</li>"
                for item in readings[:20]
            )
            parts.append("</ul>")
        return "".join(parts)

    @staticmethod
    def _execute_table_analysis(dsl, path, column_name, x_column_name):
        engine, pipeline, logs = IndustrialBuilderPage._validate_static(dsl)
        if engine.steps or not pipeline.steps:
            raise ValueError("Table analysis requires an analysis-only plan.")
        if path.lower().endswith(".csv"):
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)
        else:
            try:
                from openpyxl import load_workbook
            except ImportError as exc:
                raise RuntimeError("Excel analysis requires openpyxl. Install project requirements and restart.") from exc
            book = load_workbook(path, read_only=True, data_only=True)
            sheet = book.active
            raw_rows = sheet.iter_rows(values_only=True)
            headers = [str(v) if v is not None else "" for v in next(raw_rows, ())]
            rows = [dict(zip(headers, row)) for row in raw_rows]
            book.close()
        if not headers:
            raise ValueError("The table needs a header row.")
        column = column_name or next((h for h in headers if h and any(
            _as_number(row.get(h)) is not None for row in rows)), "")
        if column not in headers:
            raise ValueError(f"Y column {column!r} was not found. Available: {', '.join(headers)}")
        if x_column_name and x_column_name not in headers:
            raise ValueError(f"X column {x_column_name!r} was not found. Available: {', '.join(headers)}")
        values, x_values = [], []
        for row_no, row in enumerate(rows, 2):
            yv = _as_number(row.get(column))
            xv = _as_number(row.get(x_column_name)) if x_column_name else float(row_no - 2)
            if yv is None:
                if row.get(column) in (None, ""):
                    continue
                raise ValueError(f"Y column {column!r} contains a nonnumeric value at row {row_no}.")
            if xv is None:
                raise ValueError(f"X column {x_column_name!r} contains a nonnumeric value at row {row_no}.")
            values.append(yv); x_values.append(xv)
        if not values:
            raise ValueError(f"No numeric values found in column {column!r}.")
        output = pipeline.execute(values, x_values)
        record = [{"channel": column, "value": v, "timestamp": i} for i, v in enumerate(values)]
        run_status = {"status": "ANALYSIS_ONLY", "steps_count": 0, "readings": record, "elapsed_s": 0}
        return {"result": {"logs": logs, "run_status": run_status,
                            "pipeline_results": output},
                "dsl": dsl, "board": get_board("atmega2560").get_pinout_summary(),
                "steps": [], "docs": [{"filename": os.path.basename(path),
                                          "type": "table_data", "analysis_y_column": column,
                                          "analysis_x_column": x_column_name or "row index"}],
                "provider": "none", "mode": "analysis only"}

    @staticmethod
    def _validate_static(dsl):
        class NoopDriver:
            def send_command(self, _command):
                raise RuntimeError("Validation must not send controller commands")
        hal = get_board("atmega2560")
        engine = TaskEngine(hal, NoopDriver())
        return CommandDSLCompiler.compile(dsl, hal, engine)

    def _analysis_done(self, value):
        self._run_done(value)

    def _save_report(self):
        if not self.latest_results:
            QMessageBox.information(self, "No run to report", "Run an approved plan first so the report can reflect recorded results.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save build report", "industrial_build_report.md", "Markdown (*.md)")
        if not path:
            return
        value = self.latest_results
        result = value["result"]
        md = SystemReportGenerator.generate_markdown(
            project_name="User-defined Industrial Control Task", board_summary=value["board"],
            ingested_docs=value["docs"], dsl_code=value["dsl"], sequence_steps=value["steps"],
            pipeline_results=result["pipeline_results"],
            run_status={**result["run_status"], "execution_mode": value["mode"],
                        "provider": value["provider"]})
        SystemReportGenerator.save_report(md, path)
        QMessageBox.information(self, "Report saved", f"Saved report to:\n{path}")

    def _failed(self, error):
        self._set_busy(False)
        self.output.setPlainText("Operation failed: " + error)
        QMessageBox.warning(self, "Industrial Builder", error)


def _as_number(value):
    try:
        if value is None or value == "":
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None
