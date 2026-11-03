"""
High-Fidelity Mock Microcontroller Controller (Software Emulator)
Simulates ATmega 2560 Pro running the Universal Firmware Engine.
Allows offline testing, development, and verification.
"""

import time
import math
import threading
from typing import Dict, List, Optional, Callable

class MockMCUController:
    """Simulates hardware registers, sequence execution, and polling at 9600 baud."""

    def __init__(self, board_name: str = "ATmega 2560 Pro"):
        self.board_name = board_name
        self.digital_pins: Dict[int, int] = {p: 0 for p in range(54)}
        self.pin_modes: Dict[int, str] = {p: "IN" for p in range(54)}
        self.analog_inputs: Dict[int, float] = {p: 512.0 for p in range(16)}

        # Sequencer state
        self.seq_steps: List[Dict[str, any]] = []
        self.seq_running = False
        self._seq_thread: Optional[threading.Thread] = None

        # Poller state
        self.pollers: Dict[int, Dict[str, any]] = {}  # pin -> {interval, is_analog, last_poll}
        self.is_running = True
        self._poller_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._poller_thread.start()

        # Output line callback (simulates UART TX to PC)
        self.tx_callback: Optional[Callable[[str], None]] = None

    def set_tx_callback(self, callback: Callable[[str], None]):
        self.tx_callback = callback

    def _emit(self, text: str):
        if self.tx_callback:
            self.tx_callback(text)

    def write_line(self, line: str):
        """Processes an incoming command from the PC over virtual UART."""
        cmd = line.strip()
        if not cmd or cmd.startswith("#"):
            return

        if cmd == "PING":
            self._emit("PONG")
            return

        if cmd == "ESTOP":
            self.seq_running = False
            self.seq_steps.clear()
            self.pollers.clear()
            for p in range(54):
                if self.pin_modes[p] in ("OUT", "PWM"):
                    self.digital_pins[p] = 0
            self._emit("ACK ESTOP SAFE")
            return

        if cmd == "STATUS":
            uptime = int(time.time() * 1000) % 1000000
            self._emit(f"STATUS board={self.board_name} seq_running={1 if self.seq_running else 0} seq_steps={len(self.seq_steps)} uptime={uptime}")
            return

        if cmd.startswith("PIN "):
            parts = cmd[4:].split()
            if len(parts) >= 2:
                pin = int(parts[0])
                mode = parts[1].upper()
                self.pin_modes[pin] = mode
                self._emit(f"ACK PIN {pin} {mode}")
            else:
                self._emit("ERR PIN_SYNTAX")
            return

        if cmd.startswith("W "):
            parts = cmd[2:].split()
            if len(parts) >= 2:
                pin = int(parts[0])
                val = int(parts[1])
                self.digital_pins[pin] = val
                self._emit(f"ACK W {pin} {val}")
            else:
                self._emit("ERR W_SYNTAX")
            return

        if cmd.startswith("R "):
            pin = int(cmd[2:].strip())
            val = self.digital_pins.get(pin, 0)
            self._emit(f"VAL {pin} {val}")
            return

        if cmd.startswith("A "):
            ch = int(cmd[2:].strip())
            # Simulate a realistic analog read with slight sine modulation
            base = self.analog_inputs.get(ch, 512.0)
            noise = math.sin(time.time() * 2.0) * 15.0
            val = int(max(0, min(1023, base + noise)))
            self._emit(f"VAL A{ch} {val}")
            return

        if cmd.startswith("POLL "):
            parts = cmd[5:].split()
            if len(parts) >= 2:
                pin = int(parts[0])
                interval = int(parts[1])
                is_analog = (len(parts) >= 3 and parts[2].upper() == "A")
                self.pollers[pin] = {
                    "pin": pin,
                    "interval": interval / 1000.0,
                    "is_analog": is_analog,
                    "last_poll": time.time()
                }
                self._emit(f"ACK POLL {pin} OK")
            else:
                self._emit("ERR POLL_SYNTAX")
            return

        if cmd.startswith("POLL_STOP "):
            pin = int(cmd[10:].strip())
            self.pollers.pop(pin, None)
            self._emit(f"ACK POLL_STOP {pin}")
            return

        if cmd == "SEQ_CLEAR":
            self.seq_running = False
            self.seq_steps.clear()
            self._emit("ACK SEQ_CLEAR")
            return

        if cmd.startswith("SEQ_ADD "):
            parts = cmd[8:].split()
            op = parts[0]
            if op == "W":
                pin = int(parts[1])
                val = int(parts[2])
                self.seq_steps.append({"type": "W", "pin": pin, "val": val})
            elif op == "DLY":
                delay_ms = int(parts[1])
                self.seq_steps.append({"type": "DLY", "delay_ms": delay_ms})
            elif op == "R":
                pin = int(parts[1])
                self.seq_steps.append({"type": "R", "pin": pin})
            elif op == "A":
                pin = int(parts[1])
                self.seq_steps.append({"type": "A", "pin": pin})
            self._emit(f"ACK SEQ_ADD {len(self.seq_steps)}")
            return

        if cmd == "SEQ_RUN":
            if not self.seq_steps:
                self._emit("ERR SEQ_EMPTY")
                return
            self.seq_running = True
            self._emit("ACK SEQ_RUN STARTED")
            self._seq_thread = threading.Thread(target=self._run_sequence_worker, daemon=True)
            self._seq_thread.start()
            return

        if cmd == "SEQ_STOP":
            self.seq_running = False
            self._emit("ACK SEQ_STOPPED")
            return

        self._emit(f"ERR UNKNOWN_CMD {cmd}")

    def _run_sequence_worker(self):
        for step in self.seq_steps:
            if not self.seq_running:
                break
            stype = step["type"]
            if stype == "W":
                self.digital_pins[step["pin"]] = step["val"]
            elif stype == "DLY":
                time.sleep(step["delay_ms"] / 1000.0)
            elif stype == "R":
                val = self.digital_pins.get(step["pin"], 0)
                self._emit(f"DATA R_{step['pin']} {val}")
            elif stype == "A":
                base = self.analog_inputs.get(step["pin"], 512.0)
                val = int(max(0, min(1023, base + math.sin(time.time()) * 10)))
                self._emit(f"DATA A_{step['pin']} {val}")

        if self.seq_running:
            self.seq_running = False
            self._emit("NOTIFY SEQ_COMPLETED")

    def _polling_loop(self):
        while self.is_running:
            now = time.time()
            for pin, pdata in list(self.pollers.items()):
                if now - pdata["last_poll"] >= pdata["interval"]:
                    pdata["last_poll"] = now
                    ts_ms = int(now * 1000) % 10000000
                    if pdata["is_analog"]:
                        base = self.analog_inputs.get(pin, 480.0)
                        val = int(max(0, min(1023, base + math.cos(now * 3.0) * 25.0)))
                        self._emit(f"DATA A{pin} {val} {ts_ms}")
                    else:
                        val = self.digital_pins.get(pin, 0)
                        self._emit(f"DATA D{pin} {val} {ts_ms}")
            time.sleep(0.01)

    def close(self):
        self.is_running = False
        self.seq_running = False
