"""
Industrial Task Sequence Engine
Compiles high-level sequence definitions into deterministic hardware execution.
"""

import time
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from ..hal.board_base import BoardHAL
from ..driver.serial_driver import SerialDriver
from ..protocol.ascii_protocol import ASCIIProtocol, TelemetryData

@dataclass
class SequenceStep:
    step_type: str  # 'WRITE', 'PWM', 'DELAY', 'READ_DIGITAL', 'READ_ANALOG'
    pin: int
    value: int = 0
    delay_ms: int = 0
    description: str = ""

class TaskEngine:
    """Manages creation, HAL validation, upload, and execution of deterministic sequences."""

    def __init__(self, hal: BoardHAL, driver: SerialDriver):
        self.hal = hal
        self.driver = driver
        self.steps: List[SequenceStep] = []
        self.recorded_readings: List[Dict[str, Any]] = []
        self.pin_modes: Dict[int, str] = {}

    def clear(self):
        self.steps.clear()
        self.recorded_readings.clear()
        self.pin_modes.clear()

    def add_write(self, pin: int, value: int, description: str = "") -> "TaskEngine":
        if not self.hal.validate_digital_pin(pin) or pin in {0, 1}:
            raise ValueError(f"Pin {pin} is not a valid digital pin on {self.hal.name}")
        self.steps.append(SequenceStep(
            step_type='WRITE',
            pin=pin,
            value=1 if value else 0,
            description=description or f"Digital Write pin {pin} -> {value}"
        ))
        return self

    def add_pwm(self, pin: int, duty_cycle: int, description: str = "") -> "TaskEngine":
        if not self.hal.validate_pwm_pin(pin) or pin in {0, 1}:
            raise ValueError(f"Pin {pin} does not support hardware PWM on {self.hal.name}")
        if not 0 <= duty_cycle <= 255:
            raise ValueError("PWM duty cycle must be between 0 and 255")
        clamped = duty_cycle
        self.steps.append(SequenceStep(
            step_type='PWM',
            pin=pin,
            value=clamped,
            description=description or f"PWM pin {pin} -> {clamped}"
        ))
        return self

    def add_delay(self, delay_ms: int, description: str = "") -> "TaskEngine":
        if not 0 <= delay_ms <= 65535:
            raise ValueError("Delay must be between 0 and 65535 ms for this firmware")
        self.steps.append(SequenceStep(
            step_type='DELAY',
            pin=0,
            delay_ms=delay_ms,
            description=description or f"Wait {delay_ms} ms"
        ))
        return self

    def add_read_digital(self, pin: int, description: str = "") -> "TaskEngine":
        if not self.hal.validate_digital_pin(pin) or pin in {0, 1}:
            raise ValueError(f"Pin {pin} is not a valid digital pin on {self.hal.name}")
        self.steps.append(SequenceStep(
            step_type='READ_DIGITAL',
            pin=pin,
            description=description or f"Read Digital pin {pin}"
        ))
        return self

    def add_read_analog(self, channel: int, description: str = "") -> "TaskEngine":
        if not self.hal.validate_analog_channel(channel):
            raise ValueError(f"Analog channel A{channel} is not valid on {self.hal.name}")
        self.steps.append(SequenceStep(
            step_type='READ_ANALOG',
            pin=channel,
            description=description or f"Read Analog channel A{channel}"
        ))
        return self

    def upload_to_controller(self):
        """Uploads the sequence buffer into the Universal Firmware Engine."""
        if len(self.steps) > 64:
            raise ValueError("Sequence exceeds the controller's 64-step buffer")
        self.driver.send_command_wait(ASCIIProtocol.seq_clear())

        for pin, mode in self.pin_modes.items():
            self.driver.send_command_wait(ASCIIProtocol.pin_mode(pin, mode))

        for step in self.steps:
            if step.step_type == 'WRITE':
                command = ASCIIProtocol.seq_add_write(step.pin, step.value)
            elif step.step_type == 'PWM':
                command = ASCIIProtocol.seq_add_write(step.pin, step.value)
            elif step.step_type == 'DELAY':
                command = ASCIIProtocol.seq_add_delay(step.delay_ms)
            elif step.step_type == 'READ_DIGITAL':
                command = ASCIIProtocol.seq_add_read(step.pin, is_analog=False)
            elif step.step_type == 'READ_ANALOG':
                command = ASCIIProtocol.seq_add_read(step.pin, is_analog=True)
            else:
                raise ValueError(f"Unsupported step type: {step.step_type}")
            self.driver.send_command_wait(command)

    def run_hardware_sequence(self, timeout_sec: float = 10.0) -> Dict[str, Any]:
        """Runs the sequence on MCU using the MCU hardware timers."""
        if not self.driver.is_connected:
            raise RuntimeError("Controller is not connected")
        if not self.steps:
            raise ValueError("There are no hardware steps to execute")
        self.upload_to_controller()
        self.recorded_readings.clear()

        done_event = threading.Event()
        def _listener(evt_type, payload):
            nonlocal done_event
            if evt_type == "NOTIFY" and payload.get("message") == "SEQ_COMPLETED":
                done_event.set()
            elif evt_type == "DATA" and "telemetry" in payload:
                telem: TelemetryData = payload["telemetry"]
                self.recorded_readings.append({
                    "channel": telem.channel,
                    "value": telem.value,
                    "timestamp": telem.timestamp_ms or int(time.time() * 1000)
                })

        self.driver.register_listener(_listener)
        start_t = time.time()
        try:
            self.driver.send_command_wait(ASCIIProtocol.seq_run())
            if not done_event.wait(timeout_sec):
                self.driver.send_command_wait(ASCIIProtocol.seq_stop())
        finally:
            self.driver.unregister_listener(_listener)

        return {
            "status": "COMPLETED" if done_event.is_set() else "TIMEOUT",
            "steps_count": len(self.steps),
            "readings": self.recorded_readings,
            "elapsed_s": round(time.time() - start_t, 3)
        }
