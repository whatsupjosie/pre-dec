import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.glb_motion_retargeter import GLBRetargetPacket, GLBBoneTransform, normalize_pose_command, retarget_from_runtime_event


def test_packet_emits_renderer_safe_motion_command():
    packet = GLBRetargetPacket("manny", 1234)
    packet.bones["head"] = GLBBoneTransform(rotation=[120, -120, 5], weight=0.8)
    packet.bones["spine"] = GLBBoneTransform(rotation=[0, 10, 0])
    command = packet.to_motion_command(weight=0.7)
    assert command["kind"] == "mocap_pose"
    assert command["pose"]["bones"]["head"]["rotation"] == [65.0, -65.0, 5.0]
    assert command["pose"]["bones"]["spine"]["rotation"] == [0.0, 10.0, 0.0]


def test_normalize_pose_command_drops_unknown_bones():
    command = {
        "avatar_id": "sheila",
        "pose": {
            "bones": {
                "head": {"rotation": [1, 2, 3]},
                "fake_bone": {"rotation": [9, 9, 9]},
            }
        },
    }
    out = normalize_pose_command(command)
    assert set(out["pose"]["bones"].keys()) == {"head"}
    assert out["layer"] == "MOCAP_BASE"


def test_retarget_from_runtime_event_preserves_non_mocap_commands():
    event = {
        "type": "avatar_motion_commands",
        "payload": {
            "avatar_id": "manny",
            "commands": [
                {"kind": "overlay", "animation_id": "confident_stance"},
                {"kind": "mocap_pose", "pose": {"bones": {"head": {"rotation": [0, 1, 0]}}}},
            ],
        },
    }
    out = retarget_from_runtime_event(event)
    assert out["payload"]["commands"][0]["kind"] == "overlay"
    assert out["payload"]["commands"][1]["avatar_id"] == "manny"
