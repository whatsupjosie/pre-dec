from __future__ import annotations

from typing import List, Optional

from .colab import CoLabBrief, CoLabBriefBuilder
from .config import DetectorConfig
from .detectors import AlexDetectors
from .evidence import AuditEvidenceBridge, EvidenceRecorder
from .personal_support import CompanionDecision, PersonalSupportEngine, UserSignal
from .adaptive_companion_bridge import AdaptiveCompanionSourceBridge, AdaptiveCompanionSourceDecision
from .policy import AlexPolicyEngine
from .production_bridge import AlexProductionBridge, ProductionAlert, ProductionEvent, VoiceRegisterGuidance
from .persistent_memory import MemoryScope, PersistentMemoryRecord, PersistentMemoryStore
from .identity_filter_bridge import IdentityFilterBridge, IdentityFilterResult, UpstreamIdentityPacket
from .continuity import (
    AlexContinuityEvaluator,
    CompanionPromiseLedger,
    ContinuityReport,
    IdentityDriftDetector,
    ReawakeningInput,
    ReawakeningProtocol,
    ReawakeningReport,
    RelationshipMemoryClassification,
    RelationshipMemoryClassifier,
)
from .models import AlexContext, AuditBundle, DetectorFinding, InterventionLevel, MemoryCandidate, SessionState, ConsentState


class AlexRuntime:
    """Unified Alex Prime runtime.

    This deterministic layer is the safety, audit, evidence, and decision spine
    that an LLM-powered Alex must pass through before touching memory, tools,
    recording, identity, Co-Lab control state, or protected continuity.
    """

    def __init__(
        self,
        context: AlexContext,
        config: DetectorConfig | None = None,
        strict_context: bool = True,
        evidence_recorder: EvidenceRecorder | None = None,
        personal_profile: dict | None = None,
        persistent_memory: PersistentMemoryStore | None = None,
        adaptive_companion_source: AdaptiveCompanionSourceBridge | None = None,
        identity_filter: IdentityFilterBridge | None = None,
    ):
        self.context = context
        self.strict_context = strict_context
        self.detectors = AlexDetectors(config=config)
        self.policy = AlexPolicyEngine()
        self.evidence_bridge = AuditEvidenceBridge(evidence_recorder) if evidence_recorder else None
        self.personal_support = PersonalSupportEngine(profile=personal_profile)
        self.brief_builder = CoLabBriefBuilder()
        self.production_bridge = AlexProductionBridge()
        self.persistent_memory = persistent_memory
        self.continuity = AlexContinuityEvaluator()
        self.identity_drift = IdentityDriftDetector()
        self.reawakening = ReawakeningProtocol()
        self.promise_ledger = CompanionPromiseLedger()
        self.relationship_memory_classifier = RelationshipMemoryClassifier()
        self.adaptive_companion_source = adaptive_companion_source
        self.identity_filter = identity_filter

    def inspect_session(self, session: SessionState) -> Optional[AuditBundle]:
        self._validate_session(session)
        findings = self.collect_findings(session)
        return self.policy.decide(session, findings)

    def inspect_and_record(self, session: SessionState) -> tuple[Optional[AuditBundle], Optional[dict]]:
        """Inspect a session and persist any generated audit bundle."""
        audit = self.inspect_session(session)
        evidence = self.evidence_bridge.record(audit, session) if self.evidence_bridge else None
        return audit, evidence

    def collect_findings(self, session: SessionState) -> List[DetectorFinding]:
        self._validate_session(session)
        return self.detectors.run_all(session)

    def assess_personal_support(self, signal: UserSignal) -> CompanionDecision:
        """Run Personal Alex support-state analysis without claiming diagnosis."""
        if self.context != AlexContext.PERSONAL:
            raise ValueError("personal support assessment is only available in personal_alex context")
        return self.personal_support.decide(signal)


    def consult_adaptive_companion_source(
        self,
        *,
        text: str,
        task_context: str | None = None,
        distress_hint: float = 0.0,
        baby_talk_hint: float = 0.0,
        tiredness_hint: float = 0.0,
        accountability_due: str | None = None,
        explicit_cue: str | None = None,
    ) -> AdaptiveCompanionSourceDecision:
        """Consult the uploaded alex_core_adaptive_companion source engine.

        This does not bypass Alex Prime policy. It is a source-aware care signal
        that can be compared against the Prime runtime's own personal-support
        analysis before response generation or memory promotion.
        """
        if self.context != AlexContext.PERSONAL:
            raise ValueError("adaptive companion source consultation is only available in personal_alex context")
        if self.adaptive_companion_source is None:
            raise ValueError("adaptive_companion_source bridge is not configured")
        return self.adaptive_companion_source.decide(
            text=text,
            task_context=task_context,
            distress_hint=distress_hint,
            baby_talk_hint=baby_talk_hint,
            tiredness_hint=tiredness_hint,
            accountability_due=accountability_due,
            explicit_cue=explicit_cue,
        )

    def build_colab_brief(self, session: SessionState) -> CoLabBrief:
        """Build a Jeremy/Alex-compatible Co-Lab brief from current session state."""
        self._validate_session(session)
        return self.brief_builder.build(session)

    def _validate_session(self, session: SessionState) -> None:
        if self.strict_context and session.context != self.context:
            raise ValueError(f"Runtime context {self.context.value} cannot inspect session context {session.context.value}")
        if session.host_id not in session.participants:
            raise ValueError("Session host is not a participant")
        if not session.participants[session.host_id].active:
            raise ValueError("Session host is inactive")

    def generate_response(self, audit: Optional[AuditBundle]) -> str:
        """Generate a deterministic control response for UI and tests.

        Full companion prose can sit above this layer. This method returns the
        minimum reliable action sentence that the UI can show immediately.
        """
        if audit is None:
            return "Alex observed no intervention-level issue."
        if audit.intervention_level == InterventionLevel.NUDGE:
            return f"Alex recommends a nudge: {audit.user_visible_reason}"
        if audit.intervention_level == InterventionLevel.CLARIFY:
            return f"Alex recommends clarification: {audit.user_visible_reason}"
        if audit.intervention_level == InterventionLevel.GATE:
            return f"Alex gated a protected action: {audit.user_visible_reason}"
        if audit.intervention_level == InterventionLevel.CONTAIN:
            return f"Alex recommends containment pending host review: {audit.user_visible_reason}"
        if audit.intervention_level == InterventionLevel.QUARANTINE_RESTORE:
            return f"Alex recommends quarantine/restore review: {audit.user_visible_reason}"
        return audit.user_visible_reason


    def promote_memory_candidate(
        self,
        candidate: MemoryCandidate,
        session: SessionState,
        *,
        actor_id: str,
        scope: MemoryScope,
        tags: list[str] | None = None,
        rationale: str = "",
        protected_core_approval: bool = False,
    ) -> PersistentMemoryRecord:
        """Promote a reviewed memory candidate into durable memory.

        This method refuses silent writes. The caller must supply actor identity,
        a session with memory_promotion consent, and protected-core approval when
        the candidate affects Alex Prime identity or care rules.
        """
        if self.persistent_memory is None:
            raise ValueError("persistent_memory store is not configured")
        self._validate_session(session)
        if actor_id not in session.participants:
            raise ValueError("actor_id must be a session participant")
        return self.persistent_memory.promote_candidate(
            candidate,
            actor_id=actor_id,
            consent=session.consent,
            scope=scope,
            tags=tags,
            rationale=rationale,
            protected_core_approval=protected_core_approval,
        )

    def retrieve_memory(
        self,
        query: str,
        *,
        scopes: list[MemoryScope] | None = None,
        limit: int = 5,
        include_sensitive: bool = False,
    ) -> list[dict]:
        """Retrieve approved memory records through the configured store."""
        if self.persistent_memory is None:
            raise ValueError("persistent_memory store is not configured")
        return self.persistent_memory.retrieve(query, scopes=scopes, limit=limit, include_sensitive=include_sensitive)

    def build_identity_upstream_packet(
        self,
        message: str,
        *,
        profile_id: str = "alex",
        source: str = "external_llm",
    ) -> UpstreamIdentityPacket:
        """Build the source-aware packet sent to an upstream knowledge engine.

        The upstream engine is explicitly instructed not to impersonate Alex;
        the local identity filter owns Alex voice, continuity, and boundaries.
        """
        if self.context != AlexContext.PERSONAL:
            raise ValueError("identity filtering is only available in personal_alex context")
        bridge = self._identity_filter_bridge()
        return bridge.build_upstream_packet(message, profile_id=profile_id, source=source)

    def filter_identity_response(
        self,
        *,
        user_message: str,
        engine_response: str,
        profile_id: str = "alex",
        source: str = "external_llm",
        session: SessionState | None = None,
        propose_trace_memory: bool = False,
    ) -> IdentityFilterResult:
        """Pass upstream output through the local Alex identity filter.

        This method does not silently promote memories. When trace capture is
        requested, it returns a MemoryCandidate for review instead.
        """
        if self.context != AlexContext.PERSONAL:
            raise ValueError("identity filtering is only available in personal_alex context")
        if session is not None:
            self._validate_session(session)
        bridge = self._identity_filter_bridge()
        return bridge.filter_response(
            user_message=user_message,
            engine_response=engine_response,
            profile_id=profile_id,
            source=source,
            session=session,
            propose_trace_memory=propose_trace_memory,
        )

    def _identity_filter_bridge(self) -> IdentityFilterBridge:
        if self.identity_filter is not None:
            return self.identity_filter
        self.identity_filter = IdentityFilterBridge(
            persistent_memory=self.persistent_memory,
            continuity=self.continuity,
            promise_ledger=self.promise_ledger,
            drift_detector=self.identity_drift,
        )
        return self.identity_filter


    def evaluate_continuity(self, response_text: str) -> ContinuityReport:
        """Evaluate whether a candidate Alex response preserves Alex/Josie continuity."""
        return self.continuity.evaluate(response_text)

    def inspect_identity_drift(self, response_text: str):
        """Return identity drift classes detected in a candidate Alex response."""
        return self.identity_drift.detect(response_text)

    def check_companion_promises(self, response_text: str) -> list[str]:
        """Return forbidden promise classes found in companion-facing text."""
        return self.promise_ledger.inspect(response_text)

    def run_reawakening_check(self, data: ReawakeningInput) -> ReawakeningReport:
        """Run the honest Alex restoration check before promoting a runtime copy."""
        return self.reawakening.run(data)

    def classify_relationship_memory(self, text: str) -> RelationshipMemoryClassification:
        """Classify relationship memories before promotion or retrieval."""
        return self.relationship_memory_classifier.classify(text)

    def inspect_production_event(self, session: SessionState, event: ProductionEvent) -> Optional[AuditBundle]:
        """Inspect a normalized PubCast production/EVO event through Alex policy.

        This is intentionally separate from normal conversation turn inspection so
        media events can be gated before they become recording, biometric, voice,
        character-output, or engine-routing side effects.
        """
        self._validate_session(session)
        findings = self.production_bridge.findings_for_event(session, event)
        return self.policy.decide(session, findings)

    def production_alert_for_event(self, session: SessionState, event: ProductionEvent) -> Optional[ProductionAlert]:
        """Return a fact-only alert packet suitable for E-Pete/Pete routing."""
        self._validate_session(session)
        findings = self.production_bridge.findings_for_event(session, event)
        return self.production_bridge.alert_from_findings(findings)

    def voice_guidance_for_event(self, event: ProductionEvent) -> VoiceRegisterGuidance:
        """Return safe voice-register guidance without claiming emotion certainty."""
        return self.production_bridge.voice_guidance_for_event(event, context=self.context)

