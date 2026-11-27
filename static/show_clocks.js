/* show_clocks.js - the two show clocks (step 3 of 3, Josie's design from handoffs/STUDIO_ASSEMBLY_2026-11-23.md).
 *
 * Top clock IN: how far into the show you are.  Bottom clock LEFT: how much is left to the show's set length.
 * LEFT exists only for a show that has a set length (like 24:10); with no set length it is hidden.
 * Time code is HH:MM:SS:FF (frames, 24 by default), seven-segment digits, near-black panel.
 * Defaults: IN green, LEFT blue. Each clock can be switched on its own among blue, green, yellow and red.
 * The colour belongs to the screen you are on (saved in this browser for this page), not to the director.
 *
 * Reads GET /api/timeline/status. Counts smoothly between reads using the browser clock while the show is running.
 * If the host cannot be read (not signed in, host down) the digits go dark and say nothing, rather than show a time
 * that is not known.
 *
 * Labels IN and LEFT are the builder's words, not Josie's (she was asked and has not answered); change LABELS below.
 * One line per screen mounts it:  <script src="/static/show_clocks.js" defer></script>
 * A page can opt out with <html data-show-clocks="off">.
 */
(function (root) {
  "use strict";

  var STATUS_URL = "/api/timeline/status";
  var POLL_MS = 500;
  var MAX_SAMPLE_AGE = 2000;
  var STATES = ["idle","running","paused","complete","failed"];
  var DEFAULT_RATE = 24;
  var SUPPORTED_RATES = [24, 25, 30];
  var LABELS = { top: "IN", bottom: "LEFT" };
  var COLORS = { green: "#3ddc84", blue: "#4da3ff", yellow: "#ffd23f", red: "#ff4d4d" };
  var COLOR_ORDER = ["blue", "green", "yellow", "red"];
  var DEFAULT_COLOR = { top: "green", bottom: "blue" };
  var PANEL = "#0b0f0e";
  var UNLIT_OPACITY = 0.1;

  /* Same arithmetic as modules/timeline.py format_time_code: frames are counted down to the whole frame,
     the small addition absorbs binary rounding, a negative position keeps a leading minus. */
  function splitTimeCode(seconds, rate) {
    if (typeof seconds !== "number" || !isFinite(seconds)) return null;
    if (SUPPORTED_RATES.indexOf(rate) < 0) rate = DEFAULT_RATE;
    var frames = Math.floor(Math.abs(seconds) * rate + 1e-6);
    var wholeSeconds = Math.floor(frames / rate);
    var ff = frames % rate;
    var ss = wholeSeconds % 60;
    var mm = Math.floor(wholeSeconds / 60) % 60;
    var hh = Math.floor(wholeSeconds / 3600);
    return { negative: seconds < 0 && frames > 0, hh: hh, mm: mm, ss: ss, ff: ff };
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function formatTimeCode(seconds, rate) {
    var p = splitTimeCode(seconds, rate);
    if (!p || p.hh > 99) return null;
    return (p.negative ? "-" : "") + pad2(p.hh) + ":" + pad2(p.mm) + ":" + pad2(p.ss) + ":" + pad2(p.ff);
  }

  /* Seven segments a (top) b (upper right) c (lower right) d (bottom) e (lower left) f (upper left) g (middle). */
  var SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": ""
  };
  var SEG_RECT = { /* x, y, width, height inside a 10 x 18 cell */
    a: [1.5, 0.5, 7, 1.6], b: [8.0, 2.0, 1.6, 6.5], c: [8.0, 9.5, 1.6, 6.5], d: [1.5, 15.9, 7, 1.6],
    e: [0.4, 9.5, 1.6, 6.5], f: [0.4, 2.0, 1.6, 6.5], g: [1.5, 8.2, 7, 1.6]
  };
  var NS = "http://www.w3.org/2000/svg";

  function svgEl(name, attrs) {
    var el = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) el.setAttribute(k, attrs[k]);
    return el;
  }

  /* One clock face: a sign slot, eight digits and three colons. Returns {svg, set(text|null), setColor(hex)}. */
  function buildFace() {
    var cellW = 12, height = 18;
    var slots = ["sign", 0, 1, "colon", 2, 3, "colon", 4, 5, "colon", 6, 7];
    var widths = { sign: 8, colon: 5 };
    var x = 0, cells = [];
    var svg = svgEl("svg", { role: "img", "aria-hidden": "true", preserveAspectRatio: "xMinYMid meet" });
    var group = svgEl("g", {});
    svg.appendChild(group);
    slots.forEach(function (slot) {
      if (slot === "colon") {
        var c1 = svgEl("rect", { x: x + 1.6, y: 5, width: 1.8, height: 1.8, fill: "currentColor" });
        var c2 = svgEl("rect", { x: x + 1.6, y: 11.2, width: 1.8, height: 1.8, fill: "currentColor" });
        group.appendChild(c1); group.appendChild(c2);
        cells.push({ kind: "colon", els: [c1, c2] });
        x += widths.colon;
        return;
      }
      var w = slot === "sign" ? widths.sign : cellW;
      var segs = {};
      var cell = svgEl("g", { transform: "translate(" + x + ",0)" });
      "abcdefg".split("").forEach(function (s) {
        var r = SEG_RECT[s];
        var el = svgEl("rect", { x: r[0], y: r[1], width: r[2], height: r[3], rx: 0.5, fill: "currentColor" });
        el.setAttribute("opacity", String(UNLIT_OPACITY));
        cell.appendChild(el);
        segs[s] = el;
      });
      group.appendChild(cell);
      cells.push({ kind: slot === "sign" ? "sign" : "digit", segs: segs });
      x += w;
    });
    svg.setAttribute("viewBox", "0 0 " + x + " " + height);
    var totalWidth = x;
    var shown; /* last text drawn; repainting the same text is skipped (this runs every animation frame) */

    function lit(cell, chars) {
      for (var s in cell.segs) cell.segs[s].setAttribute("opacity", chars.indexOf(s) >= 0 ? "1" : String(UNLIT_OPACITY));
    }
    return {
      svg: svg,
      width: totalWidth,
      height: height,
      /* text like "-00:23:49:12", or null for dark (unknown) */
      set: function (text) {
        if (text === undefined) text = null;
        if (text === shown) return;
        shown = text;
        /* The drawn time as text, for screen readers and for tests that check what is on screen. */
        svg.setAttribute("data-time", text === null ? "" : text);
        var digitCells = cells.filter(function (c) { return c.kind === "digit"; });
        var signCell = cells.filter(function (c) { return c.kind === "sign"; })[0];
        var colons = cells.filter(function (c) { return c.kind === "colon"; });
        if (text === null) {
          digitCells.forEach(function (c) { lit(c, ""); });
          lit(signCell, "");
          colons.forEach(function (c) { c.els.forEach(function (e) { e.setAttribute("opacity", String(UNLIT_OPACITY)); }); });
          return;
        }
        var negative = text.charAt(0) === "-";
        var digits = text.replace(/[^0-9]/g, "");
        lit(signCell, negative ? SEGMENTS["-"] : "");
        digitCells.forEach(function (c, i) { lit(c, SEGMENTS[digits.charAt(i)] || ""); });
        colons.forEach(function (c) { c.els.forEach(function (e) { e.setAttribute("opacity", "1"); }); });
      },
      setColor: function (hex) { svg.style.color = hex; }
    };
  }

  function loadColor(row) {
    try {
      var saved = root.localStorage.getItem("pubcast.showClocks." + root.location.pathname + "." + row);
      if (saved && Object.prototype.hasOwnProperty.call(COLORS,saved)) return saved;
    } catch (e) { /* storage can be missing or blocked; the default colour stands */ }
    return DEFAULT_COLOR[row];
  }
  function saveColor(row, name) {
    try { root.localStorage.setItem("pubcast.showClocks." + root.location.pathname + "." + row, name); } catch (e) { /* ignore */ }
  }

  function mount() {
    var html = document.documentElement;
    if (html.getAttribute("data-show-clocks") === "off") return null;
    if (document.getElementById("pubcast-show-clocks")) return null;

    var box = document.createElement("div");
    box.id = "pubcast-show-clocks";
    box.setAttribute("role", "timer");
    box.setAttribute("aria-label", "Show clocks");
    box.style.cssText = "position:fixed;right:10px;bottom:10px;z-index:9000;background:" + PANEL +
      ";border:1px solid #26302d;border-radius:6px;padding:6px 8px;display:flex;flex-direction:column;gap:5px;" +
      "font:600 10px/1 Consolas,'Courier New',monospace;letter-spacing:1px;color:#9aa5a1;user-select:none;" +
      "box-shadow:0 2px 10px rgba(0,0,0,.5);pointer-events:none";
    /* The panel never takes clicks meant for the page under it; only the colour dots do. */

    var rows = {};
    ["top", "bottom"].forEach(function (row) {
      var line = document.createElement("div");
      line.style.cssText = "display:flex;align-items:center;gap:6px";
      var label = document.createElement("span");
      label.textContent = LABELS[row];
      label.style.cssText = "width:30px;text-align:right";
      var face = buildFace();
      face.svg.style.cssText = "display:block;width:min(" + Math.round(face.width * 4.2) + "px,calc(100vw - 110px));height:auto;aspect-ratio:" + face.width + "/" + face.height;
      var swatches = document.createElement("span");
      swatches.style.cssText = "display:flex;flex-direction:column;gap:2px";
      var state = { name: loadColor(row), buttons: {} };
      COLOR_ORDER.forEach(function (name) {
        var b = document.createElement("button");
        b.type = "button";
        b.title = LABELS[row] + " clock: " + name;
        b.setAttribute("aria-label", LABELS[row] + " clock " + name);
        b.style.cssText = "all:unset;box-sizing:border-box;width:14px;height:14px;border-radius:50%;cursor:pointer;" +
          "pointer-events:auto;background:" + COLORS[name] + ";opacity:.35";
        b.setAttribute("data-color", name);
        b.addEventListener("click", function () {
          state.name = name; saveColor(row, name); apply();
        });
        state.buttons[name] = b;
        swatches.appendChild(b);
      });
      function apply() {
        face.setColor(COLORS[state.name]);
        COLOR_ORDER.forEach(function (n) { state.buttons[n].style.opacity = n === state.name ? "1" : ".35";state.buttons[n].setAttribute("aria-pressed",String(n===state.name)); });
      }
      apply();
      line.setAttribute("data-clock", row);
      face.svg.setAttribute("data-clock-face", row);
      line.appendChild(label); line.appendChild(face.svg); line.appendChild(swatches);
      box.appendChild(line);
      rows[row] = { line: line, face: face };
    });
    document.body.appendChild(box);
    return { box: box, rows: rows };
  }

  function sample(j, requestedAt, receivedAt) {
    if(!j||STATES.indexOf(j.state)<0||typeof j.elapsed!=="number"||!isFinite(j.elapsed)||j.elapsed<0)throw new Error("Invalid timeline sample");
    if(!isFinite(requestedAt)||!isFinite(receivedAt)||receivedAt<requestedAt||receivedAt-requestedAt>MAX_SAMPLE_AGE)throw new Error("Timeline sample delayed");
    return {state:j.state,loaded:typeof j.timeline_name==="string"&&!!j.timeline_name,
      elapsed:j.elapsed,remaining:typeof j.remaining==="number"&&isFinite(j.remaining)?j.remaining:null,
      rate:SUPPORTED_RATES.indexOf(j.frame_rate)>=0?j.frame_rate:DEFAULT_RATE,
      at:receivedAt,requestedAt:requestedAt};
  }
  function display(s,now){
    if(!s||!s.loaded||now-s.requestedAt>MAX_SAMPLE_AGE||now<s.at)return {top:null,bottom:null};
    var delta=s.state==="running"?(now-s.at)/1000:0;
    return {top:formatTimeCode(Math.max(0,s.elapsed+delta),s.rate),
      bottom:s.remaining===null?null:formatTimeCode(s.remaining-delta,s.rate)};
  }
  function start() {
    var ui=mount();if(!ui)return;
    var snap=null,controller=null,stopped=false,revision=0,pollTimer,frame,changing=false;
    async function read(){
      if(stopped||controller||changing)return;
      var ctrl=new AbortController();controller=ctrl;var version=revision,requested=performance.now();
      var timer=setTimeout(function(){ctrl.abort();},MAX_SAMPLE_AGE);
      try{
        var res=await fetch(STATUS_URL,{credentials:"same-origin",cache:"no-store",signal:ctrl.signal});
        if(!res.ok)throw new Error("status "+res.status);
        var data=await res.json();
        if(!stopped&&version===revision&&!ctrl.signal.aborted)snap=sample(data,requested,performance.now());
      }catch(e){if(!stopped&&version===revision)snap=null;}
      finally{clearTimeout(timer);if(controller===ctrl)controller=null;}
    }
    function invalidate(){revision++;snap=null;controller?.abort();}
    function paint(){
      if(stopped)return;
      var value=display(snap,performance.now());
      ui.rows.top.face.set(value.top);ui.rows.bottom.face.set(value.bottom);
      ui.rows.bottom.line.style.display=value.bottom===null?"none":"flex";
      ui.box.setAttribute("aria-label",value.top===null?"Show clocks unavailable":"Show elapsed "+value.top+(value.bottom===null?"":", remaining "+value.bottom));
      frame=root.requestAnimationFrame(paint);
    }
    function begin(){changing=true;invalidate();}
    function changed(){changing=false;invalidate();read();}
    root.addEventListener("pubcast:timeline-changing",begin);
    root.addEventListener("pubcast:timeline-changed",changed);
    function suspend(){stopped=true;invalidate();root.clearInterval(pollTimer);root.cancelAnimationFrame(frame);}
    function resume(){if(!stopped)return;stopped=false;changing=false;read();pollTimer=root.setInterval(read,POLL_MS);frame=root.requestAnimationFrame(paint);}
    root.addEventListener("pagehide",suspend);
    root.addEventListener("pageshow",resume);
    read();pollTimer=root.setInterval(read,POLL_MS);frame=root.requestAnimationFrame(paint);
  }

  var api = { splitTimeCode: splitTimeCode, formatTimeCode: formatTimeCode, sample:sample, display:display, SEGMENTS: SEGMENTS, COLORS: COLORS };
  root.PubCastShowClocks = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (typeof document !== "undefined" && root.document) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
  }
})(typeof window !== "undefined" ? window : globalThis);
