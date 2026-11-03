"""Strict, side-effect-free compiler for the compact control DSL."""

import re
import math
from typing import List, Tuple

from ..analysis.pipeline import AnalysisPipeline
from ..hal.board_base import BoardHAL
from ..sequence.task_engine import TaskEngine


class CommandDSLCompiler:
    MAX_COMMANDS = 64

    @staticmethod
    def compile(dsl_text: str, hal: BoardHAL, task_engine: TaskEngine
                ) -> Tuple[TaskEngine, AnalysisPipeline, List[str]]:
        pipeline = AnalysisPipeline(name="User-directed data pipeline")
        logs: List[str] = []
        task_engine.clear()
        command_count = 0
        for line_no, raw in enumerate(dsl_text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            for command in (part.strip() for part in line.split(";") if part.strip()):
                try:
                    CommandDSLCompiler._compile_one(command, hal, task_engine, pipeline, logs)
                    if not command.upper().startswith("PIPE "):
                        command_count += 1
                except (ValueError, IndexError) as exc:
                    task_engine.clear()
                    raise ValueError(f"DSL line {line_no}: {exc}") from exc
                if command_count > CommandDSLCompiler.MAX_COMMANDS:
                    task_engine.clear()
                    raise ValueError("Plan exceeds the controller's 64-step sequence buffer.")
        if not task_engine.steps and not pipeline.steps:
            raise ValueError("The plan contains no sequence steps or analysis operations.")
        return task_engine, pipeline, logs

    @staticmethod
    def _compile_one(command, hal, engine, pipeline, logs):
        parts = command.split()
        op = parts[0].upper()
        if op in ("CONFIG", "PIN"):
            if len(parts) != 3:
                raise ValueError("Use CONFIG <pin> <OUT|IN|PULLUP|PWM>.")
            pin, mode = int(parts[1]), parts[2].upper()
            if mode not in {"OUT", "IN", "PULLUP", "PWM"}:
                raise ValueError(f"Unsupported pin mode {mode}.")
            if not hal.validate_digital_pin(pin) or pin in {0, 1}:
                raise ValueError(f"Pin {pin} is invalid or reserved for UART.")
            if mode == "PWM" and not hal.validate_pwm_pin(pin):
                raise ValueError(f"Pin {pin} does not support PWM on {hal.name}.")
            expected = engine.pin_modes.get(pin)
            if expected and expected != mode:
                raise ValueError(f"Pin {pin} is already required as {expected}, conflicting with CONFIG {mode}.")
            engine.pin_modes[pin] = mode
            logs.append(f"Configure D{pin} as {mode}")
        elif op in {"W", "WRITE"}:
            if len(parts) != 3: raise ValueError("Use W <pin> <0|1|0..255>.")
            pin, val = int(parts[1]), int(parts[2])
            expected = engine.pin_modes.get(pin)
            # On a PWM-configured pin, 0 and 1 are valid duty-cycle values too.
            # Otherwise infer PWM for intermediate values and digital OUT for 0/1.
            mode = "PWM" if expected == "PWM" or val not in (0, 1) else "OUT"
            if expected and expected != mode:
                raise ValueError(f"Pin {pin} must be configured as {mode} for this write, not {expected}.")
            engine.pin_modes.setdefault(pin, mode)
            if mode == "PWM":
                engine.add_pwm(pin, val)
                logs.append(f"Queue PWM on D{pin}: {val}")
            else:
                engine.add_write(pin, val)
                logs.append(f"Queue write on D{pin}: {val}")
        elif op in {"DLY", "DELAY"}:
            if len(parts) != 2: raise ValueError("Use DLY <milliseconds>.")
            engine.add_delay(int(parts[1])); logs.append(f"Wait {parts[1]} ms")
        elif op in {"R", "READ"}:
            if len(parts) != 2: raise ValueError("Use R <digital-pin>.")
            pin = int(parts[1])
            expected = engine.pin_modes.get(pin)
            if expected and expected not in {"IN", "PULLUP"}:
                raise ValueError(f"Pin {pin} must be configured as an input for a digital read, not {expected}.")
            engine.pin_modes.setdefault(pin, "IN")
            engine.add_read_digital(pin); logs.append(f"Read D{pin}")
        elif op in {"A", "ANALOG"}:
            if len(parts) != 2: raise ValueError("Use A <analog-channel>.")
            channel = int(parts[1].lstrip("Aa"))
            engine.add_read_analog(channel); logs.append(f"Read A{channel}")
        elif op == "PIPE":
            if len(parts) < 2: raise ValueError("PIPE needs at least one analysis block.")
            for block in parts[1:]:
                name = block.split("(", 1)[0].upper()
                args = re.fullmatch(r"[A-Z_]+(?:\(([^()]*)\))?", block.upper())
                if not args: raise ValueError(f"Malformed analysis block: {block}")
                vals = [float(x) for x in args.group(1).split(",")] if args.group(1) else []
                if any(not math.isfinite(v) for v in vals):
                    raise ValueError(f"Analysis parameters must be finite: {block}")
                if name in {"MEDIAN", "MOVING_AVG", "MA"} and len(vals) == 1:
                    window = int(vals[0])
                    if vals[0] != window or window < 1 or window > 51 or window % 2 == 0:
                        raise ValueError("Filter window must be an odd integer from 1 to 51.")
                    if name == "MEDIAN": pipeline.add_filter_median(window)
                    else: pipeline.add_filter_moving_average(window)
                elif name == "CALIB" and len(vals) == 2: pipeline.add_calibration_scale(*vals)
                elif name == "STATS" and not vals: pipeline.add_statistics()
                elif name == "REG_LIN" and not vals: pipeline.add_linear_regression()
                elif name == "REG_POLY" and not vals: pipeline.add_polynomial_regression()
                elif name == "DERIVATIVE" and not vals: pipeline.add_numerical_derivative()
                elif name == "INTEGRAL" and not vals: pipeline.add_numerical_integral()
                elif name == "PEAKS" and len(vals) == 1 and 0 <= vals[0] <= 1: pipeline.add_peak_detection(vals[0])
                else: raise ValueError(f"Unsupported arguments or analysis block: {block}")
                logs.append(f"Analysis: {block}")
        else:
            raise ValueError(f"Unsupported command {op!r}.")
