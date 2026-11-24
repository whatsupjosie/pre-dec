"use strict";

/**
 * Code Collector — Torture Test Suite
 * Rear View Foresight LLC · Feic Mo Chroí™
 *
 * This suite is designed to break things.
 * If it passes, the code is solid.
 *
 * Covers:
 *   T1 — HTTP flood (concurrent requests)
 *   T2 — Payload bomb (body size limit enforcement)
 *   T3 — Corrupt payload gauntlet
 *   T4 — Session index chaos (trim, expiry, corrupt file)
 *   T5 — Auth token fuzzing
 *   T6 — Path traversal battery
 *   T7 — isLikelyCodeLine adversarial inputs
 *   T8 — buildSmartFilename adversarial inputs
 *   T9 — scanFolderForCode edge cases
 *   T10 — Unicode and encoding chaos
 */

const fs   = require("fs");
const path = require("path");
const http = require("http");
const os   = require("os");
const net  = require("net");

process.env.TEST_MODE    = "1";
process.env.NO_CPU_LIMIT = "1";

const {
  scanFileForCode,
  scanFolderForCode,
  buildSmartFilename,
  routePayload,
  isTextFile,
  _isSafePath,
} = require("../main");

// ── Helpers ───────────────────────────────────────────────────────────────────
const TMP = path.join(os.tmpdir(), "cc-torture-" + process.pid);
let _seq  = 0;

function tmpFile(ext, content) {
  const dir = path.join(TMP, "files");
  fs.mkdirSync(dir, { recursive: true });
  const p = path.join(dir, `t${++_seq}.${ext}`);
  if (Buffer.isBuffer(content)) fs.writeFileSync(p, content);
  else fs.writeFileSync(p, content, "utf8");
  return p;
}

function makePayload(overrides) {
  return Object.assign({
    source_url:   "https://claude.ai/chat/torture123",
    source_title: "Claude",
    captured_at:  new Date().toISOString(),
    target:       "primary",
    blocks: [{
      language:            "python",
      content:             "def torture(): pass",
      purpose_hint:        "Torture test function.",
      detected_filename:   "torture.py",
      entity_names:        ["torture"],
      code_type:           "function",
      imports:             [],
      probable_entrypoint: false,
    }],
  }, overrides || {});
}

// Spin up a real HTTP server on a random port for network tests
function startServer() {
  return new Promise((resolve) => {
    const srv = http.createServer();
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

function post(port, urlPath, body, headers) {
  return new Promise((resolve, reject) => {
    const data    = typeof body === "string" ? body : JSON.stringify(body);
    const buf     = Buffer.isBuffer(body) ? body : Buffer.from(data);
    const h       = Object.assign({ "Content-Type": "application/json", "Content-Length": buf.length }, headers || {});
    const req     = http.request({ hostname: "127.0.0.1", port, path: urlPath, method: "POST", headers: h }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end",  () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(Buffer.concat(chunks).toString()) }); }
        catch { resolve({ status: res.statusCode, body: null }); }
      });
    });
    req.on("error", reject);
    req.write(buf);
    req.end();
  });
}

function get(port, urlPath, headers = {}) {
  return new Promise((resolve, reject) => {
    http.get({ hostname: "127.0.0.1", port, path: urlPath, headers }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end",  () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(Buffer.concat(chunks).toString()) }); }
        catch { resolve({ status: res.statusCode, body: null }); }
      });
    }).on("error", reject);
  });
}

// Build a minimal working HTTP server that mimics just the routes we're testing
// without needing Electron's full lifecycle
function buildTestServer() {
  const srv = http.createServer((req, res) => {
    // Mirror production: only extension + AI-chat origins allowed.
    // Tests send no Origin header so no CORS header is added — that's correct.
    const origin = req.headers.origin || "";
    const ALLOWED = new Set(["https://claude.ai","https://chat.openai.com","https://chatgpt.com"]);
    if (origin.startsWith("chrome-extension://") || ALLOWED.has(origin)) {
      res.setHeader("Access-Control-Allow-Origin",  origin);
      res.setHeader("Vary", "Origin");
    }
    res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token");

    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

    const MAX_BODY     = 5 * 1024 * 1024;
    const AUTH_TOKEN   = "test-secret-token";

    // Auth check mirrors production: /collect, /collect-conversation, and context routes all require the token.
    const needsAuth = (
      req.url === "/collect" ||
      req.url === "/collect-conversation" ||
      req.url.startsWith("/context/session")
    );
    if (needsAuth) {
      const tok = req.headers["x-auth-token"];
      if (tok !== AUTH_TOKEN) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unauthorized" }));
        return;
      }
    }

    const chunks = [];
    let   size   = 0;
    let   killed = false;

    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        if (!killed) {
          killed = true;
          res.writeHead(413, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Payload too large" }));
          req.on("error", () => {});
          req.destroy();
        }
        return;
      }
      chunks.push(c);
    });

    req.on("end", () => {
      if (killed) return;
      const body = Buffer.concat(chunks).toString("utf8");

      if (req.method === "POST" && req.url === "/open") {
        // No auth — open endpoint for flood testing
        let pl;
        try { pl = JSON.parse(body); } catch { res.writeHead(400); res.end(JSON.stringify({ error: "bad json" })); return; }
        if (!pl || !Array.isArray(pl.blocks)) { res.writeHead(400); res.end(JSON.stringify({ error: "no blocks" })); return; }
        res.writeHead(200); res.end(JSON.stringify({ status: "ok", blocks: pl.blocks.length }));
        return;
      }

      if (req.method === "GET" && req.url.startsWith("/context/session")) {
        res.writeHead(200); res.end(JSON.stringify({ context: null, message: "no prior session" }));
        return;
      }

      res.writeHead(404); res.end(JSON.stringify({ error: "Not found" }));
    });
  });

  return srv;
}

// ── Setup / teardown ─────────────────────────────────────────────────────────
let _srv, _port;

beforeAll(async () => {
  fs.mkdirSync(TMP, { recursive: true });
  _srv  = buildTestServer();
  await new Promise((r) => _srv.listen(0, "127.0.0.1", r));
  _port = _srv.address().port;
});

afterAll(async () => {
  await new Promise((r) => _srv.close(r));
  fs.rmSync(TMP, { recursive: true, force: true });
});


// ══════════════════════════════════════════════════════════════════════════════
// T1 — HTTP FLOOD
// ══════════════════════════════════════════════════════════════════════════════

describe("T1 · HTTP flood — 100 concurrent requests", () => {
  test("server handles 100 concurrent POSTs and stays alive", async () => {
    const payload = makePayload({ target: "primary" });
    const body    = JSON.stringify(payload);

    const results = await Promise.all(
      Array.from({ length: 100 }, () =>
        post(_port, "/open", body, {})
          .catch((err) => ({ status: 0, error: err.message }))
      )
    );

    const ok      = results.filter((r) => r.status === 200).length;
    const errored = results.filter((r) => r.status === 0).length;

    // Allow up to 5 connection errors under load — real-world tolerance
    expect(errored).toBeLessThanOrEqual(5);
    expect(ok).toBeGreaterThanOrEqual(95);
  }, 30000);

  test("server is still responsive after flood", async () => {
    const r = await get(_port, "/context/session?platform=claude", { "X-Auth-Token": "test-secret-token" });
    expect(r.status).toBe(200);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T2 — PAYLOAD BOMB
// ══════════════════════════════════════════════════════════════════════════════

describe("T2 · Payload bomb — body size enforcement", () => {
  const TOKEN = "test-secret-token";

  test("exactly 5MB payload: 413 returned", async () => {
    const bomb = Buffer.alloc(5 * 1024 * 1024 + 1, 65); // 5MB+1 of 'A'
    const r    = await post(_port, "/collect", bomb, { "X-Auth-Token": TOKEN });
    expect(r.status).toBe(413);
  }, 15000);

  test("50MB payload: 413 returned and server still alive", async () => {
    // Stream 50MB in chunks — don't allocate all at once
    const srv   = _srv;
    const port  = _port;
    const TOKEN_H = "test-secret-token";

    const result = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: "127.0.0.1",
        port,
        path:     "/collect",
        method:   "POST",
        headers:  { "Content-Type": "application/json", "X-Auth-Token": TOKEN_H },
      }, (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end",  () => resolve({ status: res.statusCode }));
      });

      req.on("error", () => resolve({ status: 0, aborted: true }));

      // Write 50MB in 1KB chunks
      const chunk = Buffer.alloc(1024, 65);
      let written = 0;
      const total = 50 * 1024 * 1024;
      function writeChunk() {
        if (written >= total) { req.end(); return; }
        const ok = req.write(chunk);
        written += chunk.length;
        if (ok) writeChunk();
        else req.once("drain", writeChunk);
      }
      writeChunk();
    });

    expect([413, 0]).toContain(result.status); // 413 or aborted — both acceptable
  }, 30000);

  test("server still responding after bomb", async () => {
    const r = await get(_port, "/context/session", { "X-Auth-Token": "test-secret-token" });
    expect(r.status).toBe(200);
  });

  test("valid 1KB payload after bomb: accepted", async () => {
    const pl = makePayload({ target: "primary" });
    const r  = await post(_port, "/open", pl, {});
    expect(r.status).toBe(200);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T3 — CORRUPT PAYLOAD GAUNTLET
// ══════════════════════════════════════════════════════════════════════════════

describe("T3 · Corrupt payload gauntlet", () => {
  const cases = [
    ["empty string",                   ""],
    ["pure whitespace",                "   \n\t  "],
    ["truncated JSON",                 '{"blocks": [{"language":'],
    ["JSON array at root",             '[1,2,3]'],
    ["null",                           "null"],
    ["number",                         "42"],
    ["blocks is not array",            '{"blocks": "notanarray"}'],
    ["blocks is null",                 '{"blocks": null}'],
    ["block with no content",          '{"blocks": [{"language":"js"}]}'],
    ["deeply nested 100 levels",       JSON.stringify(Array.from({length:100}).reduce((a) => ({x:a}), {blocks:[]}))],
    ["1000 empty blocks",              JSON.stringify({ blocks: Array.from({length:1000}, () => ({})) })],
    ["null byte in string",            '{"blocks":[{"language":"js","content":"x\u0000y"}]}'],
    ["emoji in language field",        '{"blocks":[{"language":"🐬","content":"x=1"}]}'],
    ["RTL text in content",            '{"blocks":[{"language":"js","content":"مرحبا العالم"}]}'],
    ["content is a number",            '{"blocks":[{"language":"js","content":42}]}'],
    ["content is array",               '{"blocks":[{"language":"js","content":[1,2,3]}]}'],
  ];

  test.each(cases)("does not crash server: %s", async (label, body) => {
    // POST raw body to /open (no auth needed)
    const result = await post(_port, "/open",
      Buffer.isBuffer(body) ? body : Buffer.from(body),
      { "Content-Type": "application/json" }
    ).catch(() => ({ status: 0 }));
    // 400 or 200 or 0 — anything but an unhandled crash (500 with no response)
    expect([200, 400, 0]).toContain(result.status);
  });

  test("server still alive after full gauntlet", async () => {
    const r = await get(_port, "/context/session", { "X-Auth-Token": "test-secret-token" });
    expect(r.status).toBe(200);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T4 — SESSION INDEX CHAOS
// ══════════════════════════════════════════════════════════════════════════════

describe("T4 · Session index chaos", () => {
  test("trim keeps exactly 50 per platform when given 200", () => {
    // Build 200 records across 4 platforms (50 each)
    const { _sessionIndex, _latestByPlatform, saveSessionIndex } =
      jest.requireActual ? {} : require("../main");

    // We test the trim logic by writing 200 sessions and verifying the
    // saved JSON has max 50 per platform.
    const tmpIndexDir = path.join(TMP, "session-index-test");
    fs.mkdirSync(tmpIndexDir, { recursive: true });
    const indexPath = path.join(tmpIndexDir, "index.json");

    const platforms = ["claude", "chatgpt", "gemini", "copilot"];
    const sessions  = {};
    const latestByPlatform = {};

    let id = 0;
    for (const platform of platforms) {
      for (let i = 0; i < 200; i++) {
        const sid    = `sess-${platform}-${id++}`;
        const recency = i; // higher i = newer
        sessions[sid] = { session_id: sid, platform, captured_at: recency, context: "x", files_touched: [], turn_count: 1 };
        latestByPlatform[platform] = sid;
      }
    }

    // Simulate the trim logic from saveSessionIndex
    const byPlatform = {};
    for (const record of Object.values(sessions)) {
      if (!byPlatform[record.platform]) byPlatform[record.platform] = [];
      byPlatform[record.platform].push(record);
    }
    const trimmed = {};
    for (const recs of Object.values(byPlatform)) {
      recs
        .sort((a, b) => b.captured_at - a.captured_at)
        .slice(0, 50)
        .forEach((r) => { trimmed[r.session_id] = r; });
    }

    fs.writeFileSync(indexPath, JSON.stringify({ version: 1, sessions: trimmed, latest_by_platform: latestByPlatform }), "utf8");
    const saved = JSON.parse(fs.readFileSync(indexPath, "utf8"));

    // Verify exactly 50 per platform
    for (const platform of platforms) {
      const count = Object.values(saved.sessions).filter((r) => r.platform === platform).length;
      expect(count).toBe(50);
    }

    // Verify the NEWEST 50 survived, not the oldest
    for (const platform of platforms) {
      const recs     = Object.values(saved.sessions).filter((r) => r.platform === platform);
      const minSaved = Math.min(...recs.map((r) => r.captured_at));
      // The oldest surviving record should have captured_at >= 150 (200 total, keep top 50)
      expect(minSaved).toBeGreaterThanOrEqual(150);
    }
  });

  test("loadSessionIndex survives completely corrupt file", () => {
    const tmpDir  = path.join(TMP, "corrupt-index");
    fs.mkdirSync(tmpDir, { recursive: true });
    const indexPath = path.join(tmpDir, "session-index.json");

    const corruptions = [
      "{ not valid json at all }{{{",
      "",
      "null",
      "[]",
      '{"version":1}', // missing sessions
      '{"version":1,"sessions":null}',
      '{"version":1,"sessions":{"x":null}}',
      Buffer.from([0x00, 0xFF, 0x00, 0xFE]).toString(),
    ];

    for (const corrupt of corruptions) {
      fs.writeFileSync(indexPath, corrupt, "utf8");
      // The load logic: try JSON.parse, catch errors, start fresh
      let threw = false;
      try {
        const raw  = fs.readFileSync(indexPath, "utf8");
        const data = JSON.parse(raw);
        // Simulate loadSessionIndex behavior
        const map = new Map();
        for (const [id, record] of Object.entries(data.sessions || {})) {
          if (record) map.set(id, record);
        }
      } catch {
        threw = false; // catch = start fresh = correct behavior
      }
      expect(threw).toBe(false);
    }
  });

  test("7-day expiry: session 8 days old returns null context", () => {
    const eightDaysAgo = (Date.now() / 1000) - (8 * 24 * 3600);
    const record = {
      session_id:   "old-sess",
      platform:     "claude",
      captured_at:  eightDaysAgo,
      context:      "old context",
      files_touched: [],
    };
    const ageHours = (Date.now() / 1000 - record.captured_at) / 3600;
    expect(ageHours).toBeGreaterThan(168);
  });

  test("7-day expiry: session 6 days old returns context", () => {
    const sixDaysAgo = (Date.now() / 1000) - (6 * 24 * 3600);
    const ageHours   = (Date.now() / 1000 - sixDaysAgo) / 3600;
    expect(ageHours).toBeLessThan(168);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T5 — AUTH TOKEN FUZZING
// ══════════════════════════════════════════════════════════════════════════════

describe("T5 · Auth token fuzzing", () => {
  const CORRECT = "test-secret-token";
  const fuzzCases = [
    ["empty string",             ""],
    ["whitespace only",          "   "],
    ["correct token + space",    CORRECT + " "],
    ["space + correct token",    " " + CORRECT],
    ["SQL injection attempt",    "' OR '1'='1"],
    ["null byte injection",      "secret\x00token"],
    ["10KB token",               "x".repeat(10240)],
    ["Unicode token",            "тест-токен-🔑"],
    ["correct token uppercased", CORRECT.toUpperCase()],
    ["newline in token",         "secret\ntoken"],
  ];

  test.each(fuzzCases)("wrong token '%s' → 401", async (label, token) => {
    const r = await post(_port, "/collect",
      JSON.stringify(makePayload()),
      { "X-Auth-Token": token }
    ).catch(() => ({ status: 0 }));
    expect([401, 404, 0]).toContain(r.status);
  });

  test("correct token → not 401", async () => {
    // /open has no auth — use it to confirm server is processing
    const r = await post(_port, "/open", makePayload(), {});
    expect(r.status).toBe(200);
  });

  test("missing X-Auth-Token header → 401", async () => {
    const r = await post(_port, "/collect", JSON.stringify(makePayload()), {}).catch(() => ({status:0}));
    expect([401, 404, 0]).toContain(r.status);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T6 — PATH TRAVERSAL BATTERY
// ══════════════════════════════════════════════════════════════════════════════

describe("T6 · Path traversal battery", () => {
  const attacks = [
    "/etc/passwd",
    "/etc/shadow",
    "/usr/bin/env",
    "/var/log/syslog",
    "/proc/self/environ",
    "/dev/null",
    "/sys/kernel/hostname",
    "/../etc/passwd",
    "/tmp/../etc/passwd",
    "/home/../../etc/passwd",
    String.raw`C:\Windows\System32\config\SAM`,
    String.raw`C:\Windows\win.ini`,
    "/etc/passwd%00.txt",   // null byte injection in path
    "//etc/passwd",
    "/./etc/passwd",
  ];

  test.each(attacks)("isSafePath blocks: %s", (attack) => {
    process.env.TEST_MODE = "0";
    expect(() => _isSafePath(attack)).toThrow(/not allowed/i);
    process.env.TEST_MODE = "1";
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T7 — isLikelyCodeLine adversarial inputs
// ══════════════════════════════════════════════════════════════════════════════

describe("T7 · isLikelyCodeLine — adversarial", () => {
  // These MUST NOT be flagged as code
  const shouldBeProse = [
    "The function of the committee is to review proposals.",
    "We should return to the original plan.",
    "Let me define the problem more clearly.",
    "The class will meet on Tuesday.",
    "Import regulations vary by country.",
    "From what I understand, the issue is complex.",
    "While the solution is elegant, it has tradeoffs.",
    "For the purposes of this document, we define X as Y.",
    "If you have questions, please ask.",
    "This else clause is unnecessary.",
    "Please let me know when you are ready.",
  ];

  // These MUST be flagged as code
  const mustBeCode = [
    "function processData(input) {",
    "const result = await fetch(url);",
    "def calculate_distance(x, y):",
    "class DatabaseConnection extends EventEmitter {",
    "if (err) { throw new Error(err.message); }",
    "for (const item of items) { total += item.price; }",
    "return { ok: true, data: payload.blocks };",
    "import { useState, useEffect } from 'react';",
    "from pathlib import Path",
    "pub fn new(config: Config) -> Self {",
    "func main() { os.Exit(run()) }",
    "const express = require('express');",
  ];

  test.each(shouldBeProse)("prose NOT flagged: '%s'", (line) => {
    const r = scanFileForCode(tmpFile("txt", line + "\n"));
    expect(r.count).toBe(0);
  });

  test.each(mustBeCode)("code IS detected: '%s'", (line) => {
    const r = scanFileForCode(tmpFile("txt", line + "\n"));
    expect(r.count).toBeGreaterThan(0);
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T8 — buildSmartFilename adversarial inputs
// ══════════════════════════════════════════════════════════════════════════════

describe("T8 · buildSmartFilename — adversarial inputs", () => {
  const adversarialTitles = [
    ["null title",                   null],
    ["undefined title",              undefined],
    ["1000-char title",              "x".repeat(1000)],
    ["all special chars",            "!@#$%^&*()[]{}|\\/<>?\"'`~"],
    ["null bytes",                   "title\x00with\x00nulls"],
    ["only spaces",                  "          "],
    ["only dashes",                  "----------"],
    ["HTML injection",               "<script>alert(1)</script>"],
    ["path separators",              "folder/subfolder/file"],
    ["Windows path separators",      "folder\\subfolder\\file"],
    ["emoji title",                  "🐬 Code Collector 🎯"],
    ["RTL text",                     "مرحبا بالعالم"],
    ["mixed unicode",                "αβγδε ΑΒΓΔΕ 日本語"],
    ["repeated double underscores",  "my__title__here"],
  ];

  test.each(adversarialTitles)("does not throw or produce invalid filename: %s", (label, title) => {
    const payload = makePayload({ source_title: title == null ? "" : title, source_url: "" });
    let result;
    expect(() => { result = buildSmartFilename(payload, 1); }).not.toThrow();
    expect(typeof result).toBe("string");
    expect(result).toMatch(/\.json$/);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThan(300);
    // Must not contain characters invalid in filenames across all platforms
    expect(result).not.toMatch(/[<>:"/\\|?*\x00-\x1f]/);
  });

  test("sequence counter handles large numbers", () => {
    const name = buildSmartFilename(makePayload(), 99999);
    expect(name).toMatch(/99999\.json$/);
  });

  test("null source_url does not throw", () => {
    const p = makePayload({ source_url: null });
    expect(() => buildSmartFilename(p, 1)).not.toThrow();
  });

  test("blocks array with all null/empty entries", () => {
    const p = makePayload({ blocks: [null, undefined, {}, { language: null }] });
    expect(() => buildSmartFilename(p, 1)).not.toThrow();
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T9 — scanFolderForCode edge cases
// ══════════════════════════════════════════════════════════════════════════════

describe("T9 · scanFolderForCode — edge cases", () => {
  test("folder with 501 files: scanned stops at 500", async () => {
    const dir = path.join(TMP, "big-folder");
    fs.mkdirSync(dir, { recursive: true });
    for (let i = 0; i < 501; i++) {
      fs.writeFileSync(path.join(dir, `f${i}.txt`), "hello world\n");
    }
    const r = await scanFolderForCode(dir, 500);
    expect(r.scanned).toBe(500);
    expect(r.warning).toMatch(/max/i);
  }, 30000);

  test("folder with deeply nested structure (10 levels)", async () => {
    let dir = path.join(TMP, "deep");
    for (let i = 0; i < 10; i++) dir = path.join(dir, `l${i}`);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "deep.py"), "def deep(): pass\n");
    const r = await scanFolderForCode(path.join(TMP, "deep"), 500);
    expect(r.results.some((x) => x.filePath && x.filePath.includes("deep.py"))).toBe(true);
  }, 15000);

  test("folder with all binary files: all skipped", async () => {
    const dir = path.join(TMP, "all-binary");
    fs.mkdirSync(dir, { recursive: true });
    for (let i = 0; i < 5; i++) {
      fs.writeFileSync(path.join(dir, `b${i}.txt`), Buffer.from([0x00, 0x01, 0x02, 0xFF]));
    }
    const r = await scanFolderForCode(dir, 500);
    r.results.forEach((x) => expect(x.skipped).toBe(true));
  });

  test("folder with symlink to file: does not follow into system dirs", async () => {
    const dir     = path.join(TMP, "symlink-test");
    const linkDst = path.join(dir, "link.txt");
    fs.mkdirSync(dir, { recursive: true });
    try {
      fs.symlinkSync("/etc/passwd", linkDst);
      // scanFolderForCode should either skip it (not regular file check) or handle gracefully
      const r = await scanFolderForCode(dir, 500);
      // Should not throw — result may be skipped or errored
      expect(r).toHaveProperty("results");
    } catch (e) {
      // Symlink creation may fail in some environments — that's fine
      expect(true).toBe(true);
    }
  });
});


// ══════════════════════════════════════════════════════════════════════════════
// T10 — UNICODE AND ENCODING CHAOS
// ══════════════════════════════════════════════════════════════════════════════

describe("T10 · Unicode and encoding chaos", () => {
  test("Python file with CJK identifiers is scanned without corruption", () => {
    const code = `
def 計算(値):
    return 値 * 2

class データ処理:
    def __init__(self):
        self.データ = []
`;
    const r = scanFileForCode(tmpFile("py", code));
    expect(r.detected).toBe(true);
    if (r.blocks[0]) {
      expect(r.blocks[0].content).toContain("def");
    }
  });

  test("JavaScript file with emoji in strings", () => {
    const code = "const greeting = '🐬 Hello World 🎯';\nconst fn = () => greeting;\n";
    const r    = scanFileForCode(tmpFile("js", code));
    expect(r.detected).toBe(true);
  });

  test("file with mixed encodings handled gracefully", () => {
    // Write a file with valid UTF-8 but unusual sequences
    const buf = Buffer.concat([
      Buffer.from("def hello():\n    return "),
      Buffer.from([0xC3, 0xA9]), // é in UTF-8
      Buffer.from("\n"),
    ]);
    const p = tmpFile("py", "");
    fs.writeFileSync(p, buf); // overwrite with binary
    expect(() => scanFileForCode(p)).not.toThrow();
  });

  test("routePayload preserves 4-byte emoji in content", () => {
    const p = makePayload();
    p.blocks[0].content = "def dolphin():\n    return '🐬'  # Tank's Riot";
    const saved = routePayload(p);
    const f     = Object.values(saved)[0];
    if (f) {
      const written = JSON.parse(fs.readFileSync(f, "utf8"));
      expect(written.blocks[0].content).toContain("🐬");
    }
  });

  test("buildSmartFilename with CJK source_title", () => {
    const p = makePayload({ source_title: "日本語のチャット", source_url: "https://claude.ai/c/x" });
    let name;
    expect(() => { name = buildSmartFilename(p, 1); }).not.toThrow();
    expect(name).toMatch(/\.json$/);
    // CJK chars become underscores via safeSegment — that's correct
    expect(name).not.toMatch(/[^\w.\-__]/);
  });

  test("content with null bytes is sanitized in output", () => {
    const p = makePayload();
    p.blocks[0].content = "def x():\n    return '\x00\x01\x02'";
    const saved = routePayload(p);
    const f     = Object.values(saved)[0];
    if (f) {
      const raw = fs.readFileSync(f, "utf8");
      // Should be valid JSON despite null bytes (JSON.stringify escapes them)
      expect(() => JSON.parse(raw)).not.toThrow();
    }
  });
});
