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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
AGENT_TOKEN = os.getenv("FORGELAB_AGENT_TOKEN", "").strip() or secrets.token_urlsafe(32)
PORT = int(os.getenv("FORGELAB_AGENT_PORT", "8787"))


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    return secrets.compare_digest(
        handler.headers.get("Authorization", "").removeprefix("Bearer ").strip(),
        AGENT_TOKEN,
    )


def run_platformio(args: list[str]) -> dict:
    command = ["pio", "run", "--project-dir", str(ROOT / "firmware"), *args]
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


class AgentHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "online", "agent": "ForgeLab Local Agent"})
            return
        if not authorized(self):
            self.send_json(401, {"error": "Valid agent token required."})
            return
        if self.path == "/api/device":
            self.send_json(200, {"status": "ready", "board": "ATmega2560", "transport": "serial"})
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
        self.send_json(400, {"error": "Supported commands: build, flash."})


if __name__ == "__main__":
    print(f"ForgeLab Local Agent listening on http://127.0.0.1:{PORT}")
    print(f"FORGELAB_AGENT_TOKEN={AGENT_TOKEN}")
    ThreadingHTTPServer(("127.0.0.1", PORT), AgentHandler).serve_forever()
