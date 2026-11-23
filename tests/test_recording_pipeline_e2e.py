"""Recording pipeline, video and audio together, end to end.

Real host (``run_reach.py``, throwaway data folders), real FFmpeg/ffprobe, real HTTP. Nothing here mocks the media.
A second host receives the bundle, so "import" is a move between two installations, not a reload of the same one.

What is proved, each judged on the resulting FILES (ffprobe, decoding, hashes, and the audio signal itself):

* record: a source carrying picture and a 440 Hz tone is recorded through ``/api/recording`` into MP4 (H.264/AAC) and
  WebM (VP9/Opus); both files hold a video stream and an audio stream, last about as long as the take, and the tone is
  still 440 Hz;
* a recording that cannot start, or an encoder that cannot keep up, is reported, not returned as a silent success;
* download: ``/api/vod`` serves the exact bytes on disk;
* change file type: export to MP4, WebM, MOV (ProRes/PCM) and WAV; each render decodes and keeps the picture, the
  audio and the duration; the original is bundled byte-for-byte; every manifest hash is true;
* import: the bundle goes into a second host, comes back out unchanged, and a tampered or repeated bundle is refused
  leaving nothing behind;
* upload: a browser take is uploaded in chunks, validated, downloaded back identical and exported; ``/api/upload``
  accepts a real replay file.

Skips without ffmpeg/ffprobe.
"""
from __future__ import annotations

import hashlib
import io
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

TONE_HZ = 440
HOLD = 6.0          # seconds each recording is held


# --- media helpers --------------------------------------------------------------------------------------------
def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", *map(str, args)], check=True, timeout=120)


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,codec_name,width,height,sample_rate,channels,duration:format=duration,format_name",
                                   "-of", "json", str(path)], timeout=30)
    data = json.loads(out)
    data["video"] = [s for s in data["streams"] if s["codec_type"] == "video"]
    data["audio"] = [s for s in data["streams"] if s["codec_type"] == "audio"]
    data["seconds"] = float(data["format"]["duration"])
    return data


def decode_audio(path, seconds=2.0):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-t", str(seconds), "-ac", "1",
                          "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True, timeout=60).stdout
    return np.frombuffer(raw, dtype="<i2").astype(float)


def dominant_hz(path):
    samples = decode_audio(path)
    assert len(samples) > 48000, "audio is shorter than one second"
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return float(np.argmax(spectrum) * 48000 / len(samples))


def rms(path):
    return float(np.sqrt(np.mean(decode_audio(path) ** 2)))


def decodes_clean(path):
    done = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"], capture_output=True, timeout=120)
    return done.returncode == 0 and not done.stderr.strip()


def frame_count(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                   "stream=nb_read_frames", "-of", "csv=p=0", str(path)], timeout=120)
    return int(out.strip())


def sha256(path_or_bytes):
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return hashlib.sha256(path_or_bytes).hexdigest()
    h = hashlib.sha256()
    with open(path_or_bytes, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --- hosts ----------------------------------------------------------------------------------------------------
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_host(tmp_path_factory, name):
    data = tmp_path_factory.mktemp(name)
    (data / "assets").mkdir()
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
            raise AssertionError("run_reach.py exited during startup:\n" + (data / "host.log").read_text(encoding="utf-8")[-4000:])
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(0.3)
    else:
        raise AssertionError("host did not start within 120 s")
    password = secrets.token_urlsafe(20)
    assert httpx.post(base + "/api/auth/setup", json={"username": "owner", "password": password, "confirm_password": password}, timeout=10).status_code in (200, 201)
    login = httpx.post(base + "/api/auth/login", json={"username": "owner", "password": password}, timeout=10)
    assert login.status_code == 200, login.text
    client = httpx.Client(base_url=base, headers={"Authorization": "Bearer " + login.json()["access_token"]}, timeout=300)
    return SimpleNamespace(base=base, client=client, proc=proc, log=log, data=data / "data")


def _stop_host(host):
    host.client.close()
    host.proc.terminate()
    try:
        host.proc.wait(20)
    except subprocess.TimeoutExpired:
        host.proc.kill(); host.proc.wait(5)
    host.log.close()


@pytest.fixture(scope="module")
def host_a(tmp_path_factory):
    host = _start_host(tmp_path_factory, "recording_a")
    yield host
    _stop_host(host)


@pytest.fixture(scope="module")
def host_b(tmp_path_factory):
    host = _start_host(tmp_path_factory, "recording_b")
    yield host
    _stop_host(host)


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    """Something that carries picture AND sound: moving test video with a 440 Hz tone, longer than any take."""
    path = tmp_path_factory.mktemp("media") / "source_av.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=30", "-f", "lavfi",
           "-i", f"sine=frequency={TONE_HZ}:duration=30:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path)
    return path


def _record(host, session_id, camera, profile, hold=HOLD):
    start = host.client.post("/api/recording/start", json={"sources": [camera], "profile_id": profile, "countdown_seconds": 0, "session_id": session_id})
    assert start.status_code == 200, start.text
    assert not start.json().get("capture_errors"), start.json()["capture_errors"]
    time.sleep(hold)
    stop = host.client.post(f"/api/recording/{session_id}/stop")
    assert stop.status_code == 200, stop.text
    return start.json(), stop.json()


@pytest.fixture(scope="module")
def recorded(host_a, source):
    reg = host_a.client.post("/api/cameras/register", json={"source_id": "file_av", "name": "AV file", "transport": "file",
                                                              "endpoint": str(source), "location": "virtual"})
    assert reg.status_code == 200, reg.text
    out = {}
    for profile in ("broadcast_mp4", "web_stream"):
        sid = "e2e_" + profile
        _, stopped = _record(host_a, sid, "file_av", profile)
        assert len(stopped["artifacts"]) == 1, f"{profile}: nothing was recorded: {stopped}"
        out[profile] = SimpleNamespace(session_id=sid, stopped=stopped, path=Path(stopped["artifacts"][0]["file_path"]),
                                       name=stopped["artifacts"][0]["name"], report=stopped.get("capture_report", []))
    return out


# --- pure checks of the capture changes -------------------------------------------------------------------------
def test_profile_codec_names_become_real_encoder_names():
    from modules.capture import _build_ffmpeg_output
    from modules.recording import ContainerFormat, EncodingProfile

    def args(video, audio, container):
        return _build_ffmpeg_output(EncodingProfile(profile_id="p", name="p", container=container, video_codec=video, audio_codec=audio,
                                                    video_bitrate="8Mbps", audio_bitrate="192kbps", resolution="1280x720",
                                                    frame_rate="30", description=""), Path("out"))
    web = args("vp9", "opus", ContainerFormat.WEBM)
    assert web[web.index("-c:v") + 1] == "libvpx-vp9" and web[web.index("-c:a") + 1] == "libopus"
    assert "realtime" in web, "VP9 must be told to encode live"
    mp4 = args("h264", "aac", ContainerFormat.MP4)
    assert mp4[mp4.index("-c:v") + 1] == "libx264" and mp4[mp4.index("-preset") + 1] == "veryfast"
    assert mp4[mp4.index("-c:a") + 1] == "aac"


def test_preset_can_be_overridden(monkeypatch):
    from modules.capture import _live_encoder_args
    monkeypatch.setenv("PUBCAST_CAPTURE_X264_PRESET", "medium")
    assert _live_encoder_args("libx264") == ["-preset", "medium"]


def test_a_lagging_encoder_is_reported_and_a_healthy_one_is_not(tmp_path):
    from modules.capture import FFmpegCaptureEngine, _CaptureProcess
    engine = FFmpegCaptureEngine.__new__(FFmpegCaptureEngine)
    out = tmp_path / "take.mp4"; out.write_bytes(b"x" * 10)

    def process(log_text, rc=0):
        log = tmp_path / "take.log"; log.write_text(log_text)
        return _CaptureProcess(source_id="cam", output_path=out, proc=SimpleNamespace(returncode=rc), started_at=100.0,
                               log_path=log, stopped_at=108.0)
    opened = "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'source.mp4':\n"      # every real FFmpeg log has this once an input opens
    slow = FFmpegCaptureEngine._report_for(engine, process(opened + "frame=100 fps=20 time=00:00:04.60 bitrate=1kbits/s speed=0.57x\r"))
    assert slow["speed"] == pytest.approx(0.57) and slow["encoded_seconds"] == pytest.approx(4.6)
    assert any("0.57x" in w and "shorter than the take" in w for w in slow["warnings"])
    fine = FFmpegCaptureEngine._report_for(engine, process(opened + "frame=240 fps=30 time=00:00:07.90 bitrate=1kbits/s speed=1.02x\r"))
    assert fine["warnings"] == []
    waiting = FFmpegCaptureEngine._report_for(engine, process("Waiting for connection on rtmp://0.0.0.0:1935/live/key\n"))
    assert any("never opened the input" in w for w in waiting["warnings"]), "a listener nobody connected to must say so"
    crashed = FFmpegCaptureEngine._report_for(engine, process("Unknown encoder 'nope'\n", rc=1))
    assert any("status 1" in w and "Unknown encoder" in w for w in crashed["warnings"])


# --- record ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("profile,vcodec,acodec,fmt", [("broadcast_mp4", "h264", "aac", "mp4"), ("web_stream", "vp9", "opus", "matroska")])
def test_recording_holds_picture_and_sound_for_the_whole_take(recorded, profile, vcodec, acodec, fmt):
    rec = recorded[profile]
    info = probe(rec.path)
    assert [s["codec_name"] for s in info["video"]] == [vcodec] and [s["codec_name"] for s in info["audio"]] == [acodec]
    assert fmt in info["format"]["format_name"]
    assert decodes_clean(rec.path), "the whole file decodes without errors"
    assert HOLD * 0.85 <= info["seconds"] <= HOLD + 3, f"a {HOLD:.0f} s take produced {info['seconds']:.1f} s: {rec.report}"
    audio_len = float(info["audio"][0].get("duration") or info["seconds"])
    assert abs(audio_len - info["seconds"]) < 0.6, "picture and sound are the same length"
    assert frame_count(rec.path) > 20 * info["seconds"], "picture has real frame rate, not a few stills"
    assert abs(dominant_hz(rec.path) - TONE_HZ) < 8, "the recorded sound is the tone that went in"
    assert rms(rec.path) > 500, "the sound is audible, not silence"
    assert not any(w for item in rec.report for w in item["warnings"]), rec.report


def test_a_capture_that_cannot_start_is_reported_not_returned_as_success(host_a, tmp_path):
    host_a.client.post("/api/cameras/register", json={"source_id": "no_such_file", "name": "x", "transport": "file",
                                                        "endpoint": str(tmp_path / "missing.mp4"), "location": "virtual"})
    start = host_a.client.post("/api/recording/start", json={"sources": ["no_such_file"], "profile_id": "web_stream", "countdown_seconds": 0, "session_id": "e2e_cannot_start"})
    assert start.status_code == 200
    errors = start.json().get("capture_errors")
    assert errors and errors[0]["source_id"] == "no_such_file" and "missing.mp4" in errors[0]["error"], start.json()
    stop = host_a.client.post("/api/recording/e2e_cannot_start/stop").json()
    assert stop["artifacts"] == []
    assert any("No media was written" in w for item in stop["capture_report"] for w in item["warnings"])


def test_virtual_camera_take_is_marked_synthetic_and_carries_no_sound(host_a):
    """The built-in virtual camera is a test pattern with no microphone: say so, don't present it as a real take."""
    host_a.client.post("/api/cameras/register", json={"source_id": "virtual_cam", "name": "virtual", "transport": "virtual", "location": "virtual"})
    _, stopped = _record(host_a, "e2e_virtual", "virtual_cam", "web_stream", hold=3)
    artifact = stopped["artifacts"][0]
    assert artifact["synthetic"] is True
    assert probe(artifact["file_path"])["audio"] == [], "FFmpeg's test pattern has no audio; a real source is needed for sound"


# --- download -------------------------------------------------------------------------------------------------
def test_download_serves_the_exact_recorded_bytes(host_a, recorded):
    rec = recorded["broadcast_mp4"]
    listing = host_a.client.get("/api/vod").json()
    entry = next(f for f in listing["files"] if f["session_id"] == rec.session_id)
    assert entry["name"] == rec.name and entry["size_bytes"] == rec.path.stat().st_size
    got = host_a.client.get(entry["url"])
    assert got.status_code == 200
    assert sha256(got.content) == sha256(rec.path)
    assert host_a.client.get(f"/api/vod/{rec.session_id}/no_such_file.mp4").status_code == 404


# --- change file type (export) ----------------------------------------------------------------------------------
EXPORTS = {
    "mp4": {"video": "h264", "audio": "aac"},
    "webm": {"video": "vp9", "audio": "opus"},
    "mov": {"video": "prores", "audio": "pcm_s24le"},
    "wav": {"video": None, "audio": "pcm_s16le"},
}


@pytest.fixture(scope="module")
def exported(host_a, recorded, tmp_path_factory):
    session = recorded["broadcast_mp4"].session_id
    out = {}
    for container in EXPORTS:
        resp = host_a.client.post(f"/api/recording/{session}/export", json={"format": container})
        assert resp.status_code == 200, f"{container}: {resp.status_code} {resp.text[:300]}"
        assert resp.headers["content-type"] == "application/zip"
        folder = tmp_path_factory.mktemp("export_" + container)
        bundle = folder / "bundle.zip"
        bundle.write_bytes(resp.content)
        with zipfile.ZipFile(bundle) as z:
            assert z.testzip() is None
            z.extractall(folder / "files")
        out[container] = SimpleNamespace(bundle=bundle, files=folder / "files")
    return out


@pytest.mark.parametrize("container", list(EXPORTS))
def test_export_converts_to_the_requested_type_keeping_picture_sound_and_length(exported, recorded, container):
    want, files = EXPORTS[container], exported[container].files
    manifest = json.loads((files / "EXPORT_MANIFEST.json").read_text())
    assert manifest["requested_container"] == container
    assert not [w for w in manifest["warnings"] if "failed" in w.lower() or "unavailable" in w.lower()], manifest["warnings"]
    renders = list((files / "renders").glob(f"*.{container}"))
    assert len(renders) == 1, f"no {container} render in the bundle: {sorted(p.name for p in files.rglob('*'))}"
    render = renders[0]
    info, original = probe(render), probe(recorded["broadcast_mp4"].path)
    assert decodes_clean(render)
    assert [s["codec_name"] for s in info["audio"]] == [want["audio"]]
    if want["video"]:
        assert [s["codec_name"] for s in info["video"]] == [want["video"]]
        assert frame_count(render) > 20 * info["seconds"]
    else:
        assert info["video"] == []
    assert abs(info["seconds"] - original["seconds"]) < 0.6, f"{container}: {info['seconds']:.2f} s vs original {original['seconds']:.2f} s"
    assert abs(dominant_hz(render) - TONE_HZ) < 8 and rms(render) > 500, "the tone survived the conversion"


def test_export_bundles_the_original_unchanged_and_every_hash_is_true(exported, recorded):
    original = recorded["broadcast_mp4"].path
    for container, item in exported.items():
        manifest = json.loads((item.files / "EXPORT_MANIFEST.json").read_text())
        for member, spec in manifest["files"].items():
            path = item.files / member
            assert path.is_file(), member
            assert sha256(path) == spec["sha256"] and path.stat().st_size == spec["bytes"], f"{container}: {member}"
        media = list((item.files / "media").glob("*"))
        assert len(media) == 1 and sha256(media[0]) == sha256(original), "the original is bundled byte-for-byte"
        assert all(not d["source_master"] for d in manifest["derived"]), "a converted render is never labelled the master"


# --- import ---------------------------------------------------------------------------------------------------
def _import(host, bundle_path, name="bundle.zip"):
    with open(bundle_path, "rb") as f:
        return host.client.post("/api/recording/import", files={"file": (name, f, "application/zip")})


def test_bundle_imports_into_a_second_host_and_comes_back_out_identical(host_b, host_a, exported, recorded, tmp_path):
    rec = recorded["broadcast_mp4"]
    resp = _import(host_b, exported["mp4"].bundle, f"{rec.session_id}.zip")
    assert resp.status_code == 200, resp.text
    imported = resp.json()
    assert imported["session_id"] == rec.session_id and len(imported["artifacts"]) == 1
    stored = Path(imported["artifacts"][0]["file_path"])
    assert host_b.data in stored.parents, "the media lives in the second host's own storage"
    assert sha256(stored) == sha256(rec.path), "the imported media is the original, byte for byte"
    assert decodes_clean(stored) and probe(stored)["audio"] and probe(stored)["video"]
    # playable and downloadable from the second host
    entry = next(f for f in host_b.client.get("/api/vod").json()["files"] if f["session_id"] == rec.session_id)
    assert sha256(host_b.client.get(entry["url"]).content) == sha256(rec.path)
    # and exportable again from there, into a different type
    again = host_b.client.post(f"/api/recording/{rec.session_id}/export", json={"format": "webm"})
    assert again.status_code == 200
    with zipfile.ZipFile(io.BytesIO(again.content)) as z:
        z.extractall(tmp_path / "again")
    media = list((tmp_path / "again" / "media").glob("*"))
    assert sha256(media[0]) == sha256(rec.path)
    render = next((tmp_path / "again" / "renders").glob("*.webm"))
    assert [s["codec_name"] for s in probe(render)["video"]] == ["vp9"] and abs(dominant_hz(render) - TONE_HZ) < 8


def test_importing_the_same_recording_twice_is_refused_and_changes_nothing(host_b, exported, recorded):
    before = sha256(recorded["broadcast_mp4"].path)
    again = _import(host_b, exported["mp4"].bundle, "again.zip")
    assert again.status_code == 400 and "already exists" in again.text
    entry = next(f for f in host_b.client.get("/api/vod").json()["files"] if f["session_id"] == recorded["broadcast_mp4"].session_id)
    assert sha256(host_b.client.get(entry["url"]).content) == before


def test_a_tampered_bundle_is_refused_and_leaves_nothing_behind(host_b, exported, recorded, tmp_path):
    source_zip = exported["webm"].bundle
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(source_zip) as zin, zipfile.ZipFile(tampered, "w", zipfile.ZIP_STORED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("media/"):
                data = data[:5000] + bytes([data[5000] ^ 0xFF]) + data[5001:]     # one flipped byte inside the picture data
            zout.writestr(item, data)
    # use a session id host B has not seen: rename it inside the metadata so only the integrity check can stop it
    renamed = tmp_path / "renamed.zip"
    with zipfile.ZipFile(tampered) as zin, zipfile.ZipFile(renamed, "w", zipfile.ZIP_STORED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            # Only the take's own metadata sits at the top level; data/ holds the take's other JSON (its mode record).
            if item.filename.endswith(".json") and "/" not in item.filename and item.filename != "EXPORT_MANIFEST.json":
                meta = json.loads(data); meta["session_id"] = "e2e_tampered_copy"; data = json.dumps(meta).encode()
                zout.writestr("e2e_tampered_copy.json", data)
            else:
                zout.writestr(item, data)
    before = sorted(p.name for p in (host_b.data / "recordings").iterdir())
    resp = _import(host_b, renamed, "renamed.zip")
    assert resp.status_code == 400, resp.text
    assert "integrity" in resp.text, f"refused for the flipped byte, not for something else: {resp.text}"
    assert sorted(p.name for p in (host_b.data / "recordings").iterdir()) == before, "a refused import leaves no directory behind"
    assert all(f["session_id"] != "e2e_tampered_copy" for f in host_b.client.get("/api/vod").json()["files"])


def test_import_rejects_things_that_are_not_recording_bundles(host_b, tmp_path):
    not_zip = tmp_path / "x.zip"; not_zip.write_bytes(b"this is not a zip")
    assert _import(host_b, not_zip, "x.zip").status_code == 400
    mp4 = tmp_path / "video.mp4"; mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    assert _import(host_b, mp4, "video.mp4").status_code == 400, "only zip bundles are imported"


# --- upload ---------------------------------------------------------------------------------------------------
def test_request_size_guard_lets_real_recordings_and_replays_through(monkeypatch):
    """The host's 1 MB default body cap rejected every recording import and every replay over 1 MB before their routes ran."""
    import main
    guard = main.BodySizeLimitMiddleware
    assert guard.limit_for("/api/recording/import") >= 64 * 1024 ** 3, "follows the import route's own 64 GiB default"
    monkeypatch.setenv("PUBCAST_RECORDING_IMPORT_MAX_BYTES", str(10 * 1024 ** 2))
    assert 10 * 1024 ** 2 <= guard.limit_for("/api/recording/import") < 12 * 1024 ** 2, "and its setting"
    assert guard.limit_for("/api/upload") > 5 * 1024 ** 2, "the replay route's own 5 MB ceiling is reachable"
    assert guard.limit_for("/api/recording/start") == guard.MAX_BODY, "every other route keeps the 1 MB cap"


def _chain(chunks):
    from modules.studio25d_recording_ingest import CHAIN_SEED, extend_chain
    chain = CHAIN_SEED
    for chunk in chunks:
        chain = extend_chain(chain, hashlib.sha256(chunk).hexdigest(), len(chunk))
    return chain


def test_browser_take_uploads_in_chunks_downloads_identical_and_exports(host_a, tmp_path):
    take = tmp_path / "browser_take.webm"
    # noise picture so the file is big enough to need several 256 KiB chunks
    ffmpeg("-f", "lavfi", "-i", "nullsrc=s=320x240:r=30:d=4,geq=random(1)*255:128:128", "-f", "lavfi", "-i", f"sine=frequency={TONE_HZ}:duration=4:sample_rate=48000",
           "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "1500k", "-c:a", "libopus", "-b:a", "96k", "-shortest", take)
    content = take.read_bytes()
    chunks = [content[i:i + 256 * 1024] for i in range(0, len(content), 256 * 1024)]
    assert len(chunks) >= 2, "the take is large enough to need more than one chunk"
    host_a.client.post("/api/cameras/register", json={"source_id": "p25d_e2e_cam", "name": "studio", "location": "studio25d", "tags": ["studio25d"]})
    spec = {"take_id": "e2etake" + secrets.token_hex(4), "production_id": "prod_" + secrets.token_hex(4), "source_id": "p25d_e2e_cam",
            "mime": "video/webm;codecs=vp9,opus", "bytes": len(content), "chain": _chain(chunks), "width": 320, "height": 240,
            "duration_ms": 4000, "manifest": {"note": "e2e"}}
    created = host_a.client.post("/api/studio25d/recordings", json=spec)
    assert created.status_code == 200, created.text
    take_id = created.json()["id"]      # the host's own ID for the take; "take_id" in the response is the browser's
    # an out-of-order chunk and a corrupted chunk are refused
    assert host_a.client.put(f"/api/studio25d/recordings/{take_id}/chunks/1", content=chunks[1],
                             headers={"X-Chunk-SHA256": sha256(chunks[1]), "Content-Type": "application/octet-stream"}).status_code == 409
    assert host_a.client.put(f"/api/studio25d/recordings/{take_id}/chunks/0", content=chunks[0][:-1] + b"\x00",
                             headers={"X-Chunk-SHA256": sha256(chunks[0]), "Content-Type": "application/octet-stream"}).status_code == 422
    for index, chunk in enumerate(chunks):
        r = host_a.client.put(f"/api/studio25d/recordings/{take_id}/chunks/{index}", content=chunk,
                              headers={"X-Chunk-SHA256": sha256(chunk), "Content-Type": "application/octet-stream"})
        assert r.status_code == 200, r.text
    done = host_a.client.post(f"/api/studio25d/recordings/{take_id}/complete")
    assert done.status_code == 200, done.text
    media = host_a.client.get(f"/api/studio25d/recordings/{take_id}/media")
    assert media.status_code == 200 and media.headers["x-source-sha256"] == sha256(content)
    assert media.content == content, "downloaded bytes equal uploaded bytes"
    stored = tmp_path / "downloaded.webm"; stored.write_bytes(media.content)
    info = probe(stored)
    assert info["video"] and info["audio"] and abs(dominant_hz(stored) - TONE_HZ) < 8
    # the same take converts to another type
    bundle = host_a.client.post(f"/api/studio25d/recordings/{take_id}/bundle")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
        z.extractall(tmp_path / "bundle")
    assert sha256(next((tmp_path / "bundle" / "media").glob("*"))) == sha256(content)
    conv = host_a.client.post(f"/api/recording/{take_id}/export", json={"format": "mp4"})
    assert conv.status_code == 200
    with zipfile.ZipFile(io.BytesIO(conv.content)) as z:
        z.extractall(tmp_path / "conv")
    mp4 = next((tmp_path / "conv" / "renders").glob("*.mp4"))
    assert [s["codec_name"] for s in probe(mp4)["video"]] == ["h264"] and [s["codec_name"] for s in probe(mp4)["audio"]] == ["aac"]
    assert abs(dominant_hz(mp4) - TONE_HZ) < 8


def test_a_corrupt_browser_upload_is_refused_at_completion(host_a, tmp_path):
    content = b"RIFF" + os.urandom(2000)
    host_a.client.post("/api/cameras/register", json={"source_id": "p25d_e2e_cam", "name": "studio", "location": "studio25d", "tags": ["studio25d"]})
    spec = {"take_id": "e2ebad" + secrets.token_hex(4), "production_id": "prod_" + secrets.token_hex(4), "source_id": "p25d_e2e_cam",
            "mime": "video/webm", "bytes": len(content), "chain": _chain([content]), "width": 320, "height": 240, "duration_ms": 1000, "manifest": {}}
    created = host_a.client.post("/api/studio25d/recordings", json=spec).json()
    take_id = created["id"]
    assert host_a.client.put(f"/api/studio25d/recordings/{take_id}/chunks/0", content=content,
                             headers={"X-Chunk-SHA256": sha256(content), "Content-Type": "application/octet-stream"}).status_code == 200
    assert host_a.client.post(f"/api/studio25d/recordings/{take_id}/complete").status_code == 422
    assert host_a.client.get(f"/api/studio25d/recordings/{take_id}/media").status_code == 409


def test_replay_upload_accepts_real_audio_video_and_refuses_the_wrong_kind(host_a, host_b, tmp_path):
    clip = tmp_path / "replay.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2", "-f", "lavfi", "-i", f"sine=frequency={TONE_HZ}:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", clip)
    with open(clip, "rb") as f:
        ok = host_a.client.post("/api/upload", data={"target": "vod"}, files={"file": ("replay.mp4", f, "video/mp4")})
    assert ok.status_code == 200, ok.text
    name = ok.json()["filename"]
    served = host_a.client.get(f"/assets/vod/{name}")
    assert served.status_code == 200 and sha256(served.content) == sha256(clip), "the uploaded file is served back byte-identical"
    # an mp4 name on non-video bytes, and a video of the wrong type, are refused
    bad = host_a.client.post("/api/upload", data={"target": "vod"}, files={"file": ("fake.mp4", b"not a video at all", "video/mp4")})
    assert bad.status_code == 400
    exe = host_a.client.post("/api/upload", data={"target": "vod"}, files={"file": ("clip.mkv", clip.read_bytes(), "video/x-matroska")})
    assert exe.status_code == 400
    over = host_a.client.post("/api/upload", data={"target": "vod"}, files={"file": ("big.mp4", b"\x00" * (5 * 1024 * 1024 + 10), "video/mp4")})
    assert over.status_code == 413
