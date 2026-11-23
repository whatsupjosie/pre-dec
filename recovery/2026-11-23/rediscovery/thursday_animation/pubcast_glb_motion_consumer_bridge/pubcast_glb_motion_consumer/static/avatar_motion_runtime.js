/**
 * PubCast Avatar Motion Runtime Client
 * ------------------------------------
 * Receives server-side avatar motion command bundles and exposes a small browser
 * event bridge for stage/render code. This deliberately does not create menus.
 */
(function () {
  const state = {
    lastByAvatar: new Map(),
    listeners: new Set(),
    connected: false,
    ws: null,
  };

  function normalizeMessage(raw) {
    if (!raw) return null;
    if (typeof raw === "string") {
      try { return JSON.parse(raw); } catch { return null; }
    }
    return raw;
  }

  function emit(payload) {
    if (!payload || !payload.avatar_id) return;
    state.lastByAvatar.set(payload.avatar_id, payload);
    const event = new CustomEvent("pubcast:avatar-motion-commands", { detail: payload });
    window.dispatchEvent(event);
    for (const fn of state.listeners) {
      try { fn(payload); } catch (err) { console.error("avatar motion listener failed", err); }
    }
  }

  function handleSystemEvent(event) {
    const msg = normalizeMessage(event && event.data ? event.data : event);
    if (!msg) return;
    if (msg.type === "avatar_motion_commands") emit(msg.payload);
    if (msg.type === "system" && msg.payload && msg.payload.type === "avatar_motion_commands") emit(msg.payload.payload || msg.payload);
  }

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
    return data;
  }

  async function tick(payload) {
    const data = await postJSON("/api/avatar-motion/tick", payload || {});
    if (data.event && data.event.payload) emit(data.event.payload);
    return data;
  }

  async function emotion(avatarId, label, intensity = 0.5, ttlMs = 2500) {
    const data = await postJSON(`/api/avatar-motion/${encodeURIComponent(avatarId)}/emotion`, {
      label, intensity, ttl_ms: ttlMs,
    });
    if (data.event && data.event.payload) emit(data.event.payload);
    return data;
  }

  async function mocap(avatarId, frame, extra = {}) {
    return tick({ avatar_id: avatarId, frame, ...extra });
  }

  function connect(room = "studio") {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) return state.ws;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(room)}`);
    state.ws = ws;
    ws.addEventListener("open", () => { state.connected = true; });
    ws.addEventListener("close", () => { state.connected = false; });
    ws.addEventListener("message", handleSystemEvent);
    return ws;
  }

  function onCommands(fn) {
    state.listeners.add(fn);
    return () => state.listeners.delete(fn);
  }

  function getLast(avatarId) {
    return avatarId ? state.lastByAvatar.get(avatarId) : Array.from(state.lastByAvatar.values());
  }

  window.PubcastAvatarMotionRuntime = {
    connect,
    tick,
    emotion,
    mocap,
    onCommands,
    getLast,
    handleSystemEvent,
  };

  // Auto-attach to an existing PubCast websocket helper if one dispatches browser events.
  window.addEventListener("pubcast:system-event", (e) => handleSystemEvent(e.detail));
})();
