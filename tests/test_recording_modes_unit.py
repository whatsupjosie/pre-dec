"""Recording modes: the parts that need no host and no cameras.

* the show-data file: written, read back, verified; a file cut short by a crash still reads up to its last whole line;
  an altered line is caught by the footer hash;
* the program plan: what was on the live screen becomes pieces of files with exact in and out points, holes become
  black of exactly their length, and nothing ever overlaps;
* which hub rooms may enter the show data;
* the hub reports each message once to its listeners, and a failing listener never stops delivery;
* a take's data files go out with an export and come back with an import, byte for byte, and a bundle whose data
  does not match its metadata, or was altered, is refused.
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import shutil
import time
from types import SimpleNamespace
import zipfile
from pathlib import Path

import pytest

from modules.cameras import CameraManager, CameraSource, CameraTransport, CameraSwitchEvent
from modules.recording import create_recording_service, ContainerFormat
from modules.recording_modes import (MODE_RECORD_FILE, SHOW_DATA_FILE, Interval, ModeRequestError, Segment,
                                     ShowDataRecorder, iter_show_data, plan_program, room_is_recordable,
                                     validate_mode_request, verify_show_data)


# --- show data --------------------------------------------------------------------------------------------------
def test_show_data_reads_back_and_verifies(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    recorder = ShowDataRecorder(path, {"session_id": "t1", "mode": "data_only"})
    recorder.open()
    recorder.record("camera.switch", CameraSwitchEvent("program", "cam_b", "cam_a", 123.0))
    recorder.record("hub.system", {"type": "mocap_frame", "payload": {"bones": [[0.1, 0.2, 0.3, 1.0]] * 89}})
    recorder.record("hub.room", {"type": "chat", "payload": {"text": "ready"}}, room="studio")
    summary = recorder.close()
    assert summary["complete"] and summary["events"] == 3 and summary["bytes"] == path.stat().st_size
    lines = list(iter_show_data(path))
    assert lines[0]["header"] and lines[0]["schema"] == "pubcast-show-data/1" and lines[0]["session_id"] == "t1"
    assert [line["kind"] for line in lines[1:4]] == ["camera.switch", "hub.system", "hub.room"]
    # "transition" added 2026-11-26 (finish/control-room-engine): None for a cut, the dissolve otherwise.
    assert lines[1]["data"] == {"destination": "program", "source_id": "cam_b", "previous_source_id": "cam_a",
                                "timestamp": 123.0, "transition": None}
    assert lines[3]["room"] == "studio" and [line["seq"] for line in lines[1:4]] == [0, 1, 2]
    assert lines[-1]["footer"] and lines[-1]["sha256"] == summary["sha256"]
    check = verify_show_data(path)
    assert check["verified"] and check["closed"] and check["events"] == 3 and check["kinds"]["hub.system"] == 1
    assert path.stat().st_size < summary["uncompressed_bytes"], "compressed"


def test_a_crash_loses_at_most_the_last_second(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    recorder = ShowDataRecorder(path, {"session_id": "t2"}, flush_seconds=0.0)     # flush after every event
    recorder.open()
    for i in range(50):
        recorder.record("hub.system", {"type": "choreo_frame", "i": i})
    # The process dies here: nothing closes the file. Copy exactly what is on disk.
    crashed = tmp_path / "crashed.jsonl.gz"
    shutil.copyfile(path, crashed)
    lines = list(iter_show_data(crashed))
    assert lines[0]["header"] and [line["data"]["i"] for line in lines[1:]] == list(range(50))
    check = verify_show_data(crashed)
    assert not check["closed"] and not check["verified"] and check["events"] == 50
    # Cut mid-way through the compressed bytes too: still no exception, a whole-line prefix comes back.
    half = tmp_path / "half.jsonl.gz"
    half.write_bytes(crashed.read_bytes()[: crashed.stat().st_size * 2 // 3])
    prefix = [line["data"]["i"] for line in iter_show_data(half) if not line.get("header")]
    assert prefix == list(range(len(prefix))) and 0 < len(prefix) <= 50
    recorder.close()


def test_an_altered_line_is_caught(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    recorder = ShowDataRecorder(path, {"session_id": "t3"})
    recorder.open()
    recorder.record("camera.switch", {"destination": "program", "source_id": "cam_a"})
    recorder.close()
    text = gzip.decompress(path.read_bytes()).decode().replace("cam_a", "cam_x")
    path.write_bytes(gzip.compress(text.encode()))
    check = verify_show_data(path)
    assert check["closed"] and not check["verified"]


def test_a_take_never_overwrites_another_takes_data(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    path.write_bytes(b"earlier take")
    with pytest.raises(FileExistsError):
        ShowDataRecorder(path, {}).open()
    assert path.read_bytes() == b"earlier take"


# --- the program plan -------------------------------------------------------------------------------------------
def seg(index, offset, duration, spawned=None, source="cam"):
    s = Segment(index=index, source_id=source, key="k", file=Path(f"p{index}.mp4"), synthetic=False,
                spawned_at=spawned if spawned is not None else offset, state="stopped", duration=duration)
    s.media_offset = offset
    s.first_frame_at = max(s.spawned_at, offset)
    return s


def test_cuts_become_exact_pieces_with_no_overlap():
    segments = {1: seg(1, 100.0, 5.4), 2: seg(2, 104.2, 4.0, spawned=104.1)}
    intervals = [Interval("a", 1, "program", start_ref=1, end_ref=2), Interval("b", 2, "program", start_ref=2, end=108.0)]
    origin, pieces = plan_program(intervals, segments, frame=1 / 30)
    assert origin == 100.0
    assert pieces == [{"kind": "segment", "segment": 1, "in": 0.0, "out": 4.2},
                      {"kind": "segment", "segment": 2, "in": 0.0, "out": 3.8}]
    assert sum(p["out"] - p["in"] for p in pieces) == pytest.approx(8.0), "the program lasts exactly the take"


def test_a_file_that_starts_early_is_used_from_the_cut_not_from_its_start():
    # A file camera reads its first half second at once, so its clock zero falls before it was started.
    segments = {1: seg(1, 99.5, 6.0, spawned=100.0)}
    origin, pieces = plan_program([Interval("a", 1, "program", start_ref=1, end=105.0)], segments, frame=1 / 30)
    assert origin == 100.0 and pieces == [{"kind": "segment", "segment": 1, "in": 0.5, "out": 5.5}]


def test_holes_and_short_files_become_black_of_exactly_their_length():
    segments = {1: seg(1, 100.0, 2.0), 3: seg(3, 106.0, 3.0)}
    intervals = [Interval("a", 1, "program", start_ref=1, end=103.0),          # the file holds only 2 of these 3 s
                 Interval("private_cam", None, "private", start=103.0, end=105.0),
                 Interval("c", 3, "program", start=105.0, end=109.0)]          # starts 1 s before its file does
    origin, pieces = plan_program(intervals, segments, frame=1 / 30)
    assert origin == 100.0
    assert pieces == [{"kind": "segment", "segment": 1, "in": 0.0, "out": 2.0}, {"kind": "black", "duration": 1.0},
                      {"kind": "black", "duration": 2.0},
                      {"kind": "black", "duration": 1.0}, {"kind": "segment", "segment": 3, "in": 0.0, "out": 3.0}]
    total = sum(p["duration"] if p["kind"] == "black" else p["out"] - p["in"] for p in pieces)
    assert total == pytest.approx(9.0)


def test_slivers_shorter_than_a_frame_are_dropped():
    segments = {1: seg(1, 100.0, 5.0), 2: seg(2, 102.0, 5.0)}
    intervals = [Interval("a", 1, "program", start_ref=1, end=102.01),
                 Interval("b", 2, "program", start=102.01, end=102.02),
                 Interval("a", 1, "program", start=102.02, end=104.0)]
    _, pieces = plan_program(intervals, segments, frame=1 / 30)
    assert [p.get("segment") for p in pieces] == [1, 1]


# --- privacy for room messages --------------------------------------------------------------------------------------
def test_only_rooms_the_privacy_table_names_and_allows_enter_the_show_data(tmp_path):
    recording = create_recording_service(tmp_path, CameraManager())
    assert room_is_recordable(recording, "studio", host_override=False)
    assert room_is_recordable(recording, "pub", host_override=False)
    assert not room_is_recordable(recording, "dressing", host_override=False)
    assert not room_is_recordable(recording, "green", host_override=False)
    assert room_is_recordable(recording, "green", host_override=True), "consent rooms follow the camera rule"
    assert not room_is_recordable(recording, "chat_8f3a", host_override=True), "unknown rooms are never recorded"
    assert not room_is_recordable(recording, "dm____alex", host_override=True)
    assert not room_is_recordable(recording, "dmv2_x", host_override=True)


# --- the hub reports each message once ---------------------------------------------------------------------------
class _Socket:
    def __init__(self):
        from starlette.websockets import WebSocketState
        self.application_state = WebSocketState.CONNECTED
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


def test_the_hub_reports_each_message_once_and_a_failing_listener_changes_nothing(tmp_path):
    from modules.hub import Hub
    hub = Hub(tmp_path)
    a, b = _Socket(), _Socket()
    hub.rooms = {"studio": {a}, "pub": {b}}
    seen = []
    hub.add_event_observer(lambda kind, room, message: seen.append((kind, room, message["type"])))

    def broken(kind, room, message):
        raise RuntimeError("listener bug")
    token = hub.add_event_observer(broken)
    asyncio.run(hub.broadcast_system_event({"type": "camera_switch", "payload": {}}))
    asyncio.run(hub._broadcast("studio", {"type": "chat", "payload": {"text": "hi"}}))
    assert seen == [("system", None, "camera_switch"), ("room", "studio", "chat")], "a system message is not repeated per room"
    assert [m["type"] for m in a.sent] == ["camera_switch", "chat"] and [m["type"] for m in b.sent] == ["camera_switch"]
    assert hub.remove_event_observer(token) and not hub.remove_event_observer(token)


# --- validation -------------------------------------------------------------------------------------------------
def _service(tmp_path):
    cameras = CameraManager()
    for sid, transport, endpoint in (("cam_a", "file", "/x/a.mp4"), ("cam_b", "file", "/x/b.mp4"),
                                     ("push", "rtmp", "rtmp://0.0.0.0:1935/live/k"), ("pull", "rtmp", "rtmp://10.0.0.5/live/k")):
        cameras.register(CameraSource(source_id=sid, name=sid, location="studio", description="",
                                      transport=CameraTransport(transport), endpoint=endpoint))
    return create_recording_service(tmp_path, cameras)


def test_mode_requests_are_checked_before_anything_starts(tmp_path):
    rec = _service(tmp_path)
    assert validate_mode_request(rec, None, ["cam_a"], "broadcast_mp4") == "camcorder"
    assert validate_mode_request(rec, " Data_Only ", [], "broadcast_mp4") == "data_only"
    with pytest.raises(ModeRequestError, match="Unknown recording mode"):
        validate_mode_request(rec, "cinema", ["cam_a"], "broadcast_mp4")
    with pytest.raises(ModeRequestError, match="true or false"):
        validate_mode_request(rec, "camcorder", ["cam_a"], "broadcast_mp4", record_data="yes")
    with pytest.raises(ModeRequestError, match="no program camera"):
        validate_mode_request(rec, "main_camera", ["cam_a"], "broadcast_mp4")
    rec.cameras.set_program_source("cam_a")
    assert validate_mode_request(rec, "main_camera", ["cam_a", "cam_b", "pull"], "broadcast_mp4") == "main_camera"
    with pytest.raises(ModeRequestError, match="camcorder mode"):
        validate_mode_request(rec, "main_camera", ["cam_a", "push"], "broadcast_mp4")
    with pytest.raises(ModeRequestError, match="records picture"):
        validate_mode_request(rec, "main_camera", ["cam_a"], "audio_only")
    with pytest.raises(KeyError):
        validate_mode_request(rec, "main_camera", ["cam_a"], "no_such_profile")
    session = rec.start_session("v1", [], profile_id="broadcast_mp4", operator="t", mode="data_only", countdown_seconds=0)
    assert session.mode == "data_only" and session.record_data is True and session.sources == []
    with pytest.raises(ValueError, match="At least one source"):
        rec.start_session("v2", [], profile_id="broadcast_mp4", operator="t", mode="camcorder", countdown_seconds=0)


# --- data files travel with the take -------------------------------------------------------------------------------
def _data_take(tmp_path):
    rec = _service(tmp_path / "a")
    session = rec.start_session("take_d", [], profile_id="broadcast_mp4", operator="t", mode="data_only", countdown_seconds=0)
    folder = rec._session_dir("take_d")
    recorder = ShowDataRecorder(folder / SHOW_DATA_FILE, {"session_id": "take_d"})
    recorder.open()
    recorder.record("camera.switch", {"destination": "program", "source_id": "cam_b"})
    recorder.close()
    (folder / MODE_RECORD_FILE).write_text(json.dumps({"mode": "data_only"}))
    rec.attach_data_file("take_d", folder / SHOW_DATA_FILE)
    rec.attach_data_file("take_d", folder / MODE_RECORD_FILE)
    rec.attach_data_file("take_d", folder / SHOW_DATA_FILE)            # attaching twice changes nothing
    rec.stop_session("take_d")
    return rec, session, folder


def test_data_files_go_out_and_come_back_byte_for_byte(tmp_path):
    rec, session, folder = _data_take(tmp_path)
    assert rec.get_session("take_d").data_files == [SHOW_DATA_FILE, MODE_RECORD_FILE]
    with pytest.raises(ValueError):
        rec.attach_data_file("take_d", tmp_path / "elsewhere.json")
    bundle = rec.export_session("take_d", container=ContainerFormat.MP4)
    with zipfile.ZipFile(bundle) as z:
        manifest = json.loads(z.read("EXPORT_MANIFEST.json"))
        for name in (SHOW_DATA_FILE, MODE_RECORD_FILE):
            data = z.read("data/" + name)
            assert data == (folder / name).read_bytes()
            assert manifest["files"]["data/" + name] == {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    other = _service(tmp_path / "b")
    imported = other.import_session(bundle)
    assert imported.mode == "data_only" and imported.data_files == [SHOW_DATA_FILE, MODE_RECORD_FILE]
    copied = other._session_dir("take_d")
    assert (copied / SHOW_DATA_FILE).read_bytes() == (folder / SHOW_DATA_FILE).read_bytes()
    assert verify_show_data(copied / SHOW_DATA_FILE)["verified"]
    # After a restart the take is found again with its mode and data files.
    restarted = create_recording_service(tmp_path / "b", other.cameras)
    again = restarted.get_session("take_d")
    assert again.mode == "data_only" and again.data_files == [SHOW_DATA_FILE, MODE_RECORD_FILE]


def _rewrite(bundle, out, change):
    with zipfile.ZipFile(bundle) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            data = change(item.filename, zin.read(item.filename))
            if data is not None:
                zout.writestr(item.filename, data)
    return out


def test_an_altered_or_missing_data_file_is_refused_and_leaves_nothing(tmp_path):
    rec, _, _ = _data_take(tmp_path)
    bundle = rec.export_session("take_d", container=ContainerFormat.MP4)
    other = _service(tmp_path / "b")
    altered = _rewrite(bundle, tmp_path / "altered.zip",
                       lambda name, data: data[:-1] + bytes([data[-1] ^ 1]) if name == "data/" + MODE_RECORD_FILE else data)
    with pytest.raises(ValueError, match="integrity"):
        other.import_session(altered)
    missing = _rewrite(bundle, tmp_path / "missing.zip",
                       lambda name, data: None if name == "data/" + SHOW_DATA_FILE else data)
    with pytest.raises(ValueError):
        other.import_session(missing)
    sneaky = _rewrite(bundle, tmp_path / "sneaky.zip", lambda name, data: data)
    with zipfile.ZipFile(sneaky, "a") as z:
        z.writestr("data/../../escape.json", b"{}")
    with pytest.raises(ValueError):
        other.import_session(sneaky)
    assert not other._session_dir("take_d").exists(), "a refused bundle leaves no take behind"


def test_a_take_from_before_modes_existed_still_loads_as_camcorder(tmp_path):
    rec = _service(tmp_path)
    session = rec.start_session("old", ["cam_a"], profile_id="broadcast_mp4", operator="t", countdown_seconds=0)
    path = rec._session_dir("old") / "old.json"
    meta = json.loads(path.read_text())
    for key in ("mode", "record_data", "data_files"):
        meta.pop(key)
    path.write_text(json.dumps(meta))
    restarted = create_recording_service(tmp_path, rec.cameras)
    old = restarted.get_session("old")
    assert old.mode == "camcorder" and old.record_data is False and old.data_files == []
    assert session.mode == "camcorder"


# --- joining the program after a restart, from the record alone ----------------------------------------------------
@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe not available")
def test_a_stopped_take_can_be_joined_from_its_record_after_a_restart(tmp_path):
    import subprocess
    from modules.recording_modes import RecordingModeController
    rec = _service(tmp_path)
    rec.cameras.set_program_source("cam_a")
    rec.start_session("joined", ["cam_a", "cam_b"], profile_id="web_stream", operator="t",
                      mode="main_camera", countdown_seconds=0)
    folder = rec._session_dir("joined")
    for name, colour, hz in (("program_0001_cam_a.webm", "red", 440), ("program_0002_cam_b.webm", "blue", 880)):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-f", "lavfi", "-i", f"color=c={colour}:s=320x180:r=30:d=3",
                        "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=3", "-c:v", "libvpx-vp9", "-deadline", "realtime",
                        "-c:a", "libopus", "-shortest", str(folder / name)], check=True, timeout=120)
    t0 = 1_000_000.0
    record = {"schema": "pubcast-recording-mode/1", "session_id": "joined", "mode": "main_camera", "state": "recording",
              "take_started_utc": t0, "stopped_at": 4.0, "notes": [], "sound": [], "microphone": None,
              "program": {"cuts": [{"requested_at": 0.0, "to": "cam_a", "kind": "start", "segment": 1, "handled": "started"},
                                   {"requested_at": 2.0, "to": "cam_b", "kind": "cut", "segment": 2, "handled": "started",
                                    "effective_at": 2.0}],
                          "intervals": [{"source_id": "cam_a", "segment": 1, "reason": "program", "start": 0.0,
                                         "start_at_first_frame_of": None, "end": 2.0, "end_at_first_frame_of": None},
                                        {"source_id": "cam_b", "segment": 2, "reason": "program", "start": 2.0,
                                         "start_at_first_frame_of": None, "end": 4.0, "end_at_first_frame_of": None}],
                          "segments": [{"index": 1, "source_id": "cam_a", "file": "program_0001_cam_a.webm", "synthetic": False,
                                        "state": "stopped", "spawned_at": 0.0, "stopped_at": 3.0, "media_offset": 0.0,
                                        "first_frame_at": 0.0, "duration": 3.0, "has_audio": True},
                                       {"index": 2, "source_id": "cam_b", "file": "program_0002_cam_b.webm", "synthetic": False,
                                        "state": "stopped", "spawned_at": 2.0, "stopped_at": 5.0, "media_offset": 2.0,
                                        "first_frame_at": 2.0, "duration": 3.0, "has_audio": True}]},
              "assembly": {"state": "running"}}
    (folder / MODE_RECORD_FILE).write_text(json.dumps(record))
    rec.stop_session("joined")

    async def run():
        controller = RecordingModeController(cameras=rec.cameras, recording=rec)
        status = controller.status("joined")
        assert status["interrupted"], "a record left mid-take after the server stopped says so"
        result = await controller.assemble("joined")
        with pytest.raises(ModeRequestError, match="never overwritten"):
            await controller.assemble("joined")
        return result
    result = asyncio.run(run())
    assert result["state"] == "complete", result
    assert result["duration"] == pytest.approx(4.0, abs=0.1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(folder / result["file"]), "-vf", "fps=4,scale=1:1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    colours = ["R" if raw[i] > 150 else "B" if raw[i + 2] > 150 else "?" for i in range(0, len(raw), 3)]
    assert colours[:7] == ["R"] * 7 and colours[9:15] == ["B"] * 6, colours
    assert "program.webm" in [a.name for a in rec.get_session("joined").artifacts]


# --- following cuts: never more cameras recording than the mode allows ----------------------------------------------
class _FakeEngine:
    """Stands in for FFmpeg: each start is a 'process' that runs until stopped. Only the mode logic is under test."""
    available = True

    def __init__(self):
        self.running_keys = {}
        self.started = []

    async def start(self, key, sources, profile, folder, audio_input=None):
        path = Path(folder) / f"{sources[0].source_id}.{profile.container.value}"
        path.write_bytes(b"media")
        self.running_keys[key] = (time.time(), path)
        self.started.append(key)
        return [path]

    async def start_audio_input(self, key, audio_input, profile, folder, *, name="microphone"):
        return await self.start(key, [SimpleNamespace(source_id=name)], profile, folder)

    def startup_failures(self, key):
        return []

    def running(self, key):
        return key in self.running_keys

    def live_report(self, key):
        return [{"encoded_seconds": 0.5}] if key in self.running_keys else []

    async def stop(self, key):
        started, path = self.running_keys.pop(key, (time.time(), None))
        self.last = {key: time.time() - started}
        return [path] if path else []

    def report(self, key):
        return [{"speed": 1.0, "encoded_seconds": 1.0}]


def test_cut_following_never_leaves_a_camera_recording_it_should_not(tmp_path, monkeypatch):
    import random
    import modules.recording_modes as modes
    monkeypatch.setattr(modes, "probe_media", lambda path: {"duration": 1.0, "video": True, "audio": False})
    names = ["cam_a", "cam_b", "cam_c", "cam_d"]
    cameras = CameraManager()
    for sid in names + ["dress"]:
        cameras.register(CameraSource(source_id=sid, name=sid, location="dressing" if sid == "dress" else "studio",
                                      description="", transport=CameraTransport.VIRTUAL, endpoint=f"virtual://{sid}"))
    rng = random.Random(20261122)

    async def scenario(run, armed):
        rec = create_recording_service(tmp_path / f"r{run}", cameras)
        cameras.set_program_source("cam_a"); cameras.set_preview_source("cam_b")
        engine = _FakeEngine()
        controller = modes.RecordingModeController(cameras=cameras, recording=rec, capture_engine=engine)
        session = rec.start_session(f"run{run}", list(names), profile_id="web_stream", operator="t",
                                    mode="main_camera", countdown_seconds=0)
        await controller.begin(session, arm_preview=armed)
        take = controller._takes[session.session_id]
        for _ in range(12):
            action = rng.choice(["program", "preview", "take"])
            target = rng.choice(names + ["dress"])
            if action == "program":
                cameras.set_program_source(target)
            elif action == "preview":
                cameras.set_preview_source(target)
            else:
                cameras.take()
            for _ in range(20):
                await asyncio.sleep(0)            # let the cut follower catch up
            while not take._queue.empty():
                await asyncio.sleep(0.001)
            await asyncio.sleep(0.005)
            picture = [k for k in engine.running_keys if "~pgm" in k]
            assert len(picture) <= (2 if armed else 1) + 1, f"too many cameras recording: {picture}"
            program_seg = take.segments.get(take._program) if take._program is not None else None
            program_cam = cameras.get_program_source().source_id
            if program_seg is not None:
                assert program_seg.source_id == program_cam, "the camera recording as program is the one on air"
            else:
                assert take.intervals[-1].source_id == program_cam and take.intervals[-1].segment is None
            if take._preview is not None:
                assert armed and take.segments[take._preview].source_id == cameras.get_preview_source().source_id
            # Settle: the overlap at a cut is temporary; once settled, only program (and armed preview) record.
            await asyncio.sleep(0.01)
            running = {take.segments[i].source_id for i, s in take.segments.items() if s.state == "running"}
            allowed = {program_cam} | ({cameras.get_preview_source().source_id} if armed else set())
            assert running <= allowed, f"recording {running}, allowed {allowed}"
        await controller.end(session.session_id)
        assert not [k for k in engine.running_keys if "~pgm" in k], "everything stops with the take"
        intervals = take.intervals
        assert all(i.end is not None or i.end_ref is not None for i in intervals), "every stretch is closed"
        dress = [i for i in intervals if i.source_id == "dress"]
        assert all(i.reason == "private" and i.segment is None for i in dress)
        assert not any(s.source_id == "dress" for s in take.segments.values()), "the dressing room never records"
        rec.stop_session(session.session_id)

    for run in range(60):
        asyncio.run(scenario(run, armed=bool(run % 2)))
