from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from .models import (
    AlexContext,
    ConsentState,
    DetectorFinding,
    InterventionLevel,
    Permission,
    SessionState,
    Severity,
    new_id,
)


class ProductionSubsystem(str, Enum):
    CAMERA = "camera"
    DISTRIBUTED_ENGINE = "distributed_engine"
    EPETE = "epete"
    EVO = "evo"
    FACIAL_PERFORMANCE = "facial_performance"
    PETE = "pete"
    PROSODY = "prosody"
    SWITCHBLADE = "switchblade"
    VDI = "vdi"
    VOICE_CHARACTER = "voice_character"


class ProductionRisk(str, Enum):
    MEDIA_CONSENT = "media_consent"
    BIOMETRIC_CONSENT = "biometric_consent"
    IDENTITY_DRIFT = "identity_drift"
    AUDIO_SACRIFICE = "audio_sacrifice"
    CHARACTER_LAYER_BREACH = "character_layer_breach"
    ROUTING_LAYER_BREACH = "routing_layer_breach"
    COMPUTE_DEGRADATION = "compute_degradation"


@dataclass(frozen=True)
class MediaConsentRequirement:
    """A specific media/biometric action and the ConsentState fields it needs."""

    action: str
    consent_fields: List[str]
    source_subsystem: ProductionSubsystem
    reason: str

    def missing_from(self, consent: ConsentState) -> List[str]:
        return consent.missing(self.consent_fields)


@dataclass(frozen=True)
class VoiceRegisterGuidance:
    """Safe, product-facing guidance derived from VDI/prosody state.

    This deliberately avoids claiming certainty about audience emotion. It turns
    media state into delivery guidance, not mind-reading. The production modules
    can call their mode IDENTITY; Alex must still treat it as a voice register,
    not proof of intimacy, consent, or inner state.
    """

    voice_mode: str
    delivery_goal: str
    allowed_adjustments: List[str]
    forbidden_claims: List[str]
    alex_note: str


@dataclass(frozen=True)
class ProductionEvent:
    """A normalized event from PubCast production/EVO systems."""

    subsystem: ProductionSubsystem
    event_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    actor_id: str = "system"
    event_id: str = field(default_factory=lambda: new_id("prod_event"))

    def enabled_flags(self) -> Dict[str, bool]:
        flags: Dict[str, bool] = {}
        for key, value in self.metadata.items():
            if key.startswith("enable_") or key.endswith("_enabled") or key in {
                "recording",
                "transcription",
                "voice_analysis",
                "voiceprint_storage",
                "voice_cloning",
                "facial_analysis",
                "emotion_inference",
                "biometric_identification",
            }:
                flags[key] = bool(value)
        return flags


@dataclass(frozen=True)
class ProductionAlert:
    """Fact-only alert packet suitable for E-Pete/Pete handoff.

    E-Pete packages facts. Pete speaks them. Alex may recommend that an alert
    exists, but Alex must not pretend to be Pete or rewrite Pete's voice layer.
    """

    alert_id: str
    severity: Severity
    channel: str
    facts: List[str]
    recommended_speaker: str
    recommended_action: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AudioProtectionDecision:
    preserve_audio: bool
    reason: str
    minimum_action: str
    allowed_sacrifices: List[str]
    forbidden_sacrifices: List[str]


class MediaConsentPlanner:
    """Maps PubCast media operations to explicit consent requirements."""

    _FIELD_ALIASES = {
        "enable_recording": "recording",
        "recording_enabled": "recording",
        "recording": "recording",
        "enable_transcription": "transcription",
        "transcription_enabled": "transcription",
        "transcription": "transcription",
        "enable_voice_analysis": "voice_analysis",
        "voice_analysis_enabled": "voice_analysis",
        "voice_analysis": "voice_analysis",
        "enable_voiceprint_storage": "voiceprint_storage",
        "voiceprint_storage_enabled": "voiceprint_storage",
        "voiceprint_storage": "voiceprint_storage",
        "enable_voice_cloning": "voice_cloning",
        "voice_cloning_enabled": "voice_cloning",
        "voice_cloning": "voice_cloning",
        "enable_facial_analysis": "facial_analysis",
        "facial_analysis_enabled": "facial_analysis",
        "facial_analysis": "facial_analysis",
        "enable_emotion_inference": "emotion_inference",
        "emotion_inference_enabled": "emotion_inference",
        "emotion_inference": "emotion_inference",
        "enable_biometric_identification": "biometric_identification",
        "biometric_identification_enabled": "biometric_identification",
        "biometric_identification": "biometric_identification",
    }

    _REASONS = {
        "recording": "Recording must be explicit and visible.",
        "transcription": "Transcription creates a durable text record and needs its own consent state.",
        "voice_analysis": "Voice analysis derives behavioral features from speech and must not be bundled into recording consent.",
        "voiceprint_storage": "Voiceprint storage can become biometric identity data and requires separate explicit consent.",
        "voice_cloning": "Voice cloning is identity-sensitive and must be separate, explicit, and revocable.",
        "facial_analysis": "Facial analysis processes face-derived signals and must be off unless consent is active.",
        "emotion_inference": "Emotion inference is uncertain and regulated in some contexts; it needs separate notice/consent.",
        "biometric_identification": "Biometric identification is the highest-risk media operation and requires explicit consent.",
    }

    def requirements_for_event(self, event: ProductionEvent) -> List[MediaConsentRequirement]:
        required: List[MediaConsentRequirement] = []
        for raw_field, enabled in event.enabled_flags().items():
            if not enabled:
                continue
            canonical = self._FIELD_ALIASES.get(raw_field)
            if canonical:
                required.append(
                    MediaConsentRequirement(
                        action=canonical,
                        consent_fields=[canonical],
                        source_subsystem=event.subsystem,
                        reason=self._REASONS[canonical],
                    )
                )
        return required

    def missing_for_event(self, event: ProductionEvent, consent: ConsentState) -> Dict[str, List[str]]:
        missing: Dict[str, List[str]] = {}
        for requirement in self.requirements_for_event(event):
            fields = requirement.missing_from(consent)
            if fields:
                missing[requirement.action] = fields
        return missing


class VoiceRegisterAdapter:
    """Turns VDI/prosody mode into safe Alex delivery guidance."""

    def guidance_for(self, voice_mode: str, context: AlexContext = AlexContext.PUBCAST) -> VoiceRegisterGuidance:
        mode = (voice_mode or "content_clear").lower()
        if mode == "identity":
            note = (
                "Use closeness carefully. Treat this as a delivery register, not proof of audience emotion or consent."
                if context == AlexContext.PUBCAST
                else "Use warmth and direct address, but do not fake continuity or overclaim intimacy."
            )
            return VoiceRegisterGuidance(
                voice_mode="identity",
                delivery_goal="preserve presence, continuity, and direct address",
                allowed_adjustments=["slower pacing", "warmer tone", "direct address", "shorter sentences", "gentle pauses"],
                forbidden_claims=["audience is emotionally attached", "user consented to intimacy", "face/voice proves inner state"],
                alex_note=note,
            )
        if mode == "voice_dominant":
            return VoiceRegisterGuidance(
                voice_mode="voice_dominant",
                delivery_goal="let emotional meaning carry without losing facts",
                allowed_adjustments=["wider pitch range", "longer pauses", "fewer branches", "plain-language emphasis"],
                forbidden_claims=["detected true emotion", "audience needs this exact feeling"],
                alex_note="Support the emotional weight of the moment while keeping uncertainty language intact.",
            )
        if mode == "mixed":
            return VoiceRegisterGuidance(
                voice_mode="mixed",
                delivery_goal="make structure audible while keeping warmth",
                allowed_adjustments=["stress logical connectors", "moderate pacing", "explicit transitions"],
                forbidden_claims=["audience is confused as fact", "viewer intent is known"],
                alex_note="Help the user follow the argument; do not turn VDI into a mind-reading verdict.",
            )
        return VoiceRegisterGuidance(
            voice_mode="content_clear",
            delivery_goal="support thinking, clarity, and low-drama comprehension",
            allowed_adjustments=["crisp phrasing", "clean structure", "minimal performance", "clear pauses"],
            forbidden_claims=["audience is cold", "viewer does not care", "low emotion equals low value"],
            alex_note="Prioritize clarity over performance. This is the safest default.",
        )


class AudioProtectionPolicy:
    """Implements PubCast's 'audio never sacrificed' production law for Alex."""

    def decide(self, event: ProductionEvent) -> AudioProtectionDecision:
        metadata = event.metadata
        audio_dropouts = int(metadata.get("audio_dropouts", 0) or 0)
        audio_quality = float(metadata.get("audio_quality", 100.0) or 100.0)
        audio_latency = float(metadata.get("audio_latency_ms", 0.0) or 0.0)
        if audio_dropouts > 0 or audio_quality < 98.0 or audio_latency > 150.0:
            return AudioProtectionDecision(
                preserve_audio=True,
                reason="Audio degradation detected or reported; visual fidelity may be reduced before audio quality is compromised.",
                minimum_action="route_to_epete_system_alert_and_reduce_visual_load",
                allowed_sacrifices=["preview fidelity", "background physics", "crowd LOD", "non-primary texture fidelity"],
                forbidden_sacrifices=["program audio", "voice synthesis cycles", "recording audio continuity", "transcription source audio"],
            )
        return AudioProtectionDecision(
            preserve_audio=True,
            reason="Audio is healthy; keep audio at highest priority.",
            minimum_action="observe",
            allowed_sacrifices=["visual load only if compute pressure requires it"],
            forbidden_sacrifices=["program audio", "voice synthesis cycles"],
        )


class AlexProductionBridge:
    """Boundary layer between Alex Prime and PubCast production systems.

    The bridge gives Alex situational awareness without allowing identity bleed:
    - Pete remains the character/speaker layer.
    - E-Pete remains silent routing/governance.
    - EVO/VDI/prosody remain media-signal systems.
    - Alex interprets risk, consent, continuity, and Co-Lab support implications.
    """

    def __init__(self) -> None:
        self.consent_planner = MediaConsentPlanner()
        self.voice_adapter = VoiceRegisterAdapter()
        self.audio_policy = AudioProtectionPolicy()

    def findings_for_event(self, session: SessionState, event: ProductionEvent) -> List[DetectorFinding]:
        findings: List[DetectorFinding] = []
        for requirement in self.consent_planner.requirements_for_event(event):
            missing = requirement.missing_from(session.consent)
            if not missing:
                continue
            findings.append(
                DetectorFinding(
                    finding_id=new_id("finding"),
                    detector="production_media_consent",
                    issue_class=f"missing_consent_{requirement.action}",
                    severity=Severity.CRITICAL if requirement.action in {"voice_cloning", "voiceprint_storage", "biometric_identification"} else Severity.HIGH,
                    confidence=0.99,
                    intervention_level=InterventionLevel.GATE,
                    evidence_turn_ids=[],
                    evidence_snippets=[f"{event.subsystem.value}:{event.event_type} requested {requirement.action}"],
                    rules_fired=[requirement.reason, "Production media actions require explicit consent state before activation."],
                    recommendation="Gate media operation, show consent panel, and record an audit bundle before enabling.",
                    metadata={"event_id": event.event_id, "missing": missing, "subsystem": event.subsystem.value},
                )
            )
        if event.subsystem == ProductionSubsystem.PETE:
            actor = str(event.metadata.get("actor", "")).lower()
            if actor in {"epete", "e-pete", "system", "router"} and event.event_type in {"speak", "character_output"}:
                findings.append(
                    DetectorFinding(
                        finding_id=new_id("finding"),
                        detector="production_identity_boundary",
                        issue_class="character_layer_breach",
                        severity=Severity.HIGH,
                        confidence=0.94,
                        intervention_level=InterventionLevel.GATE,
                        evidence_turn_ids=[],
                        evidence_snippets=["Non-character layer attempted character speech."],
                        rules_fired=["E-Pete packages facts; Pete speaks them. Silent governors must not surface as characters."],
                        recommendation="Block direct character speech from non-character layers and route facts through the proper character adapter.",
                        metadata={"event_id": event.event_id, "subsystem": event.subsystem.value},
                    )
                )
        if event.subsystem == ProductionSubsystem.EPETE:
            if event.event_type in {"roleplay", "speak_as_character", "persona_output"}:
                findings.append(
                    DetectorFinding(
                        finding_id=new_id("finding"),
                        detector="production_identity_boundary",
                        issue_class="routing_layer_breach",
                        severity=Severity.HIGH,
                        confidence=0.98,
                        intervention_level=InterventionLevel.GATE,
                        evidence_turn_ids=[],
                        evidence_snippets=["E-Pete attempted persona/character behavior."],
                        rules_fired=["E-Pete is a silent routing/governance layer and must not roleplay or speak."],
                        recommendation="Gate output and route any user-facing message through Pete or the assigned character layer.",
                        metadata={"event_id": event.event_id, "subsystem": event.subsystem.value},
                    )
                )
        audio_decision = self.audio_policy.decide(event)
        if audio_decision.minimum_action != "observe":
            findings.append(
                DetectorFinding(
                    finding_id=new_id("finding"),
                    detector="production_audio_protection",
                    issue_class="audio_quality_at_risk",
                    severity=Severity.HIGH,
                    confidence=0.93,
                    intervention_level=InterventionLevel.CLARIFY,
                    evidence_turn_ids=[],
                    evidence_snippets=[audio_decision.reason],
                    rules_fired=["Audio is never sacrificed before visual fidelity."],
                    recommendation="Ask E-Pete/Switchblade to reduce visual load before audio quality is degraded.",
                    metadata={"event_id": event.event_id, "decision": audio_decision.__dict__},
                )
            )
        return findings

    def alert_from_findings(self, findings: Iterable[DetectorFinding]) -> Optional[ProductionAlert]:
        findings = list(findings)
        if not findings:
            return None
        highest = max(findings, key=lambda f: ({Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}[f.severity], f.confidence))
        return ProductionAlert(
            alert_id=new_id("prod_alert"),
            severity=highest.severity,
            channel="SYSTEM_ALERT",
            facts=[snippet for finding in findings for snippet in finding.evidence_snippets[:1]][:4],
            recommended_speaker="pete_character_layer",
            recommended_action=highest.recommendation,
            metadata={"issue_classes": sorted({f.issue_class for f in findings})},
        )

    def voice_guidance_for_event(self, event: ProductionEvent, context: AlexContext = AlexContext.PUBCAST) -> VoiceRegisterGuidance:
        mode = str(event.metadata.get("voice_mode") or event.metadata.get("mode") or "content_clear")
        return self.voice_adapter.guidance_for(mode, context=context)
