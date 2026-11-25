"""The capture engine keeps every recording, pauses for real, and says which camera failed.

These run the real FFmpeg (skipped where it is not installed) on short real-time inputs, so each
test takes a few seconds.
"""
import asyncio
import os
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


def test_pause_stops_the_encoder_and_is_not_reported_as_lag(tmp_path):
    if os.name == "nt":
        pytest.skip("this test signals FFmpeg the POSIX way")
    tone = _tone(tmp_path / "tone.wav", 30)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        [path] = await engine.start("take", [_file_source("mic", tone)], _audio_profile(tmp_path), take)
        await asyncio.sleep(2.0)
        await engine.pause("take")
        assert engine.is_paused("take")
        await asyncio.sleep(0.5)               # anything already buffered reaches the file
        held = path.stat().st_size
        await asyncio.sleep(2.0)
        still = path.stat().st_size
        await engine.resume("take")
        assert not engine.is_paused("take")
        await asyncio.sleep(2.0)
        await engine.stop("take")
        return engine, path, held, still

    engine, path, held, still = asyncio.run(run())
    assert still == held, "the file kept growing while the take was paused"
    assert path.stat().st_size > held, "recording did not continue after resume"
    [report] = engine.report("take")
    assert report["paused_seconds"] >= 2.0
    assert not any("shorter" in w or "behind" in w for w in report["warnings"]), report["warnings"]
    assert not report.get("failed")


def test_a_pause_that_cannot_reach_every_encoder_changes_none_of_them(tmp_path, monkeypatch):
    tone = _tone(tmp_path / "tone.wav", 10)
    take = tmp_path / "take"
    take.mkdir()

    async def run():
        engine = _engine()
        await engine.start("take", [_file_source("a", tone), _file_source("b", tone)], _audio_profile(tmp_path), take)
        second = engine._active["take"][1]
        second.proc.kill()
        await second.proc.wait()
        with pytest.raises(RuntimeError):
            await engine.pause("take")
        first = engine._active["take"][0]
        assert first.paused is False and first.proc.returncode is None
        await engine.stop("take")
        return engine

    engine = asyncio.run(run())
    failures = engine.failures("take")
    assert [f["source_id"] for f in failures if f["phase"] == "stop"] == ["b"]


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
