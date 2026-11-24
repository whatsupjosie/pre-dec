/**
 * claude_scraper.js
 * ══════════════════
 * Content script for claude.ai.
 *
 * FULLY AUTOMATIC CAPTURE. No banners. No buttons. No clicks.
 *
 * Conversation turns are scraped silently every 5 turns and on tab close.
 * Session context is stored in the local server's memory index so the
 * next session can pick up where this one left off.
 *
 * Auto-inject into the input box is DISABLED — context is available
 * via the API but nothing types into your chat without you asking.
 *
 * Rear View Foresight LLC — Feic Mo Chroí
 */

"use strict";

const PLATFORM = "claude";

const SELECTORS = {
  turn:          '[data-testid="user-message"], [data-testid="assistant-message"]',
  userTurn:      '[data-testid="user-message"]',
  assistantTurn: '[data-testid="assistant-message"]',
  turnContent:   '.whitespace-pre-wrap, [class*="prose"]',
  input:         '[data-testid="composer-input"], div[contenteditable="true"]',
  sendButton:    '[data-testid="send-button"]',
};

let _sessionId     = _extractSessionId(location.href);
let _lastTurnCount = 0;
let _primed        = false;

// ── SPA navigation detection ──────────────────────────────────────────────────
// Claude is a SPA. When you switch conversations the URL changes but the page
// doesn't reload, so content script state persists. We patch history.pushState
// to detect navigation and reset per-conversation state cleanly.
(function _patchHistory() {
  const _push    = history.pushState.bind(history);
  const _replace = history.replaceState.bind(history);

  function _onNavigate(url) {
    const newSessionId = _extractSessionId(url || location.href);
    if (newSessionId !== _sessionId) {
      _sessionId     = newSessionId;
      _lastTurnCount = 0;
      _primed        = false;
      // Re-run auto-context on the new conversation
      setTimeout(_maybeAutoSendContext, 800);
    }
  }

  history.pushState = function (...args) {
    _push(...args);
    _onNavigate(args[2]); // args[2] is the URL
  };

  history.replaceState = function (...args) {
    _replace(...args);
    _onNavigate(args[2]);
  };

  window.addEventListener("popstate", () => _onNavigate(location.href));
})();

// Port cache — updated whenever we successfully read settings.
// Used by sendBeacon on beforeunload — can't do async storage reads there.
// Both port and token are cached so the final capture can authenticate.
let _cachedPort  = 8765;
let _cachedToken = "";

// Restore from session storage on content script load — survives SW restarts
chrome.storage.session.get({ _cc_port: 8765, _cc_token: "" }, (vals) => {
  if (!chrome.runtime.lastError) {
    _cachedPort  = vals._cc_port;
    _cachedToken = vals._cc_token;
  }
});

// ── Entry point ───────────────────────────────────────────────────────────────
// Guard: only activate on chat pages. claude.ai/settings, /account, /teams etc
// have no turn DOM structure — running observers there wastes resources and
// could interfere with unrelated page behavior.
// Chat URLs: /chat/*, / (new chat), or pages that already have turn elements.

(function init() {
  const path = location.pathname;
  const isChatPage = (
    path.startsWith("/chat/") ||
    path === "/" ||
    path === "/new" ||
    path === "/chat/new" ||
    document.querySelector('[data-testid="user-message"], [data-testid="assistant-message"]') !== null
  );

  if (!isChatPage) {
    // Still listen for messages so background can probe us if needed
    _listenForMessages();
    return;
  }

  _maybeAutoSendContext();
  _observeTurns();
  _listenForMessages();
})();

// ── Auto-send context — DISABLED. Silent only. ────────────────────────────────
// Context is fetched and stored but never typed into the input box.
// Nothing fires on its own. Right-click to capture, that is all.
async function _maybeAutoSendContext() {
  // Intentionally no-op. Auto-inject removed.
}

// _formatContextMessage and _typeAndSend removed — auto-inject is disabled.

// ── Background capture ────────────────────────────────────────────────────────

let _turnObserver = null;

function _observeTurns() {
  // Disconnect any previous observer before creating a new one.
  // SPA navigation calls this again on each new conversation — without
  // disconnecting, observers stack up and each one fires on every DOM change.
  if (_turnObserver) {
    _turnObserver.disconnect();
    _turnObserver = null;
  }
  _turnObserver = new MutationObserver(_debounce(() => {
    const count = document.querySelectorAll(SELECTORS.turn).length;
    if (count > _lastTurnCount) {
      _lastTurnCount = count;
      if (count % 5 === 0) _capture();
    }
  }, 1000));
  _turnObserver.observe(document.body, { childList: true, subtree: true });
}

function _capture() {
  const turns = _scrapeTurns();
  if (!turns.length) return;
  chrome.runtime.sendMessage({
    type:         "CONVERSATION_CAPTURE",
    platform:     PLATFORM,
    session_id:   _sessionId,
    source_url:   location.href,
    source_title: document.title || "Claude",
    turns,
  });
}

function _scrapeTurns() {
  const turns = [];
  // Use a base timestamp with per-turn offset so turns have ordered, distinct
  // timestamps even though we capture them all at once. The extractor uses
  // timestamps for chronological ordering — all-same breaks that.
  const baseTs  = Date.now() / 1000;
  let   turnIdx = 0;
  document.querySelectorAll(SELECTORS.turn).forEach((node) => {
    const role = node.matches(SELECTORS.userTurn) ? "user" : "assistant";
    const content = (node.querySelector(SELECTORS.turnContent) || node)
      .innerText?.trim() || "";
    if (content.length > 3) {
      turns.push({ role, content, ts: baseTs + turnIdx });
      turnIdx++;
    }
  });
  return turns;
}

// ── Fetch prior context from local server ─────────────────────────────────────

async function _fetchLastSession() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      { type: "FETCH_LAST_SESSION", platform: PLATFORM },
      (response) => {
        if (chrome.runtime.lastError) { resolve(null); return; }
        // Keep port and token cache fresh for sendBeacon
        if (response?._port)  _cachedPort  = response._port;
        if (response?._token !== undefined) _cachedToken = response._token;
        // Persist so values survive SW termination mid-session
        chrome.storage.session.set({ _cc_port: _cachedPort, _cc_token: _cachedToken });
        resolve(response || null);
      }
    );
  });
}

// ── Message listener ──────────────────────────────────────────────────────────

function _listenForMessages() {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {

    // Manual capture trigger (from background or devtools)
    if (message.type === "CAPTURE_SESSION_NOW") {
      _capture();
      sendResponse({ ok: true });
      return;
    }

    // Prior context push from background tab watcher.
    // Auto-inject is disabled — we acknowledge the message but do not type
    // anything into the input box. Silent.
    if (message.type === "SHOW_PRIOR_CONTEXT") {
      sendResponse({ ok: false, reason: "auto-inject disabled" });
      return;
    }
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _isNewConversation() {
  // Require explicit new-chat URL signal — zero turns alone is too loose.
  // A blank DOM during loading, a selector drift, or a slow render can all
  // produce zero turns on an existing conversation. Don't fire on ambiguity.
  const path = location.pathname;
  const isNewChatUrl = path === "/chat/new" || path === "/new";
  if (!isNewChatUrl) return false;
  // Also confirm no turns exist — belt and suspenders.
  return document.querySelectorAll(SELECTORS.turn).length === 0;
}

function _extractSessionId(url) {
  const m = url.match(/\/chat\/([a-zA-Z0-9\-]+)/);
  return m ? m[1] : Math.random().toString(36).slice(2, 14);
}

function _debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// Capture on tab close — final state
window.addEventListener("beforeunload", () => {
  const turns = _scrapeTurns();
  if (!turns.length) return;
  // Uses _cachedPort — kept fresh by _fetchLastSession calls during the session.
  // Falls back to 8765 if never updated (no prior session fetched this tab).
  navigator.sendBeacon(
    `http://localhost:${_cachedPort}/collect-conversation`,
    new Blob([JSON.stringify({
      session_id:   _sessionId,
      platform:     PLATFORM,
      source_url:   location.href,
      source_title: document.title || "Claude",
      turns,
      // sendBeacon cannot set custom headers — auth token carried in body.
      // Server checks _beacon_token field when X-Auth-Token header is absent.
      _beacon_token: _cachedToken,
    })], { type: "application/json" })
  );
});
