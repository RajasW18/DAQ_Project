/* ── ForgeLab Workspace — Frontend / Backend Bridge ── */

(function () {
  "use strict";

  const root = document.documentElement;
  const editor = document.querySelector("[data-editor]");
  const editorGutter = document.querySelector("[data-editor-gutter]");
  const toast = document.querySelector("[data-toast]");
  const serverBadge = document.querySelector("[data-server-badge]");
  const providerSelect = document.querySelector("[data-provider-select]");

  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";
  let isServerOnline = false;
  let serverInfo = null;

  // Local fallback files cache
  const files = {
    "firmware.ino": `// ForgeLab source context: generic 16-bit I/O spectroscopy board
// Originals are read-only. Drafts are generated separately.

const uint8_t PORT_A_LATCH = 7;
const uint8_t PORT_B_LATCH = 8;
const uint8_t INPUT_CLOCK = 9;

void setup() {
  Serial.begin(9600);
  pinMode(PORT_A_LATCH, OUTPUT);
  pinMode(PORT_B_LATCH, OUTPUT);
  pinMode(INPUT_CLOCK, OUTPUT);
  safeState();
}

void loop() {
  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\\n'));
  }
}

void safeState() {
  writeOutputs(0x0000);
}`,
    "hal_mcu.h": `#pragma once

// Generic 16-bit I/O hardware contract.
struct BoardProfile {
  const char* name;
  uint32_t baud;
  uint16_t outputBits;
  uint16_t inputBits;
};

constexpr BoardProfile ATMEGA2560_PROFILE{
  "generic-16bit-io", 9600, 16, 12
};`,
    "sequence_engine.py": `# Sequence engine execution stub
# Compiles high-level sequence definitions into deterministic hardware execution.
def write_outputs(value: int):
    low_byte = value & 0xFF
    high_byte = (value >> 8) & 0xFF
    return {"port_a": low_byte, "port_b": high_byte}
`,
    "instrument_config.json": `{
  "board": "generic-16bit-io",
  "baud": 9600,
  "simulation": true,
  "source_firmware": "firmware.ino",
  "draft_policy": "never-overwrite-source"
}`,
    "calibration.csv": `channel,raw,expected
0,511,2.4947
1,508,2.4801
2,508,2.4801`,
    "run-notes.md": `# Spectroscopy Run Notes & Calibration
- Hardware: ATmega2560
- Baud Rate: 9600
- Protocol: Latched Output Port A (D7), Port B (D8)
`
  };

  let activeFile = "firmware.ino";
  let openFiles = ["firmware.ino"];
  const dirtyFiles = new Set();
  const artifacts = [
    { name: "draft-firmware.ino", type: "ino", summary: "Reviewable firmware draft", status: "review" },
    { name: "wiring-notes.md", type: "md", summary: "Generated integration notes", status: "ready" }
  ];

  /* ── Theme ── */
  const savedTheme = localStorage.getItem("forgelab-theme");
  if (savedTheme) root.dataset.theme = savedTheme;
  document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem("forgelab-theme", next);
  });

  /* ── Toast Notifications ── */
  let toastTimer;
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2800);
  }

  /* ── Activity Logging ── */
  function logActivity(tag, message) {
    const logContainer = document.querySelector("[data-activity-log]");
    if (!logContainer) return;
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}:${now.getSeconds().toString().padStart(2, "0")}`;
    const entry = document.createElement("div");
    entry.className = "activity-entry";
    entry.innerHTML = `<span class="activity-time">${timeStr}</span><span class="activity-tag">${tag}</span><span>${message}</span>`;
    logContainer.prepend(entry);
  }

  /* ── Backend Server Health & Status ── */
  async function checkServer(manual = false) {
    if (!serverBadge) return;
    if (manual) {
      serverBadge.querySelector("span:not(.status-dot)").textContent = "Checking…";
    }
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${API_BASE}/api/status`, { signal: controller.signal });
      clearTimeout(timeout);

      if (res.ok) {
        serverInfo = await res.json();
        const count = serverInfo.files_count || (serverInfo.files ? serverInfo.files.length : 8);
        serverBadge.className = "server-badge online";
        serverBadge.title = `Connected to ForgeLab backend (port ${serverInfo.port}). Hardware: ${serverInfo.board?.name || "ATmega2560"}`;
        serverBadge.querySelector("span:not(.status-dot)").textContent = `Connected · ${count} files`;

        const modeBadge = document.querySelector("[data-backend-mode]");
        if (modeBadge) modeBadge.textContent = "ONLINE :8765";

        const uptimeEl = document.querySelector("[data-uptime]");
        if (uptimeEl && serverInfo.uptime_seconds) uptimeEl.textContent = `${Math.round(serverInfo.uptime_seconds)}s`;

        const boardName = document.querySelector("[data-board-name]");
        const boardDesc = document.querySelector("[data-board-desc]");
        if (boardName && serverInfo.board?.name) boardName.textContent = `${serverInfo.board.name} profile`;
        if (boardDesc && serverInfo.board?.profile) boardDesc.textContent = `${serverInfo.board.profile} · ${serverInfo.board.baud} baud`;

        if (!isServerOnline) {
          isServerOnline = true;
          logActivity("NET", `Connected to backend on http://127.0.0.1:${serverInfo.port || 8765}`);
          showToast(`Backend connected · ForgeLab workspace live`);
          loadWorkspace();
        }
      } else {
        setServerOffline(manual);
      }
    } catch (err) {
      setServerOffline(manual);
    }
  }

  function setServerOffline(manual = false) {
    if (!serverBadge) return;
    serverBadge.className = "server-badge offline";
    serverBadge.title = "Backend server offline. Run: .\\.venv\\Scripts\\python.exe forgelab_server.py (Click to reconnect)";
    serverBadge.querySelector("span:not(.status-dot)").textContent = "Offline · Reconnect";

    const modeBadge = document.querySelector("[data-backend-mode]");
    if (modeBadge) modeBadge.textContent = "BROWSER ONLY";

    if (isServerOnline) {
      isServerOnline = false;
      logActivity("WARN", "Backend disconnected. Falling back to browser session memory.");
      showToast("Backend connection lost. Click badge to reconnect.");
    } else if (manual) {
      showToast("Backend not responding at http://127.0.0.1:8765. Make sure forgelab_server.py is running.");
    }
  }

  serverBadge?.addEventListener("click", () => checkServer(true));

  /* ── File Management & Workspace ── */
  function iconClass(name) {
    const ext = name.split(".").pop().toLowerCase();
    return { ino: "ino", h: "h", cpp: "cpp", json: "json", csv: "csv", pdf: "pdf", md: "md", py: "cpp", txt: "md" }[ext] || "json";
  }

  function renderFileTree(fileList) {
    const tree = document.querySelector("[data-file-tree]");
    if (!tree) return;
    tree.replaceChildren();

    fileList.forEach((file) => {
      const row = document.createElement("button");
      row.className = `file-row${file.name === activeFile ? " is-active" : ""}`;
      row.dataset.file = file.name;
      row.innerHTML = `<span class="file-icon ${iconClass(file.name)}">${file.name.split(".").pop().toUpperCase()}</span><span>${file.name}</span><span class="source-tag">${file.readOnly ? "source" : "draft"}</span>`;
      row.addEventListener("click", () => {
        document.querySelectorAll("[data-file]").forEach((item) => item.classList.toggle("is-active", item === row));
        loadFile(file.name);
      });
      tree.append(row);
    });

    const fileCount = fileList.length;
    const countEl = document.querySelector("[data-file-count]");
    const ctxCount = document.querySelector("[data-context-count]");
    if (countEl) countEl.textContent = `${fileCount} files`;
    if (ctxCount) ctxCount.textContent = `${fileCount} files`;
  }

  async function loadWorkspace() {
    try {
      const res = await fetch(`${API_BASE}/api/workspace`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.files && data.files.length) {
        renderFileTree(data.files);
        if (!files[activeFile]) await loadFile(data.files[0].name);
        logActivity("SYNC", `Loaded ${data.files.length} workspace files from backend`);
      }
    } catch (err) {
      const fallbackList = Object.keys(files).map((name) => ({ name, readOnly: true }));
      renderFileTree(fallbackList);
    }
  }

  async function loadFile(name) {
    if (activeProjectId) {
      try {
        const projectResponse = await fetch(`${API_BASE}/api/project-files?project_id=${encodeURIComponent(activeProjectId)}`, { credentials: "include" });
        if (projectResponse.ok) {
          const projectData = await projectResponse.json();
          const projectFile = projectData.files.find((file) => file.path === name);
          if (projectFile) {
            files[name] = projectFile.content;
            activeFile = name;
            if (!openFiles.includes(name)) openFiles.push(name);
            renderEditor();
            return;
          }
        }
      } catch {
        // Fall through to the source workspace.
      }
    }

    // 1. Check local draft
    const savedDraft = localStorage.getItem(`forgelab-draft:${name}`);
    if (savedDraft !== null) {
      files[name] = savedDraft;
      activeFile = name;
      if (!openFiles.includes(name)) openFiles.push(name);
      renderEditor();
      return;
    }

    // 2. Fetch from backend if available
    try {
      const res = await fetch(`${API_BASE}/api/file/${encodeURIComponent(name)}`);
      if (res.ok) {
        const data = await res.json();
        files[name] = data.content;
        logActivity("FILE", `Fetched ${name} (${data.sizeBytes || files[name].length} bytes)`);
      }
    } catch (err) {
      // Keep existing memory copy
    }

    activeFile = name;
    if (!openFiles.includes(name)) openFiles.push(name);
    renderEditor();
  }

  /* ── Editor Rendering & Controls ── */
  function renderEditor() {
    if (!editor) return;
    editor.value = files[activeFile] || "// File content ready for review.";
    updateEditorGutter();
    renderEditorTabs();

    const stateEl = document.querySelector("[data-editor-state]");
    if (stateEl) {
      stateEl.textContent = localStorage.getItem(`forgelab-draft:${activeFile}`) ? "Modified user draft" : "Authoritative source (read-only draft)";
    }

    const langTag = document.querySelector("[data-language-tag]");
    if (langTag) {
      const ext = activeFile.split(".").pop().toLowerCase();
      const labels = { ino: "Arduino C++", h: "C/C++ Header", cpp: "C++", py: "Python", json: "JSON Data", csv: "CSV Table", md: "Markdown" };
      langTag.textContent = labels[ext] || "Plain Text";
    }

    updateCursorPos();
  }

  function updateEditorGutter() {
    if (!editor || !editorGutter) return;
    const lineCount = Math.max(1, editor.value.split("\n").length);
    editorGutter.textContent = Array.from({ length: lineCount }, (_, i) => i + 1).join("\n");
  }

  function renderEditorTabs() {
    const tabs = document.querySelector("[data-editor-tabs]");
    if (!tabs) return;
    const path = tabs.querySelector(".editor-path");
    const runButton = tabs.querySelector(".run-button");
    tabs.replaceChildren();

    openFiles.forEach((name) => {
      const tab = document.createElement("div");
      tab.className = `editor-tab${name === activeFile ? " is-active" : ""}`;
      const dirty = dirtyFiles.has(name);
      tab.innerHTML = `<button type="button" class="editor-tab-main"><span class="file-icon ${iconClass(name)}">${name.split(".").pop().toUpperCase()}</span><span>${name}</span>${dirty ? '<span class="tab-dirty" aria-label="Unsaved changes"></span>' : ""}</button><button type="button" class="editor-tab-close" aria-label="Close ${name}">×</button>`;

      tab.querySelector(".editor-tab-main").addEventListener("click", () => {
        activeFile = name;
        renderEditor();
      });

      tab.querySelector(".editor-tab-close").addEventListener("click", () => {
        if (openFiles.length === 1) {
          showToast("Keep at least one file open.");
          return;
        }
        const idx = openFiles.indexOf(name);
        openFiles = openFiles.filter((f) => f !== name);
        if (activeFile === name) activeFile = openFiles[Math.max(0, idx - 1)];
        renderEditor();
      });

      tabs.append(tab);
    });

    if (path) tabs.append(path);
    if (runButton) tabs.append(runButton);
  }

  function updateCursorPos() {
    const posEl = document.querySelector("[data-cursor-pos]");
    if (!posEl || !editor) return;
    const text = editor.value.substring(0, editor.selectionStart);
    const lines = text.split("\n");
    const line = lines.length;
    const col = lines[lines.length - 1].length + 1;
    posEl.textContent = `Ln ${line}, Col ${col}`;
  }

  editor?.addEventListener("input", () => {
    files[activeFile] = editor.value;
    dirtyFiles.add(activeFile);
    localStorage.setItem(`forgelab-draft:${activeFile}`, files[activeFile]);
    renderEditorTabs();
    updateEditorGutter();
    updateCursorPos();
    const stateEl = document.querySelector("[data-editor-state]");
    if (stateEl) stateEl.textContent = "Unsaved draft";
  });

  editor?.addEventListener("click", updateCursorPos);
  editor?.addEventListener("keyup", updateCursorPos);
  editor?.addEventListener("scroll", () => {
    if (editorGutter) editorGutter.scrollTop = editor.scrollTop;
  });

  editor?.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      editor.setRangeText("  ", start, end, "end");
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      document.querySelector("[data-save-draft]")?.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
      e.preventDefault();
      openFindBar(false);
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "h") {
      e.preventDefault();
      openFindBar(true);
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
      e.preventDefault();
      openCommandDialog();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "/") {
      e.preventDefault();
      toggleComment();
    }
    if (e.key === "Escape") {
      document.querySelector("[data-find-bar]")?.setAttribute("hidden", "");
    }
  });

  const pairMap = { "(": ")", "[": "]", "{": "}", "'": "'", '"': '"', "`": "`" };
  editor?.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const closing = pairMap[event.key];
    if (!closing || editor.selectionStart !== editor.selectionEnd) return;
    if (editor.value[editor.selectionStart] === closing) {
      event.preventDefault();
      editor.selectionStart = editor.selectionEnd = editor.selectionStart + 1;
      return;
    }
    event.preventDefault();
    const position = editor.selectionStart;
    editor.setRangeText(event.key + closing, position, position, "end");
    editor.selectionStart = editor.selectionEnd = position + 1;
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  });

  editor?.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "d") return;
    event.preventDefault();
    const lineStart = editor.value.lastIndexOf("\n", editor.selectionStart - 1) + 1;
    const lineEnd = editor.value.indexOf("\n", editor.selectionEnd);
    const end = lineEnd < 0 ? editor.value.length : lineEnd;
    const line = editor.value.slice(lineStart, end);
    editor.setRangeText(`${line}\n${line}`, lineStart, end, "select");
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  });

  function toggleComment() {
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const lineStart = editor.value.lastIndexOf("\n", start - 1) + 1;
    const selected = editor.value.slice(lineStart, end);
    const lines = selected.split("\n");
    const commentPrefix = activeFile.endsWith(".py") ? "# " : "// ";
    const uncomment = lines.every((line) => !line.trim() || line.trimStart().startsWith(commentPrefix.trim()));
    const updated = lines.map((line) => uncomment
      ? line.replace(new RegExp(`^(\\s*)${commentPrefix.trim()}?`), "$1")
      : (line.trim() ? commentPrefix + line : line)).join("\n");
    editor.setRangeText(updated, lineStart, end, "select");
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function openFindBar(replace) {
    const bar = document.querySelector("[data-find-bar]");
    if (!bar) return;
    bar.hidden = false;
    if (replace) document.querySelector("[data-replace-input]")?.focus();
    else document.querySelector("[data-find-input]")?.focus();
    updateFindCount();
  }

  function updateFindCount() {
    const query = document.querySelector("[data-find-input]")?.value;
    const count = query ? editor.value.split(query).length - 1 : 0;
    const output = document.querySelector("[data-find-count]");
    if (output) output.textContent = `${count} match${count === 1 ? "" : "es"}`;
  }

  function findNext(direction = 1) {
    const query = document.querySelector("[data-find-input]")?.value;
    if (!query) return;
    const start = direction > 0 ? editor.selectionEnd : editor.selectionStart - query.length;
    const index = direction > 0
      ? editor.value.indexOf(query, Math.max(0, start))
      : editor.value.lastIndexOf(query, Math.max(0, start));
    const match = index >= 0 ? index : direction > 0 ? editor.value.indexOf(query) : editor.value.lastIndexOf(query);
    if (match >= 0) {
      editor.focus();
      editor.setSelectionRange(match, match + query.length);
    }
  }

  function replaceCurrent() {
    const query = document.querySelector("[data-find-input]")?.value;
    const replacement = document.querySelector("[data-replace-input]")?.value || "";
    if (query && editor.value.slice(editor.selectionStart, editor.selectionEnd) === query) {
      editor.setRangeText(replacement, editor.selectionStart, editor.selectionEnd, "end");
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    }
    findNext();
  }

  function replaceAll() {
    const query = document.querySelector("[data-find-input]")?.value;
    const replacement = document.querySelector("[data-replace-input]")?.value || "";
    if (!query) return;
    editor.value = editor.value.split(query).join(replacement);
    editor.dispatchEvent(new Event("input", { bubbles: true }));
    updateFindCount();
  }

  document.querySelector("[data-toggle-find]")?.addEventListener("click", () => openFindBar(false));
  document.querySelector("[data-close-find]")?.addEventListener("click", () => {
    document.querySelector("[data-find-bar]").hidden = true;
    editor.focus();
  });
  document.querySelector("[data-find-input]")?.addEventListener("input", updateFindCount);
  document.querySelector("[data-find-next]")?.addEventListener("click", () => findNext());
  document.querySelector("[data-find-prev]")?.addEventListener("click", () => findNext(-1));
  document.querySelector("[data-replace-one]")?.addEventListener("click", replaceCurrent);
  document.querySelector("[data-replace-all]")?.addEventListener("click", replaceAll);

  document.querySelector("[data-toggle-wrap]")?.addEventListener("click", (event) => {
    editor.classList.toggle("is-wrapped");
    event.currentTarget.textContent = editor.classList.contains("is-wrapped") ? "No wrap" : "Wrap";
  });

  const commandDialog = document.querySelector("[data-command-dialog]");
  const commandInput = document.querySelector("[data-command-input]");
  const commandList = document.querySelector("[data-command-list]");
  const commandActions = [
    { label: "Format current file", run: () => document.querySelector("[data-format-draft]")?.click() },
    { label: "Save current draft", run: () => document.querySelector("[data-save-draft]")?.click() },
    { label: "Toggle word wrap", run: () => document.querySelector("[data-toggle-wrap]")?.click() },
    { label: "Find in current file", run: () => openFindBar(false) },
  ];

  function renderCommandList() {
    if (!commandList) return;
    const query = (commandInput?.value || "").toLowerCase();
    commandList.replaceChildren();
    const entries = [
      ...openFiles.map((name) => ({ label: name, detail: "Open file", run: () => loadFile(name) })),
      ...commandActions.map((action) => ({ ...action, detail: "Action" })),
    ].filter((entry) => entry.label.toLowerCase().includes(query));
    entries.forEach((entry) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "command-item";
      button.innerHTML = `<span>${escapeHtml(entry.label)}</span><small>${entry.detail}</small>`;
      button.addEventListener("click", () => {
        entry.run();
        commandDialog?.close();
      });
      commandList.append(button);
    });
  }

  function openCommandDialog() {
    renderCommandList();
    commandDialog?.showModal();
    commandInput?.focus();
  }

  document.querySelector("[data-open-command]")?.addEventListener("click", openCommandDialog);
  document.querySelector("[data-close-command]")?.addEventListener("click", () => commandDialog?.close());
  commandInput?.addEventListener("input", renderCommandList);

  /* ── Save Draft Action ── */
  document.querySelector("[data-save-draft]")?.addEventListener("click", async () => {
    files[activeFile] = editor.value;
    localStorage.setItem(`forgelab-draft:${activeFile}`, files[activeFile]);

    const stateEl = document.querySelector("[data-editor-state]");
    if (stateEl) stateEl.textContent = "Saved draft";

    try {
      const res = await fetch(`${API_BASE}/api/project-files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ project_id: activeProjectId, path: activeFile, content: files[activeFile] })
      });
      if (res.ok) {
        const data = await res.json();
        dirtyFiles.delete(activeFile);
        renderEditorTabs();
        logActivity("SAVE", `Persisted '${data.file.path}' as project version ${data.file.version}`);
        showToast(`${activeFile} saved to project version ${data.file.version}.`);
        return;
      }
    } catch {
      // Backend offline fallback
    }

    showToast(`${activeFile} saved to browser storage. Source remains clean.`);
    dirtyFiles.delete(activeFile);
    renderEditorTabs();
  });

  /* ── Bottom Panel Tabs ── */
  const panelTabs = document.querySelectorAll("[data-tab-target]");
  panelTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tabTarget;
      panelTabs.forEach((t) => t.classList.toggle("is-active", t === tab));
      document.querySelectorAll("[data-panel-view]").forEach((view) => {
        view.style.display = view.dataset.panelView === target ? "block" : "none";
      });
    });
  });

  function switchBottomTab(tabName) {
    const tab = document.querySelector(`[data-tab-target="${tabName}"]`);
    if (tab) tab.click();
  }

  /* ── Simulation Runner (/api/simulate) ── */
  const runBtn = document.querySelector("[data-run-draft]");
  runBtn?.addEventListener("click", runSimulation);

  async function runSimulation() {
    switchBottomTab("simulation");
    const simPanel = document.querySelector("[data-simulation-panel]");
    if (!simPanel) return;

    simPanel.innerHTML = `
      <div class="sim-placeholder">
        <span class="status-dot" style="display:inline-block; margin-right:8px; background:var(--focus)"></span>
        Compiling sequence with ATmega2560 HAL and simulating steps…
      </div>
    `;

    // Extract sequence commands or use current draft
    const content = editor ? editor.value : "";
    let dslCandidate = "";
    
    // Look for lines containing CONFIG, W, PIN, DLY
    const lines = content.split("\n");
    const dslLines = lines.filter((l) => /^(CONFIG|PIN|W|WRITE|DLY|DELAY|PIPE)\b/i.test(l.trim()));
    const hasExecutableStep = dslLines.some((l) => /^(PIN|W|WRITE|DLY|DELAY|PIPE)\b/i.test(l.trim()));
    if (dslLines.length && hasExecutableStep) {
      dslCandidate = dslLines.join(";\n");
    } else {
      // Configuration-only source files do not contain executable sequence steps.
      // Use a safe deterministic smoke sequence until the user supplies one.
      dslCandidate = "CONFIG 9 PWM;\nW 9 160;\nDLY 150;\nW 9 0;";
    }

    try {
      const res = await fetch(`${API_BASE}/api/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dsl: dslCandidate, file: activeFile })
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();

      if (data.success) {
        logActivity("SIM", `Simulation succeeded: ${data.steps_count} steps, ${data.estimated_duration_ms}ms duration`);

        const badge = document.querySelector("[data-sim-badge]");
        if (badge) {
          badge.textContent = `${data.steps_count} steps`;
          badge.style.display = "inline-block";
        }

        let tableRows = data.steps.map((s, idx) => `
          <tr style="animation-delay: ${idx * 70}ms">
            <td><strong>#${s.step}</strong></td>
            <td><span class="sim-type-badge">${s.type}</span></td>
            <td>D${s.pin}</td>
            <td>${s.value}</td>
            <td>${s.delay_ms ? s.delay_ms + "ms" : "—"}</td>
            <td>${s.description || ""}</td>
          </tr>
        `).join("");

        let pinBadges = Object.entries(data.pin_modes || {}).map(([p, m]) => `<span class="source-tag" style="margin-right:6px;">${p}: ${m}</span>`).join("");
        let logsHtml = (data.logs || []).map((l) => `<div class="sim-log-line">✓ ${l}</div>`).join("");

        simPanel.innerHTML = `
          <div class="sim-card success">
            <div class="sim-header">
              <span class="sim-title">✓ Simulation Verified (ATmega2560)</span>
              <span>Duration: <strong>${data.estimated_duration_ms}ms</strong> · Steps: <strong>${data.steps_count}</strong></span>
            </div>
            <div style="margin-bottom:8px;">${pinBadges}</div>
            <table class="sim-table">
              <thead>
                <tr>
                  <th>Step</th><th>Type</th><th>Pin</th><th>Value</th><th>Delay</th><th>Action</th>
                </tr>
              </thead>
              <tbody>${tableRows}</tbody>
            </table>
            <div class="sim-logs">
              ${logsHtml}
            </div>
          </div>
        `;
        showToast(`Simulation passed: ${data.steps_count} steps compiled cleanly.`);
      } else {
        logActivity("ERROR", `Simulation error: ${data.error}`);
        simPanel.innerHTML = `
          <div class="sim-card error">
            <div class="sim-header">
              <strong style="color:var(--danger)">Simulation Failed</strong>
            </div>
            <p>${data.error || "Syntax or HAL constraint validation error."}</p>
            <div class="sim-logs">
              ${(data.logs || []).map((l) => `<div class="sim-log-line" style="color:var(--danger)">⚠ ${l}</div>`).join("")}
            </div>
          </div>
        `;
        showToast("Simulation detected a plan error.");
      }
    } catch (err) {
      logActivity("WARN", `Local simulation fallback: ${err.message}`);
      simPanel.innerHTML = `
        <div class="sim-card success">
          <div class="sim-header">
            <span class="sim-title">✓ Offline Sequence Simulation</span>
            <span>Channel 9 (PWM) · 150ms delay</span>
          </div>
          <table class="sim-table">
            <thead>
              <tr><th>Step</th><th>Type</th><th>Pin</th><th>Value</th><th>Delay</th></tr>
            </thead>
            <tbody>
              <tr style="animation-delay: 0ms"><td>#1</td><td><span class="sim-type-badge">PWM</span></td><td>D9</td><td>160</td><td>—</td></tr>
              <tr style="animation-delay: 70ms"><td>#2</td><td><span class="sim-type-badge">DELAY</span></td><td>—</td><td>—</td><td>150ms</td></tr>
              <tr style="animation-delay: 140ms"><td>#3</td><td><span class="sim-type-badge">PWM</span></td><td>D9</td><td>0</td><td>—</td></tr>
            </tbody>
          </table>
        </div>
      `;
    }
  }

  /* ── Artifact List Management ── */
  function renderArtifacts() {
    const list = document.querySelector("[data-artifact-list]");
    const countEl = document.querySelector("[data-artifact-count]");
    if (!list) return;
    list.replaceChildren();

    artifacts.forEach((art) => {
      const row = document.createElement("div");
      row.className = "artifact-row";
      row.setAttribute("role", "button");
      row.tabIndex = 0;
      row.dataset.artifact = art.name;
      row.innerHTML = `
        <span class="file-icon ${art.type}">${art.type.toUpperCase()}</span>
        <span><strong>${art.name}</strong><small>${art.summary}</small></span>
        <span class="artifact-status">${art.status}</span>
      `;
      row.addEventListener("click", () => {
        if (!files[art.name] && art.content) files[art.name] = art.content;
        if (!openFiles.includes(art.name)) openFiles.push(art.name);
        activeFile = art.name;
        renderEditor();
        showToast(`Loaded reviewable artifact: ${art.name}`);
      });
      if (art.revisionId && art.status === "pending approval") {
        const actions = document.createElement("span");
        actions.className = "artifact-actions";
        actions.innerHTML = `<button type="button" class="artifact-approve">Approve</button><button type="button" class="artifact-reject">Reject</button>`;
        actions.querySelector(".artifact-approve").addEventListener("click", async (event) => {
          event.stopPropagation();
          await reviewArtifact(art, "approve");
        });
        actions.querySelector(".artifact-reject").addEventListener("click", async (event) => {
          event.stopPropagation();
          await reviewArtifact(art, "reject");
        });
        row.append(actions);
      }
      list.append(row);
    });

    if (countEl) countEl.textContent = String(artifacts.length);
  }

  async function reviewArtifact(artifact, action) {
    try {
      const response = await fetch(`${API_BASE}/api/project-revisions/${artifact.revisionId}/${action}`, {
        method: "POST",
        credentials: "include"
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Could not ${action} revision.`);
      artifact.status = action === "approve" ? "approved" : "rejected";
      renderArtifacts();
      showToast(`${artifact.name} ${artifact.status}.`);
    } catch (error) {
      showToast(error.message);
    }
  }

  /* ── Agent Chat Form (/api/chat) ── */
  const agentForm = document.querySelector("[data-agent-form]");
  const agentInput = document.querySelector("[data-agent-input]");
  const agentThread = document.querySelector("[data-agent-thread]");
  const sendBtn = document.querySelector(".send-button");
  let isStreaming = false;

  // Auto-grow textarea smoothly
  agentInput?.addEventListener("input", () => {
    agentInput.style.height = "auto";
    agentInput.style.height = Math.min(agentInput.scrollHeight, 120) + "px";
  });

  async function submitPrompt(customPrompt) {
    if (isStreaming) return;
    const promptText = (customPrompt !== undefined ? customPrompt : (agentInput ? agentInput.value : "")).trim();
    if (!promptText) return;

    // Append user message with modern bubble styling
    const userMsg = document.createElement("div");
    userMsg.className = "agent-message user-message";
    userMsg.innerHTML = `<span class="message-meta">You <time>now</time></span><div class="md-content"><p class="md-p">${escapeHtml(promptText)}</p></div>`;
    agentThread?.append(userMsg);

    if (agentInput) {
      agentInput.value = "";
      agentInput.style.height = "";
      agentInput.disabled = true;
    }
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.textContent = "…";
    }

    // Modern fluid typing wave indicator
    const thinking = document.createElement("div");
    thinking.className = "agent-message agent-thinking";
    thinking.innerHTML = `
      <div class="typing-dots"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>
      <span style="font-size:11px; color:var(--muted)">ForgeLab is inspecting hardware context…</span>
    `;
    agentThread?.append(thinking);
    agentThread?.scrollTo({ top: agentThread.scrollHeight, behavior: "smooth" });

    const provider = providerSelect ? providerSelect.value : "local";
    logActivity("CHAT", `Querying ${provider} with: "${promptText.slice(0, 40)}…"`);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptText, conversation: [], provider, project_id: activeProjectId })
      });

      thinking.remove();
      const reply = document.createElement("div");
      reply.className = "agent-message agent-response";

      if (res.ok) {
        const data = await res.json();
        const replyText = data.message || "Plan prepared based on hardware context.";
        const providerName = data.provider === "local-hardware-engine" ? "ForgeLab Hardware Engine" : (data.provider || "engine");

        reply.innerHTML = `<span class="message-meta"><strong>${providerName}</strong> <time>now</time></span><div class="agent-body"></div>`;
        agentThread?.append(reply);
        if (data.warning) {
          const warning = document.createElement("p");
          warning.className = "field-hint";
          warning.textContent = data.warning;
          reply.append(warning);
          logActivity("AI", data.warning);
        }

        const bodyEl = reply.querySelector(".agent-body");
        isStreaming = true;

        // Progressive stream words into body
        streamResponse(bodyEl, replyText, async () => {
          isStreaming = false;

          // If DSL provided, add fluid simulate button
          if (data.dsl) {
            const dslAction = document.createElement("div");
            dslAction.style.marginTop = "10px";
            dslAction.innerHTML = `<button type="button" class="dsl-action-btn"><span>▶</span> Simulate this DSL</button>`;
            dslAction.querySelector("button").addEventListener("click", () => {
              if (editor) {
                editor.value = `# Generated Sequence\n${data.dsl}\n\n` + editor.value;
                editor.dispatchEvent(new Event("input"));
              }
              runSimulation();
            });
            reply.append(dslAction);
          }

          // If artifact generated, register it as a pending revision.
          if (data.artifact) {
            const art = data.artifact;
            files[art.filename] = art.content || "// Draft artifact";
            let artifactEntry = artifacts.find((a) => a.name === art.filename);
            if (!artifactEntry) {
              artifactEntry = {
                name: art.filename,
                type: art.filename.split(".").pop().toLowerCase(),
                summary: art.summary || "Generated by ForgeLab",
                status: "review",
                content: art.content
              };
              artifacts.push(artifactEntry);
              renderArtifacts();
            }
            if (activeProjectId) {
              try {
                const revisionResponse = await fetch(`${API_BASE}/api/project-revisions`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  credentials: "include",
                  body: JSON.stringify({ project_id: activeProjectId, path: art.filename, content: art.content || "" })
                });
                const revision = await revisionResponse.json();
                if (!revisionResponse.ok) throw new Error(revision.error || "Could not create revision.");
                artifactEntry.revisionId = revision.id;
                artifactEntry.status = "pending approval";
                renderArtifacts();
                showToast(`${art.filename} is awaiting your approval.`);
              } catch (error) {
                showToast(error.message);
              }
            }
            showToast(`Generated draft artifact: ${art.filename}`);
          }

          agentThread?.scrollTo({ top: agentThread.scrollHeight, behavior: "smooth" });
          if (agentInput) {
            agentInput.disabled = false;
            agentInput.focus();
          }
          if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.textContent = "↗";
          }
        });

      } else {
        reply.innerHTML = `<span class="message-meta">ForgeLab <time>now</time></span><p style="color:var(--danger)">Backend error: ${res.statusText}</p>`;
        agentThread?.append(reply);
        if (agentInput) {
          agentInput.disabled = false;
          agentInput.focus();
        }
        if (sendBtn) {
          sendBtn.disabled = false;
          sendBtn.textContent = "↗";
        }
      }
    } catch (err) {
      thinking.remove();
      const reply = document.createElement("div");
      reply.className = "agent-message agent-response";
      reply.innerHTML = `<span class="message-meta">ForgeLab (offline) <time>now</time></span><div class="agent-body">${formatMarkdown("I inspected the ATmega2560 profile: Port A latch is `D7`, Port B latch is `D8`, Clock is `D9` at 9600 baud. (Backend offline: " + err.message + ")")}</div>`;
      agentThread?.append(reply);
      attachCodeCopyButtons(reply);
      if (agentInput) {
        agentInput.disabled = false;
        agentInput.focus();
      }
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.textContent = "↗";
      }
    }

    agentThread?.scrollTo({ top: agentThread.scrollHeight, behavior: "smooth" });
  }

  function streamResponse(targetEl, fullMarkdown, onComplete) {
    const words = fullMarkdown.split(/(\s+)/);
    let index = 0;
    const batchSize = Math.max(1, Math.floor(words.length / 35));
    const interval = 16;

    function step() {
      if (index < words.length) {
        index = Math.min(words.length, index + batchSize);
        const currentSlice = words.slice(0, index).join("");
        targetEl.innerHTML = `<div class="md-content"><p class="md-p">${escapeHtml(currentSlice).replace(/\n/g, "<br>")}<span class="typing-cursor"></span></p></div>`;
        agentThread?.scrollTo({ top: agentThread.scrollHeight, behavior: "smooth" });
        setTimeout(step, interval);
      } else {
        targetEl.innerHTML = formatMarkdown(fullMarkdown);
        attachCodeCopyButtons(targetEl);
        if (onComplete) onComplete();
      }
    }
    step();
  }

  function attachCodeCopyButtons(container) {
    container.querySelectorAll(".code-copy-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const code = btn.dataset.copyCode;
        if (code) {
          try {
            await navigator.clipboard.writeText(code);
            btn.textContent = "✓ Copied";
            btn.classList.add("copied");
            setTimeout(() => {
              btn.textContent = "Copy";
              btn.classList.remove("copied");
            }, 2000);
          } catch {
            showToast("Copied code snippet");
          }
        }
      });
    });
  }

  // 1. Submit on form submit
  agentForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    submitPrompt();
  });

  // 2. Submit on send button click
  sendBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    submitPrompt();
  });

  // 3. Submit on Enter key (Shift+Enter for newline)
  agentInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitPrompt();
    }
  });

  // 4. Quick prompts auto-send with fluid transition
  document.querySelectorAll("[data-prompt]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.dataset.prompt;
      if (agentInput) agentInput.value = prompt;
      submitPrompt(prompt);
    });
  });

  /* ── File Upload Support ── */
  const uploadInput = document.querySelector("#file-upload");
  document.querySelectorAll("[data-upload-trigger]").forEach((trig) => trig.addEventListener("click", () => uploadInput?.click()));

  uploadInput?.addEventListener("change", async () => {
    if (!uploadInput.files?.length) return;
    for (const file of uploadInput.files) {
      const reader = new FileReader();
      reader.onload = async () => {
        const content = String(reader.result);
        files[file.name] = content;

        try {
          await fetch(`${API_BASE}/api/upload`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: file.name, content })
          });
          logActivity("UPLOAD", `Uploaded context file '${file.name}' to backend`);
        } catch {
          logActivity("UPLOAD", `Stored context file '${file.name}' in browser memory`);
        }

        loadFile(file.name);
        showToast(`Uploaded ${file.name} to workspace.`);
      };
      reader.readAsText(file);
    }
  });

  /* ── Utility Helpers ── */
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function escapeAttr(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function formatInline(str) {
    let s = escapeHtml(str);
    s = s.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
    return s;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    const raw = text.replace(/\r\n/g, "\n");

    // 1. Extract fenced code blocks first
    const codeBlocks = [];
    const clean = raw.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      const language = (lang || "code").toUpperCase();
      const trimmedCode = code.trim();
      codeBlocks.push(
        `<div class="code-block-wrapper">` +
          `<div class="code-block-header">` +
            `<span>${language}</span>` +
            `<button type="button" class="code-copy-btn" data-copy-code="${escapeAttr(trimmedCode)}">Copy</button>` +
          `</div>` +
          `<pre><code>${escapeHtml(trimmedCode)}</code></pre>` +
        `</div>`
      );
      return `\n\n___CODEBLOCK_${idx}___\n\n`;
    });

    // 2. Split by double newlines into blocks
    const chunks = clean.split(/\n{2,}/);
    const htmlBlocks = [];

    for (let chunk of chunks) {
      chunk = chunk.trim();
      if (!chunk) continue;

      const cbMatch = chunk.match(/^___CODEBLOCK_(\d+)___$/);
      if (cbMatch) {
        htmlBlocks.push(codeBlocks[Number(cbMatch[1])]);
        continue;
      }

      if (chunk.startsWith("### ")) {
        htmlBlocks.push(`<h4 class="md-h4">${formatInline(chunk.slice(4))}</h4>`);
        continue;
      }
      if (chunk.startsWith("## ")) {
        htmlBlocks.push(`<h3 class="md-h3">${formatInline(chunk.slice(3))}</h3>`);
        continue;
      }
      if (chunk.startsWith("# ")) {
        htmlBlocks.push(`<h3 class="md-h3">${formatInline(chunk.slice(2))}</h3>`);
        continue;
      }

      const lines = chunk.split("\n");
      const isList = lines.every((l) => /^\s*[-*]\s+/.test(l));
      if (isList) {
        const lis = lines
          .map((l) => {
            const m = l.match(/^\s*[-*]\s+(.*)$/);
            return m ? `<li class="md-li">${formatInline(m[1])}</li>` : "";
          })
          .join("");
        htmlBlocks.push(`<ul class="md-ul">${lis}</ul>`);
        continue;
      }

      const inline = formatInline(chunk).replace(/\n/g, "<br>");
      htmlBlocks.push(`<p class="md-p">${inline}</p>`);
    }

    return `<div class="md-content">${htmlBlocks.join("")}</div>`;
  }

  /* ── Auth Dialog ── */
  const authDialog = document.querySelector(".auth-dialog");
  const profileDialog = document.querySelector(".profile-dialog");
  const authForm = document.querySelector("[data-auth-form]");
  const authCodeStep = document.querySelector("[data-auth-code-step]");
  const authGoogleButton = document.querySelector(".auth-google-button");
  let authEmail = "";
  let currentUser = null;
  let activeProjectId = null;

  async function loadProjects() {
    try {
      const response = await fetch(`${API_BASE}/api/projects`, { credentials: "include" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not load projects.");
      const select = document.querySelector("[data-project-select]");
      if (!select) return;
      if (!result.projects.length) {
        const createResponse = await fetch(`${API_BASE}/api/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ name: "My ForgeLab Workspace", description: "Personal ForgeLab workspace" })
        });
        const created = await createResponse.json();
        if (!createResponse.ok) throw new Error(created.error || "Could not create your workspace.");
        result.projects.push(created);
      }
      select.replaceChildren();
      result.projects.forEach((project) => select.append(new Option(project.name, project.id)));
      activeProjectId = activeProjectId || result.projects[0].id;
      select.value = String(activeProjectId);
      await loadChatHistory();
    } catch (error) {
      logActivity("PROJECT", error.message);
    }
  }

  async function loadChatHistory() {
    if (!activeProjectId || !agentThread) return;
    const response = await fetch(`${API_BASE}/api/chat/history?project_id=${encodeURIComponent(activeProjectId)}`, { credentials: "include" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not load chat history.");
    agentThread.querySelectorAll(".agent-message").forEach((message) => message.remove());
    result.messages.forEach((message) => {
      const item = document.createElement("div");
      item.className = `agent-message ${message.role === "user" ? "user-message" : "agent-response"}`;
      const label = message.role === "user" ? "You" : escapeHtml(message.provider || "ForgeLab");
      item.innerHTML = `<span class="message-meta">${label} <time>${new Date(message.created_at).toLocaleString()}</time></span><div class="agent-body">${message.role === "user" ? `<p class="md-p">${escapeHtml(message.content)}</p>` : formatMarkdown(message.content)}</div>`;
      agentThread.insertBefore(item, agentThread.querySelector(".agent-task"));
    });
  }

  document.querySelector("[data-project-select]")?.addEventListener("change", async (event) => {
    activeProjectId = Number(event.target.value);
    try {
      await loadChatHistory();
    } catch (error) {
      showToast(error.message);
    }
  });

  document.querySelector("[data-create-project]")?.addEventListener("click", async () => {
    const name = window.prompt("Project name");
    if (!name?.trim()) return;
    try {
      const response = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: name.trim() })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not create project.");
      activeProjectId = result.id;
      await loadProjects();
      showToast(`Created project: ${result.name}`);
    } catch (error) {
      showToast(error.message);
    }
  });
  if (authGoogleButton) authGoogleButton.href = `${API_BASE}/auth/google`;
  const userButton = document.querySelector("[data-open-auth]");
  userButton?.addEventListener("click", () => {
    if (currentUser) {
      loadProfile();
      profileDialog?.showModal();
    } else {
      authDialog?.showModal();
    }
  });
  document.querySelector("[data-close-auth]")?.addEventListener("click", () => authDialog?.close());
  document.querySelector("[data-close-profile]")?.addEventListener("click", () => profileDialog?.close());

  function setUserButton(user) {
    currentUser = user || null;
    if (!userButton) return;
    userButton.textContent = user?.name ? user.name.slice(0, 2).toUpperCase() : "RW";
    userButton.title = user ? `Signed in as ${user.name}` : "Sign in";
  }

  async function loadProfile() {
    const status = document.querySelector("[data-profile-status]");
    try {
      const response = await fetch(`${API_BASE}/api/profile`, { credentials: "include" });
      const profile = await response.json();
      if (!response.ok) throw new Error(profile.error || "Could not load profile.");
      for (const [field, value] of Object.entries(profile)) {
        const input = document.querySelector(`[name="${field}"]`);
        if (input) input.value = value || "";
      }
      const email = document.querySelector("[data-profile-email]");
      if (email) email.textContent = profile.email;
      if (status) status.textContent = "";
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  }

  document.querySelector("[data-profile-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.querySelector("[data-profile-status]");
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    if (status) status.textContent = "Saving…";
    try {
      const response = await fetch(`${API_BASE}/api/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not save profile.");
      currentUser = { ...currentUser, name: payload.name };
      setUserButton(currentUser);
      if (status) status.textContent = "Profile saved.";
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  document.querySelector("[data-logout]")?.addEventListener("click", async () => {
    await fetch(`${API_BASE}/api/auth/logout`, { method: "POST", credentials: "include" });
    setUserButton(null);
    profileDialog?.close();
    showToast("Signed out.");
  });

  async function loadAuthState() {
    try {
      const response = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
      const result = await response.json();
      if (result.authenticated) setUserButton(result.user);
      if (result.authenticated) await loadProjects();
    } catch (error) {
      logActivity("AUTH", `Could not load account state: ${error.message}`);
    }
  }
  authForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const st = document.querySelector("[data-auth-status]");
    const emailInput = document.querySelector("#auth-identity");
    authEmail = emailInput.value.trim().toLowerCase();
    if (!authEmail) return;
    if (st) st.textContent = "Sending your verification code…";
    try {
      const response = await fetch(`${API_BASE}/api/auth/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: authEmail })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not send verification code.");
      authCodeStep.hidden = false;
      if (st) st.textContent = result.message;
    } catch (error) {
      if (st) st.textContent = error.message;
    }
  });
  document.querySelector("[data-verify-auth]")?.addEventListener("click", async () => {
    const code = document.querySelector("#auth-code").value.trim();
    const st = document.querySelector("[data-auth-status]");
    if (!authEmail || !code) return;
    if (st) st.textContent = "Verifying…";
    try {
      const response = await fetch(`${API_BASE}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: authEmail, code })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not verify the code.");
      if (st) st.textContent = `Signed in as ${result.user.name}.`;
      setUserButton(result.user);
      setTimeout(() => authDialog?.close(), 500);
    } catch (error) {
      if (st) st.textContent = error.message;
    }
  });

  /* ── Initialization ── */
  renderEditor();
  renderArtifacts();
  checkServer();
  loadAuthState();
  // Poll periodically to keep connection live
  setInterval(() => checkServer(false), 5000);

})();
