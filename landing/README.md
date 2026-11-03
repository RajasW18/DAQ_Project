# ForgeLab workspace

Start the local workspace from the repository root:

```powershell
.\.venv\Scripts\python.exe forgelab_server.py
```

Then open `http://127.0.0.1:8765/`.

The workspace reads the project files through the local API. `firmware.ino`
is a read-only UI alias for `firmware/src/main.cpp`, so the existing Universal
Firmware Engine remains the source of truth. Uploads are kept as reviewable
draft context. Agent requests are proxied to the configured local Ollama
endpoint or Groq provider, and no browser request can flash or execute
hardware.
