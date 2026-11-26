/* PubCast reconstruction render host.
 *
 * Draws recorded 2.5D production frames with the live studio's own renderer, one frame per call
 * entry, on a fixed time step, so the same performance data always gives the same pictures.
 * Driven only by modules/reconstruction.py through a headless browser. No timers, no wall clock,
 * no network: every file comes from the driver, and every frame's time step is given to it.
 *
 * Copyright 2026 Rearview Foresight. Feic Mo Chroí — See My Heart.
 */
(function () {
"use strict";
const Core = window.PubCast25D, Renderer = window.PubCast25DRenderer;
const W = Renderer.W, H = Renderer.H;
const AVATARS = {female: "/static/world/test_avatars/MakeHuman_Female.glb", male: "/static/world/test_avatars/MakeHuman_Male.glb"};
const out = document.getElementById("out");
const outCtx = out.getContext("2d", {alpha: false});
const world = document.createElement("canvas"); world.width = W; world.height = H;
const mixCanvas = document.createElement("canvas"); mixCanvas.width = W; mixCanvas.height = H;
const mixCtx = mixCanvas.getContext("2d", {alpha: false});
let pkg = null, assets = {}, loaded = new Map();

function glb() {
  if (window.PubCastGLB) return Promise.resolve(window.PubCastGLB);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error("3D actor renderer did not load")), 20000);
    document.addEventListener("pubcast-glb-ready", () => { clearTimeout(timer); resolve(window.PubCastGLB); }, {once: true});
  });
}
function staticPath(value) {
  if (value == null || value === "") return null;
  if (typeof value !== "string" || !/^\/static\/[A-Za-z0-9_\-./]+$/.test(value) || value.includes("..")) throw Error("Asset path must be inside /static/: " + value);
  return value;
}
function image(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(Error("Set image could not be read: " + url));
    img.src = url;
  });
}
function shotOf(spec) {
  if (!spec || !Array.isArray(spec.center) || spec.center.length !== 2) throw Error("Shot needs center [x, y]");
  const center = spec.center.map(Number), zoom = Number(spec.zoom);
  if (!center.every(n => Number.isFinite(n) && n >= 0 && n <= 1)) throw Error("Shot center must be within 0..1");
  if (!Number.isFinite(zoom) || zoom < 1 || zoom > 4) throw Error("Shot zoom must be within 1..4");
  return {center, zoom};
}

async function prepare(spec) {
  const engine = await glb();
  if (!Core.PACKAGES[spec.package]) throw Error("Unknown production package: " + spec.package);
  pkg = Core.PACKAGES[spec.package];
  for (const id of loaded.keys()) engine.clear(id);
  loaded = new Map(); assets = {};
  const report = {package: pkg.id, performers: [], assets: {}};
  for (const p of spec.performers || []) {
    const url = p.avatar_url ? staticPath(p.avatar_url) : AVATARS[p.avatar];
    if (!url) throw Error("Performer " + p.id + " has no avatar");
    const info = await engine.load(p.id, url, p.slot || p.id);
    loaded.set(p.id, url);
    report.performers.push({id: p.id, url, clips: info.clips, tris: info.tris, bones: info.bones, skinned: info.skinned});
  }
  for (const layer of ["back", "mid", "front"]) {
    const url = staticPath(spec.assets && spec.assets[layer]);
    if (url) { assets[layer] = await image(url); report.assets[layer] = url; }
  }
  engine.setHologram(!!spec.hologram);
  return report;
}

function sceneState(scene, frame, reuse) {
  return {
    performers: (scene.performers || []).filter(p => loaded.has(p.id)).map(p => ({
      id: p.id, position: p.position, vx: p.vx || 0, vy: p.vy || 0, moving: !!p.moving})),
    lowerThird: !!scene.lowerThird, lowerText: scene.lowerText || "", scores: scene.scores || [0, 0],
    blackout: !!scene.blackout, voxelProp: scene.voxelProp || null, assets,
    avatarBridge: window.PubCastGLB, pixelScale: 1,
    reuseActorFrame: reuse, actorFrameStamp: frame.stamp};
}

function drawOne(ctx, frame) {
  const engine = window.PubCastGLB, scene = frame.scene || {};
  for (const g of frame.gestures || []) {
    if (loaded.has(g.performer) && !engine.playClip(g.performer, String(g.clip))) frame.notes.push("no clip " + g.clip + " on " + g.performer);
  }
  for (const p of scene.performers || []) {
    if (loaded.has(p.id) && Number.isFinite(p.jaw)) engine.setJaw(p.id, p.jaw);
  }
  const shot = shotOf(frame.shot);
  Renderer.renderCamera(ctx, pkg, shot, sceneState(scene, frame, false), world, frame.dt);
  if (frame.mix_to && frame.mix > 0) {
    // A dissolve: the incoming camera sees the same actor pose (no second animation step).
    Renderer.renderCamera(mixCtx, pkg, shotOf(frame.mix_to), sceneState(scene, frame, true), world, 0);
    ctx.save(); ctx.globalAlpha = Math.min(1, frame.mix); ctx.drawImage(mixCanvas, 0, 0); ctx.restore();
  }
}

function renderFrames(frames, options) {
  if (!pkg) throw Error("prepare() first");
  const format = options && options.format === "jpeg" ? "image/jpeg" : "image/png";
  const quality = options && Number.isFinite(options.quality) ? options.quality : 0.95;
  const results = [];
  for (const frame of frames) {
    frame.notes = [];
    try {
      drawOne(outCtx, frame);
      const url = out.toDataURL(format, quality);
      results.push({stamp: frame.stamp, data: url.slice(url.indexOf(",") + 1), notes: frame.notes});
    } catch (e) {
      results.push({stamp: frame.stamp, error: String(e && e.message || e), notes: frame.notes});
    }
  }
  return results;
}

window.PubCastReconstruct = {prepare, renderFrames, width: W, height: H,
  packages: () => Object.fromEntries(Object.entries(Core.PACKAGES).map(([id, p]) => [id,
    {cameras: p.cameras.map(c => ({id: c.id, label: c.label, center: c.center, zoom: c.zoom})),
     performers: p.performers.map(x => ({id: x.id, slot: x.slot, avatar: x.avatar, position: x.position}))}]))};
document.documentElement.dataset.reconstruct = "ready";
})();
