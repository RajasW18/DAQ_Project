"""
Automated System Build & Operation Documentation Generator
Creates comprehensive technical specification manuals in Markdown and HTML.
"""

import os
import json
import time
from typing import Dict, Any, List

class SystemReportGenerator:
    """Generates complete documentation for what the Industrial Control Builder created and ran."""

    @staticmethod
    def generate_markdown(
        project_name: str,
        board_summary: Dict[str, Any],
        ingested_docs: List[Dict[str, Any]],
        dsl_code: str,
        sequence_steps: List[Any],
        pipeline_results: Dict[str, Any],
        run_status: Dict[str, Any]
    ) -> str:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"# Industrial Control System Specification & Build Report",
            f"**Project:** {project_name}  ",
            f"**Generated:** {timestamp}  ",
            f"**Planner:** User-directed LLM draft with deterministic validation  ",
            "",
            "---",
            "",
            "## 1. Executive Summary & Objective",
            f"This document provides the definitive technical specification for the automated industrial control system configured on the **{board_summary.get('board', 'MCU Target')}**.",
            "The LLM drafted a compact command plan. The application validated the plan and executed approved operations through deterministic modules.",
            "",
            "## 2. Hardware Platform & Pinout Specification",
            f"- **Target Board:** `{board_summary.get('board')}`",
            f"- **Architecture:** `{board_summary.get('architecture')}`",
            f"- **Operating Logic Level:** `{board_summary.get('operating_voltage')}`",
            f"- **Total Digital I/O:** `{board_summary.get('digital_io_count')}` pins",
            f"- **PWM Channels:** `{', '.join(map(str, board_summary.get('pwm_pins', [])))}`",
            f"- **Analog Channels:** `{', '.join(board_summary.get('analog_channels', []))}` ({board_summary.get('adc_resolution')})",
            f"- **Serial Communication:** UART @ `{board_summary.get('uart_default_baud')} Baud`, 8-N-1",
            "",
            "## 3. Ingested Technical Context & User Documents",
        ]

        if ingested_docs:
            for doc in ingested_docs:
                lines.append(f"- **File:** `{doc.get('filename')}` (Type: `{doc.get('type')}`)")
        else:
            lines.append("- *No external documents ingested; standard profile utilized.*")

        lines.extend([
            "",
            "## 4. Workspace Firmware Protocol Reference",
            "This protocol reference describes the firmware in the workspace. It is distinct from the supplied spectroscopy sketch, which uses O/A/B/I/T commands and does not implement SEQ_*.",
            "",
            "| Command | Syntax | Description | Example |",
            "| :--- | :--- | :--- | :--- |",
            "| `PIN` | `PIN <pin> <OUT/IN/PWM>` | Configures GPIO hardware direction | `PIN 13 OUT` |",
            "| `W` | `W <pin> <0/1/val>` | Digital write or PWM duty cycle | `W 13 1` |",
            "| `R` | `R <pin>` | Non-blocking digital read | `R 12` |",
            "| `A` | `A <channel>` | Analog read (10-bit / 12-bit) | `A 0` |",
            "| `SEQ_ADD` | `SEQ_ADD <W/DLY/R/A> ...` | Adds a step to the MCU sequence buffer | `SEQ_ADD DLY 200` |",
            "| `SEQ_RUN` | `SEQ_RUN` | Starts the buffered sequence | `SEQ_RUN` |",
            "| `ESTOP` | `ESTOP` | Immediate safe-state shutdown | `ESTOP` |",
            "",
            "## 5. Token-Efficient Orchestration DSL",
            "```text",
            dsl_code.strip(),
            "```",
            "",
            "## 6. Compiled Hardware Task Sequence",
            "| Step # | Type | Pin / Channel | Value / Param | Delay (ms) | Description |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ])

        for idx, step in enumerate(sequence_steps):
            stype = getattr(step, 'step_type', 'STEP')
            pin = getattr(step, 'pin', '-')
            val = getattr(step, 'value', '-')
            dly = getattr(step, 'delay_ms', 0)
            desc = getattr(step, 'description', '')
            lines.append(f"| {idx+1} | `{stype}` | `{pin}` | `{val}` | `{dly}` | {desc} |")

        lines.extend([
            "",
            "## 7. Mathematical Modeling & Analysis Pipeline Results",
            f"**Pipeline:** `{pipeline_results.get('pipeline_name', 'Data Analysis')}`  ",
            f"**Sample Count Processed:** `{pipeline_results.get('input_count', 0)}` points  ",
            ""
        ])

        step_outputs = pipeline_results.get("step_outputs", {})
        for step_name, out in step_outputs.items():
            lines.append(f"### {step_name.replace('_', ' ').title()}")
            if "equation" in out:
                lines.append(f"- **Fitted Mathematical Model:** `{out['equation']}`")
                lines.append(f"- **Coefficient of Determination ($R^2$):** `{out.get('r_squared')}`")
            elif "mean" in out:
                lines.append(f"- **Mean:** `{out.get('mean')}` | **Median:** `{out.get('median')}`")
                lines.append(f"- **Std Dev:** `{out.get('std')}` | **Range:** `[{out.get('min')} ... {out.get('max')}]`")
            elif "accumulated_integral" in out:
                lines.append(f"- **Trapezoidal Integral:** `{out.get('accumulated_integral')}` unit*s")
            elif "detected_peaks" in out:
                lines.append(f"- **Peaks Detected:** `{out.get('peak_count')}` points")
            else:
                lines.append(f"```json\n{json.dumps(out, indent=2)}\n```")
            lines.append("")

        lines.extend([
            "## 8. Hardware Execution Summary",
            f"- **Execution Status:** `{run_status.get('status', 'NOT RUN')}`",
            f"- **Execution Mode:** `{run_status.get('execution_mode', 'not recorded')}`",
            f"- **Total Sequence Runtime:** `{run_status.get('elapsed_s', 0)} seconds`",
            f"- **Telemetry Points Collected:** `{len(run_status.get('readings', []))}` readings",
            "",
            "---",
            "This report describes the configured plan and recorded results; it is not a hardware safety certification."
        ])

        return "\n".join(lines)

    @staticmethod
    def save_report(md_content: str, output_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
