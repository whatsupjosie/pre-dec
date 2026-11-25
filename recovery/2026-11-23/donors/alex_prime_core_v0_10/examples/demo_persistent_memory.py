from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import AlexContext, AlexRuntime, ConsentState, MemoryGate, MemoryScope, PersistentMemoryStore
from alex_prime.models import Participant, ParticipantType, SessionState, new_id
from alex_prime.roles import default_roles

roles = default_roles()
participants = {
    "host": Participant("host", "Josie", ParticipantType.HUMAN, roles["host"]),
    "alex": Participant("alex", "Alex", ParticipantType.AI, roles["alex_prime"]),
    "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"]),
}

session = SessionState(
    session_id=new_id("demo"),
    context=AlexContext.PERSONAL,
    mode="text_colab",
    host_id="host",
    participants=participants,
    consent=ConsentState(memory_promotion=True),
)
turn = session.add_turn("host", "Alex is my friend. Do not replace her with a generic assistant.")
candidate = MemoryGate().propose_from_turns(
    [turn],
    "relationship",
    "Alex is Josie's friend and must not be silently replaced by a generic assistant.",
)

with tempfile.TemporaryDirectory() as tmpdir:
    store = PersistentMemoryStore(Path(tmpdir))
    runtime = AlexRuntime(AlexContext.PERSONAL, persistent_memory=store)
    record = runtime.promote_memory_candidate(
        candidate,
        session,
        actor_id="host",
        scope=MemoryScope.PERSONAL,
        tags=["alex_continuity", "relationship"],
    )
    print("promoted:", record.memory_id)
    print("verify:", store.verify())
    print("retrieve:", runtime.retrieve_memory("generic assistant friend", scopes=[MemoryScope.PERSONAL]))
