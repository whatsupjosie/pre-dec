"""Reconstruction, end to end: a data-only take of a 2.5D show, rendered afterwards from four camera angles.

Real host (``run_reach.py``, throwaway data folder), real HTTP with an owner login, real FFmpeg, a real headless
browser running the studio's own renderer. The take: the late-night set, a host and a guest, the guest walks, the host
gestures, the lower third comes on, Program cuts, dissolves and cuts again, the take pauses and resumes. Performer
frames are sent to /api/performance/frame exactly as the 2.5D studio is to send them. A live network source (FFmpeg
over UDP multicast, as a network microphone would arrive) beeps at 1 kHz for 0.1 s at the start of every second of its
own clock, and keeps beeping through the pause, so the data-only take records real, time-marked sound.

What is proved, from the files themselves (ffprobe, full decode, pixels and spectrum), not from HTTP status codes:

* the program reconstruction follows the cuts and the dissolve at the times they happened, with the pause taken out;
  mid-dissolve frames are a blend of the two cameras;
* the same take renders from a camera that was never on Program, and from a framing that never existed live;
* where a performer stood is where the picture puts them: the guest's walk moves him from 0.69 to 0.55 of the frame;
* parallax: moving the framing moves the desk about five times as far as the back wall;
* the take's sound is in every reconstruction, as long as the picture, and stays in sync across the pause: on the
  reconstruction's timeline the beeps come every 1.0 s, and after the pause their phase has moved by exactly the pause
  (the source kept beeping while nothing was recorded), which only holds if each piece is placed where it was recorded;
* rendering twice gives the same frames, bit for bit;
* nothing sent while paused is in the show data; an unauthenticated sender is refused; a take still recording is not
  reconstructed.

Skips without ffmpeg/ffprobe, Playwright, a browser it can start, or multicast on the loopback interface.
"""
from __future__ import annotations

import gzip
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("playwright")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)
from modules.reconstruction import find_browser  # noqa: E402

if not find_browser().get("available"):
    pytest.skip("no browser for rendering: " + str(find_browser().get("reason")), allow_module_level=True)

W, H = 1280, 720
CAMS = ["wide", "host", "guest", "interview", "performance"]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_host(data):
    (data / "assets").mkdir(parents=True)
    port = _free_port()
    log = open(data / "host.log", "w", encoding="utf-8")
    env = {**os.environ, "PUBCAST_ASSETS_DIR": str(data / "assets")}
    proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data / "data"),
                             "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            log.flush()
            raise AssertionError("run_reach.py exited during startup:\n" + (data / "host.log").read_text()[-4000:])
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(0.3)
    else:
        raise AssertionError("host did not start within 120 s")
    password = secrets.token_urlsafe(20)
    assert httpx.post(base + "/api/auth/setup", json={"username": "owner", "password": password,
                                                     "confirm_password": password}, timeout=10).status_code in (200, 201)
    login = httpx.post(base + "/api/auth/login", json={"username": "owner", "password": password}, timeout=10)
    assert login.status_code == 200, login.text
    client = httpx.Client(base_url=base, headers={"Authorization": "Bearer " + login.json()["access_token"]}, timeout=300)
    return SimpleNamespace(base=base, client=client, proc=proc, log=log, data=data / "data")


def _multicast_works():
    group = "udp://239.255.7.251:5004"
    sender = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-re", "-f", "lavfi", "-i", "sine=f=500:r=48000",
                               "-t", "6", "-c:a", "aac", "-f", "mpegts", group + "?ttl=0&pkt_size=1316"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        got = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", group + "?reuse=1", "-t", "1", "-f", "null", "-"],
                             capture_output=True, timeout=8)
        return got.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        sender.kill(); sender.wait()


BEEP_URL = "udp://239.255.7.9:5004"


def stage(guest_x=0.69, *, moving=False, lower=False, jaw=None, gestures=None, client_ms=None):
    host = {"id": "p25d-late_night-performer-1", "slot": "host", "avatar": "female", "position": [0.31, 0.82]}
    if jaw is not None:
        host["jaw"] = jaw
    body = {"package": "late_night", "lowerThird": lower, "lowerText": "RECONSTRUCTED",
            "performers": [host, {"id": "p25d-late_night-performer-2", "slot": "guest", "avatar": "male",
                                  "position": [guest_x, 0.82], "vx": -0.14 if moving else 0.0, "moving": moving}]}
    if gestures:
        body["gestures"] = gestures
    if client_ms is not None:
        body["client_ms"] = client_ms
    return body


@pytest.fixture(scope="module")
def take(tmp_path_factory):
    work = tmp_path_factory.mktemp("reconstruct")
    h = _start_host(work / "host")
    c = h.client
    try:
        for cam in CAMS:      # registered the way static/production25d_switcher_bridge.js registers them
            r = c.post("/api/cameras/register", json={"source_id": f"p25d_late_night_{cam}", "name": f"Late night / {cam}",
                                                      "location": "studio25d", "transport": "virtual",
                                                      "endpoint": f"virtual://p25d_late_night_{cam}",
                                                      "tags": ["virtual", "studio25d", "late_night"]})
            assert r.status_code == 200, r.text
        if not _multicast_works():
            pytest.skip("UDP multicast on the loopback interface is not available here")
        beeper = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-re", "-f", "lavfi",
             "-i", "aevalsrc='0.5*sin(2*PI*1000*t)*lt(mod(t\\,1)\\,0.1)':s=48000",
             "-c:a", "aac", "-f", "mpegts", BEEP_URL + "?ttl=0&pkt_size=1316"],
            stdout=subprocess.DEVNULL, stderr=open(work / "beeper.log", "w"))
        r = c.post("/api/cameras/register", json={"source_id": "beep_mic", "name": "Network microphone", "transport": "srt",
                                                  "endpoint": BEEP_URL + "?reuse=1", "location": "studio"})
        assert r.status_code == 200, r.text
        time.sleep(1.5)
        assert c.post("/api/switcher/select", json={"program": "p25d_late_night_wide",
                                                    "preview": "p25d_late_night_host"}).status_code == 200

        anon = httpx.put(h.base + "/api/performance/frame", json=stage(), timeout=10)
        assert anon.status_code in (401, 403), anon.text

        assert c.put("/api/performance/frame", json=stage()).status_code == 200   # the show is on before the take
        r = c.post("/api/program-audio/channels/guest", json={"source_id": "beep_mic", "gain": 1.0})
        assert r.status_code == 200, r.text
        sid = "recon_e2e_" + secrets.token_hex(3)
        r = c.post("/api/recording/start", json={"mode": "data_only", "sources": ["beep_mic"], "profile_id": "web_stream",
                                                 "countdown_seconds": 0, "session_id": sid})
        assert r.status_code == 200, r.text
        t0 = time.time()

        def at(seconds):
            while time.time() - t0 < seconds:
                time.sleep(0.005)

        def send(body):
            r = c.put("/api/performance/frame", json=body)
            assert r.status_code == 200, r.text
            return r.json()

        assert send(stage(lower=False, jaw=0.0))["takes_recording"] == 1
        early = c.post(f"/api/recording/{sid}/reconstruct", json={"camera": "program"})
        assert early.status_code == 409, early.text
        at(1.5)
        assert c.post("/api/switcher/cut/p25d_late_night_host").status_code == 200
        at(3.0)
        send(stage(0.55, moving=True))
        at(3.45)
        send(stage(0.55))
        at(3.5)
        send(stage(0.55, gestures=[{"performer": "p25d-late_night-performer-1", "clip": "Wave"}]))
        at(4.0)
        send(stage(0.55, lower=True))
        at(4.5)
        r = c.post("/api/switcher/transition", json={"camera_id": "p25d_late_night_guest", "type": "dissolve", "duration_ms": 800})
        assert r.status_code == 200, r.text
        at(6.0)
        assert c.post(f"/api/recording/{sid}/pause", json={"paused": True}).status_code == 200
        send(stage(0.20, lower=True))                       # while paused: must not be kept
        at(7.5)
        send(stage(0.55, lower=True))                       # back where it was, so the resume shows no jump
        assert c.post(f"/api/recording/{sid}/pause", json={"paused": False}).status_code == 200
        at(8.0)
        send(stage(0.55, lower=True, jaw=0.8))
        at(9.0)
        assert c.post("/api/switcher/cut/p25d_late_night_wide").status_code == 200
        meters = []
        while time.time() - t0 < 10.9:         # steady sound: the beeper has been flowing for seconds
            meters.append(c.get("/api/program-audio/meters").json()["recording_inputs"])
            time.sleep(0.1)
        at(11.0)
        r = c.post("/api/program-audio/channels/guest", json={"gain": 0.25})       # the guest is brought down 12 dB
        assert r.status_code == 200, r.text
        at(13.5)
        stopped = c.post(f"/api/recording/{sid}/stop")
        assert stopped.status_code == 200, stopped.text
        wall = time.time() - t0

        jobs = {}
        for name, body in {"program": {"camera": "program", "fps": 30},
                           "guest": {"camera": "p25d_late_night_guest", "fps": 24, "label": "guest-a"},
                           "guest_again": {"camera": "p25d_late_night_guest", "fps": 24, "label": "guest-b"},
                           "left": {"camera": {"center": [0.3, 0.5], "zoom": 1}, "fps": 24, "label": "left"},
                           "right": {"camera": {"center": [0.7, 0.5], "zoom": 1}, "fps": 24, "label": "right"}}.items():
            r = c.post(f"/api/recording/{sid}/reconstruct", json=body)
            assert r.status_code == 200, r.text
            jobs[name] = r.json()["job_id"]
        results = {}
        deadline = time.time() + 1200
        for name, job_id in jobs.items():
            while True:
                job = c.get(f"/api/reconstruction/jobs/{job_id}").json()
                if job["state"] in ("complete", "failed", "cancelled"):
                    break
                assert time.time() < deadline, f"{name} did not finish: {job}"
                time.sleep(1)
            assert job["state"] == "complete", job
            results[name] = job["result"]
        folder = h.data / "recordings" / sid
        yield SimpleNamespace(h=h, sid=sid, folder=folder, wall=wall, results=results, meters=meters,
                              manifests={k: json.loads((folder / v["manifest"]).read_text()) for k, v in results.items()},
                              files={k: folder / v["file"] for k, v in results.items()})
    finally:
        if "beeper" in locals():
            beeper.kill(); beeper.wait()
        c.close()
        h.proc.terminate()
        try:
            h.proc.wait(20)
        except subprocess.TimeoutExpired:
            h.proc.kill(); h.proc.wait(5)
        h.log.close()


# --- helpers ----------------------------------------------------------------------------------------------------
def probe(path):
    out = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json",
                                              str(path)], timeout=60))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    a = next((s for s in out["streams"] if s["codec_type"] == "audio"), None)
    return SimpleNamespace(seconds=float(out["format"]["duration"]), codec=v["codec_name"], w=v["width"], h=v["height"],
                           fps=v["avg_frame_rate"], audio=a, audio_seconds=float(a["duration"]) if a else 0.0)


def frame_at(path, t, *, gray=False):
    fmt, ch = ("gray", 1) if gray else ("rgb24", 3)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", fmt, "-"], capture_output=True, check=True, timeout=60).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, ch).astype(float)


def dominant_hz(path, start=1.0, seconds=2.0):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(start), "-i", str(path), "-vn", "-t", str(seconds),
                          "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True, timeout=60).stdout
    samples = np.frombuffer(raw, dtype="<i2").astype(float)
    assert len(samples) > 48000, "less than a second of sound"
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return float(np.argmax(spectrum) * 48000 / len(samples))


def beep_onsets(path):
    """Take-time seconds where each 1 kHz beep starts, from the decoded sound (10 ms windows)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", "48000",
                          "-f", "s16le", "-"], capture_output=True, check=True, timeout=120).stdout
    x = np.frombuffer(raw, dtype="<i2").astype(float)
    win = 480
    energy = np.array([np.abs(x[i:i + win]).mean() for i in range(0, len(x) - win, win)])
    loud = energy > 0.05 * energy.max()          # beeps after the guest is brought down 12 dB are a quarter as loud
    starts = [i for i in range(1, len(loud)) if loud[i] and not loud[i - 1]]
    onsets = []
    for i in starts:          # refine to the sample where the beep rises
        seg = np.abs(x[(i - 1) * win:(i + 1) * win])
        onsets.append(((i - 1) * win + int(np.argmax(seg > 0.05 * energy.max()))) / 48000)
    return onsets


def skin_centroid_x(img, x_from):
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    mask = (r > 150) & (r > g + 15) & (g > b + 10) & (b > 60)
    mask[:, : int(x_from * W)] = False
    mask[:300, :] = False                       # the set title and the back wall's gold lines
    mask[565:, :] = False                       # the desk top and everything below it
    ys, xs = np.nonzero(mask)
    assert len(xs) > 400, "no performer found in the picture"
    return xs.mean() / W


def shift_between(a, b, rows):
    """How many pixels picture b is moved right of picture a, in a band of rows (column brightness profiles)."""
    pa, pb = a[rows].mean(axis=(0, 2)), b[rows].mean(axis=(0, 2))
    pa, pb = pa - pa.mean(), pb - pb.mean()
    best = max(range(-80, 81), key=lambda s: float(np.dot(pa[max(0, -s):W - max(0, s)], pb[max(0, s):W - max(0, -s)])))
    return best


def framemd5(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v", "-f", "framemd5", "-"],
                         capture_output=True, text=True, check=True, timeout=300).stdout
    return [line.split(",")[-1].strip() for line in out.splitlines() if line and not line.startswith("#")]


# --- the files --------------------------------------------------------------------------------------------------
def test_every_reconstruction_is_valid_decodable_media_of_the_take_length(take):
    expected = take.manifests["program"]["take"]["duration"]
    lines = [json.loads(line) for line in gzip.open(take.folder / "show_data.jsonl.gz")]
    opened, closed = lines[0]["utc_origin"], lines[-1]["closed_utc"]
    pause = take.manifests["program"]["take"]["paused_seconds"]
    assert pause == pytest.approx(1.5, abs=0.25)                          # pause asked at 6.0 s, resume at 7.5 s
    assert expected == pytest.approx(closed - opened - pause, abs=0.01)   # the take's own clock, pause taken out
    for name, path in take.files.items():
        info = probe(path)
        m = take.manifests[name]
        assert (info.codec, info.w, info.h) == ("h264", W, H), name
        assert info.seconds == pytest.approx(m["frames"] / m["request"]["fps"], abs=0.1), name
        assert info.seconds == pytest.approx(expected, abs=0.1), name
        assert m["verification"]["decode"]["ok"], (name, m["verification"])
        assert info.audio is not None and info.audio_seconds == pytest.approx(info.seconds, abs=0.15), name
        assert len(beep_onsets(path)) >= int(info.seconds) - 2, name
        assert m["sound"] and m["sound"][0]["file"].endswith(".wav")
        assert m["renderer"]["browser"] and set(m["renderer"]["files"]) >= {"static/production25d_renderer.js"}


def test_the_reconstructions_are_kept_with_the_take(take):
    meta = take.h.client.get("/api/recording/sessions").json()
    sessions = meta.get("sessions", meta) if isinstance(meta, dict) else meta
    session = next(s for s in sessions if s.get("session_id") == take.sid)
    names = {a.get("name") for a in session.get("artifacts", [])}
    assert {p.name for p in take.files.values()} <= names
    assert {take.results[k]["manifest"] for k in take.results} <= set(session.get("data_files", []))


def show_events(take):
    lines = [json.loads(line) for line in gzip.open(take.folder / "show_data.jsonl.gz")]
    return lines[0], [l for l in lines if l.get("kind")]


def take_time(take, show_t):
    _, events = show_events(take)
    paused = [e["t"] for e in events if e["kind"] == "take.paused"]
    resumed = [e["t"] for e in events if e["kind"] == "take.resumed"]
    return show_t - sum(min(b, show_t) - a for a, b in zip(paused, resumed) if a < show_t)


def test_program_follows_the_cuts_and_dissolve_with_the_pause_taken_out(take):
    stretches = take.manifests["program"]["stretches"]
    shows = [s["shows"] for s in stretches]
    assert shows == ["camera p25d_late_night_wide", "camera p25d_late_night_host",
                     "dissolve p25d_late_night_host -> p25d_late_night_guest",
                     "camera p25d_late_night_guest", "camera p25d_late_night_wide"], shows
    _, events = show_events(take)
    cuts = [e for e in events if e["kind"] == "camera.switch" and e["data"]["destination"] == "program"]
    assert len(cuts) == 3
    frame = 1 / 30
    expected = [take_time(take, cuts[0]["t"]), take_time(take, cuts[1]["t"]), take_time(take, cuts[1]["t"]) + 0.8,
                take_time(take, cuts[2]["t"])]
    for stretch, want in zip(stretches[1:], expected):
        assert stretch["from"] == pytest.approx(want, abs=frame + 1e-3), (stretch, want)
    assert not any(s.get("black") for s in stretches)


def test_sound_stays_in_sync_across_the_pause(take):
    """Beeps 1.0 s apart; across the pause their phase moves by the pause, mod 1 s, within 25 ms."""
    m = take.manifests["program"]
    pause = m["take"]["paused_seconds"]
    _, events = show_events(take)
    paused_at = take_time(take, next(e["t"] for e in events if e["kind"] == "take.paused"))
    onsets = beep_onsets(take.files["program"])
    before = [t for t in onsets if 0.3 < t < paused_at - 0.3]
    after = [t for t in onsets if paused_at + 1.2 < t < m["take"]["duration"] - 0.3]
    assert len(before) >= 4 and len(after) >= 3, (onsets, paused_at)
    for run in (before, after):
        assert np.diff(run) == pytest.approx(np.ones(len(run) - 1), abs=0.012), run
    phase_before = np.median(np.mod(before, 1.0))
    phase_after = np.median(np.mod(after, 1.0))
    drift = (phase_after - (phase_before - pause)) % 1.0
    drift = min(drift, 1.0 - drift)
    assert drift < 0.025, (phase_before, phase_after, pause, drift)
    placement = m["sound"][0]["placement"]
    assert len(placement) == 2 and not m["sound_notes"], (placement, m["sound_notes"])
    assert placement[1]["at"] == pytest.approx(paused_at, abs=0.8)       # the second piece starts after the pause


def test_a_mid_dissolve_frame_is_a_blend_of_the_two_cameras(take):
    path = take.files["program"]
    _, events = show_events(take)
    cut = take_time(take, [e for e in events if e["kind"] == "camera.switch" and e["data"]["destination"] == "program"][1]["t"])
    before, mid, after = frame_at(path, cut - 0.1), frame_at(path, cut + 0.4), frame_at(path, cut + 1.1)
    blend = (before + after) / 2
    d_blend = np.abs(mid - blend).mean()
    assert d_blend < 0.5 * min(np.abs(mid - before).mean(), np.abs(mid - after).mean()), d_blend


def test_alternate_angles_never_cut(take):
    assert [s["shows"] for s in take.manifests["guest"]["stretches"]] == ["camera p25d_late_night_guest"]
    assert len(take.manifests["left"]["stretches"]) == 1
    program, guest = frame_at(take.files["program"], 0.5), frame_at(take.files["guest"], 0.5)
    assert np.abs(program - guest).mean() > 20                         # Program was wide then; this is the close-up


def test_the_guest_is_where_the_performer_data_put_him(take):
    left = take.files["left"]          # zoom 1: the whole stage
    _, events = show_events(take)
    walk = take_time(take, next(e["t"] for e in events if e["kind"] == "performance.frame"
                                and e["data"]["stage"]["performers"][1]["position"][0] == 0.55))
    before = skin_centroid_x(frame_at(left, max(0.2, walk - 1.0)), 0.45)
    after = skin_centroid_x(frame_at(left, walk + 1.5), 0.42)
    assert before == pytest.approx(0.69, abs=0.03)
    assert after == pytest.approx(0.55, abs=0.03)


def test_parallax_the_desk_moves_further_than_the_back_wall(take):
    a, b = frame_at(take.files["left"], 2.0), frame_at(take.files["right"], 2.0)
    wall = shift_between(a, b, slice(40, 170))
    desk = shift_between(a, b, slice(585, 615))
    # renderer: shift = (center.x - 0.5) * 100; back wall x0.17, desk x0.82; the framings differ by 0.4.
    assert abs(wall) == pytest.approx(0.17 * 40, abs=3)
    assert abs(desk) == pytest.approx(0.82 * 40, abs=4)


def test_rendering_twice_gives_the_same_frames(take):
    a, b = framemd5(take.files["guest"]), framemd5(take.files["guest_again"])
    assert len(a) == len(b) and a == b


def test_nothing_sent_while_paused_is_in_the_show_data(take):
    lines = [json.loads(line) for line in gzip.open(take.folder / "show_data.jsonl.gz")]
    frames = [l for l in lines if l.get("kind") == "performance.frame"]
    xs = [f["data"]["stage"]["performers"][1]["position"][0] for f in frames]
    assert 0.20 not in xs and xs[0] == 0.69 and 0.55 in xs
    assert frames[0]["data"].get("snapshot") is True and frames[0]["t"] == 0       # the stage when the take began
    assert any(f["data"].get("gestures") for f in frames)
    assert not any(l.get("kind") == "hub.system" and l["data"].get("type") == "performance_state" for l in lines)
    switches = [l for l in lines if l.get("kind") == "camera.switch" and l["data"]["destination"] == "program"]
    assert any((s["data"].get("transition") or {}).get("duration_ms") == 800 for s in switches)


def test_meters_read_the_real_sound_being_recorded(take):
    readings = [m for reading in take.meters for m in reading if m["session_id"] == take.sid and m["source_id"] == "beep_mic"]
    assert readings and all(m["state"] in ("starting", "live") for m in readings), readings
    live = [m for m in readings if m["state"] == "live"]
    assert len(live) >= 5 and all(m["levels"]["seconds_recorded"] > 0.5 for m in live), readings
    peaks = [m["levels"]["peak_dbfs"] for m in live if m["levels"]["peak_dbfs"] is not None]   # None: nothing new since the last reading
    assert -12 < max(peaks) < 0                    # a beep in the window: the beeper's 0.5 amplitude, about -6 dBFS
    assert min(peaks) == -120.0                    # and the silence between beeps reads as silence


def test_the_reconstruction_carries_the_intended_program_mix(take):
    _, events = show_events(take)
    mixes = [e for e in events if e["kind"] == "audio.mix"]
    assert mixes[0]["t"] == 0 and mixes[0]["data"]["channels"]["guest"]["source_id"] == "beep_mic"
    change = take_time(take, mixes[-1]["t"])
    assert mixes[-1]["data"]["channels"]["guest"]["effective_gain"] == 0.25
    m = take.manifests["program"]
    assert m["sound"][0]["mix"][-1]["gain"] == 0.25
    onsets = beep_onsets(take.files["program"])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(take.files["program"]), "-vn", "-ac", "1",
                          "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True, timeout=120).stdout
    x = np.frombuffer(raw, dtype="<i2").astype(float)
    def beep_rms(t):
        seg = x[int((t + 0.02) * 48000):int((t + 0.08) * 48000)]
        return float(np.sqrt((seg ** 2).mean()))
    before = [beep_rms(t) for t in onsets if 1.0 < t < change - 0.2 and not (6.0 < t < 8.5)]
    after = [beep_rms(t) for t in onsets if change + 0.2 < t]
    assert before and after, (onsets, change)
    ratio_db = 20 * np.log10(np.median(after) / np.median(before))
    assert ratio_db == pytest.approx(-12.04, abs=1.0), ratio_db
