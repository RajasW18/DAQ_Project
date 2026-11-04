"""Local ForgeLab hardware agent.

Run this on the computer connected to the ATmega2560. The cloud IDE must
eventually pair with this agent before requesting commands. Flashing is never
performed without the explicit ``confirm_flash`` field.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import serial
except ImportError:
    serial = None

ROOT = Path(__file__).resolve().parent
AGENT_TOKEN = os.getenv("FORGELAB_AGENT_TOKEN", "").strip() or secrets.token_urlsafe(32)
PORT = int(os.getenv("FORGELAB_AGENT_PORT", "8787"))
SERIAL_PORT = os.getenv("FORGELAB_SERIAL_PORT", "").strip()
SERIAL_BAUD = int(os.getenv("FORGELAB_SERIAL_BAUD", "9600"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
serial_connection = None
serial_lock = threading.Lock()


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    return secrets.compare_digest(
        handler.headers.get("Authorization", "").removeprefix("Bearer ").strip(),
        AGENT_TOKEN,
    )


def cors_origin(handler: BaseHTTPRequestHandler) -> str:
    origin = handler.headers.get("Origin", "")
    if origin.startswith(("http://localhost:", "http://127.0.0.1:")) or origin == FRONTEND_ORIGIN:
        return origin
    return "null"


def run_platformio(args: list[str]) -> dict:
    command = [sys.executable, "-m", "platformio", "run", "--project-dir", str(ROOT / "firmware"), *args]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"success": False, "error": str(exc)}
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-20000:],
    }


def device_status() -> dict:
    return {
        "status": "ready" if serial_connection and serial_connection.is_open else "offline",
        "board": "ATmega2560",
        "transport": "serial",
        "port": SERIAL_PORT or None,
        "baud": SERIAL_BAUD,
        "serial_available": serial is not None,
    }


def send_serial_command(line: str) -> str:
    global serial_connection
    if serial is None:
        raise RuntimeError("pyserial is not installed.")
    if not SERIAL_PORT:
        raise RuntimeError("FORGELAB_SERIAL_PORT is not configured.")
    with serial_lock:
        if serial_connection is None or not serial_connection.is_open:
            serial_connection = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
        serial_connection.reset_input_buffer()
        serial_connection.write((line.rstrip("\r\n") + "\n").encode("utf-8"))
        serial_connection.flush()
        response = serial_connection.readline().decode("utf-8", errors="replace").strip()
        if not response:
            raise TimeoutError(f"No response from controller for {line!r}.")
        return response


class AgentHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", cors_origin(self))
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", cors_origin(self))
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "online", "agent": "ForgeLab Local Agent"})
            return
        if not authorized(self):
            self.send_json(401, {"error": "Valid agent token required."})
            return
        if self.path == "/api/device":
            self.send_json(200, device_status())
            return
        self.send_json(404, {"error": "Unknown agent endpoint."})

    def do_POST(self):
        if not authorized(self):
            self.send_json(401, {"error": "Valid agent token required."})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": f"Invalid agent request: {exc}"})
            return
        if urlparse(self.path).path != "/api/command":
            self.send_json(404, {"error": "Unknown agent endpoint."})
            return
        command = request.get("command")
        if command == "build":
            self.send_json(200, run_platformio([]))
            return
        if command == "flash":
            if request.get("confirm_flash") is not True:
                self.send_json(409, {"error": "Flashing requires confirm_flash=true."})
                return
            self.send_json(200, run_platformio(["--target", "upload"]))
            return
        if command == "serial":
            line = str(request.get("line", "")).strip()
            if not line or len(line) > 60:
                self.send_json(400, {"error": "A serial command of 1-60 characters is required."})
                return
            read_only = line in {"PING", "STATUS"}
            if not read_only and request.get("confirm_hardware") is not True:
                self.send_json(409, {"error": "Hardware writes require confirm_hardware=true."})
                return
            try:
                response = send_serial_command(line)
            except (OSError, RuntimeError, TimeoutError) as exc:
                self.send_json(502, {"error": str(exc)})
                return
            self.send_json(200, {"success": True, "command": line, "response": response})
            return
        self.send_json(400, {"error": "Supported commands: build, flash, serial."})


if __name__ == "__main__":
    print(f"ForgeLab Local Agent listening on http://127.0.0.1:{PORT}")
    print(f"FORGELAB_AGENT_TOKEN={AGENT_TOKEN}")
    ThreadingHTTPServer(("127.0.0.1", PORT), AgentHandler).serve_forever()
