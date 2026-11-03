"""Adapter for the user's unchanged ATmega2560 spectroscopy firmware.

The firmware exposes logical ports, not arbitrary MCU GPIO pins. Output
values and the T-command delay argument are hexadecimal on the UART wire.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Dict, List, Optional

from ..analysis.pipeline import AnalysisPipeline
from ..ai_orchestrator.command_dsl import CommandDSLCompiler
from ..hal.registry import get_board
from ..sequence.task_engine import TaskEngine


@dataclass(frozen=True)
class PortCommand:
    op: str
    port: Optional[str] = None
    value: Optional[int] = None


def _parse_hex_byte(token: str) -> int:
    raw = token.strip().lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if not raw or not re.fullmatch(r"[0-9a-f]{1,2}", raw):
        raise ValueError("Output value must be a hexadecimal byte, such as 3C or 0x3C.")
    return int(raw, 16)


def compile_port_plan(dsl: str):
    """Validate port DSL locally without opening a serial connection."""
    commands: List[PortCommand] = []
    pipeline = AnalysisPipeline(name="User-directed data pipeline")
    logs: List[str] = []
    seen_pipe = False

    for line_no, raw in enumerate(dsl.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        for statement in (part.strip() for part in line.split(";") if part.strip()):
            parts = statement.split()
            op = parts[0].upper()
            try:
                if op == "OUT":
                    if len(parts) != 3 or parts[1].upper() not in {"A", "B"}:
                        raise ValueError("Use OUT <A|B> <hex byte>, for example OUT A 3C.")
                    port, value = parts[1].upper(), _parse_hex_byte(parts[2])
                    if port == "B" and value > 0x7F:
                        raise ValueError("Port B uses only 7 output bits; value must be 00–7F hex.")
                    commands.append(PortCommand("OUT", port, value))
                    logs.append(f"Set Port {port} to 0x{value:02X}")
                elif op == "WAIT":
                    if len(parts) != 2 or not parts[1].isdigit():
                        raise ValueError("Use WAIT <milliseconds> with a decimal duration.")
                    duration = int(parts[1])
                    if not 0 <= duration <= 60000:
                        raise ValueError("WAIT must be between 0 and 60000 milliseconds.")
                    commands.append(PortCommand("WAIT", value=duration))
                    logs.append(f"Wait {duration} ms")
                elif op == "READ12":
                    if len(parts) != 1:
                        raise ValueError("Use READ12 with no arguments.")
                    commands.append(PortCommand("READ12"))
                    logs.append("Read the 12-bit digital input bus")
                elif op == "ADC12":
                    if len(parts) != 1:
                        raise ValueError("Use ADC12 with no arguments.")
                    commands.append(PortCommand("ADC12"))
                    logs.append("Trigger and read the firmware's 12-bit conversion")
                elif op == "PIPE":
                    if seen_pipe:
                        raise ValueError("Use one PIPE line containing all analysis blocks.")
                    # Reuse the deterministic, allow-listed analysis compiler.
                    class _NoopDriver:
                        def send_command(self, _command):
                            raise RuntimeError("Validation must not send controller commands")

                    engine = TaskEngine(get_board("atmega2560"), _NoopDriver())
                    _, parsed, _ = CommandDSLCompiler.compile(statement, engine.hal, engine)
                    pipeline.steps.extend(parsed.steps)
                    seen_pipe = True
                    logs.append(f"Analysis: {' '.join(parts[1:])}")
                else:
                    raise ValueError(f"Unsupported command {op!r}.")
            except (ValueError, IndexError) as exc:
                raise ValueError(f"DSL line {line_no}: {exc}") from exc

            if len(commands) > 64:
                raise ValueError("Plan exceeds the 64-command safety limit.")

    if not commands and not pipeline.steps:
        raise ValueError("Plan has no port commands or analysis operations.")
    return commands, pipeline, logs


class SpectroscopyPortController:
    """Small synchronous protocol client; caller must explicitly approve live use."""

    def __init__(self, port: str, baud_rate: int = 9600):
        if not port:
            raise ValueError("Select a serial port before live execution.")
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Live serial control requires pyserial.") from exc
        self.serial = serial.Serial(port=port, baudrate=baud_rate, timeout=0.1,
                                    write_timeout=2)
        # Opening an Arduino-compatible serial port often resets the AVR.
        time.sleep(2.0)
        self.serial.reset_input_buffer()

    def _read_response(self, accepted, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self.serial.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("# ERROR") or line.startswith("ERR"):
                raise RuntimeError(f"Controller error: {line}")
            if not line or line.startswith("#"):
                continue
            if accepted(line):
                return line
        raise TimeoutError("No expected response from controller before timeout.")

    def _send(self, command: str, accepted, timeout=3.0):
        self.serial.write((command + "\n").encode("ascii"))
        self.serial.flush()
        return self._read_response(accepted, timeout)

    def execute(self, commands: List[PortCommand], approved: bool = False):
        if not approved:
            raise PermissionError("Live controller execution requires explicit approval.")
        start = time.monotonic()
        logs, readings = [], []
        for command in commands:
            if command.op == "OUT":
                response = self._send(
                    f"O,{command.port},{command.value:02X}",
                    lambda line: line == "K")
                logs.append(f"Port {command.port} set to 0x{command.value:02X} ({response})")
            elif command.op == "WAIT":
                # The firmware parses T's milliseconds as hexadecimal.
                response = self._send(f"T,{command.value:X}", lambda line: line == "K")
                time.sleep(command.value / 1000.0)
                logs.append(f"Waited {command.value} ms ({response})")
            elif command.op == "READ12":
                response = self._send("I", lambda line: line.startswith("D,"))
                value = int(response.split(",", 1)[1], 10)
                if not 0 <= value <= 4095:
                    raise RuntimeError(f"Controller returned out-of-range 12-bit value: {value}")
                readings.append({"channel": "INPUT12", "value": value,
                                 "timestamp": time.monotonic() - start})
                logs.append(f"Read 12-bit input: {value}")
            elif command.op == "ADC12":
                # The unchanged sketch uses this Port A trigger pair and
                # emits D,<value> after its 100 ms conversion delay.
                self._send("O,A,7C", lambda line: line == "K")
                self._send("O,A,3C", lambda line: line == "K")
                self._send("T,64", lambda line: line == "K")  # 0x64 = 100 ms
                time.sleep(0.12)
                response = self._read_response(lambda line: line.startswith("D,"), timeout=2.0)
                value = int(response.split(",", 1)[1], 10)
                if not 0 <= value <= 4095:
                    raise RuntimeError(f"Controller returned out-of-range 12-bit value: {value}")
                readings.append({"channel": "ADC12", "value": value,
                                 "timestamp": time.monotonic() - start})
                logs.append(f"Triggered 12-bit conversion: {value}")
        return {"status": "COMPLETED", "steps_count": len(commands),
                "readings": readings, "elapsed_s": round(time.monotonic() - start, 3),
                "commands": logs}

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
