"""The three recording modes, end to end, against live cameras.

Real host (``run_reach.py``, throwaway data folders), real FFmpeg/ffprobe, real HTTP, real files judged afterwards.

The two "live cameras" are FFmpeg processes sending in real time over UDP multicast, so that every recorder process
can open them at once, as it could a network camera. They are registered with the ``srt`` transport only because the
capture input builder passes any non-listening network address straight to FFmpeg; nothing about SRT is being tested.
Each camera paints its own clock into the picture: the green channel ramps 0..250 every ten seconds (25 per second),
red camera red, blue camera blue. Reading the green back out of a recorded frame says *when* that camera showed it, so
the program file can be checked against real time, not only against its own record. Each camera also sends a tone
(red 440 Hz, blue 880 Hz) so the sound tracks can be told apart.

What is proved:

* camcorder: the take records as before, and now also keeps the show data and the mode record;
* data only: no picture at all, every camera's sound for the whole take, and show data holding the cuts made during it;
* main camera only: the program file shows red, blue, red, blue in the order cut, changes camera where the mode
  record says the cuts took effect, keeps real time across every cut (the clock in the picture agrees), lasts as long
  as the take, and no camera was recorded long outside its time on the live screen; the sound of both cameras runs the
  whole take;
* main camera only with the preview armed: a take (preview to program) lands with no delay;
* a camera in the dressing room is never recorded: its stretch is black and no file of it exists;
* requests a mode cannot honour are refused with a reason;
* the show data and mode record travel with an exported take.

Skips without ffmpeg/ffprobe or without multicast on the loopback interface.
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
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

np = pytest.importorskip("numpy")
ROOT = Path(__file__).resolve().parents[1]
if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)

PROFILE = "web_stream"           # 1280x720, 30 fps: light enough for two encoders at once on a small machine
FPS = 30
RAMP = 25.0                      # green levels per second of camera clock
WRAP = 10.0                      # seconds before the green ramp starts again
CAMERAS = {"live_red": ("239.255.7.1", 440, "r=255:b=0"), "live_blue": ("239.255.7.2", 880, "r=0:b=255")}


# --- helpers ----------------------------------------------------------------------------------------------------
def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
                                   "-of", "json", str(path)], timeout=30)
    data = json.loads(out)
    return {"video": any(s["codec_type"] == "video" for s in data["streams"]),
            "audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "seconds": float(data["format"]["duration"])}


def dominant_hz(path, start=0.5, seconds=2.0):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(start), "-i", str(path), "-vn", "-t", str(seconds),
                          "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True, timeout=60).stdout
    samples = np.frombuffer(raw, dtype="<i2").astype(float)
    assert len(samples) > 24000, "less than half a second of sound"
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return float(np.argmax(spectrum) * 48000 / len(samples))


def frames(path, fps=10):
    """(time, colour, green) for each sampled frame; colour is R, B or K (black)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vf", f"fps={fps},scale=8:8:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, timeout=120).stdout
    out = []
    for i in range(0, len(raw) // 192):
        px = np.frombuffer(raw[i * 192:(i + 1) * 192], dtype=np.uint8).reshape(-1, 3)[16:48].astype(float)  # middle rows
        r, g, b = px[:, 0].mean(), px[:, 1].mean(), px[:, 2].mean()
        colour = "R" if r > 150 and b < 100 else "B" if b > 150 and r < 100 else "K" if r + b < 60 and g < 40 else "?"
        out.append(((i + 0.5) / fps, colour, g))
    return out


def circular(delta, wrap=WRAP):
    return (delta + wrap / 2) % wrap - wrap / 2


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _multicast_works(tmp):
    group = "udp://239.255.7.250:5004"
    sender = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-re", "-f", "lavfi", "-i", "color=c=red:s=64x36:r=10",
                               "-t", "6", "-c:v", "libx264", "-g", "5", "-f", "mpegts", group + "?ttl=0&pkt_size=1316"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        got = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", group + "?reuse=1", "-t", "1", "-f", "null", "-"],
                             capture_output=True, timeout=8)
        return got.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        sender.kill(); sender.wait()


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


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    work = tmp_path_factory.mktemp("modes")
    if not _multicast_works(work):
        pytest.skip("UDP multicast on the loopback interface is not available here")
    h = _start_host(work / "host")
    senders = {}
    for camera, (group, hz, rb) in CAMERAS.items():
        url = f"udp://{group}:5004"
        started = time.time()
        senders[camera] = SimpleNamespace(url=url, started=started, proc=subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-re",
             "-f", "lavfi", "-i", f"color=c=black:s=160x90:r={FPS},geq={rb}:g='mod(T*{RAMP}\\,{RAMP * WRAP})'",
             "-f", "lavfi", "-i", f"sine=frequency={hz}:sample_rate=48000",
             "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "10", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-f", "mpegts", url + "?ttl=0&pkt_size=1316"],
            stdout=subprocess.DEVNULL, stderr=open(work / f"{camera}.log", "w")))
        reg = h.client.post("/api/cameras/register", json={"source_id": camera, "name": camera, "transport": "srt",
                                                            "endpoint": url + "?reuse=1", "location": "studio"})
        assert reg.status_code == 200, reg.text
    dressing = work / "dressing.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-f", "lavfi", "-i", "color=c=green:s=160x90:r=30:d=120",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dressing)], check=True, timeout=120)
    reg = h.client.post("/api/cameras/register", json={"source_id": "dressing_cam", "name": "Dressing room",
                                                        "transport": "file", "endpoint": str(dressing), "location": "dressing"})
    assert reg.status_code == 200, reg.text
    time.sleep(1.5)
    h.senders = senders
    yield h
    for sender in senders.values():
        sender.proc.kill(); sender.proc.wait()
    h.client.close()
    h.proc.terminate()
    try:
        h.proc.wait(20)
    except subprocess.TimeoutExpired:
        h.proc.kill(); h.proc.wait(5)
    h.log.close()


def program(host, camera):
    r = host.client.post("/api/cameras/switch", json={"target": "program", "source_id": camera})
    assert r.status_code == 200, r.text


def preview(host, camera):
    r = host.client.post("/api/cameras/switch", json={"target": "preview", "source_id": camera})
    assert r.status_code == 200, r.text


def start(host, session_id, mode, **extra):
    body = {"mode": mode, "profile_id": PROFILE, "countdown_seconds": 0, "session_id": session_id, **extra}
    r = host.client.post("/api/recording/start", json=body)
    assert r.status_code == 200, r.text
    assert not r.json().get("capture_errors"), r.json()["capture_errors"]
    return r.json(), time.time()


def stop(host, session_id):
    r = host.client.post(f"/api/recording/{session_id}/stop")
    assert r.status_code == 200, r.text
    return r.json()


def mode_record(host, session_id, *, joined=False, timeout=300):
    deadline = time.time() + timeout
    while True:
        r = host.client.get(f"/api/recording/{session_id}/mode")
        assert r.status_code == 200, r.text
        record = r.json()
        if not joined or record["assembly"]["state"] not in ("pending", "running", "waiting") or time.time() > deadline:
            return record
        time.sleep(0.5)


def session_dir(host, session_id):
    return host.data / "recordings" / session_id


def show_data(path):
    lines = [json.loads(line) for line in gzip.open(path)]
    return lines[0], lines[1:-1], lines[-1]


def at(t0, seconds):
    while time.time() - t0 < seconds:
        time.sleep(0.01)


# --- requests a mode cannot honour --------------------------------------------------------------------------------
def test_requests_a_mode_cannot_honour_are_refused_with_a_reason(host):
    c = host.client
    modes = c.get("/api/recording/modes").json()
    assert [m["mode"] for m in modes["modes"]] == ["camcorder", "data_only", "main_camera"] and modes["default"] == "camcorder"
    bad = c.post("/api/recording/start", json={"mode": "cinema", "profile_id": PROFILE, "countdown_seconds": 0})
    assert bad.status_code == 400 and "Unknown recording mode" in bad.text
    nodata = c.post("/api/recording/start", json={"mode": "data_only", "record_data": False, "sources": ["live_red"],
                                                  "profile_id": PROFILE, "countdown_seconds": 0})
    assert nodata.status_code == 400 and "show data" in nodata.text
    program(host, "live_red")
    sound_only = c.post("/api/recording/start", json={"mode": "main_camera", "sources": ["live_red"],
                                                      "profile_id": "audio_only", "countdown_seconds": 0})
    assert sound_only.status_code == 400 and "records picture" in sound_only.text
    listener = c.post("/api/cameras/register", json={"source_id": "phone_push", "name": "Phone", "transport": "rtmp",
                                                      "endpoint": "rtmp://0.0.0.0:19350/live/x", "location": "studio"})
    assert listener.status_code == 200
    refused = c.post("/api/recording/start", json={"mode": "main_camera", "sources": ["live_red", "phone_push"],
                                                   "profile_id": PROFILE, "countdown_seconds": 0})
    assert refused.status_code == 400 and "camcorder mode" in refused.text, refused.text
    not_live = c.post("/api/recording/start", json={"mode": "main_camera", "sources": ["live_blue"],
                                                    "profile_id": PROFILE, "countdown_seconds": 0})
    assert not_live.status_code == 400 and "live screen" in not_live.text
    assert not any(p.name.startswith("phone_push") for p in (host.data / "recordings").glob("*/*"))


# --- camcorder ----------------------------------------------------------------------------------------------------
def test_camcorder_records_as_before_and_keeps_the_show_data(host):
    program(host, "live_red"); preview(host, "live_blue")
    started, t0 = start(host, "mode_camcorder", "camcorder", sources=["live_red"])
    assert started["mode"] == "camcorder" and started["record_data"] is True
    at(t0, 2.0)
    program(host, "live_blue")
    at(t0, 4.0)
    stopped = stop(host, "mode_camcorder")
    names = [a["name"] for a in stopped["artifacts"]]
    assert names == ["live_red.webm"], names
    info = probe(session_dir(host, "mode_camcorder") / "live_red.webm")
    assert info["video"] and info["audio"] and 3.0 <= info["seconds"] <= 5.5
    assert sorted(stopped["data_files"]) == ["recording_mode.json", "show_data.jsonl.gz"]
    header, events, footer = show_data(session_dir(host, "mode_camcorder") / "show_data.jsonl.gz")
    assert header["mode"] == "camcorder" and footer["footer"] and footer["events"] == len(events)
    switches = [e for e in events if e["kind"] == "camera.switch"]
    assert [(s["data"]["destination"], s["data"]["source_id"]) for s in switches] == [("program", "live_blue")]
    assert all("endpoint" not in camera for camera in header["cameras"]), "stream addresses can hold keys; they stay out"
    record = mode_record(host, "mode_camcorder")
    assert record["mode"] == "camcorder" and record["state"] == "stopped" and record["program"] is None
    assert record["show_data"]["complete"] and record["show_data"]["events"] == len(events)


# --- data only ----------------------------------------------------------------------------------------------------
def test_data_only_records_no_picture_every_sound_and_the_show_data(host):
    program(host, "live_red"); preview(host, "live_blue")
    started, t0 = start(host, "mode_data", "data_only", sources=["live_red", "live_blue"])
    assert started["mode"] == "data_only"
    at(t0, 2.0)
    program(host, "live_blue")
    at(t0, 3.5)
    program(host, "live_red")
    at(t0, 6.0)
    stopped = stop(host, "mode_data")
    folder = session_dir(host, "mode_data")
    names = sorted(a["name"] for a in stopped["artifacts"])
    assert names == ["sound_live_blue.wav", "sound_live_red.wav"], names
    for name, hz in (("sound_live_red.wav", 440), ("sound_live_blue.wav", 880)):
        info = probe(folder / name)
        assert not info["video"] and info["audio"], f"{name} must be sound only"
        assert 5.0 <= info["seconds"] <= 7.0, f"{name} covers the whole take: {info['seconds']}"
        assert abs(dominant_hz(folder / name) - hz) < 10, f"{name} is that camera's own sound"
    assert not any(probe(p)["video"] for p in folder.iterdir() if p.suffix in (".webm", ".mp4", ".mov")), "no picture at all"
    header, events, footer = show_data(folder / "show_data.jsonl.gz")
    cuts = [(e["data"]["destination"], e["data"]["source_id"]) for e in events if e["kind"] == "camera.switch"]
    assert ("program", "live_blue") in cuts and ("program", "live_red") in cuts, cuts
    assert any(e["kind"] == "hub.system" and e["data"].get("type") == "camera_switch" for e in events), \
        "what the stage pages were sent is in the record too"
    times = [e["t"] for e in events]
    assert times == sorted(times) and all(0 <= t < 8 for t in times)
    record = mode_record(host, "mode_data")
    assert record["show_data"]["sha256"] == footer["sha256"] and record["show_data"]["complete"]
    assert {s["source_id"]: s["state"] for s in record["sound"]} == {"live_red": "recorded", "live_blue": "recorded"}


# --- main camera only ---------------------------------------------------------------------------------------------
def _check_program(host, session_id, cut_plan, *, t_stop):
    """Judge a main-camera take's program file against its own record and against the cameras' clocks."""
    record = mode_record(host, session_id, joined=True)
    folder = session_dir(host, session_id)
    assert record["assembly"]["state"] == "complete", record["assembly"]
    assert not record["assembly"]["warnings"], record["assembly"]["warnings"]
    path = folder / record["assembly"]["file"]
    info = probe(path)
    origin = record["assembly"]["origin"]
    assert abs(info["seconds"] - (record["stopped_at"] - origin)) < 0.3, "the program keeps real time"
    cuts = [c for c in record["program"]["cuts"] if c["kind"] == "cut"]
    assert [c["to"] for c in cuts] == [camera for _, camera in cut_plan]
    for cut in cuts:
        assert cut["effective_at"] >= cut["requested_at"] - 0.005, "a cut never lands before it was asked for"
        assert 0 <= cut["late_by_ms"] <= 3000, cut
    # What camera the program shows, sampled ten times a second.
    sampled = frames(path)
    boundaries = [0.0] + [c["effective_at"] - origin for c in cuts] + [info["seconds"]]
    order = ["R" if record["program"]["cuts"][0]["to"] == "live_red" else "B"]
    for _, camera in cut_plan:
        order.append("R" if camera == "live_red" else "B")
    offsets = {"R": [], "B": []}
    for t, colour, green in sampled:
        stretch = max(i for i in range(len(boundaries) - 1) if t >= boundaries[i])
        if min(abs(t - b) for b in boundaries) < 0.15:
            continue                          # a frame either side of a cut may belong to either camera
        assert colour == order[stretch], f"at {t:.2f} s the program shows {colour}, not {order[stretch]}"
        camera = "live_red" if colour == "R" else "live_blue"
        clock = green / RAMP                  # the camera's own clock, from the picture
        wall = record["take_started_utc"] + origin + t
        offsets[colour].append(circular(clock - (wall - host.senders[camera].started)))
    for colour, values in offsets.items():
        assert values, f"no {colour} frames to judge"
        spread = float(np.percentile(values, 95) - np.percentile(values, 5))
        # The same lag for every stretch of a camera: what the program shows after each cut is what that camera
        # showed at that moment. (The lag itself is the sender's start-up and the network buffer, about the same
        # for every stretch.)
        assert spread < 0.35, f"{colour}: picture time drifts by {spread:.2f} s across the cuts: {values}"
    segments = record["program"]["segments"]
    for interval in record["program"]["intervals"]:
        if interval["segment"] is None or record["arm_preview"]:
            continue          # an armed preview records while it waits on preview, by design
        seg = next(s for s in segments if s["index"] == interval["segment"])
        start = interval["start"] if interval["start"] is not None else seg["first_frame_at"]
        end = interval["end"] if interval["end"] is not None else next(
            s["first_frame_at"] for s in segments if s["index"] == interval["end_at_first_frame_of"])
        assert seg["duration"] <= (end - start) + 3.5, \
            f"{seg['source_id']} was recorded {seg['duration']:.1f} s for a {end - start:.1f} s stretch on the live screen"
    for sound in record["sound"]:
        assert sound["state"] == "recorded"
        assert probe(folder / sound["file"])["seconds"] >= t_stop - 1.0, "each camera's sound runs the whole take"
    return record, sampled


def test_main_camera_records_only_the_camera_on_the_live_screen(host):
    program(host, "live_red"); preview(host, "live_blue")
    started, t0 = start(host, "mode_main", "main_camera", sources=["live_red", "live_blue"])
    assert started["mode"] == "main_camera"
    plan = [(3.0, "live_blue"), (6.5, "live_red"), (9.5, "live_blue")]
    for when, camera in plan:
        at(t0, when)
        program(host, camera)
    at(t0, 13.0)
    stopped = stop(host, "mode_main")
    names = sorted(a["name"] for a in stopped["artifacts"])
    assert names == ["program_0001_live_red.webm", "program_0002_live_blue.webm", "program_0003_live_red.webm",
                     "program_0004_live_blue.webm", "sound_live_blue.wav", "sound_live_red.wav"], names
    record, _ = _check_program(host, "mode_main", plan, t_stop=13.0)
    assert record["arm_preview"] is False
    assert all(c["handled"] == "started" for c in record["program"]["cuts"][1:])
    session = next(s for s in host.client.get("/api/recording/sessions").json() if s["session_id"] == "mode_main")
    assert "program.webm" in [a["name"] for a in session["artifacts"]], "the joined program is part of the take"


def test_an_armed_preview_takes_to_the_live_screen_with_no_delay(host):
    program(host, "live_red"); preview(host, "live_blue")
    started, t0 = start(host, "mode_armed", "main_camera", sources=["live_red", "live_blue"], arm_preview=True)
    plan = [(3.0, "live_blue"), (6.0, "live_red")]
    for when, _ in plan:
        at(t0, when)
        assert host.client.post("/api/cameras/cut").status_code == 200     # preview and program swap
    at(t0, 9.0)
    stop(host, "mode_armed")
    record, _ = _check_program(host, "mode_armed", plan, t_stop=9.0)
    assert record["arm_preview"] is True
    for cut in record["program"]["cuts"][1:]:
        assert cut["handled"] == "armed" and cut["late_by_ms"] == 0, cut


def test_a_camera_in_the_dressing_room_is_never_recorded(host):
    program(host, "live_red"); preview(host, "live_blue")
    refused = host.client.post("/api/recording/start", json={"mode": "main_camera", "profile_id": PROFILE,
                                                             "countdown_seconds": 0, "sources": ["live_red", "dressing_cam"]})
    assert refused.status_code == 400 and "forbidden in dressing" in refused.text, "it cannot even be chosen"
    started, t0 = start(host, "mode_private", "main_camera", sources=["live_red", "live_blue"])
    at(t0, 2.5)
    program(host, "dressing_cam")
    at(t0, 5.0)
    program(host, "live_blue")
    at(t0, 8.0)
    stop(host, "mode_private")
    record = mode_record(host, "mode_private", joined=True)
    assert record["assembly"]["state"] == "complete", record["assembly"]
    reasons = [(i["source_id"], i["reason"]) for i in record["program"]["intervals"]]
    assert reasons == [("live_red", "program"), ("dressing_cam", "private"), ("live_blue", "program")], reasons
    assert all(s["source_id"] != "dressing_cam" for s in record["program"]["segments"])
    folder = session_dir(host, "mode_private")
    assert not [p.name for p in folder.iterdir() if "dressing" in p.name], "no file of the dressing room exists"
    origin = record["assembly"]["origin"]
    gap = next(i for i in record["program"]["intervals"] if i["reason"] == "private")
    blue = next(c for c in record["program"]["cuts"] if c["to"] == "live_blue")
    inside = [colour for t, colour, _ in frames(folder / record["assembly"]["file"])
              if gap["start"] - origin + 0.2 < t < blue["effective_at"] - origin - 0.2]
    assert inside and set(inside) == {"K"}, f"the dressing-room stretch is black: {set(inside)}"


def test_the_show_data_and_mode_record_travel_with_an_exported_take(host):
    r = host.client.post("/api/recording/mode_data/export", json={"format": "webm"})
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(__import__("io").BytesIO(r.content)) as bundle:
        manifest = json.loads(bundle.read("EXPORT_MANIFEST.json"))
        for name in ("data/show_data.jsonl.gz", "data/recording_mode.json"):
            data = bundle.read(name)
            assert manifest["files"][name]["sha256"] == __import__("hashlib").sha256(data).hexdigest()
        original = (session_dir(host, "mode_data") / "show_data.jsonl.gz").read_bytes()
        assert bundle.read("data/show_data.jsonl.gz") == original, "byte for byte"
        meta = json.loads(bundle.read("mode_data.json"))
        assert meta["mode"] == "data_only" and sorted(meta["data_files"]) == ["recording_mode.json", "show_data.jsonl.gz"]
