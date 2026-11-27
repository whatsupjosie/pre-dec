"""The preflight every start runs: what it checks, what it refuses, and that no start path can go around it."""
from collections import namedtuple
from pathlib import Path

import pytest

import modules.studio_camera_preflight as pf
from modules.cameras import create_default_cameras
from modules.recording import create_recording_service
from modules.studio_camera_preflight import PreflightRefusal, bits_per_second, recording_preflight

Usage = namedtuple("Usage", "total used free")


def service(tmp_path: Path):
    cameras = create_default_cameras()
    return cameras, create_recording_service(tmp_path, cameras)


def test_bitrates_are_read_the_way_profiles_write_them():
    assert bits_per_second("50Mbps") == 50e6 and bits_per_second("320kbps") == 320e3
    assert bits_per_second("1.5Mbps") == 1.5e6 and bits_per_second("880Mbps") == 880e6
    assert bits_per_second(None) is None and bits_per_second("fast") is None


def test_the_machine_report_counts_each_output_the_mode_makes(tmp_path):
    cameras, recording = service(tmp_path)
    cam = recording_preflight(cameras, recording, sources=["wide_shot", "close_up"], profile_id="broadcast_mp4",
                              mode="camcorder")
    assert [o["output"] for o in cam["machine"]["outputs"]] == ["wide_shot (broadcast_mp4)", "close_up (broadcast_mp4)"]
    per_minute = (50e6 + 320e3) * 2 * pf.DISK_MARGIN / 8 * 60
    assert cam["machine"]["estimated_bytes_per_minute"] == round(per_minute)
    assert cam["machine"]["writable"] and cam["gate"]["pass"] and cam["ready"]
    data = recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="broadcast_mp4", mode="data_only")
    assert [o["output"] for o in data["machine"]["outputs"]] == ["wide_shot sound (audio_only)"]
    assert not list(Path(recording.recordings_dir).glob(".preflight-*"))       # its test write is cleaned up


def test_a_mode_the_start_would_refuse_is_reported_by_the_same_rule(tmp_path):
    cameras, recording = service(tmp_path)
    r = recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="audio_only", mode="main_camera")
    assert not r["ready"] and any(i["code"] == "mode_refused" and "picture" in i["message"] for i in r["issues"])
    r = recording_preflight(cameras, recording, mode="cinema")
    assert any(i["code"] == "mode_refused" for i in r["issues"])


def test_disk_short_of_the_plan_warns_and_disk_for_under_two_minutes_refuses(tmp_path, monkeypatch):
    cameras, recording = service(tmp_path)
    per_minute = (50e6 + 320e3) * pf.DISK_MARGIN / 8 * 60
    monkeypatch.setattr(pf.shutil, "disk_usage", lambda p: Usage(0, 0, int(per_minute * 10)))
    r = recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="broadcast_mp4", mode="camcorder")
    assert r["machine"]["minutes_of_disk"] == pytest.approx(10, abs=0.1)
    assert r["ready"] and r["gate"]["pass"] and any(w["code"] == "disk_short" for w in r["warnings"])
    monkeypatch.setattr(pf.shutil, "disk_usage", lambda p: Usage(0, 0, int(per_minute * 1.5)))
    r = recording_preflight(cameras, recording, sources=["wide_shot"], profile_id="broadcast_mp4", mode="camcorder")
    assert not r["ready"] and [x["code"] for x in r["gate"]["refusals"]] == ["disk_full"]


def test_the_start_itself_refuses_and_leaves_nothing_behind(tmp_path, monkeypatch):
    cameras, recording = service(tmp_path)
    monkeypatch.setattr(pf.shutil, "disk_usage", lambda p: Usage(0, 0, 1000))
    with pytest.raises(PreflightRefusal) as err:
        recording.start_session("full_disk", ["wide_shot"], profile_id="broadcast_mp4", operator="t", countdown_seconds=0)
    assert "disk" in str(err.value) and isinstance(err.value, ValueError)
    assert "full_disk" not in [s.session_id for s in recording.list_sessions()]
    assert not (Path(recording.recordings_dir) / "full_disk").exists()


def test_no_ffmpeg_refuses_a_take_that_encodes_but_not_one_that_only_keeps_show_data(tmp_path, monkeypatch):
    cameras, recording = service(tmp_path)
    monkeypatch.setattr(pf.shutil, "which", lambda name: None)
    with pytest.raises(PreflightRefusal) as err:
        recording.start_session(None, ["wide_shot"], profile_id="broadcast_mp4", operator="t", countdown_seconds=0)
    assert "FFmpeg" in str(err.value)
    session = recording.start_session(None, [], profile_id="broadcast_mp4", operator="t", countdown_seconds=0,
                                      mode="data_only")
    assert session.mode == "data_only"


def test_a_folder_that_cannot_be_written_refuses(tmp_path, monkeypatch):
    cameras, recording = service(tmp_path)
    real_open = open

    def failing_open(path, *a, **k):
        if ".preflight-" in str(path):
            raise PermissionError("read-only file system")
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(PreflightRefusal) as err:
        recording.start_session(None, ["wide_shot"], profile_id="broadcast_mp4", operator="t", countdown_seconds=0)
    assert "cannot be written" in str(err.value)


def test_a_started_take_carries_what_the_director_should_know(tmp_path, monkeypatch):
    cameras, recording = service(tmp_path)
    per_minute = (50e6 + 320e3) * pf.DISK_MARGIN / 8 * 60
    monkeypatch.setattr(pf.shutil, "disk_usage", lambda p: Usage(0, 0, int(per_minute * 12)))
    session = recording.start_session(None, ["wide_shot"], profile_id="broadcast_mp4", operator="t", countdown_seconds=0)
    assert session.preflight["minutes_of_disk"] == pytest.approx(12, abs=0.1)
    assert any(w["code"] == "disk_short" for w in session.preflight["warnings"])


def test_every_start_path_goes_through_the_gate(tmp_path, monkeypatch):
    """The studio console action starts takes with its own code; it still meets the gate."""
    from modules.program_audio import ProgramAudioState
    from modules.studio_console_actions import execute_studio_action
    cameras, recording = service(tmp_path)
    monkeypatch.setattr(pf.shutil, "disk_usage", lambda p: Usage(0, 0, 1000))
    with pytest.raises(ValueError) as err:
        execute_studio_action("recording.start", {"confirm": True, "sources": ["wide_shot"]}, cameras=cameras,
                              recording=recording, audio_state=ProgramAudioState(), actor="t")
    assert "disk" in str(err.value)


def test_the_start_route_refuses_with_the_reason_and_the_preflight_route_explains(tmp_path):
    """Through the real application, in its own process with its own data folder: the route answers 409 with the
    gate's refusal and nothing is recorded; the preflight route reports the machine."""
    import json
    import os
    import subprocess
    import sys
    script = r"""
import json, sys
from collections import namedtuple
from fastapi.testclient import TestClient
import modules.studio_camera_preflight as pf
import main
Usage = namedtuple("Usage", "total used free")
out = {}
with TestClient(main.app) as client:
    r = client.post("/api/recording/preflight", json={"mode": "camcorder", "planned_minutes": 1e9})
    out["preflight"] = [r.status_code, r.json()]
    pf.shutil.disk_usage = lambda p: Usage(0, 0, 1000)
    r = client.post("/api/recording/start", json={"countdown_seconds": 0, "session_id": "gate_route"})
    out["start"] = [r.status_code, r.json()]
    out["sessions"] = [s["session_id"] for s in client.get("/api/recording/sessions").json()]
print("RESULT " + json.dumps(out))
"""
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if k != "PUBCAST_ENFORCE_AUTH"}
    env.update(PUBCAST_DATA_DIR=str(tmp_path / "data"), PUBCAST_ASSETS_DIR=str(tmp_path / "assets"))
    done = subprocess.run([sys.executable, "-c", script], cwd=str(root), env=env, capture_output=True, text=True,
                          timeout=300)
    line = [l for l in done.stdout.splitlines() if l.startswith("RESULT ")]
    assert line, done.stdout[-3000:] + done.stderr[-3000:]
    out = json.loads(line[-1][7:])
    status, body = out["preflight"]
    assert status == 200 and body["mode"] == "camcorder" and body["machine"]["writable"] is True
    assert any(w["code"] == "disk_short" for w in body["warnings"])          # nobody has a billion minutes
    status, body = out["start"]
    assert status == 409, body
    assert [x["code"] for x in body["detail"]["refusals"]] == ["disk_full"] and "Cannot roll" in body["detail"]["message"]
    assert "gate_route" not in out["sessions"]
    assert not (tmp_path / "data" / "recordings" / "gate_route").exists()
