"""
ASCII Text Protocol Formatter and Parser
Token-efficient line-based protocol for industrial control.
"""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class TelemetryData:
    channel: str       # e.g., 'A0', 'D13', 'R_12'
    value: float
    timestamp_ms: Optional[int] = None

class ASCIIProtocol:
    """Encodes commands and decodes telemetry/responses for the Universal Firmware Engine."""

    # Outgoing Command Encoders
    @staticmethod
    def ping() -> str:
        return "PING"

    @staticmethod
    def estop() -> str:
        return "ESTOP"

    @staticmethod
    def status() -> str:
        return "STATUS"

    @staticmethod
    def pin_mode(pin: int, mode: str) -> str:
        # mode: 'OUT', 'IN', 'PULLUP', 'PWM'
        return f"PIN {pin} {mode.upper()}"

    @staticmethod
    def write(pin: int, value: int) -> str:
        return f"W {pin} {value}"

    @staticmethod
    def read_digital(pin: int) -> str:
        return f"R {pin}"

    @staticmethod
    def read_analog(channel: int) -> str:
        return f"A {channel}"

    @staticmethod
    def poll_start(pin: int, interval_ms: int, is_analog: bool = True) -> str:
        mode_char = "A" if is_analog else "D"
        return f"POLL {pin} {interval_ms} {mode_char}"

    @staticmethod
    def poll_stop(pin: int) -> str:
        return f"POLL_STOP {pin}"

    @staticmethod
    def seq_clear() -> str:
        return "SEQ_CLEAR"

    @staticmethod
    def seq_add_write(pin: int, value: int) -> str:
        return f"SEQ_ADD W {pin} {value}"

    @staticmethod
    def seq_add_delay(delay_ms: int) -> str:
        return f"SEQ_ADD DLY {delay_ms}"

    @staticmethod
    def seq_add_read(pin: int, is_analog: bool = False) -> str:
        op = "A" if is_analog else "R"
        return f"SEQ_ADD {op} {pin}"

    @staticmethod
    def seq_run() -> str:
        return "SEQ_RUN"

    @staticmethod
    def seq_stop() -> str:
        return "SEQ_STOP"

    # Incoming Line Parser
    @staticmethod
    def parse_line(line: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Parses a response line from the MCU.
        Returns: (event_type, payload)
        Event types: 'ACK', 'VAL', 'DATA', 'STATUS', 'NOTIFY', 'PONG', 'ERR', 'UNKNOWN'
        """
        clean = line.strip()
        if not clean or clean.startswith("#"):
            return ("COMMENT", {"text": clean})

        if clean == "PONG":
            return ("PONG", {})

        if clean.startswith("ACK "):
            return ("ACK", {"raw": clean[4:].strip()})

        if clean.startswith("ERR "):
            return ("ERR", {"error": clean[4:].strip()})

        if clean.startswith("NOTIFY "):
            return ("NOTIFY", {"message": clean[7:].strip()})

        if clean.startswith("STATUS "):
            # Parse key=value pairs
            parts = clean[7:].split()
            status_dict = {}
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    status_dict[k] = v
            return ("STATUS", status_dict)

        if clean.startswith("VAL "):
            # e.g., VAL 13 1 or VAL A0 512
            parts = clean[4:].split()
            if len(parts) >= 2:
                channel = parts[0]
                try:
                    val = float(parts[1])
                    return ("VAL", {"channel": channel, "value": val})
                except ValueError:
                    pass

        if clean.startswith("DATA "):
            # e.g., DATA A0 512 124500 (polling stream)
            parts = clean[5:].split()
            if len(parts) >= 2:
                channel = parts[0]
                try:
                    val = float(parts[1])
                    ts = int(parts[2]) if len(parts) >= 3 else None
                    return ("DATA", {"telemetry": TelemetryData(channel=channel, value=val, timestamp_ms=ts)})
                except ValueError:
                    pass

        return ("UNKNOWN", {"raw": clean})
