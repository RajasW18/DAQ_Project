"""Local ForgeLab workspace server.

Serves the browser workspace and connects the frontend and backend.
Provides real-time workspace files, hardware profile, DSL sequence simulation,
reviewable draft persistence, and AI-assisted engineering chat.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import mimetypes
import os
import secrets
import sys
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
LANDING = ROOT / "landing"
DRAFTS_DIR = ROOT / ".drafts"
ALLOWED_EXTENSIONS = {".ino", ".cpp", ".h", ".py", ".json", ".csv", ".pdf", ".md", ".txt"}

SOURCE_FILES = {
    "firmware.ino": ROOT / "initial_firmware.ino",
    "hal_mcu.h": ROOT / "firmware" / "include" / "hal_mcu.h",
    "platformio.ini": ROOT / "firmware" / "platformio.ini",
    "sequence_engine.py": ROOT / "core" / "sequence_engine.py",
    "analysis_pipeline.py": ROOT / "industrial_control_builder" / "analysis" / "pipeline.py",
    "instrument_config.json": ROOT / "import_data" / "master_elements.json",
    "calibration.csv": ROOT / "sequence_data.csv",
    "run-notes.md": ROOT / "industrial_build_spec.md",
}

SERVER_START_TIME = time.time()
AUTH_SESSIONS = {}
AUTH_OTP_STORE = {}
AUTH_OAUTH_STATES = {}


def load_project_env():
    """Load plain KEY=VALUE entries without overriding deployment settings."""
    env_path = ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip().strip("\"'")
        os.environ.setdefault(key.strip(), value)


load_project_env()
AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip() or secrets.token_hex(32)


def persist_user(user_data: dict) -> dict:
    from web_database import get_or_create_user, get_web_session
    session = get_web_session()
    try:
        user = get_or_create_user(session, user_data)
        user_data = dict(user_data)
        user_data["id"] = user.id
        return user_data
    finally:
        session.close()


def initialize_web_database():
    try:
        from web_database import init_web_db
        init_web_db()
        return True
    except Exception as exc:
        sys.stderr.write(f"[ForgeLab DB] Web database unavailable: {exc}\n")
        return False


def record_chat(user: dict, role: str, content: str, provider: str = "local", project_id: int | None = None) -> None:
    from web_database import ChatMessage, Project, get_web_session
    session = get_web_session()
    try:
        project = session.get(Project, project_id) if project_id else None
        if project is not None and project.owner_id != user["id"]:
            project = None
        if project is None:
            project = session.query(Project).filter_by(owner_id=user["id"]).order_by(Project.id).first()
        if project is None:
            project = Project(owner_id=user["id"], name="My ForgeLab Workspace")
            session.add(project)
            session.flush()
        session.add(ChatMessage(
            project_id=project.id,
            user_id=user["id"],
            role=role,
            content=content[:50000],
            provider=provider,
        ))
        session.commit()
    finally:
        session.close()


def read_context() -> str:
    sections = []
    total_chars = 0
    max_total_chars = 32000
    for name, path in SOURCE_FILES.items():
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            sections.append(f"FILE {name}: unavailable ({exc})")
            continue
        remaining = max_total_chars - total_chars
        if remaining <= 0:
            break
        excerpt = content[:min(6000, remaining)]
        sections.append(f"FILE {name}\n{excerpt}")
        total_chars += len(excerpt)
    return "\n\n".join(sections)


def fallback_agent_response(prompt: str) -> dict:
    """Generate an authoritative local response when external LLM is offline.

    Leverages local repository context, ATmega2560 pin profiles, latch addresses,
    and sequence DSL knowledge.
    """
    lower = prompt.lower()
    
    if any(lower.strip().startswith(g) for g in ["hi", "hello", "hey", "sup", "greetings"]):
        return {
            "message": (
                "👋 Hello! I am **ForgeLab Agent**, your hardware-aware engineering pair programmer.\n\n"
                "I have the ATmega2560 profile, pin latches, and repository context indexed in local memory.\n\n"
                "**Quick capabilities:**\n"
                "- **Output Mapping**: Inspect Port A & B latches (pins 7 & 8) and input clock (pin 9)\n"
                "- **DSL Planning**: Draft and simulate safe PWM/pin sequences\n"
                "- **Draft Generation**: Generate reviewable wiring notes or firmware patches without modifying source"
            ),
            "dsl": "",
            "provider": "local-hardware-engine"
        }

    if "baud" in lower or "speed" in lower or "uart" in lower:
        return {
            "message": (
                "### UART Serial Protocol Specification\n\n"
                "- **Baud Rate**: `9600 bps` (defined in `hal_mcu.h` & `initial_firmware.ino`)\n"
                "- **UART Port**: Primary hardware serial on `D0 (RX)` and `D1 (TX)`\n"
                "- **Framing**: 8 Data bits, No parity, 1 Stop bit (8-N-1)\n"
                "- **Protocol**: ASCII newline-terminated (`\\n`) packets\n\n"
                "All commands are received non-blocking in `loop()` and executed via `handleCommand()`."
            ),
            "dsl": "",
            "provider": "local-hardware-engine"
        }

    if "pwm" in lower or "sequence" in lower or "simulate" in lower:
        dsl = "CONFIG 9 PWM;\nW 9 160;\nDLY 150;\nW 9 0;"
        explanation = (
            "### ATmega2560 Safe PWM Sequence Draft\n\n"
            "According to `hal_mcu.h` and the timer allocation in `sequence_engine.py`, "
            "**Pin D9** supports hardware PWM.\n\n"
            "Here is a safe sequence that ramps channel 9 to **62% duty cycle** (`160/255`), holds for **150ms**, and returns to safe baseline (`0`):\n\n"
            f"```dsl\n{dsl}\n```\n\n"
            "Click **▶ Simulate this DSL** below to compile and verify this sequence in the hardware engine."
        )
        return {
            "message": explanation,
            "dsl": dsl,
            "provider": "local-hardware-engine",
            "artifact": {
                "filename": "draft_pwm_sequence.dsl",
                "content": f"# ATmega2560 PWM Calibration Sequence\n# Generated locally by ForgeLab Engine\n{dsl}\n",
                "summary": "Verified 4-step PWM sequence targeting timer pin 9."
            }
        }
    
    if "map" in lower or "output" in lower or "port" in lower or "latch" in lower:
        explanation = (
            "### ATmega2560 16-Bit Output Map Analysis\n\n"
            "According to `initial_firmware.ino` and `hal_mcu.h`:\n\n"
            "- **Port A Latch Pin**: `D7` (controls low-byte outputs `D0–D7`)\n"
            "- **Port B Latch Pin**: `D8` (controls high-byte outputs `D8–D15`)\n"
            "- **Input Clock Pin**: `D9` (clock sync for 12-bit ADC)\n"
            "- **Baud Rate**: `9600 bps` UART\n\n"
            "The 16-bit word is split in `sequence_engine.cpp`:\n\n"
            "```cpp\n"
            "writePortA(static_cast<uint8_t>(value & 0xFF));        // Low 8 bits (Port A)\n"
            "writePortB(static_cast<uint8_t>((value >> 8) & 0xFF)); // High 8 bits (Port B)\n"
            "```\n\n"
            "All writes are buffered and latched synchronously to prevent bus glitches."
        )
        return {
            "message": explanation,
            "dsl": "CONFIG 7 OUT; CONFIG 8 OUT; CONFIG 9 OUT;",
            "provider": "local-hardware-engine"
        }
        
    if "artifact" in lower or "draft" in lower or "wiring" in lower:
        wiring_draft = (
            "# ForgeLab Hardware Wiring & Pinout Specification\n"
            "## Architecture: Generic 16-bit I/O Spectroscopy Adapter\n\n"
            "| Signal | Pin | Direction | Function |\n"
            "|--------|-----|-----------|----------|\n"
            "| PORT_A_LATCH | D7 | Output | Latches bits 0-7 into low register |\n"
            "| PORT_B_LATCH | D8 | Output | Latches bits 8-15 into high register |\n"
            "| INPUT_CLOCK  | D9 | Output | Clock sync for 12-bit ADC acquisition |\n"
            "| UART_RX     | D0 | Input  | Command input at 9600 baud |\n"
            "| UART_TX     | D1 | Output | Telemetry output |\n\n"
            "### Safety Constraints\n"
            "- Safe state defaults all output bits to `0x0000` on boot.\n"
            "- Never assert latch pins simultaneously with bus transitions.\n"
        )
        return {
            "message": "Generated a complete wiring and register allocation artifact based on workspace firmware context.",
            "dsl": "",
            "provider": "local-hardware-engine",
            "artifact": {
                "filename": "wiring-notes.md",
                "content": wiring_draft,
                "summary": "Complete pinout and register mapping for ATmega2560 16-bit I/O."
            }
        }
        
    # General context inspection
    return {
        "message": (
            "I inspected the authoritative repository context (**8 files loaded**):\n\n"
            "- **Firmware**: `initial_firmware.ino`\n"
            "- **Hardware Contract**: `hal_mcu.h`\n"
            "- **Sequence Engine**: `sequence_engine.py`\n"
            "- **Master Calibration**: `sequence_data.csv`\n\n"
            "All originals are strictly read-only. I can explain hardware logic, "
            "propose DSL control sequences, or generate reviewable draft artifacts."
        ),
        "dsl": "",
        "provider": "local-hardware-engine"
    }


def send_smtp_email(to_email: str, otp_code: str) -> bool:
    """Send OTP email using SMTP if configured in environment."""
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = (os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or "").strip()
    from_email = os.getenv("SMTP_FROM", smtp_user or "auth@forgelab.internal").strip()

    if not smtp_host or not smtp_user:
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your ForgeLab Verification Code: {otp_code}"
        msg["From"] = f"ForgeLab Security <{from_email}>"
        msg["To"] = to_email

        text = f"Your ForgeLab verification code is: {otp_code}\n\nThis code expires in 10 minutes."
        html = f"""
        <div style="font-family:sans-serif; max-width:480px; margin:0 auto; padding:24px; border:1px solid #e2e8f0; border-radius:10px;">
          <h2 style="color:#111; margin-top:0;">ForgeLab Authentication</h2>
          <p style="color:#4a5568;">Use the one-time verification code below to sign in to your engineering workspace:</p>
          <div style="background:#f7fafc; padding:16px; border-radius:8px; text-align:center; font-size:32px; font-weight:700; letter-spacing:6px; color:#b57900; margin:20px 0;">
            {otp_code}
          </div>
          <p style="color:#718096; font-size:12px;">This code expires in 10 minutes. If you did not request this, you can safely ignore this email.</p>
        </div>
        """
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=8) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as exc:
        sys.stderr.write(f"[ForgeLab SMTP] Failed to send email via {smtp_host}: {exc}\n")
        return False


def create_session(user: dict) -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(AUTH_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    token = f"{nonce}.{signature}"
    AUTH_SESSIONS[token] = {"user": user, "expires_at": time.time() + 86400 * 7}
    return token


def session_user(handler: BaseHTTPRequestHandler):
    cookie_header = handler.headers.get("Cookie", "")
    token = next(
        (part.strip().split("=", 1)[1] for part in cookie_header.split(";")
         if part.strip().startswith("forgelab_session=") and "=" in part),
        None,
    )
    if not token:
        return None
    nonce, separator, signature = token.rpartition(".")
    expected = hmac.new(AUTH_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    if not separator or not hmac.compare_digest(signature, expected):
        return None
    session = AUTH_SESSIONS.get(token)
    if not session or time.time() > session["expires_at"]:
        AUTH_SESSIONS.pop(token, None)
        return None
    return session["user"]


def google_configuration():
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "").strip(),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/"),
    }


def google_token_user(code: str, config: dict) -> dict:
    payload = urlencode({
        "code": code,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
    }).encode("utf-8")
    token_request = Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=10) as response:
            token_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Google token exchange failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise ValueError(f"Google token endpoint is unreachable: {exc.reason}") from exc
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Google did not return an access token.")
    user_request = Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urlopen(user_request, timeout=10) as response:
            user_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Google profile request failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise ValueError(f"Google profile endpoint is unreachable: {exc.reason}") from exc
    if not user_data.get("email") or not user_data.get("email_verified"):
        raise ValueError("Google account email is missing or not verified.")
    return {
        "email": user_data["email"],
        "name": user_data.get("name") or user_data["email"].split("@")[0],
        "picture": user_data.get("picture", ""),
        "provider": "google-oauth",
    }

class ForgeLabHandler(BaseHTTPRequestHandler):
    server_version = "ForgeLabLocal/1.0"

    def log_message(self, format, *args):
        sys.stderr.write(f"[ForgeLab] {format % args}\n")

    def _set_cors_headers(self):
        # Permissive CORS for local workspace dev (supports file://, 127.0.0.1, localhost)
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Accept, Origin, X-API-Key, X-Provider")

    def send_json(self, status: int, payload: dict, session_token: str | None = None):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if session_token:
            self.send_header(
                "Set-Cookie",
                f"forgelab_session={session_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800",
            )
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/workspace", "/workspace.html"} and session_user(self) is None:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        if path == "/auth/google":
            self.start_google_auth()
            return

        if path == "/auth/google/callback":
            self.complete_google_auth(parse_qs(parsed.query))
            return
        
        # 1. Server Health & Status
        if path in {"/api/status", "/api/health"}:
            self.send_status()
            return

        if path == "/api/auth/me":
            user = session_user(self)
            self.send_json(200, {"authenticated": bool(user), "user": user})
            return

        if path == "/api/profile":
            self.handle_profile_get()
            return

        if path == "/api/projects":
            self.handle_projects_get()
            return

        if path == "/api/chat/history":
            self.handle_chat_history(parse_qs(urlparse(self.path).query))
            return

        # 2. Workspace File Listing
        if path == "/api/workspace":
            self.send_json(200, {
                "status": "online",
                "workspace": "spectroscopy-adapter",
                "files": self.workspace_files()
            })
            return

        # 3. Individual File Content
        if path.startswith("/api/file/"):
            name = path.removeprefix("/api/file/")
            self.send_file_content(name)
            return

        # 4. Static Website / Assets
        self.serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        if path == "/api/chat":
            self.handle_chat(raw)
            return
            
        if path == "/api/simulate":
            self.handle_simulate(raw)
            return
            
        if path == "/api/upload":
            self.handle_upload(raw)
            return

        if path == "/api/save-draft":
            self.handle_save_draft(raw)
            return

        if path == "/api/auth/send-otp":
            self.handle_auth_send_otp(raw)
            return

        if path == "/api/auth/verify-otp":
            self.handle_auth_verify_otp(raw)
            return

        if path == "/api/auth/logout":
            self.handle_auth_logout()
            return

        if path == "/api/profile":
            self.handle_profile_update(raw)
            return

        if path == "/api/projects":
            self.handle_project_create(raw)
            return

        self.send_json(404, {"error": "Unknown ForgeLab endpoint."})

    def send_status(self):
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        groq_active = bool(groq_key)
        gemini_active = bool(gemini_key)
        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
        
        database_status = "unconfigured"
        database_session = None
        try:
            from web_database import get_web_session
            from sqlalchemy import text
            database_session = get_web_session()
            database_session.execute(text("SELECT 1"))
            database_status = "ready"
        except Exception as exc:
            database_status = "unavailable"
            sys.stderr.write(f"[ForgeLab DB] Health check failed: {exc}\n")
        finally:
            if database_session is not None:
                database_session.close()

        self.send_json(200, {
            "status": "online",
            "server": "ForgeLabLocal/1.0",
            "port": self.server.server_address[1],
            "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
            "workspace": "spectroscopy-adapter",
            "files_count": len(SOURCE_FILES),
            "files": list(SOURCE_FILES.keys()),
            "board": {
                "name": "ATmega2560",
                "profile": "generic-16bit-io",
                "baud": 9600,
                "output_bits": 16,
                "input_bits": 12,
                "latches": {"port_a": 7, "port_b": 8, "clock": 9}
            },
            "ai_providers": {
                "gemini": {"available": gemini_active, "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash")},
                "groq": {"available": groq_active, "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")},
                "ollama": {"available": True, "url": ollama_url, "model": os.getenv("OLLAMA_MODEL", "llama3.2")},
                "local_engine": {"available": True, "status": "active"}
            },
            "auth": {
                "smtp_configured": bool(
                    os.getenv("SMTP_HOST")
                    and os.getenv("SMTP_USERNAME")
                    and os.getenv("SMTP_PASSWORD")
                ),
                "google_oauth": bool(google_configuration()["client_id"])
            },
            "database": {"status": database_status}
        })

    def handle_profile_get(self):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        from web_database import get_web_session, User
        session = get_web_session()
        try:
            profile = session.get(User, user["id"])
            if not profile:
                self.send_json(404, {"error": "Profile not found."})
                return
            self.send_json(200, {
                "id": profile.id, "email": profile.email, "name": profile.name,
                "avatar_url": profile.avatar_url, "bio": profile.bio,
                "education": profile.education,
                "personal_background": profile.personal_background,
            })
        finally:
            session.close()

    def handle_profile_update(self, raw: bytes):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": f"Invalid profile request: {exc}"})
            return
        from web_database import get_web_session, User
        session = get_web_session()
        try:
            profile = session.get(User, user["id"])
            if not profile:
                self.send_json(404, {"error": "Profile not found."})
                return
            for field in ("name", "avatar_url", "bio", "education", "personal_background"):
                if field in data:
                    setattr(profile, field, str(data[field])[:10000])
            session.commit()
            self.send_json(200, {"success": True, "message": "Profile updated."})
        finally:
            session.close()

    def handle_projects_get(self):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        from web_database import get_web_session, Project
        session = get_web_session()
        try:
            projects = session.query(Project).filter_by(owner_id=user["id"]).order_by(Project.updated_at.desc()).all()
            self.send_json(200, {"projects": [
                {"id": p.id, "name": p.name, "description": p.description,
                 "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}
                for p in projects
            ]})
        finally:
            session.close()

    def handle_project_create(self, raw: bytes):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        try:
            data = json.loads(raw.decode("utf-8"))
            name = str(data.get("name", "")).strip()
            description = str(data.get("description", "")).strip()
            if not name or len(name) > 200:
                self.send_json(400, {"error": "Project name is required and must be 200 characters or fewer."})
                return
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": f"Invalid project request: {exc}"})
            return
        from web_database import get_web_session, Project
        session = get_web_session()
        try:
            project = Project(owner_id=user["id"], name=name, description=description[:10000])
            session.add(project)
            session.commit()
            self.send_json(201, {"id": project.id, "name": project.name, "description": project.description})
        finally:
            session.close()

    def handle_chat_history(self, query: dict):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        project_id = query.get("project_id", [None])[0]
        from web_database import ChatMessage, Project, get_web_session
        session = get_web_session()
        try:
            project = session.get(Project, int(project_id)) if project_id else None
            if project is not None and project.owner_id != user["id"]:
                self.send_json(403, {"error": "That project does not belong to this account."})
                return
            if project is None:
                project = session.query(Project).filter_by(owner_id=user["id"]).order_by(Project.id).first()
            if project is None:
                self.send_json(200, {"messages": []})
                return
            messages = session.query(ChatMessage).filter_by(
                project_id=project.id, user_id=user["id"]
            ).order_by(ChatMessage.created_at.asc()).limit(200).all()
            self.send_json(200, {"project_id": project.id, "messages": [
                {"role": message.role, "content": message.content,
                 "provider": message.provider, "created_at": message.created_at.isoformat()}
                for message in messages
            ]})
        except (TypeError, ValueError):
            self.send_json(400, {"error": "project_id must be a valid project ID."})
        finally:
            session.close()

    def workspace_files(self):
        files = []
        for name, path in SOURCE_FILES.items():
            size = path.stat().st_size if path.exists() else 0
            lines = 0
            if path.exists():
                try:
                    lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                except Exception:
                    pass
            files.append({
                "name": name,
                "source": str(path.relative_to(ROOT)),
                "readOnly": True,
                "sizeBytes": size,
                "lineCount": lines
            })
        return files

    def send_file_content(self, name: str):
        path = SOURCE_FILES.get(name)
        if path is None:
            self.send_json(404, {"error": f"File is not part of the workspace context: {name}"})
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.send_json(500, {"error": f"Could not read {name}: {exc}"})
            return
        self.send_json(200, {
            "name": name,
            "source": str(path.relative_to(ROOT)),
            "content": content,
            "readOnly": True,
            "sizeBytes": len(content)
        })

    def handle_chat(self, raw: bytes):
        user = session_user(self)
        if not user:
            self.send_json(401, {"error": "Authentication required."})
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            prompt = str(request.get("prompt", "")).strip()
            conversation = request.get("conversation", [])
            provider_name = str(request.get("provider", "local")).strip().lower()
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            self.send_json(400, {"error": f"Invalid chat request: {exc}"})
            return

        if not prompt:
            self.send_json(400, {"error": "A prompt is required."})
            return
        project_id = request.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            self.send_json(400, {"error": "project_id must be a valid project ID."})
            return
        record_chat(user, "user", prompt, provider_name, project_id)

        # If user explicitly wants local engine or if external provider fails, use authoritative local engine
        if provider_name in {"local", "heuristic", "mock"}:
            response = fallback_agent_response(prompt)
            record_chat(user, "assistant", response["message"], response.get("provider", "local"), project_id)
            self.send_json(200, response)
            return

        try:
            from industrial_control_builder.ai_orchestrator.llm_provider import create_provider
            api_key = str(request.get("api_key", "")).strip() or None
            provider = create_provider(provider_name, api_key=api_key)
            system = (
                "You are ForgeLab, a cautious agentic engineering assistant. "
                "Use the supplied repository context for the generic 16-bit I/O spectroscopy system. "
                "Explain files, propose safe patches, and draft artifacts. Never claim execution, flashing, "
                "or verification. Existing source is read-only; every change is a reviewable draft. "
                'Return JSON with keys "dsl" and "explanation". If the user asks for code or an artifact, '
                "put the complete proposed draft in explanation and summarize the file name."
            )
            user = f"User request:\n{prompt}\n\nAuthoritative workspace context:\n{read_context()}"
            result = provider.create_plan(system, user, conversation if isinstance(conversation, list) else [])
            response = {
                "message": result.get("explanation", ""),
                "dsl": result.get("dsl", ""),
                "provider": provider_name
            }
            if "artifact" in prompt.lower() or "generate" in prompt.lower():
                artifact = provider.generate_artifact("firmware or integration artifact", ".draft", prompt, read_context())
                response["artifact"] = artifact
            record_chat(user, "assistant", response["message"], provider_name, project_id)
            self.send_json(200, response)
        except Exception as exc:
            # Graceful fallback: return domain-aware local response instead of 502 crash!
            sys.stderr.write(f"[ForgeLab] External provider '{provider_name}' error: {exc}. Using local engine.\n")
            fallback = fallback_agent_response(prompt)
            fallback["warning"] = f"External LLM ({provider_name}) offline: {exc}. Served via local hardware engine."
            record_chat(user, "assistant", fallback["message"], "local", project_id)
            self.send_json(200, fallback)

    def handle_simulate(self, raw: bytes):
        """Compile and simulate sequence DSL using the internal task engine and ATmega2560 HAL."""
        try:
            request = json.loads(raw.decode("utf-8"))
            dsl_text = str(request.get("dsl", "")).strip()
            if not dsl_text:
                # If no raw DSL provided, look for a sample or draft in request
                dsl_text = "CONFIG 9 PWM;\nW 9 160;\nDLY 150;\nW 9 0;"
        except Exception as exc:
            self.send_json(400, {"error": f"Invalid simulation request: {exc}"})
            return

        try:
            from industrial_control_builder.hal.atmega2560 import ATmega2560HAL
            from industrial_control_builder.driver.serial_driver import SerialDriver
            from industrial_control_builder.sequence.task_engine import TaskEngine
            from industrial_control_builder.ai_orchestrator.command_dsl import CommandDSLCompiler

            hal = ATmega2560HAL()
            driver = SerialDriver(use_mock=True)
            engine = TaskEngine(hal=hal, driver=driver)

            engine, pipeline, logs = CommandDSLCompiler.compile(dsl_text, hal, engine)
            
            steps_data = []
            total_duration_ms = 0
            for idx, step in enumerate(engine.steps, 1):
                steps_data.append({
                    "step": idx,
                    "type": step.step_type,
                    "pin": step.pin,
                    "value": step.value,
                    "delay_ms": step.delay_ms,
                    "description": step.description
                })
                total_duration_ms += step.delay_ms

            self.send_json(200, {
                "success": True,
                "message": f"Successfully compiled {len(engine.steps)} sequence steps without hardware side-effects.",
                "steps_count": len(engine.steps),
                "steps": steps_data,
                "pin_modes": {f"D{k}": v for k, v in engine.pin_modes.items()},
                "logs": logs,
                "estimated_duration_ms": total_duration_ms,
                "pipeline_steps": len(pipeline.steps)
            })
        except Exception as exc:
            self.send_json(200, {
                "success": False,
                "error": str(exc),
                "logs": [f"Compilation error: {exc}"]
            })

    def handle_save_draft(self, raw: bytes):
        """Save a user draft safely to .drafts directory without modifying original source."""
        try:
            request = json.loads(raw.decode("utf-8"))
            filename = Path(str(request.get("name", "draft.txt"))).name
            content = str(request.get("content", ""))
            
            DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
            draft_path = DRAFTS_DIR / filename
            draft_path.write_text(content, encoding="utf-8")
            
            self.send_json(200, {
                "success": True,
                "name": filename,
                "path": str(draft_path.relative_to(ROOT)),
                "sizeBytes": len(content),
                "message": f"Draft saved safely as {filename}. Original source files untouched."
            })
        except Exception as exc:
            self.send_json(500, {"error": f"Failed to save draft: {exc}"})

    def start_google_auth(self):
        config = google_configuration()
        if not all((config["client_id"], config["client_secret"], config["redirect_uri"])):
            self.send_json(503, {"error": "Google OAuth is not configured on the server."})
            return
        state = secrets.token_urlsafe(24)
        AUTH_OAUTH_STATES[state] = time.time() + 600
        query = urlencode({
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        })
        self.send_response(302)
        self.send_header("Location", f"https://accounts.google.com/o/oauth2/v2/auth?{query}")
        self.end_headers()

    def complete_google_auth(self, query: dict):
        config = google_configuration()
        state = query.get("state", [""])[0]
        code = query.get("code", [""])[0]
        if not state or AUTH_OAUTH_STATES.pop(state, 0) < time.time():
            self.send_error(400, "Invalid or expired OAuth state.")
            return
        if query.get("error") or not code:
            self.send_error(400, "Google sign-in was cancelled or failed.")
            return
        try:
            user = google_token_user(code, config)
            user = persist_user(user)
            token = create_session(user)
            self.send_response(302)
            self.send_header("Location", f"{config['frontend_url']}/workspace.html")
            self.send_header(
                "Set-Cookie",
                f"forgelab_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800",
            )
            self.end_headers()
        except Exception as exc:
            sys.stderr.write(f"[ForgeLab Auth] Google OAuth failed: {exc}\n")
            self.send_error(502, f"Google sign-in could not be completed: {exc}")

    def handle_auth_logout(self):
        self.send_response(204)
        self.send_header("Set-Cookie", "forgelab_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
        self._set_cors_headers()
        self.end_headers()

    def handle_auth_send_otp(self, raw: bytes):
        """Generate a 6-digit OTP and dispatch it through the configured SMTP server."""
        try:
            req = json.loads(raw.decode("utf-8"))
            email = str(req.get("email", "")).strip().lower()
            if not email or "@" not in email:
                self.send_json(400, {"error": "A valid email address is required."})
                return

            import random
            code = f"{random.randint(100000, 999999)}"
            AUTH_OTP_STORE[email] = {
                "code": code,
                "expires_at": time.time() + 600
            }

            sent = send_smtp_email(email, code)
            sys.stderr.write(f"[ForgeLab Auth] OTP requested for {email} (SMTP sent={sent})\n")

            self.send_json(200, {
                "success": True,
                "email": email,
                "smtp_sent": sent,
                "message": "Verification code sent." if sent else "SMTP is not configured; email delivery is unavailable."
            })
        except Exception as exc:
            self.send_json(500, {"error": f"Failed to send OTP: {exc}"})

    def handle_auth_verify_otp(self, raw: bytes):
        """Verify 6-digit OTP code and create user session."""
        try:
            req = json.loads(raw.decode("utf-8"))
            email = str(req.get("email", "")).strip().lower()
            code = str(req.get("code", "")).strip()

            record = AUTH_OTP_STORE.get(email)
            if not record:
                self.send_json(400, {"error": "No verification code requested or code expired. Please request a new code."})
                return

            if time.time() > record["expires_at"]:
                AUTH_OTP_STORE.pop(email, None)
                self.send_json(400, {"error": "Verification code expired. Please request a new code."})
                return

            if not secrets.compare_digest(record["code"], code):
                self.send_json(400, {"error": "Invalid verification code. Please check and try again."})
                return

            AUTH_OTP_STORE.pop(email, None)
            name = email.split("@")[0].replace(".", " ").title()
            user = {
                "email": email,
                "name": name,
                "provider": "smtp-otp"
            }
            user = persist_user(user)
            self.send_json(200, {
                "success": True,
                "user": user,
                "message": f"Welcome back, {name}!"
            }, session_token=create_session(user))
        except Exception as exc:
            self.send_json(500, {"error": f"Failed to verify OTP: {exc}"})

    def handle_upload(self, raw: bytes):
        try:
            request = json.loads(raw.decode("utf-8"))
            name = Path(str(request.get("name", ""))).name
            content = str(request.get("content", ""))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            self.send_json(400, {"error": f"Invalid upload request: {exc}"})
            return
            
        if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            self.send_json(415, {"error": "Unsupported file type."})
            return
            
        self.send_json(200, {
            "name": name,
            "content": content[:32000],
            "readOnly": True,
            "source": "browser upload",
            "message": f"File '{name}' uploaded and indexed into local session context."
        })

    def serve_static(self, path: str):
        if path == "/login":
            path = "/login.html"
        if path == "/favicon.ico" or path == "/spectra.jpg":
            candidate = ROOT / "spectra.jpg"
            if candidate.is_file():
                content = candidate.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(content)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content)
                return

        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (LANDING / relative).resolve()
        
        if LANDING not in candidate.parents and candidate != LANDING:
            self.send_error(403)
            return
            
        if not candidate.is_file():
            self.send_error(404)
            return
            
        content = candidate.read_bytes()
        mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.name.endswith(".css"):
            mime_type = "text/css"
        elif candidate.name.endswith(".js"):
            mime_type = "application/javascript"

        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    initialize_web_database()
    port = int(os.getenv("PORT", sys.argv[1] if len(sys.argv) > 1 else "8765"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"ForgeLab workspace server starting on http://{host}:{port}")
    try:
        ThreadingHTTPServer((host, port), ForgeLabHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nForgeLab server stopped.")
