from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, ConsentState, Participant, ParticipantType, SessionState
from alex_prime.models import new_id
from alex_prime.roles import default_roles


if __name__ == "__main__":
    roles = default_roles()
    participants = {
        "host": Participant("host", "Host", ParticipantType.HUMAN, roles["host"]),
        "alex": Participant("alex", "Alex", ParticipantType.AI, roles["alex_prime"]),
        "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"]),
        "critic": Participant("critic", "Critic", ParticipantType.AI, roles["critic"]),
    }
    session = SessionState(
        session_id=new_id("brief_demo"),
        context=AlexContext.PUBCAST,
        mode="ai_roundtable_colab",
        host_id="host",
        participants=participants,
        consent=ConsentState(),
        active_goals=["Review Alex core quality before promotion."],
        active_constraints=["No silent stable-memory writes."],
    )
    session.add_turn("host", "decision: Chat Mode remains the first production target.")
    runtime = AlexRuntime(AlexContext.PUBCAST)
    brief = runtime.build_colab_brief(session)
    print(brief.to_dict())
    print(runtime.brief_builder.scoped_for_participant(brief, "critic"))
