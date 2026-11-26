"""Performer data, dissolves on the camera event, and reading show data back for reconstruction.

No browser, no FFmpeg: these check the contracts and the arithmetic. tests/test_reconstruction_e2e.py renders.
"""
from __future__ import annotations

import gzip
import json
import time

import pytest
from pydantic import ValidationError

from modules.cameras import CameraManager, CameraSource, CameraSwitchEvent, CameraTransport
from modules.performance_capture import PerformanceAuthority, PerformanceBatch, PerformanceFrame
from modules.reconstruction import ReconstructionError, ShowTimeline, check_camera, plan_frame, shot_for
from modules.recording_modes import NATIVE_SYSTEM_EVENTS, SHOW_DATA_FILE, ShowDataRecorder, iter_show_data
from modules.switcher_routes import SwitcherService

PACKAGES = {"late_night": {"cameras": [{"id": "wide", "center": [0.5, 0.5], "zoom": 1},
                                       {"id": "host", "center": [0.31, 0.62], "zoom": 2.6},
                                       {"id": "guest", "center": [0.69, 0.62], "zoom": 2.7}]}}


def frame(**over):
    body = {"package": "late_night",
            "performers": [{"id": "p1", "slot": "host", "avatar": "female", "position": [0.31, 0.82]},
                           {"id": "p2", "slot": "guest", "avatar": "male", "position": [0.69, 0.82]}]}
    body.update(over)
    return PerformanceFrame.model_validate(body)


# --- the frame contract -------------------------------------------------------------------------------------
def test_a_camera_pool_scene_is_a_valid_performance_frame():
    pool_scene = {"package": "news", "performers": [{"id": "a", "slot": "anchor", "avatar": "female",
                                                     "position": [0.5, 0.8], "vx": 0.0, "vy": 0.0, "moving": False}],
                  "lowerThird": True, "lowerText": "x", "scores": [1, 2], "blackout": False}
    assert PerformanceFrame.model_validate(pool_scene).stage()["lowerThird"] is True


@pytest.mark.parametrize("bad", [
    {"performers": [{"id": "p1", "avatar": "female", "position": [1.5, 0.5]}]},
    {"performers": [{"id": "p1", "avatar": "female", "position": [float("nan"), 0.5]}]},
    {"performers": [{"id": "p1", "position": [0.5, 0.5]}]},                                   # no body
    {"performers": [{"id": "p1", "avatar_url": "/static/../main.py", "position": [0.5, 0.5]}]},
    {"performers": [{"id": "p1", "avatar_url": "https://evil.example/x.glb", "position": [0.5, 0.5]}]},
    {"performers": [{"id": "p1", "avatar": "female", "position": [0.5, 0.5], "jaw": 1.5}]},
    {"performers": [{"id": "p1", "avatar": "female", "position": [.5, .5]},
                    {"id": "p1", "avatar": "male", "position": [.6, .5]}]},                    # duplicate id
    {"gestures": [{"performer": "nobody", "clip": "Wave"}]},
    {"assets": {"back": "/etc/passwd"}},
    {"package": "../x"},
    {"unknown": 1},
])
def test_bad_frames_are_refused_before_anything_is_kept(bad):
    with pytest.raises(ValidationError):
        frame(**bad)


def test_a_batch_must_keep_time_order():
    a, b = frame(client_ms=100.0), frame(client_ms=50.0)
    with pytest.raises(ValidationError):
        PerformanceBatch(frames=[a, b])
    with pytest.raises(ValidationError):
        PerformanceBatch(frames=[frame(), frame(client_ms=5.0)])


# --- the authority ------------------------------------------------------------------------------------------
class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_unchanged_frames_are_not_kept_twice_and_gestures_always_are():
    kept, sent, clock = [], [], Clock()
    auth = PerformanceAuthority(record=lambda kind, data, at=None: kept.append((kind, data, at)) or 1,
                                broadcast=sent.append, clock=clock)
    assert auth.publish([frame()], actor="dir")["takes_recording"] == 1
    auth.publish([frame()], actor="dir")
    assert len(kept) == 1 and auth.unchanged == 1
    clock.now += 1
    auth.publish([frame(gestures=[{"performer": "p1", "clip": "Wave"}])], actor="dir")
    assert len(kept) == 2 and kept[1][1]["gestures"] == [{"performer": "p1", "clip": "Wave"}]
    assert "gestures" not in kept[1][1]["stage"]                       # a gesture is an event, not a state
    assert sent == [{"type": "performance_state", "payload": {"sequence": 1, "stage": kept[0][1]["stage"]}}]
    assert auth.state()["sequence"] == 2


def test_pages_hear_at_most_ten_changes_a_second_but_every_change_is_recorded():
    kept, sent, clock = [], [], Clock()
    auth = PerformanceAuthority(record=lambda k, d, at=None: kept.append(d) or 1, broadcast=sent.append, clock=clock)
    for i in range(20):
        clock.now += 0.02
        auth.publish([frame(lowerText=str(i))], actor="dir")
    assert len(kept) == 20
    assert 1 <= len(sent) <= 5


def test_a_batch_keeps_the_spacing_the_sender_gave_it():
    kept, clock = [], Clock()
    auth = PerformanceAuthority(record=lambda k, d, at=None: kept.append(at) or 1, clock=clock)
    frames = [frame(lowerText=str(i), client_ms=5000.0 + i * 100) for i in range(4)]
    auth.publish(PerformanceBatch(frames=frames).frames, actor="dir")
    assert kept == pytest.approx([999.7, 999.8, 999.9, 1000.0])


def test_a_failing_recorder_or_page_never_loses_the_stage():
    def boom(*a, **k):
        raise OSError("disk full")
    auth = PerformanceAuthority(record=boom, broadcast=boom)
    assert auth.publish([frame()], actor="dir")["ok"] is True
    assert auth.state()["stage"]["package"] == "late_night"


# --- show data: timing, pauses and duplicates ---------------------------------------------------------------
def test_events_can_be_placed_in_the_recent_past_but_never_before_the_take_or_in_the_future(tmp_path):
    rec = ShowDataRecorder(tmp_path / SHOW_DATA_FILE, {"program": None})
    rec.open()
    t0 = rec._t0
    time.sleep(0.3)
    assert rec.record("performance.frame", {"n": 1}, at=t0 + 0.1)
    assert rec.record("performance.frame", {"n": 2}, at=t0 - 5)
    assert rec.record("performance.frame", {"n": 3}, at=time.monotonic() + 60)
    rec.paused = True
    assert rec.record("performance.frame", {"n": 4}) is False            # nothing is kept while paused
    rec.close()
    events = [e for e in iter_show_data(tmp_path / SHOW_DATA_FILE) if e.get("kind")]
    assert [e["data"]["n"] for e in events] == [1, 2, 3]
    assert events[0]["t"] == pytest.approx(0.1, abs=0.01)
    assert events[1]["t"] == 0
    assert 0.29 < events[2]["t"] < 1.0


def test_the_hub_copy_of_a_performance_frame_is_not_recorded_twice():
    from modules.recording_modes import RecordingModeController

    class Data:                      # the recorder's contract: nothing is kept while paused
        def __init__(self):
            self.kept, self.paused = [], False

        def record(self, kind, data, **kw):
            if self.paused:
                return False
            self.kept.append(kind)
            return True

    class Take:
        state = "recording"
        def __init__(self):
            self.data = Data()
            self.session = type("S", (), {"host_override": False})()
    controller = RecordingModeController(cameras=CameraManager(), recording=None)
    take = Take()
    controller._takes["t"] = take
    assert "performance_state" in NATIVE_SYSTEM_EVENTS
    controller._on_hub_message("system", None, {"type": "performance_state", "payload": {}})
    controller._on_hub_message("system", None, {"type": "camera_switch", "payload": {}})
    assert controller.record_event("performance.frame", {}) == 1
    assert take.data.kept == ["hub.system", "performance.frame"]
    take.data.paused = True
    assert controller.record_event("performance.frame", {}) == 0
    controller._on_hub_message("system", None, {"type": "camera_switch", "payload": {}})
    assert take.data.kept == ["hub.system", "performance.frame"]


# --- dissolves travel on the camera event -------------------------------------------------------------------
def cameras():
    m = CameraManager()
    for sid in ("p25d_late_night_wide", "p25d_late_night_host", "p25d_late_night_guest"):
        m.register(CameraSource(source_id=sid, name=sid, location="studio25d", description="2.5D test camera",
                                transport=CameraTransport.VIRTUAL, endpoint="virtual://" + sid))
    m.set_program_source("p25d_late_night_wide")
    m.set_preview_source("p25d_late_night_host")
    return m


def test_a_dissolve_is_on_the_switch_event_and_a_cut_is_not():
    m, events = cameras(), []
    m.subscribe(events.append)
    service = SwitcherService(m)
    assert service.auto("p25d_late_night_guest", transition="dissolve", duration_ms=600)
    assert service.cut("p25d_late_night_host")
    programs = [e for e in events if isinstance(e, CameraSwitchEvent) and e.destination == "program"]
    assert programs[0].transition == {"type": "dissolve", "duration_ms": 600}
    assert programs[1].transition is None
    m.set_preview_source("p25d_late_night_guest")
    assert service.auto(None, transition="dissolve", duration_ms=300)           # a take dissolves too
    programs = [e for e in events if isinstance(e, CameraSwitchEvent) and e.destination == "program"]
    assert programs[-1].source_id == "p25d_late_night_guest"
    assert programs[-1].transition == {"type": "dissolve", "duration_ms": 300}


def test_a_bad_transition_moves_nothing():
    m, events = cameras(), []
    m.subscribe(events.append)
    for bad in ({"type": "wipe"}, {"type": "dissolve", "duration_ms": 9000}, {"type": "dissolve", "duration_ms": True}):
        with pytest.raises(ValueError):
            m.set_program_source("p25d_late_night_guest", transition=bad)
        with pytest.raises(ValueError):
            m.take(transition=bad)
    assert m.get_program_source().source_id == "p25d_late_night_wide" and events == []


def test_the_stage_pages_are_told_how_program_changed():
    from modules.camera_broadcast import CameraBroadcastBridge
    m = cameras()
    bridge = CameraBroadcastBridge(m, hub=None)
    dissolve = bridge.message(CameraSwitchEvent("program", "p25d_late_night_host", "p25d_late_night_wide",
                                                transition={"type": "dissolve", "duration_ms": 600}))
    cut = bridge.message(CameraSwitchEvent("program", "p25d_late_night_host", "p25d_late_night_wide"))
    assert dissolve["payload"]["transition"] == {"type": "dissolve", "duration_ms": 600}
    assert cut["payload"]["transition"] == {"type": "cut", "duration_ms": 0}


# --- reading a take back --------------------------------------------------------------------------------------
def write_show(path, events, closed_after):
    lines = [{"schema": "x", "header": True, "utc_origin": 1000.0, "program": "p25d_late_night_wide", "session_id": "s"}]
    for i, (t, kind, data) in enumerate(events):
        lines.append({"seq": i, "t": t, "utc": 1000.0 + t, "kind": kind, "data": data})
    if closed_after is not None:
        lines.append({"footer": True, "events": len(events), "sha256": "x", "closed_utc": 1000.0 + closed_after})
    with gzip.open(path, "wt") as out:
        for line in lines:
            out.write(json.dumps(line) + "\n")


def stage(gx=0.69):
    return {"package": "late_night", "performers": [{"id": "p2", "avatar": "male", "position": [gx, 0.82]}]}


def test_pauses_are_taken_out_and_cuts_dissolve_on_take_time(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    write_show(path, [
        (0.5, "performance.frame", {"sequence": 1, "stage": stage()}),
        (2.0, "camera.switch", {"destination": "program", "source_id": "p25d_late_night_host",
                                "previous_source_id": "p25d_late_night_wide",
                                "transition": {"type": "dissolve", "duration_ms": 1000}}),
        (4.0, "take.paused", {}), (6.0, "take.resumed", {}),
        (7.0, "performance.frame", {"sequence": 2, "stage": stage(0.4)}),
        (8.0, "camera.switch", {"destination": "program", "source_id": "p25d_late_night_guest",
                                "previous_source_id": "p25d_late_night_host"}),
    ], closed_after=10.0)
    tl = ShowTimeline.read(path)
    assert tl.duration == pytest.approx(8.0) and tl.paused_seconds == pytest.approx(2.0)
    assert tl.show_time(3.9) == pytest.approx(3.9) and tl.show_time(4.0) == pytest.approx(6.0)
    assert tl.show_time(5.0) == pytest.approx(7.0)
    assert plan_frame(tl, "program", 0.2, PACKAGES)[2] == "black: no performer data yet"
    assert plan_frame(tl, "program", 1.0, PACKAGES)[2] == "camera p25d_late_night_wide"
    stage_now, shot, what = plan_frame(tl, "program", 2.5, PACKAGES)
    assert what == "dissolve p25d_late_night_wide -> p25d_late_night_host"
    assert shot["mix"] == pytest.approx(0.5) and shot["mix_to"] == {"center": [0.31, 0.62], "zoom": 2.6}
    assert plan_frame(tl, "program", 3.5, PACKAGES)[2] == "camera p25d_late_night_host"
    assert plan_frame(tl, "program", 5.5, PACKAGES)[0]["performers"][0]["position"] == [0.4, 0.82]
    assert plan_frame(tl, "program", 6.5, PACKAGES)[2] == "camera p25d_late_night_guest"
    assert plan_frame(tl, "p25d_late_night_guest", 1.0, PACKAGES)[2] == "camera p25d_late_night_guest"
    assert plan_frame(tl, {"center": [0.2, 0.3], "zoom": 3.0}, 1.0, PACKAGES)[1] == {"shot": {"center": [0.2, 0.3], "zoom": 3.0}}


def test_program_on_a_camera_this_renderer_cannot_draw_is_black_and_named(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    write_show(path, [(0.0, "performance.frame", {"stage": stage()}),
                      (1.0, "camera.switch", {"destination": "program", "source_id": "phone_cam",
                                              "previous_source_id": "p25d_late_night_wide"})], closed_after=2.0)
    tl = ShowTimeline.read(path)
    stage_now, _, what = plan_frame(tl, "program", 1.5, PACKAGES)
    assert stage_now is None and "phone_cam" in what and what.startswith("black")


def test_a_take_that_ended_abruptly_replays_to_its_last_event_and_says_so(tmp_path):
    path = tmp_path / SHOW_DATA_FILE
    write_show(path, [(0.0, "performance.frame", {"stage": stage()}), (3.0, "take.paused", {})], closed_after=None)
    tl = ShowTimeline.read(path)
    assert not tl.complete and tl.duration == pytest.approx(3.0) and tl.notes


def test_shots_and_framings_are_checked():
    assert shot_for("p25d_late_night_guest", "late_night", PACKAGES) == {"center": [0.69, 0.62], "zoom": 2.7}
    assert shot_for("p25d_news_anchor", "late_night", PACKAGES) is None
    assert check_camera({"center": [0, 1], "zoom": 4}) == {"center": [0.0, 1.0], "zoom": 4.0}
    for bad in ({"center": [0.5], "zoom": 2}, {"center": [0.5, 2], "zoom": 2}, {"center": [0.5, 0.5], "zoom": 0.5},
                {"center": [0.5, 0.5], "zoom": True}, "live_red", {"center": [0.5, 0.5], "zoom": 2, "x": 1}):
        with pytest.raises(ReconstructionError):
            check_camera(bad)


def test_a_take_started_mid_show_begins_with_the_stage_as_it_is(tmp_path):
    from types import SimpleNamespace
    from modules.recording_modes import ModeTake, RecordingModeController
    auth = PerformanceAuthority()
    assert auth.snapshot() is None
    auth.publish([frame(lowerThird=True)], actor="dir")
    controller = RecordingModeController(cameras=cameras(), recording=SimpleNamespace(
        privacy_matrix=lambda: {}, attach_data_file=lambda *a: None))
    controller.snapshot_providers.append(auth.snapshot)
    take = SimpleNamespace(controller=controller, session_id="s", mode="data_only", t0=0.0, dir=tmp_path, notes=[],
                           session=SimpleNamespace(profile_id="p", sources=[]), data=None)
    ModeTake._open_data(take)
    take.data.close()
    first = next(e for e in iter_show_data(tmp_path / SHOW_DATA_FILE) if e.get("kind"))
    assert first["kind"] == "performance.frame" and first["t"] < 0.05
    assert first["data"]["snapshot"] is True and first["data"]["stage"]["lowerThird"] is True
