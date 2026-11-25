/**
 * background_session_patch.js
 * ════════════════════════════
 * Add these message handlers to background.js.
 *
 * Handles two new message types from claude_scraper.js:
 *
 *   CONVERSATION_CAPTURE — relay turns to /collect-conversation
 *   FETCH_LAST_SESSION   — fetch prior context from /context/session
 *
 * Also handles new Claude tab detection:
 *   When a tab navigates to claude.ai/chat/new (or fresh chat),
 *   proactively fetch last session and tell the content script.
 *
 * HOW TO ADD TO background.js:
 *   1. Find your existing chrome.runtime.onMessage.addListener block
 *   2. Add the two new cases from _handleSessionMessage below
 *   3. Add the tab listener from _watchClaudeTabs below
 *   4. Make sure SERVER_PORT matches your existing port constant
 *
 * Rear View Foresight LLC — Feic Mo Chroí
 */

"use strict";

const SERVER_PORT = 8765; // match your existing port constant

// ── Message handler additions ─────────────────────────────────────────────────
//
// Add these cases inside your existing onMessage listener:
//
//   chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
//
//     ... your existing cases ...
//
//     // ── NEW: Conversation capture ────────────────────────────────────────
//     if (message.type === "CONVERSATION_CAPTURE") {
//       _relayConversationCapture(message).then(sendResponse);
//       return true; // keep channel open for async response
//     }
//
//     // ── NEW: Fetch last session ──────────────────────────────────────────
//     if (message.type === "FETCH_LAST_SESSION") {
//       _fetchLastSession(message.platform).then(sendResponse);
//       return true;
//     }
//
//   });

async function _relayConversationCapture(message) {
  const {
    session_id,
    platform,
    source_url,
    source_title,
    turns,
  } = message;

  if (!turns || turns.length === 0) {
    return { ok: false, reason: "no turns" };
  }

  try {
    const res = await fetch(`http://localhost:${SERVER_PORT}/collect-conversation`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ session_id, platform, source_url, source_title, turns }),
    });

    if (!res.ok) {
      console.warn("[cc] /collect-conversation returned", res.status);
      return { ok: false, status: res.status };
    }

    const data = await res.json();
    return { ok: true, session_id: data.session_id };

  } catch (err) {
    // Server not running — silent fail
    console.debug("[cc] server not available:", err.message);
    return { ok: false, reason: "server unavailable" };
  }
}


async function _fetchLastSession(platform = "claude") {
  try {
    const res = await fetch(
      `http://localhost:${SERVER_PORT}/context/session?platform=${platform}`,
      { signal: AbortSignal.timeout(2000) }
    );

    if (!res.ok) return { context: null };

    const data = await res.json();
    return data; // { context, session_id, source_url, captured_at, files_touched }

  } catch {
    return { context: null };
  }
}


// ── Tab watcher — paste into background.js ────────────────────────────────────
//
// Watches for Claude tabs navigating to a new conversation.
// When detected, fetches last session and pushes it to the content script.
//
// Add this block to background.js (outside any listener, at module scope):

function _watchClaudeTabs() {
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // Only care when navigation completes on Claude
    if (changeInfo.status !== "complete") return;
    if (!tab.url || !tab.url.startsWith("https://claude.ai")) return;

    // Only on new/fresh conversations
    const isNew = (
      tab.url.includes("/chat/new") ||
      tab.url === "https://claude.ai/" ||
      tab.url === "https://claude.ai"
    );
    if (!isNew) return;

    // Small delay to let the page render before injecting
    setTimeout(async () => {
      const sessionData = await _fetchLastSession("claude");
      if (!sessionData.context) return;

      // Tell the content script to show the banner
      chrome.tabs.sendMessage(tabId, {
        type:    "SHOW_PRIOR_CONTEXT",
        context: sessionData.context,
      }).catch(() => {
        // Content script not ready yet — ignore
      });
    }, 1200);
  });
}

// Call this once at background.js startup:
// _watchClaudeTabs();


// ── Export for testing ────────────────────────────────────────────────────────
if (typeof module !== "undefined") {
  module.exports = { _relayConversationCapture, _fetchLastSession, _watchClaudeTabs };
}
