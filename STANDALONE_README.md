# Standalone Industrial Control Builder

This desktop entry point launches a separate control-builder window without
opening SpectraSoft. It reuses the provider, document, and analysis packages,
and targets the supplied ATmega2560 port firmware without modifying its `.ino`
source.

## Run on Windows

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe standalone_main.py
```

Install project dependencies first if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Groq configuration uses `GROQ_API_KEY` and optional `GROQ_MODEL` from the
project-root `.env` file. Ollama can be selected in the app when its local
server and configured model are available.

## Generate code and artifacts

Open the **Generate Artifact** tab, choose a text-based output type, describe
what you want, optionally include the files selected in the control tab, and
select **Generate draft**. The result is editable before saving. Turn on
**Use the current preview as input when revising** to ask for a revision of the
displayed draft; otherwise each request starts as a new artifact. Saving
creates a new file and refuses to overwrite an existing one.

Supported outputs currently include Python, Arduino `.ino` drafts, C++ source
and headers, Markdown, JSON, CSV templates, SVG diagrams, and plain text. These
are generated as text files: the app does not run generated code, compile it,
or flash it. Review and test code separately before using it with hardware.
The providers return the artifact body as plain text, avoiding a second layer
of JSON escaping around source code.
The original supplied `.ino` remains unchanged. With Groq, prompts and any
included extracted file text are sent to Groq; Ollama can keep generation local
when a local server/model is installed.

## Hardware compatibility

Simulation and table analysis can be used independently of a connected board.
The standalone app's live serial path uses UART at 9600 baud and the supplied
firmware's existing commands: `O,<A|B>,<hex>` for outputs, `I` for an immediate
12-bit input read, and `T,<hex-ms>` for a firmware delay. `ADC12` in the app
requests the source-specific `7C`/`3C` trigger sequence and consumes its delayed
`D,<value>` response. The app does not build or flash firmware.

The supplied source defines Port A as 8 outputs, Port B as 7 outputs, and a
12-bit input assembled from digital pins. Port B's output bits are inverted by
the firmware. The app therefore exposes logical port values rather than
arbitrary GPIO configuration. Simulation is the default; live runs require an
explicit confirmation each time.
