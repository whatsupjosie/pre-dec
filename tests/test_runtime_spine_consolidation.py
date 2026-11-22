"""Behaviour the 2026-11-22 spine consolidation decided on.

Two June 2026 spines were merged: the rich one (Visual Patch Kit, motion
retargeting, 64 tests in runtime/spine/tests) and the minimal one that shipped
in pre-dec (stations, runtime state, replication). Each kept its own tests.
These cover the places where the two disagreed and a choice was made.
"""
import asyncio
import threading

import pytest

from runtime.spine import EventBus, FrozenDict, PerformerRegistry, RuntimeState
from runtime.spine.performers import AnimationAuthority, LocomotionSystem, PerformerState
from runtime.spine.stations import CameraStation


# ── event bus ────────────────────────────────────────────────────────────────

def test_a_failing_subscriber_neither_stops_the_others_nor_reaches_the_emitter():
    bus = EventBus()
    seen = []
    bus.subscribe("pub:message", lambda event: 1 / 0)
    bus.subscribe("pub:message", lambda event: seen.append(event["data"]["n"]))
    bus.emit("pub:message", {"n": 7})          # must not raise
    assert seen == [7]
    assert bus.errors()[-1]["data"]["error_type"] == "ZeroDivisionError"


def test_events_are_immutable_all_the_way_down():
    bus = EventBus()
    event = bus.emit("pub:message", {"inner": {"k": 1}, "items": [1, 2]})
    with pytest.raises(TypeError):
        event["data"]["inner"]["k"] = 2
    assert isinstance(event["data"]["inner"], FrozenDict)
    assert event["data"]["items"] == (1, 2)          # lists freeze to tuples
    assert bus.history()[-1]["data"]["items"] == [1, 2]   # history thaws them back


def test_a_handler_that_is_not_callable_is_refused_when_subscribing():
    with pytest.raises(TypeError):
        EventBus().subscribe("pub:message", "not a function")


def test_unsubscribing_the_last_listener_forgets_the_event_type():
    bus = EventBus()
    token = bus.subscribe("pub:message", lambda event: None)
    assert bus.subscriber_counts() == {"pub:message": 1}
    bus.unsubscribe(token)
    assert bus.subscriber_counts() == {}
    bus.unsubscribe(token)                      # a second unsubscribe is harmless


def test_emit_async_runs_plain_handlers_on_the_callers_thread():
    bus = EventBus()
    threads = []
    bus.subscribe("pub:message", lambda event: threads.append(threading.get_ident()))

    async def run():
        await bus.emit_async("pub:message", {})
        return threading.get_ident()

    caller = asyncio.run(run())
    assert threads == [caller]


def test_emit_async_still_awaits_coroutine_handlers_and_isolates_their_failures():
    bus = EventBus()
    seen = []

    async def good(event):
        seen.append("good")

    async def bad(event):
        raise RuntimeError("boom")

    bus.subscribe("pub:message", bad)
    bus.subscribe("pub:message", good)
    asyncio.run(bus.emit_async("pub:message", {}))
    assert seen == ["good"]
    assert bus.errors()[-1]["data"]["error_type"] == "RuntimeError"


def test_max_history_reports_the_history_limit():
    assert EventBus(history_limit=12).max_history == 12


# ── animation authority ──────────────────────────────────────────────────────

def test_a_higher_layer_takes_only_the_bones_it_drives():
    authority = AnimationAuthority()
    authority.register_animation("p1", "locomotion", {"hips": {"src": "walk"}, "thigh_l": {"src": "walk"}})
    authority.register_animation("p1", "mocap", {"hips": {"src": "mocap"}, "head": {"src": "mocap"}})
    pose = authority.resolve("p1")
    assert pose == {"hips": {"src": "mocap"}, "head": {"src": "mocap"}, "thigh_l": {"src": "walk"}}
    assert [layer["layer"] for layer in authority.resolve_layers("p1")] == ["mocap", "locomotion"]


def test_equal_priority_goes_to_the_later_registration_even_within_one_clock_tick():
    authority = AnimationAuthority()
    authority.submit("p1", "first", {"head": {"v": 1}}, priority=50)
    authority.submit("p1", "second", {"head": {"v": 2}}, priority=50)
    assert authority.resolve("p1")["head"] == {"v": 2}


def test_an_unknown_layer_needs_an_explicit_priority():
    authority = AnimationAuthority()
    with pytest.raises(ValueError):
        authority.register_animation("p1", "mystery", {"head": {}})
    authority.register_animation("p1", "mystery", {"head": {}}, priority=5)
    assert "head" in authority.resolve("p1")


def test_submit_accepts_the_minimal_spines_wrapped_pose_and_clamps_weight():
    authority = AnimationAuthority()
    authority.submit("p1", "overlay", {"bones": {"head": {"v": 1}}}, priority=10, weight=7)
    assert authority.resolve("p1") == {"head": {"v": 1}}
    assert authority.resolve_layers("p1")[0]["weight"] == 1.0


def test_resolving_returns_a_copy_and_clearing_the_last_layer_leaves_nothing():
    authority = AnimationAuthority()
    authority.register_animation("p1", "mocap", {"head": {"v": [1]}})
    authority.resolve("p1")["head"]["v"].append(99)
    assert authority.resolve("p1") == {"head": {"v": [1]}}
    authority.clear_layer("p1", "mocap")
    assert authority.resolve("p1") == {}


# ── performers ───────────────────────────────────────────────────────────────

def test_a_wrapped_or_frozen_pose_lands_as_flat_bones_with_the_name_on_the_performer():
    bus = EventBus()
    registry = PerformerRegistry(bus, bind_default_skeleton=False)
    registry.spawn_performer("p1", "Manny", [0, 0, 0], "studio")
    registry.apply_animation_frame("p1", {"animation": "wave", "bones": {"hand_r": {"r": [1, 2]}}})
    performer = registry.get_performer("p1")
    assert performer.skeleton_pose == {"hand_r": {"r": [1, 2]}}
    assert performer.current_animation == "wave"
    frozen = bus.emit("probe", {"pose": {"head": {"r": [0, 1]}}})["data"]["pose"]
    registry.apply_animation_frame("p1", frozen, animation="nod")
    assert performer.skeleton_pose == {"head": {"r": [0, 1]}}
    assert performer.current_animation == "nod"


def test_sitting_and_falling_are_valid_states_again():
    registry = PerformerRegistry(EventBus(), bind_default_skeleton=False)
    registry.spawn_performer("p1", "Manny", [0, 0, 0], "studio")
    registry.set_locomotion_state("p1", "sitting")
    registry.set_locomotion_state("p1", "falling")
    with pytest.raises(ValueError):
        registry.set_locomotion_state("p1", "teleporting")


def test_a_performer_built_from_partial_data_is_still_well_formed():
    state = PerformerState("p1", "Manny", position=[1], rotation=[], velocity=[1, 2, 3, 4])
    assert state.position == [1.0, 0.0, 0.0]
    assert state.rotation == [0.0, 0.0, 0.0, 1.0]
    assert state.velocity == [1.0, 2.0, 3.0]
    state.mark_dirty()
    assert state.dirty is True


def test_speed_and_walk_speed_name_the_same_setting_and_walking_reads_as_walk():
    bus = EventBus()
    registry = PerformerRegistry(bus, bind_default_skeleton=False)
    performer = registry.spawn_performer("p1", "Manny", [0, 0, 0], "studio")
    locomotion = LocomotionSystem(registry, bus, speed=2.0)
    assert locomotion.walk_speed == 2.0 and locomotion.speed == 2.0
    locomotion.move_to("p1", [1, 0, 0])
    locomotion.update(0.1)
    assert performer.current_animation == "walk"
    assert 0 < performer.position[0] < 1
    for _ in range(20):
        locomotion.update(0.1)
    assert performer.position == [1.0, 0.0, 0.0]
    assert performer.locomotion_state == "idle"
    assert performer.current_animation == "idle"


# ── stations and runtime state ───────────────────────────────────────────────

def test_every_station_event_says_which_station_sent_it():
    bus = EventBus()
    seen = []
    bus.subscribe("camera:live", seen.append)
    CameraStation("cam_b", bus).on_interaction("p1", {"live": True})
    data = seen[-1]["data"]
    assert (data["station_id"], data["station_type"], data["live"]) == ("cam_b", "camera", True)


def test_the_runtime_snapshot_carries_recent_events_as_plain_dicts():
    state = RuntimeState()
    state.performers.spawn_performer("p1", "Sheila", [0, 0, 0], "studio")
    state.enter_room("p1", "green_room")
    snap = state.snapshot()
    kinds = [event["event_type"] for event in snap["events"]]
    assert "room:entered" in kinds
    assert all(type(event) is dict for event in snap["events"])
    assert snap["performers"][0]["current_room"] == "green_room"
