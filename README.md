# SpectraSoft System Updates

## Deploy ForgeLab

ForgeLab is now deployable as one container: the Python server serves both the
landing pages and API, and listens on `0.0.0.0:$PORT`.

### Local production-like run

1. Copy `.env.example` to `.env` and fill in provider/auth values. Use a
   Google **App Password** for `SMTP_PASSWORD`, not the Gmail account password.
2. In Google Cloud Console, create a Web OAuth client and add
   `http://localhost:8765/auth/google/callback` as an authorized redirect URI.
3. Start the server:

   ```powershell
   .\.venv\Scripts\python.exe forgelab_server.py
   ```

4. Open `http://localhost:8765/login`.

### Free deployment

Render can deploy the included `render.yaml` and `Dockerfile` on its free web
service. Set `FRONTEND_URL` to the public Render URL and
`GOOGLE_REDIRECT_URI` to `<public-url>/auth/google/callback`, then add the
same callback URL in Google Cloud Console. Add all secrets in Render's
environment settings; never commit `.env`.

### AI providers

- **ForgeLab Local Engine** is always free and requires no key.
- **Ollama** is free locally: install Ollama and pull `llama3.2`.
- **Gemini** has a free API tier in eligible regions; set `GEMINI_API_KEY`.
- **Groq** offers a free developer tier with rate limits; set `GROQ_API_KEY`.

The provider selector exposes local, Ollama, Groq, and Gemini. Keep provider
keys on the server and do not send them from browser code.

## Standalone Industrial Control Builder

Launch the standalone app from the repository root:

```powershell
.\.venv\Scripts\python.exe standalone_main.py
```

It opens independently of SpectraSoft and targets
the supplied ATmega2560 O/A/B/I/T firmware without editing or flashing its
`.ino` source. See [STANDALONE_README.md](STANDALONE_README.md) for setup and
hardware details. Simulation is the default; live actions require confirmation.

The standalone app also has a **Generate Artifact** tab for user-directed
drafts of Python, Arduino, C++, Markdown, JSON, CSV templates, SVG, and text
files. Generated text is reviewable/editable, saved as a new file, and never
executed or flashed by the app. The original firmware remains unchanged.

### ForgeLab local workspace

ForgeLab is an optional browser workspace for inspecting the real project
context and creating reviewable AI drafts:

```powershell
.\.venv\Scripts\python.exe forgelab_server.py
```

Open `http://127.0.0.1:8765/`. The server keeps Groq credentials local,
proxies Ollama or Groq requests, maps `firmware.ino` to the authoritative
`firmware/src/main.cpp`, and never writes source files or executes hardware
actions. Uploads and generated artifacts remain reviewable browser drafts.

## Industrial Control Builder

Open **Industrial Control → AI Control Builder** from the desktop app. The first implementation supports:

- Groq hosted planning (`GROQ_API_KEY`, optional `GROQ_MODEL`) or a local Ollama endpoint (`OLLAMA_URL`, `OLLAMA_MODEL`). Install Ollama, download a model, and leave its local server running; default model is `llama3.2`.
- Document context from TXT, JSON, CSV, XLSX/XLSM, DOCX, PDF, and image references. PDF text extraction uses `pypdf`; Excel analysis uses `openpyxl`. Images are currently recorded as references only; OCR/vision extraction is not implemented.
- Compact, allow-listed DSL plans. The model does not create or execute Python. Plans are validated locally, displayed for editing, and hardware execution asks for approval.
- CSV and Excel numeric-table analysis using deterministic filters, calibration, statistics, regressions, derivatives, integration, and peak detection. Select Y and optional X columns in the page.
- PlatformIO build and explicitly confirmed firmware upload for the workspace firmware project.

Install the added document-analysis packages with `python -m pip install -r requirements.txt`. For Groq, set `GROQ_API_KEY` in the environment before starting the application. For Ollama, configure `OLLAMA_MODEL` to a model already installed locally.

### Firmware compatibility

The builder's live execution and PlatformIO upload target `firmware/`, which implements `PIN`, `W`, `SEQ_ADD`, `SEQ_RUN`, and related commands. The spectroscopy sketch supplied separately uses `O,<port>,<hex>`, `I`, and `T`; it does not implement the sequence-buffer commands. Those firmware protocols are not interchangeable. The UI calls out the required protocol before live use. Do not upload or execute against a board until the installed firmware and selected COM port are confirmed.

The builder currently compiles fixed workspace firmware; it does not let the LLM rewrite firmware source. Firmware changes should be reviewed in code and rebuilt before upload.

This document outlines the recent modifications made to the SpectraSoft application to address display sizing, data formatting, and High Voltage (HV) channel addressing issues.

## 1. CSV Data Storage Organization by Channel

**What:** 
The mock data storage format in `sequence_data.csv` was restructured to use the hardware channel number (ITG number) as the primary index rather than the element name. The CSV reader and exporter were updated to handle this new layout.

**Where:**
- `sequence_data.csv`: Added `Channel No` as the primary key column (first column).
- `core/csv_override.py`: Refactored `load_st_values()` and `list_st_numbers()` to natively parse the new channel-based format while gracefully supporting the legacy element-based format.
- `ui/analysis/analysis_run_job5.py`: Updated the `_on_export` CSV writing routine to export data strictly ordered and keyed by `Channel No`.

**Why:**
Relying on element names as primary identifiers can cause issues if element names change or if multiple channels refer to variations of the same element. Re-orienting the logic around physical channel numbers tightly aligns the software's data structures with the physical architecture of the hardware.

## 2. High Voltage (HV) HEX Address System

**What:** 
Implemented a dedicated High Voltage controller module to process UART commands properly with exact hexadecimal formatting.

**Where:**
- `core/hv_controller.py` **[NEW]**: Created a robust controller dedicated to sending proper `O,A,<hex_addr>` commands over UART for HV channels.
- `core/sequence_engine.py` & `core/attenuator_programmer.py`: Added explicit inline documentation defending the Python format `{:02X}` syntax.
- *Note on UI Hook:* The integration hook inside `ui/main_window.py` (which connected the UI's HV toggle button to this controller) was previously implemented but appears to have been recently reverted in your editor, reverting it back to a software simulation toggle.

**Why:**
Channels 10–15 mathematically map to hex addresses `09–0E`. There was an issue where hex values `0A` through `0E` (containing characters A-F) could be mistakenly identified as invalid if processed by decimal-only validators. The new controller strictly isolates and handles these values properly as strings.

## 3. Display Form & Frame Resizability

**What:**
Modified the application's root window to allow the user to resize and maximize the desktop application interface.

**Where:**
- `ui/main_window.py` *(Note: This change appears to have been recently reverted back to `setFixedSize(1100, 680)` in your editor)*.

**Why:**
The application interface was hardcoded using `self.setFixedSize()`, preventing any manual adjustment. Migrating to `self.setMinimumSize()` allows the inner layouts to dynamically stretch/shrink natively using Qt layout properties, granting better accessibility across different monitor resolutions.
