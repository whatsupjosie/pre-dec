/**
 * session_endpoints.js
 * ════════════════════
 * Add these endpoints to main.js (your Electron HTTP server).
 *
 * Three new routes:
 *
 *   POST /collect-conversation
 *     Receives raw turns from claude_scraper.js (via sendBeacon on unload).
 *     Runs the Python conversation extractor.
 *     Stores the session summary in the index.
 *
 *   GET /context/session?platform=claude
 *     Returns the most recent session summary for the given platform.
 *     Called by background.js when a new Claude tab opens.
 *     Response: { context: "WHAT WAS BUILT\n  • ...\n\nDECISIONS..." }
 *
 *   GET /context/session/all
 *     Returns all stored session summaries (for the UI / history view).
 *
 * HOW TO ADD TO main.js:
 *   1. Copy the SESSION INDEX section into module scope (near your other state)
 *   2. Copy the three route handlers into your request router
 *   3. Copy the _runConversationExtractor helper into module scope
 *   4. Make sure `spawn` or `execFile` from child_process is imported
 *
 * Rear View Foresight LLC — Feic Mo Chroí
 */

"use strict";

// ══════════════════════════════════════════════════════════════════════════════
// SESSION INDEX — paste into module scope in main.js
// ══════════════════════════════════════════════════════════════════════════════

// In-memory session index — survives as long as the tray app runs.
// Tier 2 replaces this with SQLite. Same interface.
const _sessionIndex = new Map();   // session_id → SessionRecord
const _latestByPlatform = new Map(); // platform → session_id

/**
 * @typedef {Object} SessionRecord
 * @property {string}   session_id
 * @property {string}   platform
 * @property {string}   source_url
 * @property {string}   source_title
 * @property {number}   captured_at   — unix timestamp
 * @property {string}   context       — the formatted context block text
 * @property {string[]} files_touched
 * @property {number}   turn_count
 */


// ══════════════════════════════════════════════════════════════════════════════
// ROUTE: POST /collect-conversation
// ══════════════════════════════════════════════════════════════════════════════

async function handleCollectConversation(req, res, body) {
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    res.writeHead(400);
    res.end(JSON.stringify({ error: "Invalid JSON" }));
    return;
  }

  const {
    session_id,
    platform     = "claude",
    source_url   = "",
    source_title = "Claude",
    turns        = [],
  } = payload;

  if (!turns.length) {
    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, skipped: "no turns" }));
    return;
  }

  try {
    // Run the Python extractor to produce the summary
    const summary = await _runConversationExtractor({
      session_id,
      platform,
      source_url,
      source_title,
      turns,
    });

    // Store in index
    const record = {
      session_id:   summary.session_id,
      platform:     summary.platform,
      source_url:   summary.source_url,
      source_title: summary.source_title,
      captured_at:  Date.now() / 1000,
      context:      summary.context,
      files_touched: summary.files_touched || [],
      turn_count:   summary.turn_count || turns.length,
    };

    _sessionIndex.set(session_id, record);
    _latestByPlatform.set(platform, session_id);

    console.log(
      `[session] stored ${session_id} (${platform}) — ` +
      `${turns.length} turns, ${record.files_touched.length} files`
    );

    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, session_id }));

  } catch (err) {
    console.error("[session] extractor failed:", err.message);
    // Store a minimal record even if extractor fails
    _sessionIndex.set(session_id, {
      session_id,
      platform,
      source_url,
      source_title,
      captured_at: Date.now() / 1000,
      context:     `Session captured — ${turns.length} turns\nSource: ${source_url}`,
      files_touched: [],
      turn_count:  turns.length,
    });
    _latestByPlatform.set(platform, session_id);

    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, session_id, warning: "extractor failed, minimal record stored" }));
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// ROUTE: GET /context/session
// ══════════════════════════════════════════════════════════════════════════════

function handleGetSessionContext(req, res, urlParams) {
  const platform = urlParams.get("platform") || "claude";
  const sessionId = _latestByPlatform.get(platform);

  if (!sessionId) {
    res.writeHead(200);
    res.end(JSON.stringify({ context: null, message: "no prior session" }));
    return;
  }

  const record = _sessionIndex.get(sessionId);
  if (!record) {
    res.writeHead(200);
    res.end(JSON.stringify({ context: null, message: "session not found" }));
    return;
  }

  // Don't surface context older than 7 days
  const ageHours = (Date.now() / 1000 - record.captured_at) / 3600;
  if (ageHours > 168) {
    res.writeHead(200);
    res.end(JSON.stringify({ context: null, message: "session too old" }));
    return;
  }

  res.writeHead(200);
  res.end(JSON.stringify({
    context:      record.context,
    session_id:   record.session_id,
    source_url:   record.source_url,
    captured_at:  record.captured_at,
    files_touched: record.files_touched,
    age_hours:    Math.round(ageHours * 10) / 10,
  }));
}


// ══════════════════════════════════════════════════════════════════════════════
// ROUTE: GET /context/session/all
// ══════════════════════════════════════════════════════════════════════════════

function handleGetAllSessions(req, res) {
  const sessions = Array.from(_sessionIndex.values())
    .sort((a, b) => b.captured_at - a.captured_at)
    .map((r) => ({
      session_id:   r.session_id,
      platform:     r.platform,
      source_url:   r.source_url,
      source_title: r.source_title,
      captured_at:  r.captured_at,
      files_touched: r.files_touched,
      turn_count:   r.turn_count,
      context_preview: r.context.slice(0, 200),
    }));

  res.writeHead(200);
  res.end(JSON.stringify({ sessions, total: sessions.length }));
}


// ══════════════════════════════════════════════════════════════════════════════
// HELPER: _runConversationExtractor
// Calls extractors/conversation.py as a subprocess
// ══════════════════════════════════════════════════════════════════════════════

const { execFile } = require("child_process");
const path = require("path");

function _runConversationExtractor(payload) {
  return new Promise((resolve, reject) => {
    // Path to the extractor script — adjust to match your project layout
    const scriptPath = path.join(__dirname, "extractors", "conversation_server.py");
    const input = JSON.stringify(payload);

    const proc = execFile(
      "python3",
      [scriptPath],
      { timeout: 10000 },
      (err, stdout, stderr) => {
        if (err) {
          reject(new Error(`extractor error: ${err.message}\n${stderr}`));
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error(`extractor bad JSON: ${stdout.slice(0, 200)}`));
        }
      }
    );

    // Send payload via stdin
    proc.stdin.write(input);
    proc.stdin.end();
  });
}


// ══════════════════════════════════════════════════════════════════════════════
// WIRE INTO YOUR ROUTER — paste into your existing request handler
// ══════════════════════════════════════════════════════════════════════════════
//
// In your main.js request handler (the function passed to http.createServer),
// add these cases:
//
//   if (req.method === "POST" && req.url === "/collect-conversation") {
//     return handleCollectConversation(req, res, body);
//   }
//
//   if (req.method === "GET" && req.url.startsWith("/context/session/all")) {
//     return handleGetAllSessions(req, res);
//   }
//
//   if (req.method === "GET" && req.url.startsWith("/context/session")) {
//     const urlParams = new URLSearchParams(req.url.split("?")[1] || "");
//     return handleGetSessionContext(req, res, urlParams);
//   }
//
// ══════════════════════════════════════════════════════════════════════════════

module.exports = {
  handleCollectConversation,
  handleGetSessionContext,
  handleGetAllSessions,
};
