"use strict";
/**
 * Whole-conversation capture: off by default, per-site, and the full
 * transcript is saved (JSON + readable text), rewritten in place.
 */
const fs   = require("fs");
const path = require("path");
const os   = require("os");

process.env.TEST_MODE    = "1";
process.env.NO_CPU_LIMIT = "1";

const { store, conversationCaptureAllowed, writeConversationTranscript } = require("../main");

const TMP = path.join(os.tmpdir(), "cc-conv-" + process.pid);
const turns = [
  { role: "user", content: "Write me a function", ts: 1 },
  { role: "assistant", content: "def f():\n    return 1", ts: 2 },
];

beforeEach(() => {
  fs.mkdirSync(TMP, { recursive: true });
  store.set("primaryDir", TMP);
  store.set("captureConversations", false);
  store.set("conversationSites", { claude: true, chatgpt: true, gemini: true, copilot: true, perplexity: true });
});
afterAll(() => fs.rmSync(TMP, { recursive: true, force: true }));

describe("the switch", () => {
  test("off by default: no site is allowed", () => {
    for (const site of ["claude", "chatgpt", "gemini", "copilot", "perplexity"]) {
      expect(conversationCaptureAllowed(site)).toBe(false);
    }
  });
  test("on: every listed site is allowed", () => {
    store.set("captureConversations", true);
    expect(conversationCaptureAllowed("chatgpt")).toBe(true);
    expect(conversationCaptureAllowed("gemini")).toBe(true);
  });
  test("a site switched off stays off while the rest stay on", () => {
    store.set("captureConversations", true);
    store.set("conversationSites", { claude: true, chatgpt: false });
    expect(conversationCaptureAllowed("chatgpt")).toBe(false);
    expect(conversationCaptureAllowed("claude")).toBe(true);
    expect(conversationCaptureAllowed("gemini")).toBe(true);
  });
  test("unknown sites are never allowed", () => {
    store.set("captureConversations", true);
    expect(conversationCaptureAllowed("someothersite")).toBe(false);
    expect(conversationCaptureAllowed("__proto__")).toBe(false);
  });
});

describe("the transcript", () => {
  test("saves both sides, in order, as JSON and readable text", () => {
    const out = writeConversationTranscript({
      session_id: "abc-123", platform: "chatgpt", source_url: "https://chatgpt.com/c/abc-123",
      source_title: "My chat", turns,
    });
    const rec = JSON.parse(fs.readFileSync(out.json, "utf8"));
    expect(rec.turns.map((t) => t.role)).toEqual(["user", "assistant"]);
    expect(rec.turns[1].content).toBe("def f():\n    return 1");
    const txt = fs.readFileSync(out.text, "utf8");
    expect(txt).toContain("── You ──\nWrite me a function");
    expect(txt.indexOf("Write me a function")).toBeLessThan(txt.indexOf("def f()"));
    expect(path.dirname(out.json)).toBe(path.join(TMP, "conversations", "chatgpt"));
  });
  test("a growing conversation rewrites the same files, never duplicates", () => {
    const args = { session_id: "grow", platform: "claude", source_url: "", source_title: "", turns };
    const first  = writeConversationTranscript(args);
    const second = writeConversationTranscript({ ...args, turns: [...turns, { role: "user", content: "thanks", ts: 3 }] });
    expect(second.json).toBe(first.json);
    expect(JSON.parse(fs.readFileSync(second.json, "utf8")).turns).toHaveLength(3);
    expect(fs.readdirSync(path.dirname(first.json)).filter((n) => n.startsWith("grow"))).toHaveLength(2);
    expect(fs.readdirSync(path.dirname(first.json)).some((n) => n.endsWith(".tmp"))).toBe(false);
  });
  test("a hostile session id cannot write outside the conversations folder", () => {
    const out = writeConversationTranscript({
      session_id: "../../../etc/passwd", platform: "claude", source_url: "", source_title: "", turns,
    });
    expect(out.json.startsWith(path.join(TMP, "conversations", "claude") + path.sep)).toBe(true);
  });
});
