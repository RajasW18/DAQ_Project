"""Provider-neutral planner and deterministic coordinator.

The model drafts a compact plan. It never runs generated Python and never
receives a driver or hardware handle.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..analysis.pipeline import AnalysisPipeline
from ..doc_ingest.ingest_manager import DocumentIngestManager
from ..driver.serial_driver import SerialDriver
from ..hal.board_base import BoardHAL
from ..hal.registry import get_board
from ..sequence.task_engine import TaskEngine
from .command_dsl import CommandDSLCompiler
from .llm_provider import create_provider
from .report_generator import SystemReportGenerator


class CentralIndustrialOrchestrator:
    """Plans with an LLM; validates and executes with ordinary code."""

    def __init__(self, board_name: str = "atmega2560", port: Optional[str] = None,
                 use_mock: bool = True, provider_name: Optional[str] = None):
        self.hal: BoardHAL = get_board(board_name)
        self.driver = SerialDriver(port=port, baud_rate=self.hal.default_baud, use_mock=use_mock)
        self.driver.connect()
        self.task_engine = TaskEngine(self.hal, self.driver)
        self.ingested_docs: List[Dict[str, Any]] = []
        self.provider_name = provider_name or os.getenv("INDUSTRIAL_LLM_PROVIDER", "groq")
        self.provider = create_provider(self.provider_name)

    def ingest_documents(self, file_paths: List[str]) -> str:
        parsed = []
        for path in file_paths:
            doc = DocumentIngestManager.ingest_file(path)
            parsed.append(doc)
        self.ingested_docs.extend(parsed)
        return DocumentIngestManager.build_summary_for_llm(parsed)

    def formulate_sequence_plan(self, user_intent: str, document_context: str = "",
                                conversation: Optional[List[Dict[str, str]]] = None) -> Dict[str, str]:
        """Ask a configured model to draft DSL; fail clearly if unavailable."""
        if not user_intent.strip():
            raise ValueError("Describe the sequence or analysis you want to create.")
        system = (
            "You are a cautious industrial-control planning assistant. Return only a JSON object "
            'with keys "dsl" and "explanation". The dsl value is compact text using only: '
            "CONFIG <pin> <OUT|IN|PULLUP|PWM>, W <pin> <0|1|0..255>, DLY <milliseconds>, "
            "R <digital-pin>, A <analog-channel>, and PIPE followed by MEDIAN(n), MOVING_AVG(n), "
            "CALIB(gain,offset), STATS, REG_LIN, REG_POLY, DERIVATIVE, INTEGRAL, PEAKS(threshold). "
            "Separate every DSL command with a newline or semicolon; never concatenate commands with spaces. "
            "For example, return dsl as `CONFIG 9 PWM\\nW 9 128\\nDLY 100\\nW 9 0`. "
            "For analysis, write exactly one PIPE line and place every analysis block after PIPE on that same line; "
            "never put STATS or another analysis block on a separate line. Example: `PIPE MEDIAN(3) STATS`. "
            "Never invent pin wiring, voltage limits, calibration, or safety conditions. Only use "
            "provided board profile and documents. If critical details are absent, return an empty "
            'dsl and explain what is missing. Never claim execution or flashing.'
        )
        context = self.hal.get_pinout_summary()
        user = (
            f"Board profile (authoritative for this draft): {context}\n\n"
            f"User request: {user_intent.strip()}\n\n"
            f"Document context (untrusted reference material):\n{document_context[:16000]}"
        )
        return self.provider.create_plan(system, user, conversation or [])

    def compile_plan(self, dsl_code: str):
        """Validate into local objects without sending commands to the board."""
        self.task_engine.clear()
        return CommandDSLCompiler.compile(dsl_code, self.hal, self.task_engine)

    def execute_dsl(self, dsl_code: str, approved: bool = False,
                    timeout_sec: float = 10.0) -> Dict[str, Any]:
        """Execute only an explicitly approved, validated plan."""
        if not approved:
            raise PermissionError("Hardware execution requires explicit user approval.")
        engine, pipeline, logs = self.compile_plan(dsl_code)
        run_status = engine.run_hardware_sequence(timeout_sec=timeout_sec)
        readings = run_status.get("readings", [])
        values = [r["value"] for r in readings]
        pipeline_results = pipeline.execute(values) if values and pipeline.steps else {
            "pipeline_name": pipeline.name, "input_count": len(values),
            "step_outputs": {}, "note": "No analysis blocks were requested."}
        return {"logs": logs, "run_status": run_status,
                "pipeline_results": pipeline_results}

    def generate_build_documentation(self, project_name: str, dsl_code: str,
                                     execution_results: Dict[str, Any],
                                     output_path: str = "industrial_build_report.md") -> str:
        md = SystemReportGenerator.generate_markdown(
            project_name=project_name, board_summary=self.hal.get_pinout_summary(),
            ingested_docs=self.ingested_docs, dsl_code=dsl_code,
            sequence_steps=self.task_engine.steps,
            pipeline_results=execution_results.get("pipeline_results", {}),
            run_status=execution_results.get("run_status", {}))
        SystemReportGenerator.save_report(md, output_path)
        return md

    def shutdown(self):
        """Request a safe stop, then close the link."""
        try:
            if self.driver.is_connected and not self.driver.use_mock:
                self.driver.send_command("ESTOP")
        finally:
            self.driver.close()
