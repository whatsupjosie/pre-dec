"""Real authenticated backend + Chromium acceptance for the television studio.

Run: python -m pytest -q tests/test_production25d_browser.py
No provider keys, microphone, display server or external services are required.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
GL_ARGS = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader",
           "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
           "--autoplay-policy=no-user-gesture-required"]
GENRES = ("news", "late_night", "debate", "political_discussion", "audience", "game", "variety", "general")


@pytest.fixture(scope="module")
def production_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("studio25d-server")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "PUBCAST_DATA_DIR": str(root / "data"),
           "PUBCAST_ENFORCE_AUTH": "1", "PUBCAST_JWT_SECRET": secrets.token_urlsafe(48)}
    base = f"http://127.0.0.1:{port}"
    with (root / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
                                    "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, timeout=2, trust_env=False) as api:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        if api.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        pytest.fail("Backend did not start: " + (root / "server.log").read_text()[-6000:])
                    time.sleep(.1)
                password = secrets.token_urlsafe(24) + "A9!"
                result = api.post("/api/auth/setup", json={"username": "engineer", "password": password,
                                                          "confirm_password": password})
                assert result.status_code == 201, result.text
                yield base, result.json(), api
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="module")
def production_browser():
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                args=GL_ARGS, executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
            )
        except pw.Error as exc:
            pytest.skip("Chromium unavailable: " + str(exc).splitlines()[0])
        yield browser
        browser.close()


@pytest.fixture
def studio(production_server, production_browser):
    base, auth, _ = production_server
    context = production_browser.new_context(viewport={"width": 1440, "height": 1000})
    import json
    context.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(auth["access_token"]) + ");"
                            "sessionStorage.setItem('pubcast_user'," + json.dumps(json.dumps({"username": "engineer", "role": "owner"})) + ");")
    context.add_init_script(COUNT_RECORDER_DATA)
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda exc: page.problems.append(str(exc)))
    page.goto(base + "/static/production25d.html")
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    yield page, context
    context.close()


# MediaRecorder only hands over data once the browser has actually encoded some
# (the studio asks for a chunk every second, and under load the first one can
# arrive late). Stopping before that point gives the studio nothing to save
# ("Recorder generated no video data"). Counting non-empty chunks lets a test wait
# for real media instead of guessing a delay. The counter only observes; the
# studio's own handlers are untouched.
COUNT_RECORDER_DATA = """(() => {
  const Native = window.MediaRecorder;
  if (!Native) return;
  window.__recorderChunks = 0;
  window.MediaRecorder = class extends Native {
    constructor(...args) {
      super(...args);
      this.addEventListener('dataavailable', e => { if (e.data && e.data.size > 0) window.__recorderChunks += 1; });
    }
  };
})();"""


def recorder_chunks(page):
    return page.evaluate("window.__recorderChunks || 0")


def wait_for_media_chunk(page, after=0):
    """Wait until the recorder has produced more non-empty chunks than `after`."""
    page.wait_for_function("(n) => (window.__recorderChunks || 0) > n", arg=after, timeout=30000)


def wait_for_actors(page):
    page.wait_for_function("""() => {
      const id = PubCast25DStudio.state().package;
      return !!window.PubCastGLB && PubCast25D.PACKAGES[id].performers.every(
        p => PubCastGLB.has('p25d-' + id + '-' + p.id));
    }""", timeout=30000)


@pytest.mark.parametrize("genre", GENRES)
def test_each_genre_loads_actual_glb_actors_and_distinct_camera_pixels(studio, genre):
    page, _ = studio
    page.evaluate("id => PubCast25DStudio.loadGenre(id)", genre)
    wait_for_actors(page)
    page.wait_for_function("document.querySelector('#program').getContext('2d').getImageData(40,40,1,1).data[3] > 0")
    assert page.evaluate("program.toDataURL() !== preview.toDataURL()")
    assert page.problems == []
    evidence = os.environ.get("PUBCAST_EVIDENCE_DIR")
    if evidence:
        Path(evidence).mkdir(parents=True, exist_ok=True)
        page.locator("#program").screenshot(path=str(Path(evidence) / (genre + ".png")))
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_makehuman_wave_advances_actual_rig_pixels(studio):
    page, _ = studio
    wait_for_actors(page)
    result = page.evaluate("""async () => {
      const g = PubCastGLB, id = 'gesture-probe';
      await g.load(id, './world/test_avatars/MakeHuman_Female.glb', 'Gesture probe');
      const canvas = document.createElement('canvas'); canvas.width = 400; canvas.height = 400;
      const ctx = canvas.getContext('2d');
      function draw(dt) {
        ctx.clearRect(0, 0, 400, 400);
        g.draw(ctx, id, 200, 380, 340, {moving:false, dt});
        return ctx.getImageData(0, 0, 400, 400).data;
      }
      const before = draw(0);
      const played = g.playClip(id, 'wave');
      for (let i=0;i<8;i++) draw(.1);
      const after = draw(0);
      let changed = 0;
      for (let i=0;i<before.length;i++) if (Math.abs(before[i]-after[i]) > 20) changed++;
      g.clear(id);
      return {played, changed};
    }""")
    assert result["played"]
    assert result["changed"] > 100, result
    assert page.problems == []


def test_two_real_pages_share_cut_and_actual_remote_frames(studio, production_server):
    page, context = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.wait_for_function("document.querySelector('#liveMedia').textContent.includes('CONFIRMED')")
    director = context.new_page()
    director.problems = []
    director.on("pageerror", lambda exc: director.problems.append(str(exc)))
    director.goto(production_server[0] + "/static/director_switcher.html")
    director.wait_for_function("""() => {
      const img = document.querySelector('#programMonitor img');
      return img && !img.hidden && img.naturalWidth === 640;
    }""", timeout=20000)
    old = page.evaluate("PubCast25DStudio.state()")
    assert director.evaluate("cut()") is True
    page.wait_for_function("id => PubCast25DStudio.state().program === id", arg=old["preview"])
    director.wait_for_function("document.querySelector('#programSource').textContent.includes('REAL 2.5D FRAME')")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    director.wait_for_function("document.querySelector('#programMonitor img').hidden")
    assert page.problems == []
    assert director.problems == []


def test_real_recording_reopens_after_reload_and_plays(studio):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    wait_for_media_chunk(page)
    page.wait_for_timeout(1500)  # Capture genuine time-varying media, not a mocked blob.
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.reload()
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    page.click("#sessionList button")
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    page.evaluate("playback.play()")
    page.wait_for_function("playback.currentTime > .1")
    assert page.locator("#alert").inner_text() == ""
    assert page.problems == []


def test_anonymous_cannot_drive_shared_cameras(production_server):
    _, _, api = production_server
    assert api.post("/api/switcher/cut").status_code == 401
    assert api.get("/api/studio25d/media/status").status_code in {401, 403}


def record_short_take(page):
    before = recorder_chunks(page)
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    wait_for_media_chunk(page, before)
    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording")


def test_slate_controls_stage_and_records_the_roll_before_any_upload(studio, production_server):
    import re

    page, _ = studio
    _, auth, api = production_server
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    path = "/api/studio/slate"
    created = api.post(path, headers=headers, json={"action": "create"})
    created.raise_for_status()
    edited = api.post(path, headers=headers, json={
        "action": "edit", "revision": created.json()["slate"]["revision"],
        "data": {"fields": {"production": "Pilot", "scene": "12A", "scene_title": "Night Shift",
                            "studio_package": "late_night", "take": "07"}},
    })
    edited.raise_for_status()
    try:
        page.wait_for_function("document.getElementById('genre').value === 'late_night'")
        wait_for_actors(page)
        page.click("#start")
        record_short_take(page)
        page.locator("#sessionList button").filter(has_text="Take 07").first.click()
        with page.expect_download() as download:
            page.click("#download")
        assert re.fullmatch(r"Pilot-Scene-12A-Night-Shift-Take-07_.*Z_\d\d-\d\d-\d\d-\d\d_.*\.(webm|mp4)",
                            download.value.suggested_filename)
        current = api.get(path, headers=headers).json()
        assert current["slate"]["fields"]["take"] == "08"
        assert [take["take"] for take in current["takes"]] == ["07"]
        assert api.get("/api/studio25d/recordings", headers=headers).json()["takes"] == []
    finally:
        current = api.get(path, headers=headers).json()["slate"]
        api.post(path, headers=headers, json={"action": "end", "revision": current["revision"]})


def test_multiple_takes_keep_original_media_bytes(studio):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    record_short_take(page)
    first = page.evaluate("""async () => {
      const session = (await PubCast25DStore.list())[0];
      const item = await PubCast25DStore.read(session.id);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await item.blob.arrayBuffer()))).join(',');
      return {session:session.id, take:session.media.id || session.id, hash};
    }""")
    page.click("#moveRight")
    record_short_take(page)
    result = page.evaluate("""async first => {
      const item = await PubCast25DStore.read(first.session, first.take);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await item.blob.arrayBuffer()))).join(',');
      return {count:item.session.recordings?.length || 0, hash};
    }""", first)
    assert result["hash"] == first["hash"], "Starting a second take replaced the first recording"
    assert result["count"] == 2
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.reload()
    page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
    assert page.locator("#sessionList button").filter(has_text="Take ").count() == 2
    assert page.locator("#sessionList button").filter(has_text="SYNC:").count() == 2


SLOW_TO_FIRST_DATA = """() => {
  // A busy machine encodes its first frame late; a Stop before that finds the recorder with nothing to hand over. This
  // reproduces exactly that: data events in the first 1.3 s after start are withheld from the studio, as measured when
  // the host's CPUs were saturated (idle machines produce data even 150 ms in, so load alone is not repeatable).
  const Native = window.MediaRecorder;
  window.MediaRecorder = class extends Native {
    start(slice) { this.__t0 = performance.now(); return super.start(slice); }
    set ondataavailable(fn) { super.ondataavailable = fn && (e => { if (performance.now() - this.__t0 < 1300) return; fn.call(this, e); }); }
    get ondataavailable() { return super.ondataavailable; }
  };
}"""


def test_a_very_short_take_is_still_saved_when_the_recorder_is_slow_to_produce_data(studio):
    page, _ = studio
    wait_for_actors(page)
    page.evaluate(SLOW_TO_FIRST_DATA)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.wait_for_timeout(150)
    page.click("#recordStop")                      # an ordinary Stop, 150 ms in
    page.wait_for_function("!PubCast25DStudio.state().recording", timeout=15000)
    result = page.evaluate("""async () => {
      const session = (await PubCast25DStore.list())[0];
      const item = await PubCast25DStore.read(session.id);
      return {bytes: item.blob ? item.blob.size : 0, takes: (session.recordings || []).length, alert: document.querySelector('#alert').innerText};
    }""")
    assert result["alert"] == "", result
    assert result["bytes"] > 1000 and result["takes"] == 1, result


def test_failed_storage_keeps_a_downloadable_take_and_retries(studio, tmp_path):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.evaluate("""() => {
      window.originalStudioSave = PubCast25DStore.save;
      PubCast25DStore.save = (session, blob) => blob
        ? Promise.reject(new DOMException('Storage full', 'QuotaExceededError'))
        : originalStudioSave(session, blob);
    }""")
    record_short_take(page)
    assert page.locator("#recoveryPanel").is_visible()
    assert page.locator("#record").is_disabled()
    with page.expect_download() as download:
        page.click("#recoveryDownload")
    downloaded = download.value
    downloaded.save_as(tmp_path / "recovered.webm")
    assert (tmp_path / "recovered.webm").stat().st_size > 1000
    page.evaluate("() => { PubCast25DStore.save = originalStudioSave; }")
    page.click("#recoverySave")
    page.wait_for_function("document.querySelector('#recoveryPanel').hidden")
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.click("#sessionList button")
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    # The deliberate storage exception is logged; it must have a recovery path.
    assert page.locator("#alert").inner_text() == ""


def test_recorder_error_preserves_available_media_as_incomplete(studio):
    page, _ = studio
    wait_for_actors(page)
    page.evaluate("""() => {
      const NativeRecorder=window.MediaRecorder;
      window.MediaRecorder=class extends NativeRecorder {
        constructor(...args){super(...args);window.testRecorder=this;}
      };
    }""")
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    wait_for_media_chunk(page)
    page.evaluate("testRecorder.dispatchEvent(new Event('error'))")
    page.wait_for_function("!PubCast25DStudio.state().recording")
    result = page.evaluate("""async () => {
      const session=(await PubCast25DStore.list())[0];
      const item=await PubCast25DStore.read(session.id);
      return {incomplete:session.media.incomplete,bytes:item.blob.size};
    }""")
    assert result["incomplete"] is True and result["bytes"] > 1000
    assert "INCOMPLETE" in page.locator("#sessionList").inner_text()


def test_remote_panic_stops_real_capture_blacks_program_and_silences_audio(studio, production_server):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.evaluate("""() => {
      const audio=PubcastProgramAudio, ctx=audio.context;
      const osc=ctx.createOscillator();osc.frequency.value=440;
      window.panicAnalyser=ctx.createAnalyser();panicAnalyser.fftSize=512;
      audio.master.connect(panicAnalyser);osc.connect(audio.master);osc.start();
      window.panicTone=osc;
      window.panicRMS=()=>{
        const values=new Float32Array(512);panicAnalyser.getFloatTimeDomainData(values);
        return Math.sqrt(values.reduce((sum,value)=>sum+value*value,0)/values.length);
      };
    }""")
    page.wait_for_function("panicRMS() > .1")
    wait_for_media_chunk(page)
    _, auth, api = production_server
    response = api.post("/api/production/panic", headers={"Authorization": "Bearer " + auth["access_token"]})
    assert response.status_code == 200 and response.json()["ok"] is True
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.wait_for_function("panicRMS() < .00001")
    page.wait_for_function("program.getContext('2d').getImageData(640,360,1,1).data.slice(0,3).every(x=>x===0)")
    assert "PANIC" in page.locator("#state").inner_text()
    assert page.evaluate("async () => ((await PubCast25DStore.list())[0].media.bytes > 1000)")
    page.evaluate("panicTone.stop()")


def test_approved_voxel_prop_reaches_cut_and_decoded_take(studio, production_server, tmp_path):
    import shutil

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is needed to decode the captured frame")
    page, _ = studio
    _, auth, api = production_server
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    # The preceding panic test leaves a shared blackout on this module's host.
    api.post("/api/production/video-cue", headers=headers,
             json={"cue": "blackout", "enabled": False}).raise_for_status()
    approved = api.post("/api/visual-patch/approve", headers=headers, json={
        "scene_id": "pubworld_stage", "label": "Voxel camera acceptance prop",
        "approval": {"state": "approved"}, "patch_kind": "visual_patch",
        "proposal": {"patch_id": "voxel_browser_test", "dimensions": [4, 4, 4], "color_hint": "skin"},
    })
    approved.raise_for_status()
    prop_id = approved.json()["prop"]["prop_id"]
    package = "/api/studio25d/voxel-props/news"
    page.evaluate("""() => {
      window.propPixel = id => {
        const canvas = document.getElementById(id);
        const ctx = canvas.getContext('2d');
        const pixels = ctx.getImageData(360, 180, 310, 340);
        for (let y=4; y<pixels.height-4; y+=2) for (let x=4; x<pixels.width-4; x+=2) {
          const hasColor=(dx,dy)=>{
            const i=((y+dy)*pixels.width+x+dx)*4;
            return pixels.data[i]===197&&pixels.data[i+1]===143&&pixels.data[i+2]===114;
          };
          if(hasColor(0,0)&&hasColor(4,0)&&hasColor(-4,0)&&hasColor(0,4)&&hasColor(0,-4))
            return [360+x,180+y];
        }
        return null;
      };
    }""")
    try:
        page.click("#refreshVoxelProps")
        page.wait_for_function("id => Array.from(voxelProp.options).some(o=>o.value===id)", arg=prop_id)
        assert page.evaluate("propPixel('program')") is None
        page.select_option("#voxelProp", prop_id)
        page.fill("#voxelX", "40")
        page.fill("#voxelY", "67")
        page.fill("#voxelSize", "23")
        page.locator("#voxelPlacement button[type=submit]").click()
        page.wait_for_function("voxelStatus.textContent.includes('Placed:')")
        page.wait_for_function("propPixel('program') !== null")
        page.click("#start")
        page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
        page.click("#cut")
        page.wait_for_function("PubCast25DStudio.state().program === 'anchor'")
        page.locator('[data-shot="wide"]').click()
        page.wait_for_function("PubCast25DStudio.state().preview === 'wide'")
        page.wait_for_function("propPixel('preview') !== null")
        page.click("#cut")
        page.wait_for_function("PubCast25DStudio.state().program === 'wide'")
        coord = page.wait_for_function("propPixel('program')").json_value()
        record_short_take(page)
        page.locator("#sessionList button").first.click()
        page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
        with page.expect_download() as take:
            page.click("#download")
        video = tmp_path / take.value.suggested_filename
        take.value.save_as(video)
        raw = subprocess.run([ffmpeg, "-v", "error", "-i", str(video), "-frames:v", "1",
                              "-pix_fmt", "rgb24", "-threads", "1", "-f", "rawvideo", "-"],
                             check=True, capture_output=True).stdout
        assert len(raw) == 1280 * 720 * 3
        x, y = coord
        rgb = raw[(y * 1280 + x) * 3:(y * 1280 + x) * 3 + 3]
        assert all(abs(actual - expected) < 17 for actual, expected in zip(rgb, (197, 143, 114))), rgb
        with page.expect_download() as manifest:
            page.click("#manifest")
        import json
        session = json.loads(manifest.value.path().read_text())
        assert session["voxelPlacement"]["prop_id"] == prop_id
        assert session["voxelPlacement"]["block_count"] == 56
        assert not page.problems
    finally:
        api.put(package, headers=headers, json={"placement": None}).raise_for_status()


def test_external_program_camera_blocks_roll_and_preserves_interrupted_take(studio, production_server):
    page, _ = studio
    _, auth, api = production_server
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    api.post("/api/production/video-cue", headers=headers,
             json={"cue": "blackout", "enabled": False}).raise_for_status()
    page.click("#start")
    page.wait_for_function("switcherLink.textContent === 'VIDEO: SHARED SWITCHER'")

    api.post("/api/switcher/cut/wide_shot", headers=headers).raise_for_status()
    page.wait_for_function("programShot.textContent.includes('wide_shot')")
    assert page.locator("#record").is_disabled()
    cause = page.evaluate("PubCast25DStudio.startRecording().catch(error => error.message)")
    assert "local video feed" in cause
    assert recorder_chunks(page) == 0

    api.post("/api/switcher/cut/p25d_news_wide", headers=headers).raise_for_status()
    page.wait_for_function("!record.disabled")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    page.wait_for_function("PubCast25DStudio.state().journal?.bytes > 0", timeout=30000)
    api.post("/api/switcher/cut/wide_shot", headers=headers).raise_for_status()
    page.wait_for_function("!PubCast25DStudio.state().recording")
    page.wait_for_function("sessionList.textContent.includes('INCOMPLETE')")
    page.locator("#sessionList button").first.click()
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    assert page.locator("#record").is_disabled()


def test_slate_save_preserves_edits_typed_while_a_request_is_in_flight(studio, production_server):
    page, _ = studio
    _, auth, api = production_server
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    path = "/api/studio/slate"
    created = api.post(path, headers=headers, json={"action": "create"})
    created.raise_for_status()
    held = []

    def delay_first_edit(route):
        request = route.request
        if request.method == "POST" and request.post_data_json.get("action") == "edit" and not held:
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/studio/slate", delay_first_edit)
    try:
        page.evaluate("PubCastSlate.open()")
        notes = page.locator("#pubcast-slate-floor [name=notes]")
        submit = page.locator('#pubcast-slate-floor [data-action="save"]')
        notes.fill("First edit")
        submit.click()
        import time
        deadline = time.monotonic() + 5
        while not held and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        assert held
        notes.fill("Second edit typed while saving")
        held[0].continue_()
        page.wait_for_function("""document.querySelector('#pubcast-slate-floor .status')
                                   .textContent.includes('Newer edits are still unsaved')""")
        assert notes.input_value() == "Second edit typed while saving"
        with page.expect_response(lambda response: response.url.endswith(path) and response.request.method == "POST"):
            submit.click()
        slate = api.get(path, headers=headers).json()["slate"]
        assert slate["fields"]["notes"] == "Second edit typed while saving"
    finally:
        page.unroute("**/api/studio/slate", delay_first_edit)
        current = api.get(path, headers=headers).json()["slate"]
        api.post(path, headers=headers, json={"action": "end", "revision": current["revision"]})


def test_launch_panel_starts_and_finalizes_the_selected_backend_camera(studio, production_server):
    import shutil

    if not shutil.which("ffmpeg"):
        pytest.skip("The launch panel needs FFmpeg to capture its test-pattern source")
    page, _ = studio
    base, auth, api = production_server
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    api.post("/api/switcher/cut/wide_shot", headers=headers).raise_for_status()
    page.goto(base + "/static/launch.html")
    page.locator("#btn-on").click()
    page.wait_for_function("document.querySelector('#launch-status').textContent.includes('capture started')")
    active = [row for row in api.get("/api/recording/sessions", headers=headers).json()
              if row["state"] == "active"]
    assert len(active) == 1
    assert active[0]["sources"] == ["wide_shot"]
    page.wait_for_timeout(1500)
    page.locator("#btn-on").click()
    page.wait_for_function("!document.querySelector('#btn-on').classList.contains('live')")
    recorded = next(row for row in api.get("/api/recording/sessions", headers=headers).json()
                    if row["session_id"] == active[0]["session_id"])
    assert recorded["state"] == "stopped"
    assert any(artifact["size_bytes"] > 1000 for artifact in recorded["artifacts"])
    assert recorded["artifacts"][0]["name"].endswith(".mp4")
    assert not page.problems
