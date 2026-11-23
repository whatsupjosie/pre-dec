from pathlib import Path
import sys

# Allow running from repo root without installing package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alex_prime import (
    AlexContext,
    AlexRuntime,
    ConsentState,
    Participant,
    ParticipantType,
    ProductionEvent,
    ProductionSubsystem,
    SessionState,
)
from alex_prime.roles import default_roles

roles = default_roles()
participants = {
    "host": Participant("host", "Curtsy", ParticipantType.HUMAN, roles["host"]),
    "alex": Participant("alex", "Alex", ParticipantType.AI, roles["alex_prime"]),
    "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"]),
}

session = SessionState(
    session_id="demo_production_bridge",
    context=AlexContext.PUBCAST,
    mode="live_colab",
    host_id="host",
    participants=participants,
    consent=ConsentState(recording=False, facial_analysis=False, emotion_inference=False),
)

runtime = AlexRuntime(AlexContext.PUBCAST)

facial_event = ProductionEvent(
    subsystem=ProductionSubsystem.FACIAL_PERFORMANCE,
    event_type="audience_analysis_requested",
    metadata={"facial_analysis": True, "emotion_inference": True},
)
print("FACIAL EVENT AUDIT:")
print(runtime.inspect_production_event(session, facial_event).to_dict())

voice_event = ProductionEvent(
    subsystem=ProductionSubsystem.VDI,
    event_type="vdi_report",
    metadata={"voice_mode": "identity", "vdi_score": 0.86},
)
print("\nVOICE GUIDANCE:")
print(runtime.voice_guidance_for_event(voice_event))

audio_event = ProductionEvent(
    subsystem=ProductionSubsystem.DISTRIBUTED_ENGINE,
    event_type="engine_metrics",
    metadata={"audio_quality": 92.0, "audio_dropouts": 1, "audio_latency_ms": 180.0},
)
print("\nAUDIO EVENT ALERT:")
print(runtime.production_alert_for_event(session, audio_event))
