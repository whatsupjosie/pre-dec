(() => {
  "use strict";
  const $ = id => document.getElementById("mini-" + id);
  const camera = $("camera"), mode = $("mode"), stick = $("stick");
  const rigApi = window.PubCastCameraRig;
  const degrees = rigApi.DEG;
  const monitor = window.PubCast25DRemoteFeed.create({
    targets: { preview: { image: $("screen"), status: $("feed-status") } }
  });
  const directions = {
    aim: ["pan_left", "pan_right", "tilt_up", "tilt_down"],
    truck: ["move_left", "move_right", "move_forward", "move_back"],
    roll_zoom: ["roll_left", "roll_right", "zoom_in", "zoom_out"]
  };
  const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  let sources = [], motionTimer = null, refreshTimer, pressedKey, pointer = null, axes;
  let rig, busy = false, motionVersion = 0, closed = false;
  const say = text => { $("status").textContent = text; };

  async function request(path, body, method = body ? "POST" : "GET") {
    const response = await fetch("/api/switcher/" + path, {
      method, cache: "no-store",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) {
      if (response.status === 403) throw Error("A moderator role is required for this control.");
      throw Error("Switcher " + path + " returned HTTP " + response.status);
    }
    return response.json();
  }

  function selectCamera() {
    stop();
    const source = sources.find(item => item.id === camera.value);
    const preset = source?.id.startsWith("p25d_");
    stick.disabled = !source || preset || !["virtual", "voxel_3d"].includes(source.transport);
    $("up").disabled = $("down").disabled = stick.disabled || mode.value !== "truck";
    $("preview").disabled = !source;
    monitor.setSources(null, preset ? source.id : null);
    if (!preset) $("feed-status").textContent = "Confidence preview unavailable for this source.";
  }

  function showState(next) {
    if (JSON.stringify(sources) !== JSON.stringify(next.sources)) {
      const previous = camera.value;
      sources = next.sources;
      camera.replaceChildren(...sources.map(source => new Option(source.name, source.id)));
      const preferred = sources.find(source => source.id === previous)
        || sources.find(source => source.id === next.preview) || sources[0];
      camera.value = preferred?.id || "";
      selectCamera();
    }
    $("cut").disabled = $("auto").disabled = !next.preview;
  }

  function stop() {
    motionVersion++;
    clearInterval(motionTimer);
    motionTimer = null;
    rig = null;
    axes = null;
    pressedKey = null;
    pointer = null;
  }

  async function steer(actions) {
    if (busy || stick.disabled || !actions.length) return;
    const version = motionVersion;
    const id = encodeURIComponent(camera.value);
    busy = true;
    try {
      if (!rig) {
        const current = await request("pose/" + id);
        if (version !== motionVersion) return;
        const [x, y, z] = current.position;
        const [tilt, pan, roll] = current.rotation;
        rig = rigApi.create({ x, y, z, tilt: tilt * degrees, pan: pan * degrees,
          roll: roll * degrees, fov: current.fov * degrees, focus: current.focus ?? 5 });
      }
      const pose = rig.step(0.12, rigApi.fromActions(rig.pose, actions));
      await request("ptz/" + id, {
        position: [pose.x, pose.y, pose.z],
        rotation: [pose.tilt / degrees, pose.pan / degrees, pose.roll / degrees],
        fov: pose.fov / degrees, focus: pose.focus
      });
      if (version === motionVersion) say("Camera pose confirmed.");
    } catch (error) {
      if (version === motionVersion) { stop(); say(error.message); }
    } finally {
      busy = false;
    }
  }

  function repeat() {
    const [x, y] = axes;
    const names = directions[mode.value];
    const actions = [];
    if (Math.abs(x) > 0.2) actions.push(names[x < 0 ? 0 : 1]);
    if (Math.abs(y) > 0.2) actions.push(names[y < 0 ? 2 : 3]);
    void steer(actions);
  }

  function start(x, y) {
    axes = [x, y];
    if (motionTimer !== null) return;
    repeat();
    motionTimer = setInterval(repeat, 120);
  }

  function drag(event) {
    if (pointer !== event.pointerId) return;
    const box = stick.getBoundingClientRect();
    start(2 * (event.clientX - box.left) / box.width - 1, 2 * (event.clientY - box.top) / box.height - 1);
  }

  stick.addEventListener("pointerdown", event => {
    if (pointer !== null) return;
    event.preventDefault();
    stick.focus();
    pointer = event.pointerId;
    stick.setPointerCapture(pointer);
    drag(event);
  });
  stick.addEventListener("pointermove", drag);
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) {
    stick.addEventListener(name, event => { if (pointer === event.pointerId) stop(); });
  }
  stick.addEventListener("blur", stop);
  stick.addEventListener("keydown", event => {
    if (!arrows[event.key]) return;
    event.preventDefault();
    pressedKey = event.key;
    start(...arrows[event.key]);
  });
  stick.addEventListener("keyup", event => { if (event.key === pressedKey) stop(); });
  camera.onchange = mode.onchange = selectCamera;
  $("up").onclick = () => { stop(); void steer(["move_up"]); };
  $("down").onclick = () => { stop(); void steer(["move_down"]); };

  async function command(path, label, body) {
    try {
      showState(await request(path, body, "POST"));
      say(label);
    } catch (error) { say(error.message); }
  }
  $("preview").onclick = () => command("preview/" + encodeURIComponent(camera.value), "Preview selected.");
  $("cut").onclick = () => command("cut", "Cut confirmed.");
  $("auto").onclick = () => command("transition", "Dissolve confirmed.", { type: "dissolve", duration_ms: 600 });

  async function refresh() {
    try {
      showState(await request("state"));
      await monitor.refresh();
      if ($("status").textContent === "Connecting…") say("Switcher connected.");
    } catch (error) { say(error.message); }
    finally { if (!closed) refreshTimer = setTimeout(refresh, 750); }
  }
  selectCamera();
  void refresh();
  window.addEventListener("blur", stop);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  window.addEventListener("pagehide", () => {
    closed = true;
    clearTimeout(refreshTimer);
    stop();
    monitor.stop();
  });
  window.addEventListener("pageshow", event => { if (event.persisted) location.reload(); });
})();
