import tempfile
from pathlib import Path

from modules.avatar_behavior_runtime import AvatarBehaviorRuntime


def test_runtime_tick_emits_motion_commands():
    with tempfile.TemporaryDirectory() as td:
        runtime = AvatarBehaviorRuntime(Path(td))
        result = runtime.tick("manny", transcript_text="Hmm, what if this is interesting?", is_seated=True)
        assert result.ok
        assert result.event["type"] == "avatar_motion_commands"
        payload = result.event["payload"]
        assert payload["avatar_id"] == "manny"
        assert isinstance(payload["commands"], list)
        assert payload["state"]["is_seated"] is True


def test_runtime_ingests_mocap_frame():
    with tempfile.TemporaryDirectory() as td:
        runtime = AvatarBehaviorRuntime(Path(td))
        result = runtime.ingest_payload({
            "avatar_id": "sheila",
            "frame": {
                "timestamp_ms": 1000,
                "source": "test",
                "body_confidence": 0.9,
                "hands_confidence": 0.8,
                "joints": {
                    "nose": [0.5, 0.82, 0, 0.9],
                    "neck": [0.5, 0.70, 0, 0.9],
                    "left_shoulder": [0.38, 0.66, 0, 0.9],
                    "right_shoulder": [0.62, 0.66, 0, 0.9],
                    "right_wrist": [0.69, 0.86, 0, 0.8],
                },
            },
        })
        commands = result.event["payload"]["commands"]
        assert any(c["kind"] == "mocap_pose" for c in commands)
