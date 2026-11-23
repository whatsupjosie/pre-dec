"""Every camera in a take records to its own file.

Source ids that clean to the same file name ("cam/a" and "cam_a"), or that differ only in letter case
on a folder that ignores case, used to be written over each other by FFmpeg (-y). These tests start the
real engine code path and replace only the step that launches FFmpeg, so no FFmpeg binary is needed.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from modules import capture
from modules.capture import FFmpegCaptureEngine, _file_stem, _reserve_output_path
from modules.cameras import create_default_cameras
from modules.recording import create_recording_service


def _source(source_id):
    return SimpleNamespace(source_id=source_id, transport=SimpleNamespace(value="file"), endpoint="unused")


def _started_paths(tmp_path, monkeypatch, source_ids):
    engine = FFmpegCaptureEngine()
    engine._bin = "ffmpeg-not-run"
    profile = create_recording_service(tmp_path / "svc", create_default_cameras()).get_profile("audio_only")
    monkeypatch.setattr(capture, "_build_ffmpeg_input", lambda transport, endpoint: ["-i", endpoint])

    async def launched(cmd, source_id, out_path):
        running = SimpleNamespace(returncode=None)   # FFmpeg is still running: the start did not fail
        return capture._CaptureProcess(source_id=source_id, output_path=out_path, proc=running,
                                       log_path=out_path.with_suffix(".log"))

    monkeypatch.setattr(engine, "_spawn", launched)
    session_dir = tmp_path / "take"
    session_dir.mkdir()
    return asyncio.run(engine.start("take", [_source(s) for s in source_ids], profile, session_dir)), session_dir


def test_file_stem_removes_separators_of_both_path_styles():
    assert _file_stem("cam/a") == "cam_a"
    assert _file_stem("cam\\a") == "cam_a"
    assert _file_stem("rtsp:cam") == "rtsp_cam"
    assert _file_stem("..\\..\\escape") == ".._.._escape"


def test_reserved_names_get_counted_suffixes_and_ignore_case(tmp_path):
    reserved = set()
    first = _reserve_output_path(tmp_path, "cam_a", "mp4", reserved)
    second = _reserve_output_path(tmp_path, "cam_a", "mp4", reserved)
    third = _reserve_output_path(tmp_path, "CAM_A", "mp4", reserved)
    taken = _reserve_output_path(tmp_path, "cam_a-2", "mp4", reserved)
    assert [p.name for p in (first, second, third, taken)] == [
        "cam_a.mp4", "cam_a-2.mp4", "CAM_A-3.mp4", "cam_a-2-2.mp4"]


def test_sources_whose_names_clean_alike_record_to_separate_files(tmp_path, monkeypatch):
    paths, session_dir = _started_paths(tmp_path, monkeypatch, ["cam/a", "cam_a", "Cam_A", "wide_shot"])
    assert len({p.name.casefold() for p in paths}) == 4
    assert all(p.parent == session_dir for p in paths)
    assert paths[3].name == "wide_shot.wav"
    assert paths[0].name == "cam_a.wav"


def test_a_source_with_a_backslash_cannot_leave_the_take_folder(tmp_path, monkeypatch):
    paths, session_dir = _started_paths(tmp_path, monkeypatch, ["..\\..\\outside"])
    assert [p.parent for p in paths] == [session_dir]
    assert Path(paths[0]).name == ".._.._outside.wav"
