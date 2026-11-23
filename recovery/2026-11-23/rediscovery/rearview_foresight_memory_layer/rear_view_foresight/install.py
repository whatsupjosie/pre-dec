#!/usr/bin/env python3
"""
install.py
══════════
Rear View Foresight LLC — One-shot installer.

Run once. Everything wires itself in.

  python3 install.py

What this does:
  1. Finds your Code Collector project automatically
  2. Copies thinking_context/ into it (PubCast AI memory layer)
  3. Copies memory_layer/extractors/ into it (Claude session extractor)
  4. Patches main.js  — adds 3 new routes (non-destructive)
  5. Patches background.js — adds 2 new message handlers (non-destructive)
  6. Copies claude_scraper.js into your extension folder
  7. Patches manifest.json — registers claude_scraper.js (non-destructive)
  8. Creates data/ directory for memory snapshots
  9. Writes ~/.code-collector.json if it doesn't exist

If anything can't be done automatically, it tells you exactly what to do
and where — one clear instruction per item. Nothing silent, nothing guessed.

Rear View Foresight LLC — Feic Mo Chroí
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

INSTALLER_DIR = Path(__file__).parent.resolve()
SERVER_PORT   = 8765

# Markers we inject into JS files — used to detect if already patched
PATCH_MARKER_MAIN       = "// [RVF] session-endpoints"
PATCH_MARKER_BACKGROUND = "// [RVF] session-handlers"

# Bright terminal colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg):  print(f"  {RED}✗{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def head(msg): print(f"\n{BOLD}{msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Find the project
# ─────────────────────────────────────────────────────────────────────────────

def find_project() -> Path:
    """
    Locate the Code Collector project directory.
    Searches common locations, then asks if not found.
    """
    head("Step 1 — Locating Code Collector project")

    # Signatures that identify the project root
    def _is_project_root(p: Path) -> bool:
        return (
            (p / "main.js").exists() and
            (p / "package.json").exists() and
            (p / "extension").is_dir()
        )

    # 1. Check if we're already inside the project
    for candidate in [Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]:
        if _is_project_root(candidate):
            ok(f"Found project at {candidate}")
            return candidate

    # 2. Common locations
    home = Path.home()
    search_roots = [
        home / "Desktop",
        home / "Documents",
        home / "Projects",
        home / "dev",
        home / "code",
        home,
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for p in root.rglob("main.js"):
            candidate = p.parent
            if _is_project_root(candidate):
                ok(f"Found project at {candidate}")
                return candidate

    # 3. Ask the user
    warn("Could not find project automatically.")
    print()
    while True:
        path_str = input("  Enter the full path to your Code Collector folder: ").strip()
        if not path_str:
            continue
        p = Path(path_str).expanduser().resolve()
        if _is_project_root(p):
            ok(f"Using {p}")
            return p
        err(f"Not a valid Code Collector project (no main.js + extension/ found): {p}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Copy thinking_context package
# ─────────────────────────────────────────────────────────────────────────────

def install_thinking_context(project: Path) -> None:
    head("Step 2 — Installing thinking_context package")

    src = INSTALLER_DIR / "thinking_context"
    dst = project / "thinking_context"

    if dst.exists():
        warn("thinking_context/ already exists — updating files")
        shutil.rmtree(dst)

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    ok(f"Copied thinking_context/ → {dst}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Copy memory_layer extractors
# ─────────────────────────────────────────────────────────────────────────────

def install_extractors(project: Path) -> None:
    head("Step 3 — Installing conversation extractors")

    src = INSTALLER_DIR / "memory_layer" / "extractors"
    dst = project / "extractors"
    dst.mkdir(exist_ok=True)

    for f in src.iterdir():
        if f.suffix == ".py":
            shutil.copy2(f, dst / f.name)
            ok(f"Copied extractors/{f.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Patch main.js
# ─────────────────────────────────────────────────────────────────────────────

MAIN_JS_PATCH = '''
// [RVF] session-endpoints — injected by installer
// ─────────────────────────────────────────────────
(function _rvfSessionEndpoints() {
  const _sessionIndex      = new Map();
  const _latestByPlatform  = new Map();
  const { execFile }       = require("child_process");
  const path               = require("path");

  function _runConversationExtractor(payload) {
    return new Promise((resolve, reject) => {
      const script = path.join(__dirname, "extractors", "conversation_server.py");
      const proc = execFile("python3", [script], { timeout: 10000 }, (err, stdout, stderr) => {
        if (err) return reject(new Error(err.message + "\\n" + stderr));
        try { resolve(JSON.parse(stdout)); }
        catch { reject(new Error("extractor bad JSON: " + stdout.slice(0, 200))); }
      });
      proc.stdin.write(JSON.stringify(payload));
      proc.stdin.end();
    });
  }

  // Attach handlers to the global request handler map if it exists,
  // otherwise attach to module.exports for manual wiring.
  const _routes = {
    "POST /collect-conversation": async (req, res, body) => {
      let payload;
      try { payload = JSON.parse(body); } catch { res.writeHead(400); res.end("{}"); return; }
      const { session_id, platform = "claude", source_url = "", source_title = "Claude", turns = [] } = payload;
      if (!turns.length) { res.writeHead(200); res.end(JSON.stringify({ ok: true, skipped: "no turns" })); return; }
      try {
        const summary = await _runConversationExtractor({ session_id, platform, source_url, source_title, turns });
        _sessionIndex.set(session_id, { session_id, platform, source_url, source_title,
          captured_at: Date.now() / 1000, context: summary.context,
          files_touched: summary.files_touched || [], turn_count: summary.turn_count || turns.length });
        _latestByPlatform.set(platform, session_id);
        res.writeHead(200); res.end(JSON.stringify({ ok: true, session_id }));
      } catch (e) {
        _sessionIndex.set(session_id, { session_id, platform, source_url, source_title,
          captured_at: Date.now() / 1000, context: "Session captured — " + turns.length + " turns",
          files_touched: [], turn_count: turns.length });
        _latestByPlatform.set(platform, session_id);
        res.writeHead(200); res.end(JSON.stringify({ ok: true, session_id, warning: e.message }));
      }
    },
    "GET /context/session/all": (_req, res) => {
      const sessions = Array.from(_sessionIndex.values()).sort((a, b) => b.captured_at - a.captured_at);
      res.writeHead(200); res.end(JSON.stringify({ sessions, total: sessions.length }));
    },
    "GET /context/session": (_req, res, _body, urlParams) => {
      const platform = (urlParams || new URLSearchParams()).get("platform") || "claude";
      const id = _latestByPlatform.get(platform);
      const record = id ? _sessionIndex.get(id) : null;
      if (!record) { res.writeHead(200); res.end(JSON.stringify({ context: null })); return; }
      const ageHours = (Date.now() / 1000 - record.captured_at) / 3600;
      if (ageHours > 168) { res.writeHead(200); res.end(JSON.stringify({ context: null, reason: "too old" })); return; }
      res.writeHead(200); res.end(JSON.stringify({ ...record, age_hours: Math.round(ageHours * 10) / 10 }));
    },
  };

  // Register with global router if available
  if (typeof global._rvfRoutes !== "undefined") {
    Object.assign(global._rvfRoutes, _routes);
  } else {
    global._rvfRoutes = _routes;
  }

  // Helper: call from your request handler
  // if (global._rvfRoutes) {
  //   const key = req.method + " " + req.url.split("?")[0];
  //   if (global._rvfRoutes[key]) {
  //     const urlParams = new URLSearchParams(req.url.split("?")[1] || "");
  //     return global._rvfRoutes[key](req, res, body, urlParams);
  //   }
  // }
})();
// [RVF] end session-endpoints
'''

def patch_main_js(project: Path) -> None:
    head("Step 4 — Patching main.js")

    main_js = project / "main.js"
    if not main_js.exists():
        err("main.js not found — skipping")
        return

    content = main_js.read_text(encoding="utf-8")

    if PATCH_MARKER_MAIN in content:
        ok("main.js already patched — skipping")
        return

    # Back up
    backup = project / "main.js.rvf.bak"
    shutil.copy2(main_js, backup)
    ok(f"Backed up main.js → main.js.rvf.bak")

    # Append patch at end of file
    patched = content.rstrip() + "\n\n" + MAIN_JS_PATCH.strip() + "\n"
    main_js.write_text(patched, encoding="utf-8")
    ok("Patched main.js — session routes added")

    info("ACTION REQUIRED: In your main.js request handler, add this check:")
    print()
    print("    const urlParams = new URLSearchParams((req.url.split('?')[1] || ''));")
    print("    const routeKey  = req.method + ' ' + req.url.split('?')[0];")
    print("    if (global._rvfRoutes && global._rvfRoutes[routeKey]) {")
    print("      return global._rvfRoutes[routeKey](req, res, body, urlParams);")
    print("    }")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Patch background.js
# ─────────────────────────────────────────────────────────────────────────────

BACKGROUND_JS_PATCH = '''
// [RVF] session-handlers — injected by installer
// ──────────────────────────────────────────────
(function _rvfSessionHandlers() {
  const SERVER_PORT = ''' + str(SERVER_PORT) + ''';

  async function _relayConversationCapture(message) {
    const { session_id, platform, source_url, source_title, turns } = message;
    if (!turns || !turns.length) return { ok: false };
    try {
      const res = await fetch(`http://localhost:${SERVER_PORT}/collect-conversation`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id, platform, source_url, source_title, turns }),
      });
      const data = await res.json();
      return { ok: true, session_id: data.session_id };
    } catch { return { ok: false, reason: "server unavailable" }; }
  }

  async function _fetchLastSession(platform = "claude") {
    try {
      const res = await fetch(
        `http://localhost:${SERVER_PORT}/context/session?platform=${platform}`,
        { signal: AbortSignal.timeout(2000) }
      );
      return res.ok ? await res.json() : { context: null };
    } catch { return { context: null }; }
  }

  // Tab watcher — auto-inject context on new Claude tabs
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status !== "complete") return;
    if (!tab.url || !tab.url.startsWith("https://claude.ai")) return;
    const isNew = tab.url.includes("/chat/new") ||
                  tab.url === "https://claude.ai/" ||
                  tab.url === "https://claude.ai";
    if (!isNew) return;
    setTimeout(async () => {
      const data = await _fetchLastSession("claude");
      if (!data || !data.context) return;
      chrome.tabs.sendMessage(tabId, { type: "SHOW_PRIOR_CONTEXT", context: data.context })
        .catch(() => {});
    }, 1200);
  });

  // Message handlers — wire into your existing onMessage listener:
  // if (message.type === "CONVERSATION_CAPTURE") {
  //   _relayConversationCapture(message).then(sendResponse); return true;
  // }
  // if (message.type === "FETCH_LAST_SESSION") {
  //   _fetchLastSession(message.platform).then(sendResponse); return true;
  // }
  global._rvfHandlers = { _relayConversationCapture, _fetchLastSession };
})();
// [RVF] end session-handlers
'''

def patch_background_js(project: Path) -> None:
    head("Step 5 — Patching background.js")

    bg = project / "extension" / "background.js"
    if not bg.exists():
        # Try root level
        bg = project / "background.js"
    if not bg.exists():
        err("background.js not found — skipping")
        warn("Manually add the contents of memory_layer/extension/background_session_patch.js")
        return

    content = bg.read_text(encoding="utf-8")

    if PATCH_MARKER_BACKGROUND in content:
        ok("background.js already patched — skipping")
        return

    shutil.copy2(bg, bg.parent / "background.js.rvf.bak")
    ok("Backed up background.js")

    patched = content.rstrip() + "\n\n" + BACKGROUND_JS_PATCH.strip() + "\n"
    bg.write_text(patched, encoding="utf-8")
    ok("Patched background.js — session handlers added")

    info("ACTION REQUIRED: In your onMessage listener, add:")
    print()
    print("    if (message.type === 'CONVERSATION_CAPTURE') {")
    print("      global._rvfHandlers._relayConversationCapture(message).then(sendResponse);")
    print("      return true;")
    print("    }")
    print("    if (message.type === 'FETCH_LAST_SESSION') {")
    print("      global._rvfHandlers._fetchLastSession(message.platform).then(sendResponse);")
    print("      return true;")
    print("    }")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Copy claude_scraper.js into extension
# ─────────────────────────────────────────────────────────────────────────────

def install_claude_scraper(project: Path) -> None:
    head("Step 6 — Installing claude_scraper.js")

    src = INSTALLER_DIR / "memory_layer" / "extension" / "claude_scraper.js"
    ext_dir = project / "extension"

    if not ext_dir.exists():
        ext_dir = project  # fallback to root
        warn("No extension/ folder found — placing claude_scraper.js in project root")

    dst = ext_dir / "claude_scraper.js"
    shutil.copy2(src, dst)
    ok(f"Copied claude_scraper.js → {dst}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Patch manifest.json
# ─────────────────────────────────────────────────────────────────────────────

def patch_manifest(project: Path) -> None:
    head("Step 7 — Patching manifest.json")

    manifest_path = project / "extension" / "manifest.json"
    if not manifest_path.exists():
        manifest_path = project / "manifest.json"
    if not manifest_path.exists():
        warn("manifest.json not found — add claude_scraper.js manually")
        info('Add to content_scripts in manifest.json:')
        print('    { "matches": ["https://claude.ai/*"], "js": ["claude_scraper.js"], "run_at": "document_idle" }')
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"Could not parse manifest.json: {e}")
        return

    content_scripts = manifest.get("content_scripts", [])

    # Check if already added
    for cs in content_scripts:
        if "claude_scraper.js" in cs.get("js", []):
            ok("manifest.json already has claude_scraper.js — skipping")
            return

    # Add new content script entry
    content_scripts.append({
        "matches":  ["https://claude.ai/*"],
        "js":       ["claude_scraper.js"],
        "run_at":   "document_idle"
    })
    manifest["content_scripts"] = content_scripts

    shutil.copy2(manifest_path, manifest_path.parent / "manifest.json.rvf.bak")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok("Patched manifest.json — claude_scraper.js registered for claude.ai")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Create data directory
# ─────────────────────────────────────────────────────────────────────────────

def create_data_dir(project: Path) -> None:
    head("Step 8 — Creating data directory")
    data_dir = project / "data"
    data_dir.mkdir(exist_ok=True)
    gitkeep = data_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    ok(f"data/ directory ready at {data_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Write ~/.code-collector.json
# ─────────────────────────────────────────────────────────────────────────────

def write_config() -> None:
    head("Step 9 — Writing ~/.code-collector.json")

    config_path = Path.home() / ".code-collector.json"

    if config_path.exists():
        ok("~/.code-collector.json already exists — leaving it alone")
        return

    config = {
        "port":            SERVER_PORT,
        "token":           "",
        "default_target":  "primary",
        "cloud_folder":    "",
        "memory_snapshot": "data/memory_snapshot.json",
    }
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    ok(f"Wrote ~/.code-collector.json (port {SERVER_PORT})")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print(f"{BOLD}{'═' * 56}{RESET}")
    print(f"{BOLD}  Rear View Foresight LLC — Installer{RESET}")
    print(f"{BOLD}  Feic Mo Chroí{RESET}")
    print(f"{BOLD}{'═' * 56}{RESET}")
    print()
    print("  Two things are about to be installed:")
    print("  1. thinking_context  — PubCast AI memory layer")
    print("  2. memory_layer      — Claude persistent session memory")
    print()
    input("  Press Enter to begin, Ctrl+C to cancel... ")

    project = find_project()

    install_thinking_context(project)
    install_extractors(project)
    patch_main_js(project)
    patch_background_js(project)
    install_claude_scraper(project)
    patch_manifest(project)
    create_data_dir(project)
    write_config()

    print()
    print(f"{BOLD}{'═' * 56}{RESET}")
    print(f"{BOLD}{GREEN}  Install complete.{RESET}")
    print(f"{BOLD}{'═' * 56}{RESET}")
    print()
    print("  What happens now:")
    print("  • Open a new Claude tab → prior context fires automatically")
    print("  • Claude walks in knowing what you were building")
    print("  • You do nothing. Ever again.")
    print()
    print("  Reload your browser extension to activate claude_scraper.js:")
    print("  chrome://extensions → Code Collector → reload")
    print()
    print(f"  {YELLOW}If main.js or background.js needed manual wiring,{RESET}")
    print(f"  {YELLOW}the instructions were printed above.{RESET}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}  Fatal error: {e}{RESET}\n")
        raise
