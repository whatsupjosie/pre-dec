import pytest

from modules import choreography_runtime
from modules.choreography_controller import AvatarSim
from modules.choreography_runtime import Choreography, ChoreographyStep


def test_back_to_back_cues_reach_targets_and_replay(monkeypatch):
    timestamp = 100.0
    monkeypatch.setattr(choreography_runtime.time, "time", lambda: timestamp)
    actor = AvatarSim(id="pete")
    walk = ChoreographyStep("pete", "walk", 0.0, 1.0, target_position=[2.0, 0.0, 0.0])
    run = ChoreographyStep("pete", "run", 1.0, 1.0, target_position=[4.0, 0.0, 0.0])
    choreo = Choreography(steps=[walk, run])
    choreo.start([actor])

    timestamp = 100.5
    choreo.update([actor])
    assert actor.position == [1.0, 0.0, 0.0]
    assert not run.initial_position

    timestamp = 101.5
    choreo.update([actor])
    assert walk.completed
    assert run.initial_position == [2.0, 0.0, 0.0]
    assert actor.position == [3.0, 0.0, 0.0]

    timestamp = 102.0
    choreo.update([actor])
    assert run.completed
    assert actor.position == [4.0, 0.0, 0.0]
    actor.position[0] = 5.0
    timestamp = 102.5
    choreo.update([actor])
    assert actor.position[0] == 5.0

    choreo.start([actor])
    timestamp = 103.0
    choreo.update([actor])
    assert actor.position == [3.5, 0.0, 0.0]


def test_turn_cue_applies_final_yaw_even_without_an_active_frame(monkeypatch):
    timestamp = 10.0
    monkeypatch.setattr(choreography_runtime.time, "time", lambda: timestamp)
    actor = AvatarSim(id="pete")
    turn = ChoreographyStep("pete", "look", 0.25, 0.25, target_rotation=[0.0, 1.5, 0.0])
    choreo = Choreography(steps=[turn])
    choreo.start([actor])
    timestamp = 12.0
    choreo.update([actor])
    assert actor.rotation[1] == 1.5
    assert turn.completed


@pytest.mark.asyncio
async def test_studio_controller_broadcasts_final_frame_before_completion():
    import asyncio

    from modules.choreography_controller import ChoreoController

    class Hub:
        def __init__(self):
            self.events = []
            self.complete = asyncio.Event()

        async def broadcast_system_event(self, event):
            self.events.append(event)
            if event["type"] == "choreo_complete":
                self.complete.set()

    hub = Hub()
    controller = ChoreoController(hub)
    await controller.start(
        room="stage", avatars=[{"id": "pete"}],
        steps=[{"avatar_id": "pete", "animation_type": "walk",
                "start_time": 0.0, "duration": 0.001, "target_position": [2.0, 0.0, 0.0]}],
        tick_hz=20, constraints={"enabled": False},
    )
    try:
        await asyncio.wait_for(hub.complete.wait(), timeout=1.0)
        assert hub.events[-2]["type"] == "choreo_frame"
        assert hub.events[-2]["payload"]["avatars"][0]["position"] == [2.0, 0.0, 0.0]
        assert hub.events[-1]["payload"]["room"] == "stage"
    finally:
        await controller.stop()


@pytest.mark.asyncio
async def test_constrained_cue_reaches_bounded_target_before_reporting_completion():
    import asyncio

    from modules.choreography_controller import ChoreoController

    class Hub:
        def __init__(self):
            self.frames = []
            self.complete = asyncio.Event()

        async def broadcast_system_event(self, event):
            if event["type"] == "choreo_frame":
                frame = event["payload"]["avatars"][0]
                self.frames.append((frame["position"][0], frame["rotation"][1]))
            elif event["type"] == "choreo_complete":
                self.complete.set()

    hub = Hub()
    controller = ChoreoController(hub)
    await controller.start(
        room="stage", avatars=[{"id": "pete"}],
        steps=[
            {"avatar_id": "pete", "animation_type": "walk", "start_time": .04,
             "duration": .001, "target_position": [1.0, 0.0, 0.0]},
            {"avatar_id": "pete", "animation_type": "turn", "start_time": .04,
             "duration": .001, "target_rotation": [0.0, 18.0, 0.0]},
        ],
        tick_hz=40, constraints={"enabled": True, "x_max": .12, "max_horizontal_speed": .5,
                                 "max_turn_rate_deg": 60},
    )
    try:
        await asyncio.wait_for(hub.complete.wait(), timeout=2)
        assert hub.frames[-1] == pytest.approx((.12, 18.0))
        assert any(0 < position < .12 for position, _ in hub.frames)
        assert any(0 < angle < 18 for _, angle in hub.frames)
    finally:
        await controller.stop()
