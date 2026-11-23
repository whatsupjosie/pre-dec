"""The two show clocks: how far into the show, and how much is left to its set length.

Time code is HH:MM:SS:FF, where FF is a frame (00 to rate-1), at the show's frame rate (24 unless the show says
otherwise). A show only has a time-left clock when it has a set length, such as a TV slot of 24:10.
"""
import json
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import timeline as timeline_module
from modules import timeline_routes as routes
from modules.timeline import TimelineDefinition, TimelinePlayer, format_time_code


@pytest.mark.parametrize("seconds, rate, expected", [
    (0, 24, "00:00:00:00"),
    (20.5, 24, "00:00:20:12"),          # half a second is twelve of 24 frames
    (3725, 24, "01:02:05:00"),          # 1 h 2 min 5 s
    (59.999, 24, "00:00:59:23"),        # counted down: frame 24 has not started
    (1 / 24, 24, "00:00:00:01"),
    (0.96, 25, "00:00:00:24"),
    (0.99, 30, "00:00:00:29"),
    (1450, 24, "00:24:10:00"),          # a 24 minute 10 second TV slot
    (-2.0, 24, "-00:00:02:00"),         # past the set length
    (-0.001, 24, "00:00:00:00"),        # less than a frame over is not "over"
])
def test_time_code_counts_whole_frames(seconds, rate, expected):
    assert format_time_code(seconds, rate) == expected


@pytest.mark.parametrize("seconds, rate", [
    (math.nan, 24), (math.inf, 24), (True, 24), ("5", 24), (5, 29.97), (5, 0), (5, 60), (5, True),
])
def test_time_code_refuses_what_it_cannot_count(seconds, rate):
    with pytest.raises(ValueError):
        format_time_code(seconds, rate)


def test_a_show_runs_at_24_frames_with_no_set_length_unless_it_says_otherwise(tmp_path):
    plain = TimelineDefinition.from_dict({"name": "old", "duration": 60, "events": []})
    assert (plain.frame_rate, plain.set_length) == (24, None)

    slot = TimelineDefinition(name="slot", duration=1500, frame_rate=25, set_length=1450)
    slot.save(tmp_path / "slot.json")
    again = TimelineDefinition.load(tmp_path / "slot.json")
    assert (again.frame_rate, again.set_length) == (25, 1450)
    assert json.loads((tmp_path / "slot.json").read_text())["set_length"] == 1450


@pytest.mark.parametrize("change, message", [
    ({"frame_rate": 29.97}, "Frame rate"),
    ({"frame_rate": 60}, "Frame rate"),
    ({"frame_rate": True}, "Frame rate"),
    ({"set_length": 0}, "Set length"),
    ({"set_length": -5}, "Set length"),
    ({"set_length": math.nan}, "Set length"),
    ({"set_length": math.inf}, "Set length"),
    ({"set_length": True}, "Set length"),
    ({"set_length": "1450"}, "Set length"),
])
def test_a_show_with_a_bad_frame_rate_or_set_length_is_refused(change, message):
    from modules.timeline import TimelineEvent, EventType
    definition = TimelineDefinition(name="x", duration=60, events=[TimelineEvent(t=1, event_type=EventType.CAMERA)], **change)
    assert any(message in issue for issue in definition.validate())


def _client(tmp_path, monkeypatch, **show):
    player = TimelinePlayer()
    monkeypatch.setattr(routes, "player", player)
    monkeypatch.setattr(routes, "TIMELINES_DIR", tmp_path)
    body = {"name": "show", "duration": 1500, "events": [{"t": 1, "type": "camera"}], **show}
    (tmp_path / "show.json").write_text(json.dumps(body))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), player


def test_status_gives_time_in_and_time_left_for_a_show_with_a_set_length(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, set_length=1450)[0] as client:
        assert client.post("/api/timeline/load", json={"name": "show"}).json()["set_length"] == 1450
        assert client.post("/api/timeline/seek", params={"time": 20.5}).is_success
        status = client.get("/api/timeline/status").json()
    assert status["frame_rate"] == 24
    assert status["elapsed_time_code"] == "00:00:20:12"
    assert status["remaining"] == pytest.approx(1429.5)       # 1450 - 20.5
    assert status["remaining_time_code"] == "00:23:49:12"     # 23 min 49.5 s


def test_time_left_goes_negative_once_the_show_is_past_its_set_length(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, set_length=10)[0] as client:
        client.post("/api/timeline/load", json={"name": "show"})
        client.post("/api/timeline/seek", params={"time": 25})
        status = client.get("/api/timeline/status").json()
    assert status["remaining"] == pytest.approx(-15)
    assert status["remaining_time_code"] == "-00:00:15:00"


def test_a_show_with_no_set_length_has_no_time_left_clock(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch)[0] as client:
        client.post("/api/timeline/load", json={"name": "show"})
        client.post("/api/timeline/seek", params={"time": 20.5})
        status = client.get("/api/timeline/status").json()
        listed = client.get("/api/timeline/list").json()["timelines"][0]
    assert status["elapsed_time_code"] == "00:00:20:12"
    assert status["set_length"] is None and status["remaining"] is None and status["remaining_time_code"] is None
    assert listed["set_length"] is None and listed["frame_rate"] == 24


def test_nothing_loaded_means_no_clocks(tmp_path, monkeypatch):
    client, player = _client(tmp_path, monkeypatch)
    with client:
        status = client.get("/api/timeline/status").json()
    assert player.clocks() is None and player.status()["clocks"] is None
    assert status["elapsed_time_code"] is None and status["remaining_time_code"] is None


def test_the_clocks_follow_a_running_show(monkeypatch):
    player = TimelinePlayer()
    show = TimelineDefinition(name="live", duration=60, set_length=30, frame_rate=30,
                              events=[timeline_module.TimelineEvent(t=1, event_type=timeline_module.EventType.CAMERA)])
    assert not player.load_timeline(show)
    player._state = timeline_module.TimelineState.RUNNING
    player._start_time = 100.0
    monkeypatch.setattr(timeline_module.time, "monotonic", lambda: 112.5)
    clocks = player.clocks()
    assert clocks["elapsed_time_code"] == "00:00:12:15"       # half a second is 15 of 30 frames
    assert clocks["remaining_time_code"] == "00:00:17:15"     # 30 - 12.5 = 17.5 s
