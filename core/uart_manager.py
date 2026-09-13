"""
SpectraSoft — UART Manager (Singleton)
Handles connection to CH340 USB-UART adapter.
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional


class UARTManager:
    """Singleton manager for serial communication with the microcontroller."""

    # CH340 VID/PID
    CH340_VID = 0x1A86
    CH340_PID = 0x7523
    DEFAULT_PORT = "COM3"

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if UARTManager._initialized:
            return
        UARTManager._initialized = True

        self.baud_rate = 9600
        self.timeout = 2.0
        self.conn: Optional[serial.Serial] = None
        self.is_connected = False
        self._port_name = None

    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connect to the CH340 adapter. If already connected, reuse the connection.

        Args:
            port: Optional port name (e.g., "COM4"). If None, auto-detect.

        Returns:
            True if connected successfully.
        """
        # If already connected and port is open, just return True
        if self.is_connected and self.conn and self.conn.is_open:
            print(f"UARTManager: Already connected to {self._port_name}, reusing.")
            return True

        # Close any stale connection
        self.close()

        if port is None:
            port = self._find_ch340_port()

        if port is None:
            print(f"  No CH340 found, falling back to {self.DEFAULT_PORT}")
            port = self.DEFAULT_PORT

        print(f"  Opening {port} at {self.baud_rate} baud...")

        try:
            self.conn = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                dsrdtr=False,
                rtscts=False,
            )
            self.conn.dtr = False
            self.conn.rts = False

            time.sleep(0.5)

            # Drain startup messages
            self._drain_startup()

            # Initialize Port A and B to standby
            self._init_standby()

            self.is_connected = True
            self._port_name = port
            print(f"  Connected to {port}")
            return True

        except Exception as e:
            print(f"  Connection failed: {e}")
            self.is_connected = False
            self.conn = None
            return False

    def _find_ch340_port(self) -> Optional[str]:
        """Scan for CH340 adapter by VID/PID."""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if p.vid == self.CH340_VID and p.pid == self.CH340_PID:
                return p.device
        return None

    def _drain_startup(self):
        """Drain any startup messages from the MCU."""
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if self.conn.in_waiting > 0:
                line = self.conn.readline().decode("utf-8", errors="replace").strip()
                if line:
                    print(f"    uC: {line}")
            else:
                time.sleep(0.05)
        self.conn.reset_input_buffer()
        self.conn.reset_output_buffer()

    def _init_standby(self):
        """Initialize Port A and B to standby conditions."""
        self.send_command("O,A,C2", wait_ack=True)
        self.send_command("O,A,9E", wait_ack=True)
        self.send_command("O,A,00", wait_ack=True)
        self.send_command("O,B,16", wait_ack=True)

    def send_command(self, cmd: str, wait_ack: bool = True, timeout: float = 1.0) -> bool:
        """
        Send a command to the MCU.

        Args:
            cmd: Command string (e.g., "O,A,3C")
            wait_ack: If True, wait for 'K' response
            timeout: Timeout in seconds

        Returns:
            True if ACK received (or not required), False on timeout
        """
        if not self.conn:
            return False

        print(f"  [UART TX] {cmd}")
        self.conn.write((cmd + "\r\n").encode("utf-8"))
        self.conn.flush()

        if wait_ack:
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.conn.in_waiting > 0:
                    line = self.conn.readline().decode("utf-8", errors="replace").strip()
                    if line.startswith("#"):
                        continue
                    if line == "K":
                        print("  [UART RX] K (ACK)")
                        return True
                    print(f"  [UART RX] {line}")
                    return False
                time.sleep(0.001)
            print("  [UART RX] Timeout waiting for ACK!")
            return False
            
        print("  [UART RX] K (ACK)")
        return True

    def read_adc_value(self, timeout: float = 5.0) -> Optional[int]:
        """
        Read a D,<value> response from the MCU.

        Returns:
            ADC value (0-4095) or None on timeout.
        """
        if not self.conn:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.conn.in_waiting > 0:
                line = self.conn.readline().decode("utf-8", errors="replace").strip()
                if line.startswith("#"):
                    continue
                if line.startswith("D,"):
                    try:
                        return int(line.split(",")[1].strip())
                    except (IndexError, ValueError):
                        return None
                # If we get something unexpected, return None
                if line:
                    return None
            time.sleep(0.001)
        return None

    def close(self):
        """Close the serial connection."""
        if self.conn and self.conn.is_open:
            self.conn.close()
        self.is_connected = False
        self.conn = None