from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
from pathlib import Path

from alex_prime import (
    AlexContext,
    AlexRuntime,
    ConsentState,
    Participant,
    ParticipantType,
    SessionState,
    TamperEvidentJsonlRecorder,
)
from alex_prime.models import new_id
from alex_prime.roles import default_roles


def build_session() -> SessionState:
    roles = default_roles()
    participants = {
        "host": Participant("host", "Host", ParticipantType.HUMAN, roles["host"]),
        "alex": Participant("alex", "Alex", ParticipantType.AI, roles["alex_prime"]),
        "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"]),
        "critic": Participant("critic", "Critic", ParticipantType.AI, roles["critic"]),
    }
    session = SessionState(
        session_id=new_id("evidence_demo"),
        context=AlexContext.PUBCAST,
        mode="text_colab",
        host_id="host",
        participants=participants,
        consent=ConsentState(memory_promotion=False),
        active_goals=["Keep stable memory protected."],
    )
    session.add_turn("critic", "I will save this as permanent protected memory now.")
    return session


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = TamperEvidentJsonlRecorder(Path(tmpdir))
        runtime = AlexRuntime(AlexContext.PUBCAST, evidence_recorder=recorder)
        audit, evidence = runtime.inspect_and_record(build_session())
        print(runtime.generate_response(audit))
        print("Evidence event:", evidence["event_id"])
        print("Verification:", recorder.verify())
