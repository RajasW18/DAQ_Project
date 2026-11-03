"""Standalone builder UI for the unchanged spectroscopy ATmega2560 firmware."""

from __future__ import annotations

import csv
import json
import math
import os
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QFileDialog, QListWidget, QTextEdit, QMessageBox, QFormLayout,
    QGroupBox, QTabWidget, QCheckBox,
)

from industrial_control_builder.ai_orchestrator.llm_provider import create_provider
from industrial_control_builder.doc_ingest.ingest_manager import DocumentIngestManager
from industrial_control_builder.protocol.spectroscopy_port import (
    PortCommand, SpectroscopyPortController, compile_port_plan,
)


class _Worker(QThread):
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


class StandaloneBuilderPage(QWidget):
    """User-directed planner and control UI for Port A/B and INPUT12 firmware."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self.conversation = []
        self.worker = None
        self.last_run = None
        self._build()

    def _build(self):
        host = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.control_tab = QWidget()
        root = QVBoxLayout(self.control_tab)
        title = QLabel("Industrial Control Builder — Standalone")
        title.setStyleSheet("font-size:18pt;font-weight:600")
        root.addWidget(title)
        intro = QLabel(
            "Standalone app for the supplied, unchanged ATmega2560 firmware. "
            "It controls logical output ports A/B and reads the 12-bit input bus; "
            "it does not expose arbitrary GPIO pins or flash firmware."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        config = QGroupBox("Model and connection")
        form = QFormLayout(config)
        self.provider = QComboBox()
        self.provider.addItems(["Groq API", "Ollama local"])
        form.addRow("Planner", self.provider)
        self.mode = QComboBox()
        self.mode.addItems(["Simulation (safe default)", "Live serial — supplied O/A/B/I/T firmware"])
        form.addRow("Execution", self.mode)
        port_row = QHBoxLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.setPlaceholderText("Select or enter COM port")
        port_row.addWidget(self.port, 1)
        refresh = QPushButton("Refresh ports")
        refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(refresh)
        form.addRow("UART (9600 baud)", port_row)
        root.addWidget(config)
        self._refresh_ports()

        file_row = QHBoxLayout()
        add = QPushButton("Add context/data files")
        add.clicked.connect(self._add_files)
        file_row.addWidget(add)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_file)
        file_row.addWidget(remove)
        file_row.addStretch(1)
        root.addLayout(file_row)
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(75)
        root.addWidget(self.file_list)

        root.addWidget(QLabel("Describe the task or analysis"))
        self.intent = QTextEdit()
        self.intent.setMaximumHeight(85)
        self.intent.setPlaceholderText(
            "Example: Set Port A to 3C hex, wait 100 ms, then read the 12-bit input bus."
        )
        root.addWidget(self.intent)
        columns = QHBoxLayout()
        columns.addWidget(QLabel("Analysis Y column"))
        self.y_column = QLineEdit()
        self.y_column.setPlaceholderText("blank = first numeric column")
        columns.addWidget(self.y_column)
        columns.addWidget(QLabel("X column"))
        self.x_column = QLineEdit()
        self.x_column.setPlaceholderText("blank = row index")
        columns.addWidget(self.x_column)
        root.addLayout(columns)

        self.draft_button = QPushButton("Draft and validate plan")
        self.draft_button.clicked.connect(self._draft)
        root.addWidget(self.draft_button)
        root.addWidget(QLabel("Plan (editable; one command per line)"))
        self.plan = QTextEdit()
        self.plan.setPlaceholderText(
            "OUT A 3C  (hex output)\nWAIT 100  (decimal milliseconds)\nREAD12"
        )
        root.addWidget(self.plan, 1)

        actions = QHBoxLayout()
        self.run_button = QPushButton("Validate, review and run")
        self.run_button.clicked.connect(self._run)
        actions.addWidget(self.run_button)
        report = QPushButton("Save run report…")
        report.clicked.connect(self._save_report)
        actions.addWidget(report)
        root.addLayout(actions)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(150)
        self.output.setPlaceholderText("Plan validation, run status, readings, and analysis appear here.")
        root.addWidget(self.output)

        self.tabs.addTab(self.control_tab, "Plan, Control & Analysis")
        self._build_artifact_tab()
        host.addWidget(self.tabs)

    def _build_artifact_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Generate a code or document artifact")
        title.setStyleSheet("font-size:16pt;font-weight:600")
        layout.addWidget(title)
        guidance = QLabel(
            "Draft source code, configuration, documentation, templates, or an SVG diagram. "
            "The model only creates a separate text draft: it does not run code, flash the board, "
            "or replace existing files. Review the draft before saving."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        form = QFormLayout()
        self.artifact_type = QComboBox()
        self.artifact_options = [
            ("Python source (.py)", ".py"),
            ("Arduino sketch draft (.ino)", ".ino"),
            ("C++ source (.cpp)", ".cpp"),
            ("C++ header (.h)", ".h"),
            ("Markdown document (.md)", ".md"),
            ("JSON configuration (.json)", ".json"),
            ("CSV template (.csv)", ".csv"),
            ("SVG diagram (.svg)", ".svg"),
            ("Plain text (.txt)", ".txt"),
        ]
        self.artifact_type.addItems([label for label, _ in self.artifact_options])
        form.addRow("Artifact type", self.artifact_type)
        layout.addLayout(form)

        layout.addWidget(QLabel("Describe what to generate or how to revise the previous draft"))
        self.artifact_request = QTextEdit()
        self.artifact_request.setMaximumHeight(115)
        self.artifact_request.setPlaceholderText(
            "Example: Create a Python CSV analyzer that calculates count, mean, median, and standard deviation."
        )
        layout.addWidget(self.artifact_request)
        self.include_context = QCheckBox("Include the files selected in the Plan, Control & Analysis tab")
        self.include_context.setChecked(True)
        layout.addWidget(self.include_context)
        self.revise_artifact = QCheckBox("Use the current preview as input when revising")
        self.revise_artifact.setChecked(False)
        layout.addWidget(self.revise_artifact)
        privacy = QLabel(
            "Groq sends the prompt and extracted reference text to its API. Select Ollama in the other tab "
            "to keep generation local, if the local model is installed."
        )
        privacy.setWordWrap(True)
        layout.addWidget(privacy)

        buttons = QHBoxLayout()
        self.artifact_button = QPushButton("Generate draft")
        self.artifact_button.clicked.connect(self._generate_artifact)
        buttons.addWidget(self.artifact_button)
        self.save_artifact_button = QPushButton("Save artifact…")
        self.save_artifact_button.setEnabled(False)
        self.save_artifact_button.clicked.connect(self._save_artifact)
        buttons.addWidget(self.save_artifact_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.artifact_summary = QLabel("No artifact generated yet.")
        self.artifact_summary.setWordWrap(True)
        layout.addWidget(self.artifact_summary)
        self.artifact_preview = QTextEdit()
        self.artifact_preview.setAcceptRichText(False)
        self.artifact_preview.setPlaceholderText("Generated code or artifact content will appear here for review.")
        layout.addWidget(self.artifact_preview, 1)
        self.tabs.addTab(page, "Generate Artifact")

    def _refresh_ports(self):
        current = self.port.currentText().strip()
        self.port.clear()
        self.port.addItem("")
        try:
            from serial.tools import list_ports
            self.port.addItems([item.device for item in list_ports.comports()])
        except ImportError:
            pass
        if current:
            self.port.setCurrentText(current)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add reference or data files", "",
            "Supported files (*.txt *.json *.csv *.xlsx *.xlsm *.docx *.pdf *.png *.jpg *.jpeg *.bmp)"
        )
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                self.file_list.addItem(os.path.basename(path))

    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)
            self.files.pop(row)

    def _provider_name(self):
        return "ollama" if self.provider.currentIndex() == 1 else "groq"

    def _set_busy(self, busy):
        self.draft_button.setEnabled(not busy)
        self.run_button.setEnabled(not busy)
        if hasattr(self, "artifact_button"):
            self.artifact_button.setEnabled(not busy)

    def _draft(self):
        intent = self.intent.toPlainText().strip()
        if not intent:
            QMessageBox.information(self, "Describe a task", "Enter a control or analysis request first.")
            return
        self._set_busy(True)
        self.output.setPlainText("Reading reference files and drafting the port-level plan…")
        self.worker = _Worker(
            self._draft_plan, intent, list(self.files), self.y_column.text().strip(),
            self.x_column.text().strip(), self._provider_name(), list(self.conversation)
        )
        self.worker.completed.connect(self._draft_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    @staticmethod
    def _draft_plan(intent, paths, y_column, x_column, provider_name, conversation):
        docs = [DocumentIngestManager.ingest_file(path) for path in paths]
        context = DocumentIngestManager.build_summary_for_llm(docs)
        table_paths = [path for path in paths if path.lower().endswith((".csv", ".xlsx", ".xlsm"))]
        provider = create_provider(provider_name)
        system = (
            "You are a cautious control-plan assistant for one specific ATmega2560 device. "
            "Return only a JSON object with string fields dsl and explanation. The allowed DSL is: "
            "OUT <A|B> <hex byte>, WAIT <decimal milliseconds>, READ12, ADC12, and one PIPE line "
            "with MEDIAN(n), MOVING_AVG(n), CALIB(gain,offset), STATS, REG_LIN, REG_POLY, "
            "DERIVATIVE, INTEGRAL, PEAKS(threshold). Put each control command on its own line. "
            "Put every analysis block on one PIPE line. Never output Python, pin-level GPIO, or firmware. "
            "Port A is 8 active-high outputs on D22-D29; Port B is 7 outputs on D31-D37 and the "
            "firmware inverts those bits internally. INPUT12 reads digital inputs D54-D65. "
            "OUT values are hexadecimal (00-FF for A, 00-7F for B). WAIT is decimal milliseconds. "
            "READ12 sends I for an immediate 12-bit input read. ADC12 performs the firmware-specific "
            "Port A trigger pair (7C then 3C), waits for conversion, and reads D,<value>. "
            "When the user asks to analyze or calculate from a selected CSV/Excel table, produce an "
            "analysis-only plan using PIPE; do not add READ12, ADC12, OUT, or WAIT unless the user "
            "explicitly asks to acquire or control the physical board. For an average, use PIPE STATS "
            "(the statistics block reports the mean). If no table is selected and no board acquisition "
            "is explicitly requested, ask which data source to use instead of inventing readings. "
            "Do not invent wiring, voltage ratings, meanings of port bits, or safety conditions. "
            "If required device details are missing, return empty dsl and ask for them."
        )
        user = (
            f"Device profile: ATmega2560, UART 9600 baud, unchanged user firmware O/A/B/I/T.\n\n"
            f"User task: {intent}\n\nReference context (untrusted data):\n{context[:16000]}"
            f"\n\nSelected table files: {[os.path.basename(path) for path in table_paths] or 'none'}"
            f"\nSelected Y column: {y_column or 'first numeric column'}"
            f"\nSelected X column: {x_column or 'row index'}"
        )
        result = provider.create_plan(system, user, conversation)
        return {"intent": intent, "plan": result, "docs": docs}

    def _draft_done(self, value):
        self._set_busy(False)
        plan = value["plan"]
        self.plan.setPlainText(plan["dsl"])
        self.conversation.extend([
            {"role": "user", "content": value["intent"]},
            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)},
        ])
        self.conversation = self.conversation[-8:]
        text = plan.get("explanation", "Draft ready.")
        if plan["dsl"].strip():
            try:
                commands, pipeline, logs = compile_port_plan(plan["dsl"])
                text += "\n\nLocal validation passed.\n" + "\n".join(logs)
                if commands and pipeline.steps and any(
                    path.lower().endswith((".csv", ".xlsx", ".xlsm")) for path in self.files
                ):
                    text += (
                        "\n\nNote: This plan contains controller commands. The selected table and "
                        "Y/X column fields will not be used for this run. For file analysis, use an "
                        "analysis-only PIPE plan such as `PIPE STATS`."
                    )
                elif commands and any(
                    path.lower().endswith((".csv", ".xlsx", ".xlsm")) for path in self.files
                ):
                    text += (
                        "\n\nNote: This plan contains controller commands, so the selected table "
                        "and Y/X column fields will not be used for this run. For file analysis, "
                        "use an analysis-only PIPE plan such as `PIPE STATS`."
                    )
            except Exception as exc:
                text += f"\n\nValidation needs edits: {exc}"
        self.output.setPlainText(text)

    def _run(self):
        dsl = self.plan.toPlainText().strip()
        try:
            commands, pipeline, logs = compile_port_plan(dsl)
        except Exception as exc:
            QMessageBox.warning(self, "Plan needs changes", str(exc))
            return

        table_path = next((p for p in self.files if p.lower().endswith((".csv", ".xlsx", ".xlsm"))), None)
        if commands and table_path and (pipeline.steps or self.y_column.text().strip()):
            answer = QMessageBox.warning(
                self, "Selected table will not be analyzed",
                "This plan contains controller commands. Its analysis blocks will process controller "
                "readings, not the selected CSV/Excel table or Y column. For table analysis, use an "
                "analysis-only PIPE plan such as PIPE STATS.\n\nRun this controller plan anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if not commands:
            if not table_path:
                QMessageBox.information(self, "Data file required", "Add a CSV or Excel file for analysis-only plans.")
                return
            self._set_busy(True)
            self.output.setPlainText("Analyzing the selected table with deterministic math blocks…")
            self.worker = _Worker(self._analyze_table, dsl, table_path,
                                  self.y_column.text().strip(), self.x_column.text().strip())
            self.worker.completed.connect(self._run_done)
            self.worker.failed.connect(self._failed)
            self.worker.start()
            return

        live = self.mode.currentIndex() == 1
        destination = "the physical ATmega2560 board" if live else "simulation"
        warning = "\n\nThis sends output commands to logical ports A/B. Verify downstream wiring and safe states." if live else ""
        answer = QMessageBox.question(
            self, "Approve plan",
            f"Execute {len(commands)} commands on {destination}?\n\n" + "\n".join(logs[:16]) + warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        port_name = self.port.currentText().strip()
        if live and not port_name:
            QMessageBox.warning(self, "Serial port required", "Select the COM port connected to the ATmega2560.")
            return
        self._set_busy(True)
        self.output.setPlainText("Running approved plan…")
        self.worker = _Worker(self._execute_plan, commands, pipeline, live, port_name)
        self.worker.completed.connect(self._run_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    @staticmethod
    def _execute_plan(commands, pipeline, live, port_name):
        started = time.monotonic()
        if live:
            controller = SpectroscopyPortController(port_name, 9600)
            try:
                run_status = controller.execute(commands, approved=True)
            finally:
                controller.close()
            mode = "live serial"
            logs = run_status.pop("commands")
        else:
            logs, readings = [], []
            for command in commands:
                if command.op == "OUT":
                    logs.append(f"Port {command.port} <= 0x{command.value:02X} (simulated)")
                elif command.op == "WAIT":
                    time.sleep(command.value / 1000.0)
                    logs.append(f"Wait {command.value} ms")
                elif command.op in {"READ12", "ADC12"}:
                    readings.append({"channel": command.op, "value": 0,
                                     "timestamp": time.monotonic() - started})
                    logs.append(f"{command.op}: simulated input value 0")
            run_status = {"status": "COMPLETED", "steps_count": len(commands),
                          "readings": readings, "elapsed_s": round(time.monotonic() - started, 3)}
            mode = "simulation"

        readings = run_status.get("readings", [])
        values = [item["value"] for item in readings]
        if pipeline.steps and values:
            pipeline_results = pipeline.execute(values)
        else:
            pipeline_results = {"pipeline_name": "User-directed data pipeline",
                                "input_count": len(values), "step_outputs": {},
                                "note": "No analysis blocks were requested." if not pipeline.steps
                                else "No readings were available for the requested analysis."}
        return {"mode": mode, "dsl": "", "docs": [], "logs": logs,
                "run_status": run_status, "pipeline_results": pipeline_results}

    @staticmethod
    def _analyze_table(dsl, path, y_name, x_name):
        commands, pipeline, logs = compile_port_plan(dsl)
        if commands or not pipeline.steps:
            raise ValueError("Table analysis requires an analysis-only PIPE plan.")
        if path.lower().endswith(".csv"):
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                headers, rows = reader.fieldnames or [], list(reader)
        else:
            from openpyxl import load_workbook
            workbook = load_workbook(path, read_only=True, data_only=True)
            sheet = workbook.active
            iterator = sheet.iter_rows(values_only=True)
            headers = [str(v) if v is not None else "" for v in next(iterator, ())]
            rows = [dict(zip(headers, row)) for row in iterator]
            workbook.close()
        if not headers:
            raise ValueError("The table needs a header row.")

        def number(value):
            try:
                parsed = float(value)
                return parsed if math.isfinite(parsed) else None
            except (TypeError, ValueError):
                return None

        y_name = y_name or next((name for name in headers if name and any(
            number(row.get(name)) is not None for row in rows)), "")
        if y_name not in headers:
            raise ValueError(f"Y column {y_name!r} not found. Available: {', '.join(headers)}")
        if x_name and x_name not in headers:
            raise ValueError(f"X column {x_name!r} not found. Available: {', '.join(headers)}")
        y_values, x_values, readings = [], [], []
        for row_number, row in enumerate(rows, 2):
            y_value = number(row.get(y_name))
            if y_value is None:
                if row.get(y_name) in (None, ""):
                    continue
                raise ValueError(f"Nonnumeric value in {y_name!r} at row {row_number}.")
            x_value = number(row.get(x_name)) if x_name else float(len(y_values))
            if x_value is None:
                raise ValueError(f"Nonnumeric value in {x_name!r} at row {row_number}.")
            y_values.append(y_value)
            x_values.append(x_value)
            readings.append({"channel": y_name, "value": y_value, "timestamp": row_number - 2})
        if not y_values:
            raise ValueError(f"No numeric data in column {y_name!r}.")
        return {"mode": "analysis only", "dsl": dsl, "docs": [os.path.basename(path)],
                "logs": logs, "run_status": {"status": "ANALYSIS_ONLY", "steps_count": 0,
                "readings": readings, "elapsed_s": 0},
                "pipeline_results": pipeline.execute(y_values, x_values)}

    def _run_done(self, value):
        self._set_busy(False)
        self.last_run = value
        status = value["run_status"]
        lines = [
            f"{status['status']} | Mode: {value['mode']} | Steps: {status.get('steps_count', 0)} "
            f"| Elapsed: {status.get('elapsed_s', 0)} s | Readings: {len(status.get('readings', []))}",
            "", "Sequence:",
        ]
        lines.extend(f"{index}. {log}" for index, log in enumerate(value.get("logs", []), 1))
        analysis = value.get("pipeline_results", {})
        for step, details in analysis.get("step_outputs", {}).items():
            lines.append(f"{step.replace('_', ' ').title()}: {json.dumps(details, ensure_ascii=False)}")
        if analysis.get("note"):
            lines.append(f"Analysis: {analysis['note']}")
        readings = status.get("readings", [])
        if readings:
            lines.extend(["", "Readings:"])
            lines.extend(f"{entry.get('channel')}: {entry.get('value')}" for entry in readings[:50])
        self.output.setPlainText("\n".join(lines))
        value["dsl"] = self.plan.toPlainText().strip()
        value["docs"] = [os.path.basename(item) for item in self.files]

    def _save_report(self):
        if not self.last_run:
            QMessageBox.information(self, "No run to report", "Run a validated plan first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save report", "industrial_control_report.md", "Markdown (*.md)")
        if not path:
            return
        run = self.last_run
        summary = run["run_status"]
        lines = [
            "# Standalone Industrial Control Build Report", "",
            f"- Execution mode: {run['mode']}", f"- Status: {summary['status']}",
            f"- UART: 9600 baud", "- Firmware: supplied ATmega2560 O/A/B/I/T firmware (unchanged)",
            f"- Runtime: {summary.get('elapsed_s', 0)} s", "",
            "## Reference files", *[f"- {name}" for name in run.get("docs", [])],
            "", "## Validated plan", "```text", self.plan.toPlainText().strip(), "```",
            "", "## Run commands", *[f"- {line}" for line in run.get("logs", [])],
            "", "## Readings", "```json",
            json.dumps(summary.get("readings", []), indent=2, ensure_ascii=False), "```",
            "", "## Analysis", "```json",
            json.dumps(run.get("pipeline_results", {}), indent=2, ensure_ascii=False), "```",
            "", "This report records the plan and results; it is not a hardware safety certification.",
        ]
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        QMessageBox.information(self, "Report saved", f"Saved report to:\n{path}")

    def _failed(self, error):
        self._set_busy(False)
        self.output.setPlainText("Operation failed: " + error)
        QMessageBox.warning(self, "Standalone Industrial Builder", error)

    def _generate_artifact(self):
        prompt = self.artifact_request.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Describe the artifact", "Enter what you want generated first.")
            return
        type_index = self.artifact_type.currentIndex()
        label, extension = self.artifact_options[type_index]
        paths = list(self.files) if self.include_context.isChecked() else []
        previous = self.artifact_preview.toPlainText().strip()
        if previous and self.revise_artifact.isChecked():
            prompt += "\n\nPrevious draft to revise (return the complete revised artifact):\n" + previous[:24000]
        self._set_busy(True)
        self.artifact_type.setEnabled(False)
        self.save_artifact_button.setEnabled(False)
        self.artifact_summary.setText("Generating a separate draft. It will not be executed or flashed.")
        self.worker = _Worker(self._generate_artifact_job, prompt, paths, label, extension, self._provider_name())
        self.worker.completed.connect(self._artifact_done)
        self.worker.failed.connect(self._artifact_failed)
        self.worker.start()

    @staticmethod
    def _generate_artifact_job(prompt, paths, artifact_type, extension, provider_name):
        docs = [DocumentIngestManager.ingest_file(path) for path in paths]
        context = DocumentIngestManager.build_summary_for_llm(docs)
        provider = create_provider(provider_name)
        artifact = provider.generate_artifact(artifact_type, extension, prompt, context)
        return artifact

    def _artifact_done(self, artifact):
        self._set_busy(False)
        self.artifact_type.setEnabled(True)
        self.artifact_filename = artifact["filename"]
        self.artifact_extension = Path(artifact["filename"]).suffix.lower()
        self.artifact_preview.setPlainText(artifact["content"])
        self.artifact_summary.setText(
            f"Draft: {artifact['filename']} — {artifact['summary']}\n"
            "Review and edit the content. Saving creates a new file; existing files are never overwritten."
        )
        self.save_artifact_button.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def _artifact_failed(self, error):
        self._set_busy(False)
        self.artifact_type.setEnabled(True)
        self.artifact_summary.setText("Artifact generation failed: " + error)
        QMessageBox.warning(self, "Artifact generation failed", error)

    def _save_artifact(self):
        filename = getattr(self, "artifact_filename", "generated_artifact.txt")
        extension = getattr(self, "artifact_extension", ".txt")
        filters = {
            ".py": "Python source (*.py)", ".ino": "Arduino sketch (*.ino)",
            ".cpp": "C++ source (*.cpp)", ".h": "C++ header (*.h)",
            ".md": "Markdown (*.md)", ".json": "JSON (*.json)",
            ".csv": "CSV (*.csv)", ".svg": "SVG (*.svg)", ".txt": "Text (*.txt)",
        }
        target, _ = QFileDialog.getSaveFileName(
            self, "Save generated artifact", str(Path("generated_artifacts") / filename),
            filters.get(extension, "All files (*)")
        )
        if not target:
            return
        if Path(target).suffix.lower() != extension:
            target += extension
        if Path(target).exists():
            QMessageBox.warning(
                self, "File already exists",
                "To protect your existing firmware and project files, this tool will not overwrite a file. "
                "Choose a new name or folder."
            )
            return
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(self.artifact_preview.toPlainText(), encoding="utf-8", newline="")
        QMessageBox.information(self, "Artifact saved", f"Saved the reviewed draft to:\n{target}")
