/**
 * @jest-environment jsdom
 *
 * conversation_scraper.js against small stand-in pages for each site.
 * These prove the reader's logic (order, roles, the on/off switch). They do
 * NOT prove the live sites still use these page structures; only a run in a
 * real browser on each site can show that.
 */
"use strict";
const fs   = require("fs");
const path = require("path");
const SRC  = fs.readFileSync(path.join(__dirname, "..", "extension", "conversation_scraper.js"), "utf8");

const PAGES = {
  "claude.ai": `<div data-testid="user-message"><div class="whitespace-pre-wrap">hi claude</div></div>
                <div data-testid="assistant-message"><div class="prose">hello there</div></div>`,
  "chatgpt.com": `<div data-message-author-role="user"><div class="whitespace-pre-wrap">hi gpt</div></div>
                  <div data-message-author-role="assistant"><div class="markdown">hello from gpt</div></div>`,
  "gemini.google.com": `<user-query><div class="query-text">hi gemini</div></user-query>
                        <model-response><message-content>hello from gemini</message-content></model-response>`,
};

function load(host, settings) {
  const sent = [];
  global.chrome = {
    runtime: {
      lastError: null,
      sendMessage: (msg, cb) => {
        if (msg.type === "CONVERSATION_SETTINGS") cb && cb(settings);
        else sent.push(msg);
      },
      onMessage: { addListener: () => {} },
    },
    storage: { session: { get: (_d, cb) => cb({ _cc_port: 8765, _cc_token: "" }), set: () => {} } },
  };
  // jsdom's location is fixed per test file; give the script the host it checks.
  Object.defineProperty(window, "location", {
    value: { hostname: host, href: `https://${host}/c/abc`, pathname: "/c/abc" }, configurable: true,
  });
  document.body.innerHTML = PAGES[host];
  // innerText is not implemented in jsdom; textContent stands in for it.
  Object.defineProperty(HTMLElement.prototype, "innerText", { get() { return this.textContent; }, configurable: true });
  new Function(SRC)();
  return sent;
}

const ALL_ON = { enabled: true, sites: { claude: true, chatgpt: true, gemini: true, copilot: true, perplexity: true } };

test.each([
  ["claude.ai", "claude", "hi claude", "hello there"],
  ["chatgpt.com", "chatgpt", "hi gpt", "hello from gpt"],
  ["gemini.google.com", "gemini", "hi gemini", "hello from gemini"],
])("%s: both sides captured in order when on", (host, platform, you, ai) => {
  const sent = load(host, ALL_ON);
  expect(sent).toHaveLength(1);
  expect(sent[0].platform).toBe(platform);
  expect(sent[0].turns.map((t) => [t.role, t.content])).toEqual([["user", you], ["assistant", ai]]);
});

test("switch off: nothing is read or sent", () => {
  expect(load("chatgpt.com", { enabled: false, sites: ALL_ON.sites })).toHaveLength(0);
});

test("site switched off: nothing is sent for that site", () => {
  expect(load("gemini.google.com", { enabled: true, sites: { ...ALL_ON.sites, gemini: false } })).toHaveLength(0);
});

test("app unreachable: treated as off", () => {
  expect(load("claude.ai", undefined)).toHaveLength(0);
});
