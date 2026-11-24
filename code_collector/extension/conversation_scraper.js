/**
 * conversation_scraper.js
 * ═══════════════════════
 * Whole-conversation capture for every supported AI site. Optional.
 *
 * Nothing is read off the page unless the user has turned on
 * "Capture whole conversations" in the Code Collector app AND left this
 * site switched on. The app is the source of truth; this script asks it
 * (GET /conversation-capture, via the background worker) on every page
 * and every in-page navigation. The server checks the same setting again
 * before it keeps anything, so a stale answer here can never save a
 * conversation the user switched off.
 *
 * What is captured: both sides of the conversation, in page order, with
 * the chat link. Code blocks inside are still collected by content.js the
 * usual way.
 *
 * Each site only needs its row in SITES. When a site changes its page
 * layout, that row is the one thing to update.
 *
 * Replaces claude_scraper.js (Claude only, always on), which is kept in
 * _moved_out/ for reference.
 *
 * Rear View Foresight LLC — Feic Mo Chroí
 */

"use strict";

// verified: true means the selectors match what claude_scraper.js used in
// production. false means written from the site's known structure but not
// yet checked against the live page.
const SITES = {
  claude: {
    hosts:     ["claude.ai"],
    title:     "Claude",
    verified:  true,
    user:      '[data-testid="user-message"]',
    assistant: '[data-testid="assistant-message"]',
    content:   '.whitespace-pre-wrap, [class*="prose"]',
    sessionRe: /\/chat\/([a-zA-Z0-9-]+)/,
  },
  chatgpt: {
    hosts:     ["chatgpt.com", "chat.openai.com"],
    title:     "ChatGPT",
    verified:  false,
    user:      '[data-message-author-role="user"]',
    assistant: '[data-message-author-role="assistant"]',
    content:   ".markdown, .whitespace-pre-wrap",
    sessionRe: /\/c\/([a-zA-Z0-9-]+)/,
  },
  gemini: {
    hosts:     ["gemini.google.com"],
    title:     "Gemini",
    verified:  false,
    user:      "user-query",
    assistant: "model-response",
    content:   ".query-text, message-content",
    sessionRe: /\/app\/([a-zA-Z0-9_-]+)/,
  },
  copilot: {
    hosts:     ["copilot.microsoft.com"],
    title:     "Copilot",
    verified:  false,
    user:      '[data-content="user-message"]',
    assistant: '[data-content="ai-message"]',
    content:   "",
    sessionRe: /\/chats\/([a-zA-Z0-9_-]+)/,
  },
  perplexity: {
    hosts:     ["www.perplexity.ai", "perplexity.ai"],
    title:     "Perplexity",
    verified:  false,
    user:      '[class*="group/query"]',
    assistant: '[id^="markdown-content"]',
    content:   "",
    sessionRe: /\/search\/([a-zA-Z0-9_.-]+)/,
  },
};

const PLATFORM = Object.keys(SITES).find((k) => SITES[k].hosts.includes(location.hostname));
const SITE     = PLATFORM ? SITES[PLATFORM] : null;
const TURN_SELECTOR = SITE ? `${SITE.user}, ${SITE.assistant}` : "";

let _enabled       = false;
let _sessionId     = "";
let _lastSignature = "";
let _observer      = null;
let _cachedPort    = 8765;
let _cachedToken   = "";

if (SITE) {
  _sessionId = _extractSessionId(location.href);
  chrome.storage.session.get({ _cc_port: 8765, _cc_token: "" }, (vals) => {
    if (!chrome.runtime.lastError) {
      _cachedPort  = vals._cc_port;
      _cachedToken = vals._cc_token;
    }
  });
  _patchHistory();
  _refreshSetting();
  _listenForMessages();
}

// ── Setting ───────────────────────────────────────────────────────────────────

function _refreshSetting() {
  chrome.runtime.sendMessage({ type: "CONVERSATION_SETTINGS" }, (resp) => {
    if (chrome.runtime.lastError || !resp) { _setEnabled(false); return; }
    if (resp._port)               _cachedPort  = resp._port;
    if (resp._token !== undefined) _cachedToken = resp._token;
    chrome.storage.session.set({ _cc_port: _cachedPort, _cc_token: _cachedToken });
    _setEnabled(!!resp.enabled && !!(resp.sites && resp.sites[PLATFORM]));
  });
}

function _setEnabled(on) {
  _enabled = on;
  if (on) {
    _observe();
  } else if (_observer) {
    _observer.disconnect();
    _observer = null;
  }
}

// ── Watching the page ─────────────────────────────────────────────────────────

function _observe() {
  if (_observer) _observer.disconnect();
  // Capture once the conversation has been still for a few seconds, so every
  // new turn is kept (not only every fifth) without writing on each keystroke
  // of a streaming reply.
  _observer = new MutationObserver(_debounce(_captureIfChanged, 3000));
  _observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  _captureIfChanged();
}

function _captureIfChanged() {
  if (!_enabled) return;
  const turns = _scrapeTurns();
  if (!turns.length) return;
  const last = turns[turns.length - 1];
  const signature = `${_sessionId}|${turns.length}|${last.content.length}`;
  if (signature === _lastSignature) return;
  _lastSignature = signature;
  chrome.runtime.sendMessage({
    type:         "CONVERSATION_CAPTURE",
    platform:     PLATFORM,
    session_id:   _sessionId,
    source_url:   location.href,
    source_title: document.title || SITE.title,
    turns,
  });
}

function _scrapeTurns() {
  const turns  = [];
  const baseTs = Date.now() / 1000;
  document.querySelectorAll(TURN_SELECTOR).forEach((node) => {
    // A site may nest one match inside another; keep the outermost only.
    if (node.parentElement && node.parentElement.closest(TURN_SELECTOR)) return;
    const role = node.matches(SITE.user) ? "user" : "assistant";
    const holder = (SITE.content && node.querySelector(SITE.content)) || node;
    const content = (holder.innerText || "").trim();
    if (content.length > 0) turns.push({ role, content, ts: baseTs + turns.length });
  });
  return turns;
}

// ── In-page navigation (all five sites are single-page apps) ──────────────────

function _patchHistory() {
  const onNavigate = (url) => {
    const next = _extractSessionId(url || location.href);
    if (next === _sessionId) return;
    _sessionId = next;
    _lastSignature = "";
    _refreshSetting();   // the user may have changed the setting meanwhile
  };
  for (const name of ["pushState", "replaceState"]) {
    const original = history[name].bind(history);
    history[name] = function (...args) {
      original(...args);
      onNavigate(args[2]);
    };
  }
  window.addEventListener("popstate", () => onNavigate(location.href));
}

function _listenForMessages() {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "CAPTURE_SESSION_NOW") {
      _lastSignature = "";
      _captureIfChanged();
      sendResponse({ ok: _enabled });
      return;
    }
    if (message.type === "CONVERSATION_SETTING_CHANGED") {
      _refreshSetting();
      sendResponse({ ok: true });
      return;
    }
    if (message.type === "SHOW_PRIOR_CONTEXT") {
      // Auto-typing into the chat stays disabled.
      sendResponse({ ok: false, reason: "auto-inject disabled" });
    }
  });
}

// ── Final capture when the tab closes ─────────────────────────────────────────

window.addEventListener("beforeunload", () => {
  if (!SITE || !_enabled) return;
  const turns = _scrapeTurns();
  if (!turns.length) return;
  navigator.sendBeacon(
    `http://127.0.0.1:${_cachedPort}/collect-conversation`,
    new Blob([JSON.stringify({
      session_id:    _sessionId,
      platform:      PLATFORM,
      source_url:    location.href,
      source_title:  document.title || SITE.title,
      turns,
      _beacon_token: _cachedToken,   // sendBeacon cannot set headers
    })], { type: "application/json" })
  );
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function _extractSessionId(url) {
  const m = SITE && String(url).match(SITE.sessionRe);
  // A chat with no id yet (a brand-new one) gets a per-tab id until the site
  // assigns its own.
  return m ? m[1] : (_sessionId || `${PLATFORM}_${Math.random().toString(36).slice(2, 12)}`);
}

function _debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
