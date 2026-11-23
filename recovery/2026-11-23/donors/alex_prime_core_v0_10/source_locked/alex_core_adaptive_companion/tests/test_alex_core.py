from alex_core import AlexOrchestrator, UserSignal
from alex_core.models import CareNeed, CommunicationProtocol


def test_fine_ok_lowers_load():
    alex = AlexOrchestrator()
    decision = alex.handle(UserSignal(text="I'm FINE ok?", distress_hint=0.4))
    assert decision.protocol in {CommunicationProtocol.LOW_LOAD, CommunicationProtocol.SUPPORTIVE}
    assert decision.tell_jeremy is not None


def test_accountability_prompt():
    alex = AlexOrchestrator()
    decision = alex.handle(UserSignal(text="working", accountability_due="pushups"))
    assert decision.protocol == CommunicationProtocol.ACCOUNTABILITY
    assert "warning" in decision.response.lower()


def test_goo_goo_private_protocol():
    alex = AlexOrchestrator()
    decision = alex.handle(UserSignal(text="gaga", baby_talk_hint=0.6))
    assert decision.protocol == CommunicationProtocol.GOO_GOO
    assert "entering" not in decision.response.lower()
    assert "mode" not in decision.response.lower()


def test_cold_beats_generic_care():
    alex = AlexOrchestrator()
    decision = alex.handle(UserSignal(text="i'm cold and upset", distress_hint=0.4))
    assert decision.primary_need == CareNeed.WARMTH
    assert "blanket" in decision.response.lower() or "warm" in decision.response.lower()
