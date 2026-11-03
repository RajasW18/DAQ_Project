"""
Unified Serial Driver
Seamlessly interacts with real USB-UART hardware (CH340/FTDI/CP2102) or Mock MCU.
"""

import time
import threading
import queue
from typing import Optional, Callable, Dict, Any, List
from ..protocol.ascii_protocol import ASCIIProtocol, TelemetryData
from .mock_controller import MockMCUController

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

class SerialDriver:
    """Manages full duplex communication with the controller."""

    def __init__(self, port: Optional[str] = None, baud_rate: int = 9600, use_mock: bool = False):
        self.port = port
        self.baud_rate = baud_rate
        self.use_mock = use_mock
        self.is_connected = False

        self._serial_conn = None
        self._mock_mcu: Optional[MockMCUController] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._running = False

        # Queues and Listeners
        self._ack_events: Dict[str, threading.Event] = {}
        self._telemetry_queue: queue.Queue[TelemetryData] = queue.Queue()
        self._response_queue: queue.Queue[str] = queue.Queue()
        self._line_listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    def register_listener(self, listener: Callable[[str, Dict[str, Any]], None]):
        self._line_listeners.append(listener)

    def unregister_listener(self, listener: Callable[[str, Dict[str, Any]], None]):
        try:
            self._line_listeners.remove(listener)
        except ValueError:
            pass

    def connect(self) -> bool:
        if self.use_mock:
            self._mock_mcu = MockMCUController()
            self._mock_mcu.set_tx_callback(self._on_line_received)
            self.is_connected = True
            self._running = True
            return True

        if not SERIAL_AVAILABLE:
            return False

        try:
            # Require an explicit port so a newly attached unrelated serial
            # device is never selected for an approved hardware sequence.
            target_port = self.port
            if not target_port:
                return False

            self._serial_conn = serial.Serial(
                port=target_port,
                baudrate=self.baud_rate,
                timeout=0.5
            )
            self.is_connected = True
            self._running = True
            self._rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
            self._rx_thread.start()
            return True
        except Exception:
            self.is_connected = False
            self._serial_conn = None
            return False

    def _auto_detect_port(self) -> Optional[str]:
        if not SERIAL_AVAILABLE:
            return None
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            # CH340 or standard Arduino USB
            if "CH340" in p.description or (p.vid and p.vid == 0x1A86):
                return p.device
        if ports:
            return ports[0].device
        return None

    def _rx_worker(self):
        while self._running and self._serial_conn and self._serial_conn.is_open:
            try:
                line = self._serial_conn.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self._on_line_received(line)
            except Exception:
                break

    def _on_line_received(self, line: str):
        self._response_queue.put(line)
        event_type, payload = ASCIIProtocol.parse_line(line)
        if event_type == "DATA" and payload and "telemetry" in payload:
            self._telemetry_queue.put(payload["telemetry"])

        # Notify all listeners
        for listener in self._line_listeners:
            try:
                listener(event_type, payload or {})
            except Exception:
                pass

    def send_command(self, cmd: str) -> None:
        """Sends a text command to MCU."""
        if not self.is_connected:
            raise RuntimeError("Serial driver is not connected.")

        if self.use_mock and self._mock_mcu:
            self._mock_mcu.write_line(cmd)
        elif self._serial_conn and self._serial_conn.is_open:
            self._serial_conn.write((cmd + "\r\n").encode("utf-8"))
            self._serial_conn.flush()

    def send_command_wait(self, cmd: str, timeout: float = 2.0) -> str:
        """Send one command and wait for its ACK or an explicit firmware error."""
        self.send_command(cmd)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._response_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if line.startswith("ACK "):
                return line
            if line.startswith("ERR "):
                raise RuntimeError(f"Controller rejected {cmd!r}: {line}")
        raise TimeoutError(f"Controller did not acknowledge {cmd!r} within {timeout:g}s")

    def get_telemetry_batch(self, max_items: int = 50) -> List[TelemetryData]:
        items = []
        while not self._telemetry_queue.empty() and len(items) < max_items:
            try:
                items.append(self._telemetry_queue.get_nowait())
            except queue.Empty:
                break
        return items

    def close(self):
        self._running = False
        if self._mock_mcu:
            self._mock_mcu.close()
        if self._serial_conn and self._serial_conn.is_open:
            self._serial_conn.close()
        self.is_connected = False
