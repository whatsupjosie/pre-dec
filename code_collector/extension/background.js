"use strict";

// Cached port for sendBeacon on unload (can't do async reads there).
// Chrome MV3 service workers terminate after ~30s idle — module-level vars
// reset on restart. We persist to chrome.storage.session so this survives.
let _cachedPort = 8765;

chrome.storage.session.get({ _cc_port: 8765 }, (vals) => {
  if (!chrome.runtime.lastError) _cachedPort = vals._cc_port;
});

function _persistCachedPort(port) {
  _cachedPort = port;
  chrome.storage.session.set({ _cc_port: port });
}

// ─── Context menu builder ─────────────────────────────────────────────────────
// Called on both onInstalled AND onStartup so menus survive extension reloads
function buildContextMenus() {
  chrome.contextMenus.removeAll(() => {
    if (chrome.runtime.lastError) {
      console.warn("contextMenus.removeAll error:", chrome.runtime.lastError.message);
    }

    const items = [
      { id: "cc-root",         title: "Code Collector",                  contexts: ["page", "selection"] },
      { id: "cc-save-primary", title: "Save all code → Primary folder",  contexts: ["page", "selection"], parentId: "cc-root" },
      { id: "cc-save-archive", title: "Save all code → Archive folder",  contexts: ["page", "selection"], parentId: "cc-root" },
      { id: "cc-save-both",    title: "Save all code → Both folders",    contexts: ["page", "selection"], parentId: "cc-root" },
      { id: "cc-sep",          type: "separator",                         contexts: ["page", "selection"], parentId: "cc-root" },
      { id: "cc-save-cloud",   title: "Save all code → Cloud folder",    contexts: ["page", "selection"], parentId: "cc-root" },
    ];

    for (const item of items) {
      chrome.contextMenus.create(item, () => {
        if (chrome.runtime.lastError) {
          const msg = chrome.runtime.lastError.message || "";
          if (!msg.includes("duplicate")) console.warn("contextMenus.create error:", msg);
        }
      });
    }
  });
}

chrome.runtime.onInstalled.addListener(buildContextMenus);
chrome.runtime.onStartup.addListener(buildContextMenus);

// ─── Context menu clicks ──────────────────────────────────────────────────────
const TARGET_MAP = {
  "cc-save-primary": "primary",
  "cc-save-archive": "archive",
  "cc-save-both":    "both",
  "cc-save-cloud":   "cloud",
};

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const target = TARGET_MAP[info.menuItemId];
  if (!target || !tab?.id) return;

  chrome.tabs.sendMessage(tab.id, { type: "COLLECT_AND_SEND", target }, (response) => {
    if (chrome.runtime.lastError) {
      console.warn("sendMessage to content script failed:", chrome.runtime.lastError.message);
      // Content script not yet injected — inject on demand and retry once
      chrome.scripting.executeScript(
        { target: { tabId: tab.id }, files: ["content.js"] },
        () => {
          if (chrome.runtime.lastError) return; // tab not injectable (chrome:// etc.)
          setTimeout(() => {
            chrome.tabs.sendMessage(tab.id, { type: "COLLECT_AND_SEND", target });
          }, 300);
        }
      );
    }
  });
});

// ─── Message hub ──────────────────────────────────────────────────────────────
// All message types from content scripts land here.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {

  // ── Code block capture → local server ──────────────────────────────────────
  if (msg.type === "POST_PAYLOAD") {
    const { payload, target } = msg;

    getSettings().then((settings) => {
      const port  = validatePort(settings.serverPort);
      const token = settings.authToken || "";

      const headers = { "Content-Type": "application/json" };
      if (token) headers["X-Auth-Token"] = token;

      payload.target = target;

      fetch(`http://127.0.0.1:${port}/collect`, {
        method:  "POST",
        headers,
        body:    JSON.stringify(payload),
      })
        .then(async (r) => {
          if (!r.ok) {
            let detail = `Server returned ${r.status}`;
            try { const j = await r.json(); if (j.error) detail = j.error; } catch { /* non-JSON body */ }
            throw new Error(detail);
          }
          const result = await r.json();
          // Silent badge feedback — gold checkmark for 3s, no popup
          chrome.action.setBadgeText({ text: "✓" });
          chrome.action.setBadgeBackgroundColor({ color: "#c9a84c" });
          setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
          sendResponse({ ok: true, result });
        })
        .catch((err) => {
          chrome.action.setBadgeText({ text: "!" });
          chrome.action.setBadgeBackgroundColor({ color: "#c0392b" });
          sendResponse({ ok: false, error: err.message });
        });
    });

    return true; // keep channel open for async response
  }

  // ── Conversation capture → /collect-conversation ──────────────────────────
  if (msg.type === "CONVERSATION_CAPTURE") {
    _relayConversationCapture(msg).then(sendResponse);
    return true;
  }

  // ── Is whole-conversation capture on? (asked by conversation_scraper.js) ──
  if (msg.type === "CONVERSATION_SETTINGS") {
    _fetchConversationSettings().then(sendResponse);
    return true;
  }

  // ── Fetch prior session context ───────────────────────────────────────────
  if (msg.type === "FETCH_LAST_SESSION") {
    _fetchLastSession(msg.platform).then(sendResponse);
    return true;
  }

  return false;
});

// ─── Session relay helpers ────────────────────────────────────────────────────
async function _relayConversationCapture(message) {
  const { session_id, platform, source_url, source_title, turns } = message;

  if (!turns || turns.length === 0) return { ok: false, reason: "no turns" };

  const settings = await getSettings();
  const port     = validatePort(settings.serverPort);
  const token    = settings.authToken || "";

  // Cache port for sendBeacon — persist to session storage so it survives SW restart
  _persistCachedPort(port);

  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Auth-Token"] = token;

  try {
    const res = await fetch(`http://127.0.0.1:${port}/collect-conversation`, {
      method:  "POST",
      headers,
      body:    JSON.stringify({ session_id, platform, source_url, source_title, turns }),
    });

    if (!res.ok) {
      console.warn("[cc] /collect-conversation returned", res.status);
      return { ok: false, status: res.status };
    }

    const data = await res.json();
    return { ok: true, session_id: data.session_id };

  } catch (err) {
    // Server not running — silent fail so the UI doesn't break
    console.debug("[cc] server not available:", err.message);
    return { ok: false, reason: "server unavailable" };
  }
}

// Off unless the app says on. If the app cannot be reached, nothing is read.
async function _fetchConversationSettings() {
  const settings = await getSettings();
  const port     = validatePort(settings.serverPort);
  const token    = settings.authToken || "";
  const headers  = token ? { "X-Auth-Token": token } : {};
  try {
    const res = await fetch(`http://127.0.0.1:${port}/conversation-capture`,
      { headers, signal: AbortSignal.timeout(2000) });
    if (!res.ok) return { enabled: false, sites: {}, _port: port, _token: token };
    const data = await res.json();
    return { enabled: !!data.enabled, sites: data.sites || {}, _port: port, _token: token };
  } catch {
    return { enabled: false, sites: {}, _port: port, _token: token };
  }
}

async function _fetchLastSession(platform = "claude") {
  const settings = await getSettings();
  const port     = validatePort(settings.serverPort);
  const token    = settings.authToken || "";

  const headers = {};
  if (token) headers["X-Auth-Token"] = token;

  try {
    const res = await fetch(
      `http://127.0.0.1:${port}/context/session?platform=${platform}`,
      { headers, signal: AbortSignal.timeout(2000) }
    );
    if (!res.ok) return { context: null, _port: port };
    const data = await res.json();
    // Include _port and _token so claude_scraper.js can keep its sendBeacon
    // cache current. sendBeacon fires on beforeunload and cannot do async
    // storage reads — both values must already be in memory.
    return { ...data, _port: port, _token: token };
  } catch {
    return { context: null, _port: port, _token: token };
  }
}

// ─── Tab watcher — auto-prime new Claude conversations ────────────────────────
function _watchClaudeTabs() {
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status !== "complete") return;
    if (!tab.url?.startsWith("https://claude.ai")) return;

    const isNew = (
      tab.url.includes("/chat/new") ||
      tab.url === "https://claude.ai/" ||
      tab.url === "https://claude.ai"
    );
    if (!isNew) return;

    // Small delay to let the page render before we try to inject
    setTimeout(async () => {
      const sessionData = await _fetchLastSession("claude");
      if (!sessionData.context) return;

      chrome.tabs.sendMessage(tabId, {
        type:    "SHOW_PRIOR_CONTEXT",
        context: sessionData.context,
      }).catch(() => {
        // Content script not ready yet — claude_scraper.js will handle it on its own init
      });
    }, 1200);
  });
}

// Activate the tab watcher at startup
_watchClaudeTabs();

// ─── Helpers ──────────────────────────────────────────────────────────────────
function validatePort(raw) {
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1024 || n > 65535) return 8765;
  return n;
}

async function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get({ serverPort: 8765, authToken: "" }, resolve);
  });
}
