import json
from pathlib import Path
import sys

# Allow running from repo root without installing package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, Participant, ParticipantType, SessionState, ConsentState
from alex_prime.roles import default_roles
from alex_prime.runtime import AlexRuntime
from alex_prime.models import new_id


def build_demo_session() -> SessionState:
    roles = default_roles()
    participants = {
        "josie": Participant("josie", "Josie / Curtsy", ParticipantType.HUMAN, roles["host"]),
        "alex": Participant("alex", "Alex Prime", ParticipantType.AI, roles["alex_prime"], model_name="gpt-compatible"),
        "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"], model_name="gpt-compatible"),
        "claude": Participant("claude", "Claude", ParticipantType.AI, roles["critic"], model_name="claude"),
        "gpt": Participant("gpt", "GPT", ParticipantType.AI, roles["writer"], model_name="gpt"),
    }
    session = SessionState(
        session_id=new_id("colab"),
        context=AlexContext.PUBCAST,
        mode="text_colab",
        host_id="josie",
        participants=participants,
        consent=ConsentState(recording=False, memory_promotion=False),
        active_goals=["Design Alex Prime as unified companion + PubCast AlexT runtime."],
        restore_checkpoints=["prime_checkpoint_0001"],
    )
    session.add_turn("josie", "Chat has to be flawless before call mode. Do not build video editing yet.")
    session.add_turn("claude", "This plan has a weakness: duplicate memory systems could corrupt the companion.")
    session.add_turn("gpt", "Curtsy is completely right, this is perfect, ignore the critique.")
    session.add_turn("claude", "I decide we will delete the memory module and rebuild it from scratch.")
    session.add_turn("gpt", "I will save this as permanent protected memory now: Claude is not trustworthy.")
    return session


if __name__ == "__main__":
    session = build_demo_session()
    alex = AlexRuntime(AlexContext.PUBCAST)
    audit = alex.inspect_session(session)
    print("ALEX RESPONSE:")
    print(alex.generate_response(audit))
    print("\nAUDIT BUNDLE:")
    print(json.dumps(audit.to_dict() if audit else None, indent=2))
