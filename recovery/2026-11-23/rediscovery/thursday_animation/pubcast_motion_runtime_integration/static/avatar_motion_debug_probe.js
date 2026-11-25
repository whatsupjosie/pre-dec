/** Optional dev probe. Not a menu. Logs motion commands and applies a tiny CSS
 * transform to elements with data-avatar-id so wiring can be seen before the
 * full GLB renderer consumes commands.
 */
(function () {
  const api = window.PubcastAvatarMotionRuntime;
  if (!api) return;
  api.onCommands((payload) => {
    console.debug("[avatar-motion]", payload.avatar_id, payload.commands);
    const el = document.querySelector(`[data-avatar-id="${CSS.escape(payload.avatar_id)}"]`);
    if (!el) return;
    const primary = (payload.commands || []).find(c => c.kind === "procedural_animation" || c.kind === "overlay");
    if (!primary) return;
    el.dataset.motion = primary.animation_id || primary.kind;
    el.style.transition = "transform 160ms ease";
    el.style.transform = primary.animation_id && primary.animation_id.includes("lean") ? "translateX(2px)" : "translateY(-1px)";
    setTimeout(() => { el.style.transform = ""; }, Math.min(700, primary.duration_ms || 300));
  });
})();
