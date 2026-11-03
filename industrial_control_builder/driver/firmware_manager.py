"""Constrained PlatformIO operations for the checked-in firmware project."""

from pathlib import Path
import shutil
import subprocess
import sys


class FirmwareManager:
    ENVIRONMENT = "atmega2560"

    def __init__(self):
        self.project = Path(__file__).resolve().parents[2] / "firmware"
        self.ini = self.project / "platformio.ini"
        if not self.ini.is_file():
            raise FileNotFoundError(f"PlatformIO project was not found: {self.ini}")

    def _command(self):
        for name in ("pio", "platformio"):
            binary = shutil.which(name)
            if binary:
                return [binary]
        try:
            import importlib.util
            if importlib.util.find_spec("platformio"):
                return [sys.executable, "-m", "platformio"]
        except (ImportError, ValueError):
            pass
        raise RuntimeError("PlatformIO is not installed. Install PlatformIO Core or the VS Code extension, then restart the application.")

    def _run(self, args, timeout=300):
        cmd = self._command() + args
        try:
            proc = subprocess.run(cmd, cwd=str(self.project), capture_output=True,
                                  text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"PlatformIO operation timed out after {timeout}s.") from exc
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode:
            raise RuntimeError(f"PlatformIO exited with code {proc.returncode}.\n{output[-10000:]}")
        return output[-10000:] or "PlatformIO operation completed."

    def build(self):
        return self._run(["run", "-e", self.ENVIRONMENT])

    def build_and_upload(self, port):
        if not port or any(ch.isspace() for ch in port):
            raise ValueError("Enter one serial port name, such as COM4.")
        return self._run(["run", "-e", self.ENVIRONMENT, "-t", "upload", "--upload-port", port], timeout=600)
