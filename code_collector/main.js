"use strict";

const path       = require("path");
const fs         = require("fs");
const http       = require("http");
const { execFile } = require("child_process");
const {
  app, BrowserWindow, Tray, Menu, nativeImage,
  ipcMain, dialog, shell,
} = require("electron");
const Store = require("electron-store");

// ─── CPU limiter ──────────────────────────────────────────────────────────────
const CPU_LIMIT_PERCENT = 70;

// ─── Persistent store ─────────────────────────────────────────────────────────
// Static defaults that don't need app.getPath — safe at module load time.
// Path-based defaults (primaryDir, archiveDir) are patched inside app.whenReady()
// once Electron's app object is fully initialized.
// Sites whose whole conversations can be captured. Keys match the extension's
// conversation_scraper.js SITES table and the "platform" field it sends.
const CONVERSATION_SITES_DEFAULT = Object.freeze({
  claude: true, chatgpt: true, gemini: true, copilot: true, perplexity: true,
});

const store = new Store({
  defaults: {
    primaryDir:        "",   // patched in whenReady
    secondaryDir:      "",
    archiveDir:        "",   // patched in whenReady
    cloudDir:          "",
    cloudEnabled:      false,
    authToken:         "",
    serverPort:        8765,
    startOnLogin:      false,
    saveToArchive:     true,
    cpuLimiterEnabled: true,
    // Whole-conversation capture: off unless the user turns it on.
    // When on, each enabled site's full conversation (both sides, in order)
    // is saved as a readable transcript, beside the usual code captures.
    captureConversations: false,
    conversationSites: { ...CONVERSATION_SITES_DEFAULT },
  },
});

function _initStorePathDefaults() {
  // Only set if user hasn't already configured them (empty string = not set)
  if (!store.get("primaryDir")) {
    store.set("primaryDir", path.join(app.getPath("documents"), "CodeCollector", "primary"));
  }
  if (!store.get("archiveDir")) {
    store.set("archiveDir", path.join(app.getPath("documents"), "CodeCollector", "archive"));
  }
}

// CPU usage measured as delta between two samples — NOT lifetime average.
// process.cpuUsage() is cumulative. Dividing by uptime gives a lifetime
// average that approaches zero on a long-running process, making the limiter
// useless after the first few minutes. We track the previous sample and
// compute a rolling window instead.
let _lastCpuSample = process.cpuUsage();
let _lastCpuTime   = Date.now();

function getAppCpuUsage() {
  const now     = Date.now();
  const elapsed = (now - _lastCpuTime) * 1000; // ms → microseconds
  if (elapsed < 100_000) {
    // Window too small — return 0 to avoid divide-by-near-zero noise
    return 0;
  }
  const current = process.cpuUsage();
  const delta   = (current.user - _lastCpuSample.user) + (current.system - _lastCpuSample.system);
  _lastCpuSample = current;
  _lastCpuTime   = now;
  return (delta / elapsed) * 100;
}

function isCpuLimiterEnabled() {
  return store.get("cpuLimiterEnabled", true);
}

function checkCpuLimit() {
  if (process.env.NO_CPU_LIMIT === "1") return;
  if (!isCpuLimiterEnabled()) return;
  const usage = getAppCpuUsage();
  if (usage > CPU_LIMIT_PERCENT) {
    throw new Error(
      `CPU usage too high (${usage.toFixed(1)}%). ` +
      `Limit is ${CPU_LIMIT_PERCENT}%. Wait for usage to drop or disable CPU limiter in settings.`
    );
  }
}

async function throttleForCpu() {
  if (!isCpuLimiterEnabled()) return;
  if (getAppCpuUsage() > CPU_LIMIT_PERCENT) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

// ─── Runtime state ────────────────────────────────────────────────────────────
let tray           = null;
let settingsWindow = null;
let server         = null;
let serverRunning  = false;
let captureCount   = 0;
let serverRetryCount = 0;
const MAX_SERVER_RETRIES = 3;

// Active socket tracking — lets stopServer() close immediately without
// waiting for keep-alive connections to time out on their own.
const _activeSockets = new Set();

const ASSETS   = path.join(__dirname, "assets");
const iconPath = (on) => path.join(ASSETS, on ? "icon-active.png" : "icon-inactive.png");

// ─── Filesystem helpers ───────────────────────────────────────────────────────
function ensureDir(dir) {
  if (!dir) return;
  // mkdirSync with recursive:true is atomic and idempotent — no existsSync needed.
  // The existsSync → mkdirSync pattern has a TOCTOU race: another process can
  // create the directory between the check and the mkdir.
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (err) {
    if (err.code !== "EEXIST") throw err;
  }
}

function dateSlug(isoString) {
  // Use the payload's own captured_at if provided — files land on the right
  // date even if the write is delayed or the payload was queued.
  const src = isoString || new Date().toISOString();
  try { return new Date(src).toISOString().slice(0, 10); } catch { return new Date().toISOString().slice(0, 10); }
}

function safeSegment(text, maxLen = 40) {
  return (text || "")
    .replace(/[^a-zA-Z0-9\-_.]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, maxLen) || "untitled";
}

// ─── Code file scanner ────────────────────────────────────────────────────────
function isLikelyCodeLine(line) {
  const trimmed = (line || "").trim();
  if (!trimmed) return false;

  // Tightly scoped keyword matching — each keyword requires code-specific syntax context.
  // Keywords like "function", "return", "class", "let", "else" appear in natural English
  // so we require syntactic evidence (brackets, operators, colons) to confirm code context.
  const codeTokenRe = new RegExp([
    /\bfunction\s*\w*\s*\(/,                          // function() or function foo(
    /\bdef\s+\w+\s*\(/,                               // Python: def foo(
    /\bfunc\s+(?:\w|\()/,                             // Go: func foo( or func (recv)
    /\bclass\s+\w+\s*(?:extends|implements|\{|\()/,   // class Foo { / extends / (
    /\bconst\b/,                                       // const — rare in prose
    /\blet\s+\w+\s*=/,                                // let x = ... (not "let me")
    /\bvar\b/,                                         // var — rare in prose
    /\breturn\s*;/,                                    // bare return;
    /\breturn\s+(?!(?:to|from|the|a|an|in|on|of|for|with|at|by|as|it)\b)[^\s]/,
    /\belse\s*[{(]/,                                  // } else { or else if(
    /\bif\s*\(/,                                      // if (condition)
    /\bfor\s*\(/,                                     // for (init; cond; step)
    /\bwhile\s*\(/,                                   // while (condition)
    /\b#include\b/,                                   // C/C++
    /\bpackage\s+\w/,                                 // Go/Java package
    /\bconsole\.log\b/,                               // JS debug
    /\bimport\s+(?:[{*'"]|\w+\s+from\s+['"])/,       // JS/TS: import { } or import X from 'y'
    /\bfrom\s+(?:['"]|\w+\s+import\b)/,              // Python: from X import
    /=>/,                                              // arrow function
    /\bpub\s+(?:fn|struct|enum|impl)\b/,              // Rust public items
    /\bfn\s+\w+\s*\(/,                               // Rust fn foo(
  ].map((r) => r.source).join("|"));

  if (codeTokenRe.test(trimmed)) return true;

  // Symbol density — reliable structural indicator regardless of language
  if ((trimmed.match(/[{};=<>()\[\]\\]/g) || []).length >= 2) return true;

  // Indented non-trivial line — likely code body
  if (/^\s{2,}/.test(line) && trimmed.length > 20) return true;

  return false;
}

function extractCodeBlocksFromText(text) {
  if (typeof text !== "string") return [];
  const blocks  = [];
  const lines   = text.split(/\r?\n/);
  let fenced    = false;
  let fenceLang = "";
  let current   = [];

  const flush = () => {
    const joined = current.join("\n").trim();
    if (joined.length >= 10) blocks.push({ language: fenceLang || "unknown", content: joined });
    current   = [];
    fenceLang = "";
  };

  for (const line of lines) {
    const m = line.match(/^```\s*(\w*)/);
    if (m) {
      if (fenced) { flush(); fenced = false; }
      else        { fenced = true; fenceLang = m[1] || "unknown"; current = []; }
      continue;
    }
    if (fenced)              { current.push(line); continue; }
    if (isLikelyCodeLine(line)) { current.push(line); continue; }
    if (current.length) flush();
  }
  if (current.length) flush();

  return blocks
    .map((b)  => ({ language: b.language, content: b.content.trim() }))
    .filter((b) => b.content.length > 0);
}

function isSafePath(filePath) {
  if (process.env.TEST_MODE === "1") return true;
  const absPath      = path.resolve(filePath);
  const allowedBases = [
    app.getPath("home"),
    app.getPath("documents"),
    app.getPath("downloads"),
  ].map((p) => path.resolve(p));

  const inAllowed = allowedBases.some(
    (base) => absPath.startsWith(base + path.sep) || absPath === base
  );
  if (!inAllowed) throw new Error("Path not allowed: only user directories (home, documents, downloads) are permitted.");

  // Platform-aware forbidden paths
  if (process.platform === "win32") {
    const winRoot = absPath.slice(0, 3).toUpperCase(); // e.g. "C:\"
    const forbidden = [
      `${winRoot}Windows`, `${winRoot}System32`, `${winRoot}SysWOW64`,
      `${winRoot}Program Files`, `${winRoot}Program Files (x86)`,
      `${winRoot}ProgramData`,
    ];
    if (forbidden.some((f) => absPath.startsWith(f))) throw new Error("Path not allowed: system directories are forbidden.");
  } else {
    const forbidden = ["/etc", "/usr", "/var", "/bin", "/sbin", "/boot", "/sys", "/proc", "/dev", "/lib", "/lib64"];
    if (forbidden.some((f) => absPath.startsWith(f + "/") || absPath === f)) throw new Error("Path not allowed: system directories are forbidden.");
  }

  return true;
}

function isTextFile(filePath) {
  let fd;
  try {
    fd = fs.openSync(filePath, "r");
    const buffer    = Buffer.alloc(512);
    const bytesRead = fs.readSync(fd, buffer, 0, 512, 0);
    for (let i = 0; i < bytesRead; i++) if (buffer[i] === 0) return false;
    let nonPrintable = 0;
    for (let i = 0; i < bytesRead; i++) {
      const c = buffer[i];
      if (c < 32 && c !== 9 && c !== 10 && c !== 13) nonPrintable++;
    }
    return nonPrintable <= bytesRead * 0.3;
  } catch { return false; }
  finally  { if (fd !== undefined) { try { fs.closeSync(fd); } catch { /* ignore */ } } }
}

// sanitizeCodeOutput — used ONLY when code content will be rendered in HTML.
// Do NOT apply to captured code written to JSON files — that corrupts legitimate
// HTML/JS samples that contain script tags, event handlers, or angle brackets.
// The file scanner path does NOT call this. /collect does NOT call this.
// Reserved for any future web-rendering surface.
function sanitizeCodeOutput(code) {
  return (code || "")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<[^>]+>/g, "")
    .replace(/javascript:/gi, "")
    .replace(/on\w+="[^"]*"/gi, "")
    .trim();
}

function scanFileForCode(filePath) {
  checkCpuLimit();
  if (!filePath || !fs.existsSync(filePath))  throw new Error("File not found");
  isSafePath(filePath);
  const stats = fs.statSync(filePath);
  if (!stats.isFile())                         throw new Error("Not a regular file");
  if (!isTextFile(filePath))                   throw new Error("File appears to be binary or non-text; only text files are allowed.");
  if (stats.size > 10 * 1024 * 1024)          throw new Error("File too large (max 10 MB)");

  let raw;
  try   { raw = fs.readFileSync(filePath, "utf8"); }
  catch (err) { throw new Error(`Unable to read file: ${err.message}`); }

  // Do NOT sanitize here — sanitizeCodeOutput strips HTML tags and script blocks
  // which corrupts legitimate HTML, JSX, and template code. The output is written
  // to a local JSON file, not rendered in a browser context.
  const blocks  = extractCodeBlocksFromText(raw)
    .map((b) => ({ language: b.language, content: b.content }));
  const warning = stats.size > 2 * 1024 * 1024
    ? `Large file: ${(stats.size / (1024 * 1024)).toFixed(2)} MB (scan may be slow).`
    : "";
  return { filePath, detected: blocks.length > 0, count: blocks.length, warning, blocks };
}

async function scanFolderForCode(folderPath, maxFiles = 500) {
  checkCpuLimit();
  if (!folderPath || !fs.existsSync(folderPath)) throw new Error("Folder not found");
  isSafePath(folderPath);
  const stats = fs.statSync(folderPath);
  if (!stats.isDirectory()) throw new Error("Not a directory");

  const supportedExt = new Set([
    "txt","md","json","js","ts","py","java","cpp","c","h",
    "go","rs","sh","html","css","yaml","yml",
  ]);
  const results = [];
  let count     = 0;

  async function walk(dir) {
    if (count >= maxFiles) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (count >= maxFiles) break;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) { await walk(fullPath); continue; }
      const ext = entry.name.split(".").pop().toLowerCase();
      if (!supportedExt.has(ext)) continue;
      count++;
      try {
        isSafePath(fullPath);
        const es = fs.statSync(fullPath);
        if (es.size > 10 * 1024 * 1024) { results.push({ filePath: fullPath, skipped: true, reason: "Exceeds max file size (10 MB)" }); continue; }
        if (!isTextFile(fullPath))       { results.push({ filePath: fullPath, skipped: true, reason: "Appears to be binary or non-text" }); continue; }
        results.push(scanFileForCode(fullPath));
        await throttleForCpu();
      } catch (err) {
        if (err.message?.includes("CPU usage too high")) {
          results.push({ filePath: fullPath, skipped: true, reason: "CPU limit reached - scan paused", errorType: "cpu_limit" });
          break;
        }
        results.push({ filePath: fullPath, error: err.message, errorType: "scan_error" });
      }
    }
  }

  await walk(folderPath);
  return {
    folderPath,
    scanned: count,
    maxFiles,
    results,
    warning: count >= maxFiles ? `Reached max file scan limit (${maxFiles}); some files may not be scanned.` : "",
  };
}

// ─── Smart filename ───────────────────────────────────────────────────────────
function buildSmartFilename(payload, index = 1) {
  const date     = dateSlug(payload.captured_at);
  const rawTitle = (payload.source_title || "")
    .replace(/\s*[-|–—]\s*claude\.ai.*/i, "")
    .replace(/\s*[-|–—]\s*ChatGPT.*/i, "")
    .trim();
  let hostname = "unknown";
  try { hostname = new URL(payload.source_url || "").hostname; } catch { /* ignore */ }
  const siteSlug = safeSegment(rawTitle || hostname, 30);

  let purposeSlug = "";
  const firstBlock = (payload.blocks || [])[0];
  if (firstBlock) {
    const { detected_filename, purpose_hint, entity_names, code_type, language } = firstBlock;
    if (detected_filename) {
      purposeSlug = safeSegment(detected_filename.replace(/\.[^.]+$/, ""), 36);
    } else if (purpose_hint) {
      purposeSlug = safeSegment(purpose_hint.split(/\s+/).slice(0, 5).join("-"), 36);
    } else if (entity_names?.[0]) {
      purposeSlug = safeSegment(`${code_type || language}-${entity_names[0]}`, 36);
    } else {
      purposeSlug = safeSegment(language || "snippet", 20);
    }
  }

  const seq   = String(index).padStart(3, "0");
  const parts = [siteSlug, date, purposeSlug || "capture", seq].filter(Boolean);
  return `${parts.join("__")}.json`;
}

// Derive the next sequence number by scanning existing files in the directory.
// This survives restarts — no in-memory counter that resets to 001 on quit.
// Pattern: anything ending in __NNN.json where NNN is zero-padded digits.
const _SEQ_RE = /__(\d{3,})\.json$/;

function nextSeq(dir) {
  try {
    const entries = fs.readdirSync(dir);
    let max = 0;
    for (const name of entries) {
      const m = name.match(_SEQ_RE);
      if (m) {
        const n = parseInt(m[1], 10);
        if (n > max) max = n;
      }
    }
    return max + 1;
  } catch {
    // Dir doesn't exist yet or isn't readable — start at 1, ensureDir handles creation
    return 1;
  }
}

function writePayload(dir, payload) {
  ensureDir(dir);
  const filename = buildSmartFilename(payload, nextSeq(dir));
  const outPath  = path.join(dir, filename);
  fs.writeFileSync(outPath, JSON.stringify(payload, null, 2), "utf8");
  return outPath;
}

function routePayload(payload) {
  const target       = payload.target || "primary";
  const primaryDir   = store.get("primaryDir");
  const secondaryDir = store.get("secondaryDir");
  const archiveDir   = store.get("archiveDir");
  const cloudDir     = store.get("cloudDir");
  const saved        = {};

  const writeTo = (key, dir) => {
    if (dir) { try { saved[key] = writePayload(dir, payload); } catch (e) { console.error(`Failed to write ${key}:`, e.message); } }
  };

  if (!primaryDir) {
    writeTo("primary", path.join(app.getPath("documents"), "CodeCollector", "primary"));
  } else if (target === "primary" || target === "both") {
    writeTo("primary", primaryDir);
  }

  // Secondary is an always-on mirror when configured — it writes on every
  // capture regardless of target. This is intentional: it's a backup destination.
  // If secondaryDir is set, the user has explicitly asked for a mirror copy.
  if (secondaryDir) writeTo("secondary", secondaryDir);

  if (target === "archive" || target === "both" || (target === "primary" && store.get("saveToArchive")))
    writeTo("archive", archiveDir);

  if ((target === "cloud" || target === "both") && store.get("cloudEnabled") && cloudDir)
    writeTo("cloud", cloudDir);

  return saved;
}

// ─── Session memory index ─────────────────────────────────────────────────────
// Tier 1: JSON file on disk. Tier 2 (SQLite) uses same interface, same key shapes.
const _sessionIndex      = new Map(); // session_id → SessionRecord
const _latestByPlatform  = new Map(); // platform   → session_id

const SESSION_MAX_STORED = 50; // per platform trim ceiling

// Lazy — resolved on first use inside whenReady, not at module load time.
// app.getPath("userData") is safe to call after app.whenReady() fires.
let _sessionIndexPath = null;
function getSessionIndexPath() {
  if (!_sessionIndexPath) {
    _sessionIndexPath = path.join(app.getPath("userData"), "session-index.json");
  }
  return _sessionIndexPath;
}

function loadSessionIndex() {
  try {
    const raw  = fs.readFileSync(getSessionIndexPath(), "utf8");
    const data = JSON.parse(raw);
    const cutoff = (Date.now() / 1000) - (168 * 3600); // 7 days
    let   loaded = 0;
    let   pruned = 0;

    for (const [id, record] of Object.entries(data.sessions || {})) {
      // Validate minimum required fields — corrupt records are dropped on load
      if (!record || typeof record !== "object") { pruned++; continue; }
      if (!record.session_id || !record.platform)  { pruned++; continue; }
      // Prune stale records on load — no point carrying dead weight in memory
      if (record.captured_at && record.captured_at < cutoff) { pruned++; continue; }
      _sessionIndex.set(id, record);
      loaded++;
    }

    for (const [platform, id] of Object.entries(data.latest_by_platform || {})) {
      // Only restore pointer if the session it points to actually loaded
      if (_sessionIndex.has(id)) {
        _latestByPlatform.set(platform, id);
      }
      // Otherwise we let it be re-established naturally on next capture
    }

    console.log(`[session] loaded ${loaded} session(s) from disk${pruned ? ` (${pruned} stale/corrupt pruned)` : ""}`);
  } catch {
    console.log("[session] no session index on disk — starting fresh");
  }
}

let _saveDebounceTimer = null;
function saveSessionIndex() {
  if (_saveDebounceTimer) clearTimeout(_saveDebounceTimer);
  _saveDebounceTimer = setTimeout(() => {
    _saveDebounceTimer = null;
    try {
      // Trim to SESSION_MAX_STORED per platform — not total.
      // If you use Claude and ChatGPT equally you keep 50 of each,
      // not 40/10 depending on which one you used more recently.
      const byPlatform = {};
      for (const record of _sessionIndex.values()) {
        if (!byPlatform[record.platform]) byPlatform[record.platform] = [];
        byPlatform[record.platform].push(record);
      }

      const sessions = {};
      for (const recs of Object.values(byPlatform)) {
        recs
          .sort((a, b) => b.captured_at - a.captured_at)
          .slice(0, SESSION_MAX_STORED)
          .forEach((r) => { sessions[r.session_id] = r; });
      }

      // Reconcile _latestByPlatform — after trimming, some pointers may now
      // point to sessions that were trimmed out. Update them to the newest
      // surviving session per platform.
      for (const [platform, sessionId] of _latestByPlatform.entries()) {
        if (!sessions[sessionId]) {
          // Find newest surviving session for this platform
          const surviving = Object.values(sessions)
            .filter((r) => r.platform === platform)
            .sort((a, b) => b.captured_at - a.captured_at)[0];
          if (surviving) {
            _latestByPlatform.set(platform, surviving.session_id);
          } else {
            _latestByPlatform.delete(platform);
          }
        }
      }

      // Atomic write — write to .tmp then rename.
      // A crash mid-write on a direct writeFileSync truncates the file and
      // corrupts the entire session history. rename() is atomic on the same
      // filesystem: either the old file survives intact or the new one lands.
      const indexPath = getSessionIndexPath();
      const tmpPath   = indexPath + ".tmp";
      fs.writeFileSync(
        tmpPath,
        JSON.stringify({
          version:            1,
          sessions,
          latest_by_platform: Object.fromEntries(_latestByPlatform),
        }, null, 2),
        "utf8"
      );
      fs.renameSync(tmpPath, indexPath);
    } catch (err) {
      console.error("[session] failed to save index:", err.message);
    }
  }, 500);
}

// ─── Whole-conversation capture ───────────────────────────────────────────────

function conversationCaptureAllowed(platform) {
  if (!store.get("captureConversations")) return false;
  if (!(platform in CONVERSATION_SITES_DEFAULT)) return false;
  const sites = { ...CONVERSATION_SITES_DEFAULT, ...(store.get("conversationSites") || {}) };
  return sites[platform] === true;
}

function _transcriptText({ platform, source_title, source_url, turns }) {
  const lines = [
    `${source_title || platform}`,
    `Site: ${platform}`,
    `Link: ${source_url || "(none)"}`,
    `Saved: ${new Date().toISOString()}`,
    `Turns: ${turns.length}`,
    "",
  ];
  for (const t of turns) {
    const who = t.role === "user" ? "You" : t.role === "assistant" ? "AI" : t.role;
    lines.push(`── ${who} ──`, t.content, "");
  }
  return lines.join("\n");
}

/**
 * Save the whole conversation as two files that are rewritten in place as the
 * conversation grows: <session>.json (the turns, for tools) and <session>.txt
 * (readable anywhere). Folder: <primaryDir>/conversations/<platform>/.
 * One pair per conversation, so repeated captures never pile up duplicates.
 */
function writeConversationTranscript({ session_id, platform, source_url, source_title, turns }) {
  const root = store.get("primaryDir");
  if (!root) throw new Error("No primary folder set");
  const dir = path.join(root, "conversations", safeSegment(platform, 20) || "unknown");
  ensureDir(dir);
  const stem = safeSegment(String(session_id), 80) || `session_${Date.now()}`;
  const record = { session_id, platform, source_url, source_title, saved_at: new Date().toISOString(), turns };
  const jsonPath = path.join(dir, `${stem}.json`);
  const txtPath  = path.join(dir, `${stem}.txt`);
  for (const [target, data] of [[jsonPath, JSON.stringify(record, null, 2)], [txtPath, _transcriptText(record)]]) {
    const tmp = `${target}.tmp`;
    fs.writeFileSync(tmp, data, "utf8");
    fs.renameSync(tmp, target);   // never leave a half-written transcript
  }
  return { json: jsonPath, text: txtPath, turns: turns.length };
}

/**
 * POST /collect-conversation
 * Receives raw turns, runs the Python extractor, stores the session record.
 */
async function handleCollectConversation(req, res, body) {
  let payload;
  try   { payload = JSON.parse(body); }
  catch {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Invalid JSON" }));
    return;
  }

  // Auth check — deferred to here because sendBeacon can't set headers.
  // Header token takes priority; fall back to body _beacon_token for beacons.
  const serverToken = store.get("authToken");
  if (serverToken) {
    const headerToken = req.headers["x-auth-token"];
    const bodyToken   = payload._beacon_token || "";
    if (headerToken !== serverToken && bodyToken !== serverToken) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }

  // Strip _beacon_token before any processing — it must never be stored,
  // logged, or passed to the extractor. It's auth material, not data.
  delete payload._beacon_token;

  const {
    session_id:   raw_session_id,
    platform     = "claude",
    source_url   = "",
    source_title = "Claude",
    turns        = [],
  } = payload;

  // Normalize session_id early — undefined is a valid JS Map key but produces
  // silent corruption (all undefined-id sessions overwrite each other).
  // Fallback to a timestamp-derived key if the payload omits it entirely.
  const session_id = raw_session_id || `session_${Date.now()}`;

  // Whole-conversation capture is opt-in, per site. Off means nothing is kept.
  if (!conversationCaptureAllowed(platform)) {
    res.writeHead(403, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: false, error: "Conversation capture is off for this site" }));
    return;
  }

  // Validate turns — must be array, each element must be an object with role+content
  if (!Array.isArray(turns)) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "turns must be an array" }));
    return;
  }

  // Cap turns at 500 — matches conversation.py MAX_TURNS
  const safeTurns = turns.slice(0, 500).filter(
    (t) => t && typeof t === "object" && typeof t.role === "string" && typeof t.content === "string"
  );

  // Cap source_url length to prevent huge strings in session records
  const safe_source_url   = (source_url   || "").slice(0, 2048);
  const safe_source_title = (source_title || "Claude").slice(0, 256);

  if (!safeTurns.length) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, skipped: "no turns" }));
    return;
  }

  // Full transcript first: it is the record the user asked for. The summary
  // below is extra, and its failure must never lose the conversation.
  let transcript = null;
  try {
    transcript = writeConversationTranscript({
      session_id, platform, source_url: safe_source_url, source_title: safe_source_title, turns: safeTurns,
    });
  } catch (err) {
    console.error("[session] transcript write failed:", err.message);
  }

  try {
    const summary = await _runConversationExtractor({ session_id, platform, source_url: safe_source_url, source_title: safe_source_title, turns: safeTurns });

    // Trust the extractor's session_id if it returned a clean one; otherwise keep ours.
    const canonical_id = (summary.session_id && summary.session_id !== "undefined")
      ? summary.session_id
      : session_id;

    const record = {
      session_id:    canonical_id,
      platform:      summary.platform,
      source_url:    summary.source_url,
      source_title,
      captured_at:   Date.now() / 1000,
      context:       summary.context,
      files_touched: summary.files_touched || [],
      turn_count:    summary.turn_count || turns.length,
    };

    _sessionIndex.set(canonical_id, record);
    _latestByPlatform.set(platform, canonical_id);
    saveSessionIndex();

    console.log(`[session] stored ${canonical_id} (${platform}) — ${turns.length} turns, ${record.files_touched.length} files`);

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, session_id: canonical_id, transcript }));

  } catch (err) {
    console.error("[session] extractor failed:", err.message);
    // Degrade gracefully — store a minimal record rather than losing the session
    _sessionIndex.set(session_id, {
      session_id,
      platform,
      source_url:    safe_source_url,
      source_title:  safe_source_title,
      captured_at:   Date.now() / 1000,
      context:       `Session captured — ${turns.length} turns\nSource: ${source_url}`,
      files_touched: [],
      turn_count:    turns.length,
    });
    _latestByPlatform.set(platform, session_id);
    saveSessionIndex();

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, session_id, transcript, warning: "extractor failed, minimal record stored" }));
  }
}

/**
 * GET /context/session?platform=claude
 * Returns the most recent session record for the given platform (max 7 days old).
 */
function handleGetSessionContext(req, res, urlParams) {
  const platform  = urlParams.get("platform") || "claude";
  const sessionId = _latestByPlatform.get(platform);

  if (!sessionId) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ context: null, message: "no prior session" }));
    return;
  }

  const record = _sessionIndex.get(sessionId);
  if (!record) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ context: null, message: "session not found" }));
    return;
  }

  const ageHours = (Date.now() / 1000 - record.captured_at) / 3600;
  if (ageHours > 168) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ context: null, message: "session too old" }));
    return;
  }

  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({
    context:       record.context       || null,
    session_id:    record.session_id    || null,
    source_url:    record.source_url    || "",
    captured_at:   record.captured_at   || 0,
    files_touched: record.files_touched || [],
    age_hours:     Math.round(ageHours * 10) / 10,
  }));
}

/**
 * GET /context/session/all
 * Returns all stored session records, newest first.
 */
function handleGetAllSessions(req, res) {
  const sessions = Array.from(_sessionIndex.values())
    .sort((a, b) => b.captured_at - a.captured_at)
    .map((r) => ({
      session_id:      r.session_id,
      platform:        r.platform,
      source_url:      r.source_url,
      source_title:    r.source_title,
      captured_at:     r.captured_at,
      files_touched:   r.files_touched,
      turn_count:      r.turn_count,
      context_preview: (r.context || "").slice(0, 200),
    }));

  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ sessions, total: sessions.length }));
}

/**
 * Spawns extractors/conversation_server.py as a subprocess.
 * Payload in via stdin → JSON summary out via stdout.
 */
function _runConversationExtractor(payload) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, "extractors", "conversation_server.py");
    const input      = JSON.stringify(payload);
    // On Windows: try "py" launcher first (ships with Python installer since 3.3),
    // fall back to "python". "python3" is rarely in PATH on Windows.
    // On Unix: "python3" is standard; "python" may be Python 2 on older systems.
    const pythonBin  = process.platform === "win32" ? "py" : "python3";
    const TIMEOUT_MS = 15_000;

    const proc = execFile(
      pythonBin,
      [scriptPath],
      {
        timeout:   TIMEOUT_MS,
        maxBuffer: 512 * 1024, // 512KB — matches conversation_server.py output cap
      },
      (err, stdout, stderr) => {
        if (err) {
          if (err.killed) {
            console.warn(`[session] extractor timed out after ${TIMEOUT_MS / 1000}s — storing minimal record`);
          }
          reject(new Error(`extractor error: ${err.message}\n${stderr}`));
          return;
        }
        try   { resolve(JSON.parse(stdout)); }
        catch { reject(new Error(`extractor bad JSON: ${stdout.slice(0, 200)}`)); }
      }
    );

    proc.stdin.on("error", (err) => {
      // stdin write can fail if the process exits before we finish writing
      // (e.g. Python import error on cold start). The callback above handles it.
      console.debug("[session] extractor stdin error:", err.message);
    });
    proc.stdin.write(input);
    proc.stdin.end();
  });
}

// ─── HTTP Server ──────────────────────────────────────────────────────────────
function createServer() {
  // Allowed origins: extension pages and AI chat sites that host content scripts.
  // Never * — that lets any local webpage read session memory or poison it.
  const ALLOWED_ORIGINS = new Set([
    "https://claude.ai",
    "https://chat.openai.com",
    "https://chatgpt.com",
    "https://gemini.google.com",
    "https://copilot.microsoft.com",
    "https://www.perplexity.ai",
    "https://aistudio.google.com",
  ]);

  function setCorsHeaders(req, res) {
    const origin = req.headers.origin || "";
    // chrome-extension:// origins pass through; listed AI-chat origins pass through.
    // Everything else gets no CORS header → browser blocks it.
    if (origin.startsWith("chrome-extension://") || ALLOWED_ORIGINS.has(origin)) {
      res.setHeader("Access-Control-Allow-Origin",  origin);
      res.setHeader("Vary", "Origin");
    }
    res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token");
  }

  function checkAuth(req, res, beaconToken) {
    const token = store.get("authToken");
    if (!token) return true; // no token configured → open (dev mode)
    if (req.headers["x-auth-token"] === token) return true;
    // sendBeacon cannot set custom headers — accept token from request body
    // only for /collect-conversation (the only beacon-capable route).
    if (beaconToken && beaconToken === token) return true;
    res.writeHead(401, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Unauthorized" }));
    return false;
  }

  // Normalize req.url — strip query strings and trailing slashes so
  // /collect?foo=bar and /collect/ both match correctly.
  function normalizeUrl(url) {
    return (url || "").split("?")[0].replace(/\/+$/, "") || "/";
  }

  const srv = http.createServer((req, res) => {
    setCorsHeaders(req, res);

    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

    const nurl = normalizeUrl(req.url);

    // ── POST /collect ────────────────────────────────────────────────────────
    if (req.method === "POST" && nurl === "/collect") {
      if (!checkAuth(req, res)) return;

      const MAX_BODY = 5 * 1024 * 1024; // 5MB
      const chunks = [];
      let bodySize = 0;
      let bodyRejected = false;

      req.on("data", (c) => {
        bodySize += c.length;
        if (bodySize > MAX_BODY) {
          if (!bodyRejected) {
            bodyRejected = true;
            res.writeHead(413, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Payload too large (max 5MB)" }));
            req.on("error", () => {}); // suppress error after destroy
            req.destroy();
          }
          return;
        }
        chunks.push(c);
      });
      req.on("end", () => {
        if (bodyRejected) return;
        const body = Buffer.concat(chunks).toString("utf8");
        let payload;
        try   { payload = JSON.parse(body); }
        catch {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Invalid JSON" }));
          return;
        }

        if (!payload || !Array.isArray(payload.blocks)) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Payload missing blocks array" }));
          return;
        }

        let saved_to;
        try {
          saved_to = routePayload(payload);
          captureCount++;
          updateTrayMenu();
        } catch (err) {
          console.error("Failed to save payload:", err.message);
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Failed to save payload", details: err.message }));
          return;
        }

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", blocks: payload.blocks.length, saved_to }));
      });
      return;
    }

    // ── POST /collect-conversation ───────────────────────────────────────────
    if (req.method === "POST" && nurl === "/collect-conversation") {
      // Auth check happens after body parse for this route — sendBeacon
      // cannot set headers so beacon requests carry the token in the body.
      // checkAuth is called inside handleCollectConversation after JSON parse.
      const MAX_BODY = 5 * 1024 * 1024;
      const chunks = [];
      let bodySize = 0;
      let bodyRejected = false;

      req.on("data", (c) => {
        bodySize += c.length;
        if (bodySize > MAX_BODY) {
          if (!bodyRejected) {
            bodyRejected = true;
            res.writeHead(413, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Payload too large (max 5MB)" }));
            req.on("error", () => {}); // suppress error after destroy
            req.destroy();
          }
          return;
        }
        chunks.push(c);
      });
      req.on("end", () => {
        if (bodyRejected) return;
        const body = Buffer.concat(chunks).toString("utf8");
        // Wrap in .catch() — an async handler inside req.on('end') that throws
        // produces an unhandled rejection, which crashes the server on Node 15+.
        handleCollectConversation(req, res, body).catch((err) => {
          console.error("[server] unhandled error in handleCollectConversation:", err.message);
          if (!res.headersSent) {
            res.writeHead(500, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Internal server error" }));
          }
        });
      });
      return;
    }

    // ── GET /conversation-capture ────────────────────────────────────────────
    // The extension asks this before reading any conversation off a page.
    if (req.method === "GET" && nurl === "/conversation-capture") {
      if (!checkAuth(req, res)) return;
      const sites = { ...CONVERSATION_SITES_DEFAULT, ...(store.get("conversationSites") || {}) };
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ enabled: !!store.get("captureConversations"), sites }));
      return;
    }

    // ── GET /context/session/all ─────────────────────────────────────────────
    // Must be checked before /context/session to avoid prefix collision
    if (req.method === "GET" && nurl === "/context/session/all") {
      if (!checkAuth(req, res)) return;
      handleGetAllSessions(req, res);
      return;
    }

    // ── GET /context/session ─────────────────────────────────────────────────
    if (req.method === "GET" && nurl.startsWith("/context/session")) {
      if (!checkAuth(req, res)) return;
      const urlParams = new URLSearchParams((req.url.split("?")[1] || ""));
      handleGetSessionContext(req, res, urlParams);
      return;
    }

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found" }));
  });

  // Track open sockets so stopServer() can destroy them immediately
  // instead of waiting for keep-alive connections to idle out.
  srv.on("connection", (socket) => {
    _activeSockets.add(socket);
    socket.once("close", () => _activeSockets.delete(socket));
  });

  return srv;
}

function startServer() {
  if (serverRunning) return;
  server = createServer();
  server.listen(store.get("serverPort"), "127.0.0.1", () => {
    serverRunning    = true;
    serverRetryCount = 0;
    updateTrayIcon(true);
    updateTrayMenu();
  });
  server.on("error", (err) => {
    console.error("Server error:", err.message);
    serverRunning = false;
    updateTrayIcon(false);
    updateTrayMenu();

    const recoverableErrors = ["EMFILE", "ENFILE", "ENOMEM", "ENOBUFS"];
    if (recoverableErrors.includes(err.code) && serverRetryCount < MAX_SERVER_RETRIES) {
      serverRetryCount++;
      const delay = Math.min(1000 * Math.pow(2, serverRetryCount), 30_000);
      console.log(`Attempting server restart ${serverRetryCount}/${MAX_SERVER_RETRIES} in ${delay / 1000}s…`);
      setTimeout(startServer, delay);
    } else if (err.code === "EADDRINUSE") {
      console.error(`Port ${store.get("serverPort")} is in use. Change the port in settings.`);
    } else {
      console.error(`Server failed to start after ${MAX_SERVER_RETRIES} attempts.`);
    }
  });
}

function stopServer() {
  if (!server || !serverRunning) return;
  serverRunning = false;
  updateTrayIcon(false);
  updateTrayMenu();
  // Destroy open keep-alive sockets so server.close() resolves immediately
  for (const socket of _activeSockets) socket.destroy();
  _activeSockets.clear();
  server.close(() => { server = null; });
}

// ─── Tray ─────────────────────────────────────────────────────────────────────
function updateTrayIcon(on) {
  if (!tray) return;
  try { tray.setImage(nativeImage.createFromPath(iconPath(on))); } catch (err) { console.debug("Tray image load error", err.message); }
  tray.setToolTip(on ? `Code Collector — running · ${captureCount} captured` : "Code Collector — stopped");
}

function updateTrayMenu() {
  if (!tray) return;
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: serverRunning ? "🟢  Collector running" : "🔴  Collector stopped", enabled: false },
    { label: `${captureCount} capture${captureCount !== 1 ? "s" : ""} this session`, enabled: false },
    { type: "separator" },
    { label: serverRunning ? "Stop Collector" : "Start Collector",
      click: () => serverRunning ? stopServer() : startServer() },
    { type: "separator" },
    { label: "Open Primary Folder", click: () => shell.openPath(store.get("primaryDir")) },
    { label: "Open Archive Folder", click: () => shell.openPath(store.get("archiveDir")) },
    { type: "separator" },
    { label: "Settings…", click: openSettings },
    { type: "separator" },
    { label: "Quit Code Collector", click: () => app.quit() },
  ]));
}

// ─── Settings window ──────────────────────────────────────────────────────────
function openSettings() {
  if (settingsWindow) { settingsWindow.focus(); return; }
  settingsWindow = new BrowserWindow({
    width: 580, height: 680, resizable: false,
    title: "Code Collector — Settings",
    backgroundColor: "#0d0d0d",
    webPreferences: {
      preload:          path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration:  false,
    },
  });
  settingsWindow.loadFile(path.join(__dirname, "settings.html"));
  settingsWindow.setMenuBarVisibility(false);
  settingsWindow.on("closed", () => { settingsWindow = null; });
}

// ─── IPC ──────────────────────────────────────────────────────────────────────
ipcMain.handle("get-settings",      () => store.store);
ipcMain.handle("get-server-status", () => ({ running: serverRunning, port: store.get("serverPort"), captureCount }));
ipcMain.handle("toggle-server",     () => { serverRunning ? stopServer() : startServer(); });

let serverRestartTimeout = null;
// Known-good settings keys. Anything not in this set is silently dropped.
const SETTINGS_SCHEMA = {
  primaryDir:        (v) => typeof v === "string",
  secondaryDir:      (v) => typeof v === "string",
  archiveDir:        (v) => typeof v === "string",
  cloudDir:          (v) => typeof v === "string",
  cloudEnabled:      (v) => typeof v === "boolean",
  authToken:         (v) => typeof v === "string" && v.length < 512,
  serverPort:        (v) => Number.isInteger(v) && v >= 1024 && v <= 65535,
  startOnLogin:      (v) => typeof v === "boolean",
  saveToArchive:     (v) => typeof v === "boolean",
  cpuLimiterEnabled: (v) => typeof v === "boolean",
  captureConversations: (v) => typeof v === "boolean",
  conversationSites: (v) => !!v && typeof v === "object" && !Array.isArray(v) &&
    Object.entries(v).every(([k, on]) => k in CONVERSATION_SITES_DEFAULT && typeof on === "boolean"),
};

ipcMain.handle("save-settings", (_e, updated) => {
  if (!updated || typeof updated !== "object") return { ok: false, error: "Invalid payload" };

  const oldPort     = store.get("serverPort");
  const portChanged = updated.serverPort && updated.serverPort !== oldPort;

  if (serverRestartTimeout) { clearTimeout(serverRestartTimeout); serverRestartTimeout = null; }

  // Only write keys that exist in schema and pass type validation.
  // Unknown or malformed keys are silently dropped — no arbitrary store pollution.
  let rejected = 0;
  Object.entries(updated).forEach(([k, v]) => {
    const validate = SETTINGS_SCHEMA[k];
    if (validate && validate(v)) {
      store.set(k, v);
    } else {
      rejected++;
      console.warn(`[settings] rejected key '${k}' — unknown or invalid value`);
    }
  });
  if (rejected) console.warn(`[settings] ${rejected} key(s) rejected from save-settings IPC call`);

  if (portChanged) {
    stopServer();
    serverRestartTimeout = setTimeout(() => { serverRestartTimeout = null; startServer(); }, 1000);
  }

  app.setLoginItemSettings({ openAtLogin: !!store.get("startOnLogin") });
  return { ok: true };
});

// Valid keys for pick-directory — only directory-type settings are allowed.
// Passing "authToken" or any other key would leak sensitive data as defaultPath.
const ALLOWED_DIR_KEYS = new Set(["primaryDir", "secondaryDir", "archiveDir", "cloudDir"]);

ipcMain.handle("pick-directory", async (_e, key) => {
  const safeKey = ALLOWED_DIR_KEYS.has(key) ? key : null;
  const r = await dialog.showOpenDialog(settingsWindow, {
    properties:  ["openDirectory", "createDirectory"],
    defaultPath: (safeKey ? store.get(safeKey) : null) || app.getPath("documents"),
  });
  return r.canceled ? null : (r.filePaths[0] || null);
});

ipcMain.handle("pick-file", async () => {
  const r = await dialog.showOpenDialog(settingsWindow, {
    properties: ["openFile"],
    filters: [
      { name: "Text/Code files", extensions: ["txt","md","json","js","ts","py","java","cpp","c","h","go","rs","sh","html","css","yaml","yml"] },
      { name: "All files", extensions: ["*"] },
    ],
  });
  return r.canceled ? null : (r.filePaths[0] || null);
});

ipcMain.handle("pick-folder", async () => {
  const r = await dialog.showOpenDialog(settingsWindow, { properties: ["openDirectory"] });
  return r.canceled ? null : (r.filePaths[0] || null);
});

ipcMain.handle("scan-file",   async (_e, filePath)   => { try { return scanFileForCode(filePath);   } catch (err) { return { error: err.message, errorType: "scan_error" }; } });
ipcMain.handle("scan-folder", async (_e, folderPath) => { try { return await scanFolderForCode(folderPath); } catch (err) { return { error: err.message, errorType: "scan_error" }; } });

// ─── Preflight checks ─────────────────────────────────────────────────────────
// Runs once at startup. Logs warnings for missing assets/extractor but never
// blocks launch — the app degrades gracefully rather than refusing to start.
function _runPreflight() {
  const warnings = [];

  // Icon assets
  const iconFiles = ["icon-active.png", "icon-inactive.png"];
  for (const f of iconFiles) {
    if (!fs.existsSync(path.join(ASSETS, f))) {
      warnings.push(`Missing tray icon: assets/${f} — tray may show a blank icon.`);
    }
  }

  // Python extractor
  const extractorPath = path.join(__dirname, "extractors", "conversation_server.py");
  if (!fs.existsSync(extractorPath)) {
    warnings.push("Missing extractors/conversation_server.py — session memory will degrade to minimal records.");
  }

  // Primary save directory writable
  const primaryDir = store.get("primaryDir");
  if (primaryDir) {
    try {
      fs.mkdirSync(primaryDir, { recursive: true });
      fs.accessSync(primaryDir, fs.constants.W_OK);
    } catch {
      warnings.push(`Primary directory not writable: ${primaryDir}`);
    }
  }

  // Port sanity
  const port = store.get("serverPort");
  if (!port || port < 1024 || port > 65535) {
    warnings.push(`Invalid server port ${port} — defaulting to 8765.`);
    store.set("serverPort", 8765);
  }

  if (warnings.length) {
    console.warn("[preflight] Startup warnings:");
    warnings.forEach((w) => console.warn("  !", w));
  } else {
    console.log("[preflight] All checks passed.");
  }

  return warnings;
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  _initStorePathDefaults();  // resolve path-based defaults now that app is ready
  _runPreflight();           // log any asset/extractor/directory warnings
  if (process.platform === "darwin") app.dock.hide();
  tray = new Tray(nativeImage.createFromPath(iconPath(false)));
  updateTrayMenu();
  loadSessionIndex();
  startServer();
  app.setLoginItemSettings({ openAtLogin: !!store.get("startOnLogin") });
});

app.on("window-all-closed", (e) => e.preventDefault());
app.on("before-quit", stopServer);

// ─── Exports for the test suites ──────────────────────────────────────────────
// test/main.test.js and test/torture.test.js require these. The March 23 build
// had no exports, so 130 of its 167 tests could not reach the code they test.
module.exports = {
  scanFileForCode,
  scanFolderForCode,
  buildSmartFilename,
  routePayload,
  isTextFile,
  _isSafePath: isSafePath,
  store,
  conversationCaptureAllowed,
  writeConversationTranscript,
};
