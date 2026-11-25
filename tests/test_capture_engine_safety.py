"""The capture engine keeps every recording, pauses for real (nothing is recorded while paused), and says which camera failed.

These run the real FFmpeg (skipped where it is not installed) on short real-time inputs, so each
test takes a few seconds.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.capture import FFmpegCaptureEngine
from modules.cameras import create_default_cameras
from modules.recording import create_recording_service

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="FFmpeg is not installed")


def _tone(path: Path, seconds: int = 30) -> Path:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    str(path)], check=True)
    return path


def _file_source(source_id, endpoint):
    return SimpleNamespace(source_id=source_id, transport=SimpleNamespace(value="file"), endpoint=str(endpoint))


def _audio_profile(tmp_path):
    return create_recording_service(tmp_path / "svc", create_default_cameras()).get_profile("audio_only")


def _engine():
    engine = FFmpegCaptureEngine()
    assert engine.available
    return engine


def test_a_file_already_in_the_take_folder_is_never_written_over(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 5)
    take = tmp_path / "take"
    take.mkdir()
    earlier = take / "cam_a.wav"
    earlier.write_bytes(b"earlier recording")
    (take / "CAM_B.wav.ffmpeg.log").write_text("log of a recording whose file is gone")

    async def run():
        engine = _engine()
        paths = await engine.start("take", [_file_source("cam_a", tone), _file_source("cam_b", tone)],
                                   _audio_profile(tmp_path), take)
        await asyncio.sleep(1.0)
        await engine.stop("take")
        return engine, paths

    engine, paths = asyncio.run(run())
    assert [p.name for p in paths] == ["cam_a-2.wav", "cam_b-2.wav"]
    assert earlier.read_bytes() == b"earlier recording"
    assert all(p.stat().st_size > 0 for p in paths)
    assert engine.failures("take") == []


def _probe(path: Path) -> dict:
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, check=True).stdout
    data = json.loads(out)
    return {"duration": float(data["format"]["duration"]), "streams": sorted(s["codec_type"] for s in data["streams"])}


def _live_camera(port: int):
    """A camera that streams live over UDP whether or not anyone is recording it, as a real one does."""
    return subprocess.Popen([FFMPEG, "-v", "error", "-re", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30",
                             "-f", "lavfi", "-i", "sine=frequency=300", "-c:v", "libx264", "-preset", "ultrafast",
                             "-tune", "zerolatency", "-g", "30", "-c:a", "aac", "-f", "mpegts",
                             f"udp://127.0.0.1:{port}?pkt_size=1316"])


def _udp_source(source_id, port):
    return SimpleNamespace(source_id=source_id, transport=SimpleNamespace(value="udp"),
                           endpoint=f"udp://127.0.0.1:{port}?fifo_size=100000&overrun_nonfatal=1")


def _video_profile(tmp_path):
    return create_recording_service(tmp_path / "svc", create_default_cameras()).get_profile("web_stream")


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not installed")
def test_a_paused_stretch_is_not_in_a_live_cameras_file(tmp_path):
    # Suspending FFmpeg left a 5 s pause in the file: the stream waited and was written on resume.
    port = 24000 + os.getpid() % 1000
    camera = _live_camera(port)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        [path] = await engine.start("take", [_udp_source("cam", port)], _video_profile(tmp_path), take)
        await asyncio.sleep(7.0)
        assert await engine.pause("take") == []
        assert engine.is_paused("take")
        await asyncio.sleep(1.0)
        held = path.stat().st_size
        await asyncio.sleep(4.0)
        assert path.stat().st_size == held, "the file grew while the take was paused"
        assert await engine.resume("take") == []
        await asyncio.sleep(7.0)
        await engine.stop("take")
        return engine, path

    try:
        engine, path = asyncio.run(run())
    finally:
        camera.terminate()
    [report] = engine.report("take")
    media = _probe(path)
    assert report["join"]["state"] == "joined", report
    assert report["paused_seconds"] >= 5.0
    assert media["streams"] == ["audio", "video"]
    # 14 s recorded around a 5 s pause: the file holds the recorded time, not the wall time.
    assert media["duration"] <= report["wall_seconds"] - 4.0, (media, report)
    assert abs(media["duration"] - report["recorded_seconds"]) < 1.5, (media, report)
    assert not report["warnings"], report["warnings"]
    assert sorted(p.name for p in take.iterdir() if not p.name.endswith(".log")) == ["cam.webm"]
    assert engine.failures("take") == []


def test_a_take_stopped_while_paused_keeps_what_was_recorded(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 30)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        [path] = await engine.start("take", [_file_source("mic", tone)], _audio_profile(tmp_path), take)
        await asyncio.sleep(3.0)
        await engine.pause("take")
        await asyncio.sleep(1.0)
        await engine.stop("take")
        return engine, path

    engine, path = asyncio.run(run())
    [report] = engine.report("take")
    assert not report.get("failed"), report
    assert path.stat().st_size > 0
    assert report["paused_seconds"] >= 1.0


def test_a_file_camera_resumes_where_it_has_got_to(tmp_path):
    # Five seconds of tone, then silence. Resumed about 6.5 s in, the clip has reached the silence; a camera
    # that started its clip over would record the tone again.
    clip = tmp_path / "clip.wav"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=mono", "-filter_complex", "[1]atrim=duration=25[s];[0][s]concat=n=2:v=0:a=1",
                    str(clip)], check=True)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        [path] = await engine.start("take", [_file_source("clip", clip)], _audio_profile(tmp_path), take)
        await asyncio.sleep(3.0)
        await engine.pause("take")
        await asyncio.sleep(3.0)
        await engine.resume("take")
        await asyncio.sleep(3.0)
        await engine.stop("take")
        return engine, path

    engine, path = asyncio.run(run())
    [report] = engine.report("take")
    assert report["join"]["state"] == "joined", report
    after = subprocess.run([FFMPEG, "-hide_banner", "-ss", "5.0", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    level = float(re.search(r"max_volume: (-?[0-9.]+) dB", after).group(1))
    assert level < -60, f"the resumed piece holds the start of the clip again (max {level} dB)"


def test_an_encoder_that_already_ended_does_not_block_the_pause(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 10)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        await engine.start("take", [_file_source("good", tone), _file_source("broken", tmp_path / "missing.wav")],
                           _audio_profile(tmp_path), take)
        await engine.pause("take")
        assert engine.is_paused("take")
        await engine.resume("take")
        await engine.stop("take")

    asyncio.run(run())


def test_a_camera_that_cannot_come_back_after_a_pause_is_named(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 30)
    gone = tmp_path / "gone.wav"
    shutil.copy(tone, gone)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        await engine.start("take", [_file_source("stays", tone), _file_source("unplugged", gone)],
                           _audio_profile(tmp_path), take)
        await asyncio.sleep(2.0)
        await engine.pause("take")
        gone.unlink()                       # the camera is unplugged while the take is paused
        problems = await engine.resume("take")
        await asyncio.sleep(1.0)
        paths = await engine.stop("take")
        return engine, problems, paths

    engine, problems, paths = asyncio.run(run())
    assert [p["source_id"] for p in problems] == ["unplugged"]
    assert problems[0]["phase"] == "resume"
    assert {"source_id": "unplugged", "phase": "resume"}.items() <= next(
        f for f in engine.failures("take") if f["phase"] == "resume").items()
    # What it recorded before the pause is kept.
    assert sorted(p.name for p in paths) == ["stays.wav", "unplugged.wav"]


def test_one_broken_camera_is_named_and_the_others_still_record(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 10)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        paths = await engine.start("take", [_file_source("good", tone), _file_source("broken", tmp_path / "missing.wav")],
                                   _audio_profile(tmp_path), take)
        await asyncio.sleep(1.0)
        started = time.monotonic()
        await engine.stop("take")
        return engine, paths, time.monotonic() - started

    engine, paths, _ = asyncio.run(run())
    failures = engine.failures("take")
    assert {f["source_id"] for f in failures} == {"broken"}
    assert any(f["phase"] == "start" for f in failures)
    assert (take / "good.wav").stat().st_size > 0


def test_an_encoder_that_could_not_be_launched_is_reported_as_failed_to_start(tmp_path):
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        engine._bin = str(tmp_path / "no-such-ffmpeg")
        paths = await engine.start("take", [_file_source("cam", tmp_path / "x.wav")], _audio_profile(tmp_path), take)
        return engine, paths

    engine, paths = asyncio.run(run())
    assert engine.failures("take") == [{"source_id": "cam", "phase": "start",
                                        "error": "FFmpeg could not be started for this source; see the server log"}]
    assert engine.startup_failures("take")[0]["source_id"] == "cam"


def test_every_camera_is_stopped_at_once(tmp_path):
    tone = _tone(tmp_path / "tone.wav", 30)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        await engine.start("take", [_file_source(f"cam{i}", tone) for i in range(3)], _audio_profile(tmp_path), take)
        await asyncio.sleep(1.0)
        for cp in engine._active["take"]:
            cp.proc.stdin.close()               # none of them can read "q": each needs the slower stop
        started = time.monotonic()
        await engine.stop("take")
        return engine, time.monotonic() - started

    engine, took = asyncio.run(run())
    # One at a time this is at least three 8-second waits for "q"; together it is one.
    assert took < 16, took
    assert not engine._active


def test_failed_sources_are_kept_with_the_saved_take_and_read_back(tmp_path):
    import json
    service = create_recording_service(tmp_path / "svc", create_default_cameras())
    sources = [c.source_id for c in service.cameras.list_sources()][:2]
    session = service.start_session(None, sources, profile_id="audio_only", operator="test",
                                    countdown_seconds=0, record_data=False)
    clean = json.loads((service._session_dir(session.session_id) / f"{session.session_id}.json").read_text())
    assert "capture_errors" not in clean, "a take with no failures keeps its file as before"

    service.note_capture_errors(session.session_id, [{"source_id": sources[0], "error": "no input", "phase": "start"}])
    service.note_capture_errors(session.session_id, [{"source_id": sources[0], "error": "exit 1", "phase": "start"},
                                                     {"source_id": sources[1], "error": "no media", "phase": "stop"}])
    saved = json.loads((service._session_dir(session.session_id) / f"{session.session_id}.json").read_text())
    assert saved["capture_errors"] == [{"source_id": sources[0], "error": "exit 1", "phase": "start"},
                                       {"source_id": sources[1], "error": "no media", "phase": "stop"}]
    assert service._session_from_dict(saved).capture_errors == saved["capture_errors"]
    older = dict(saved, capture_errors={sources[0]: "no input"})        # the codex/main-debug shape
    assert service._session_from_dict(older).capture_errors == [{"source_id": sources[0], "error": "no input",
                                                                 "phase": "unknown"}]
