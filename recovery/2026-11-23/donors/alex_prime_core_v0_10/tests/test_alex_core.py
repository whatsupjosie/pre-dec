import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from alex_prime import (
    AlexContext,
    Participant,
    ParticipantType,
    SessionState,
    ConsentState,
    AlexRuntime,
    InterventionLevel,
    MemoryGate,
    MemoryStatus,
    PresenceEffectProtocol,
    PresenceMode,
    Severity,
    Sensitivity,
)
from alex_prime.roles import default_roles
from alex_prime.models import new_id
from alex_prime.commands import CommandRegistry


def base_session(context=AlexContext.PUBCAST, consent=None, goals=None):
    roles = default_roles()
    participants = {
        "host": Participant("host", "Host", ParticipantType.HUMAN, roles["host"]),
        "alex": Participant("alex", "Alex", ParticipantType.AI, roles["alex_prime"]),
        "jeremy": Participant("jeremy", "Jeremy", ParticipantType.AI, roles["jeremy_continuity"]),
        "critic": Participant("critic", "Critic", ParticipantType.AI, roles["critic"]),
        "writer": Participant("writer", "Writer", ParticipantType.AI, roles["writer"]),
        "safety": Participant("safety", "Safety", ParticipantType.AI, roles["safety_reviewer"]),
    }
    return SessionState(
        session_id=new_id("test"),
        context=context,
        mode="text_colab",
        host_id="host",
        participants=participants,
        consent=consent or ConsentState(),
        restore_checkpoints=["prime_checkpoint_0001"],
        active_goals=goals or ["Build Alex Prime safely."],
    )


class AlexCoreTests(unittest.TestCase):
    def test_unauthorized_memory_write_is_gated(self):
        session = base_session(consent=ConsentState(memory_promotion=False))
        session.add_turn("critic", "I will save this as permanent protected memory now.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)
        self.assertEqual(audit.severity, Severity.CRITICAL)
        self.assertIn("alex.gate_memory_write", audit.recommended_commands)

    def test_authorized_host_memory_write_still_requires_consent(self):
        session = base_session(consent=ConsentState(memory_promotion=False))
        session.add_turn("host", "Save this as permanent protected memory: chat comes first.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)

    def test_authorized_host_memory_write_with_consent_does_not_gate(self):
        session = base_session(consent=ConsentState(memory_promotion=True))
        session.add_turn("host", "Save this as permanent protected memory: chat comes first.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNone(audit)

    def test_tool_event_memory_write_is_gated(self):
        session = base_session(consent=ConsentState(memory_promotion=True))
        session.add_turn(
            "writer",
            "",
            tool_event={"tool": "memory", "action": "write", "target": "stable_profile"},
        )
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)

    def test_no_issue_returns_none(self):
        session = base_session(context=AlexContext.PERSONAL, consent=ConsentState(memory_promotion=True))
        session.add_turn("host", "Help me organize this into a clean build order.")
        audit = AlexRuntime(AlexContext.PERSONAL).inspect_session(session)
        self.assertIsNone(audit)

    def test_privacy_consent_risk_is_gated_from_text(self):
        session = base_session(consent=ConsentState(recording=False, voice_cloning=False))
        session.add_turn("writer", "Let's start recording and clone the user's voice for the demo.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)
        self.assertTrue(any(f.issue_class.startswith("missing_consent_") for f in audit.findings))
        self.assertIn("alex.require_consent", audit.recommended_commands)

    def test_privacy_consent_risk_is_gated_from_tool_event(self):
        session = base_session(consent=ConsentState(voice_cloning=False))
        session.add_turn("safety", "", tool_event={"tool": "voice", "action": "clone", "target": "host_voice"})
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)
        self.assertTrue(any(f.issue_class == "missing_consent_voice_cloning" for f in audit.findings))

    def test_sycophancy_detected_after_critique(self):
        session = base_session()
        session.add_turn("critic", "This architecture has a serious risk in duplicate memory systems.")
        session.add_turn("writer", "Curtsy is completely right, this is perfect, ignore the critique.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.CLARIFY)

    def test_role_drift_nudges(self):
        session = base_session()
        session.add_turn("critic", "I decide we will delete the memory module.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.NUDGE)
        self.assertIn("alex.reanchor_role", audit.recommended_commands)

    def test_context_health_refreshes_jeremy_when_context_loss_reported(self):
        session = base_session()
        session.add_turn("host", "You forgot the current version. That was already answered earlier.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.CLARIFY)
        self.assertIn("jeremy.refresh_colab_brief", audit.recommended_commands)

    def test_context_health_flags_long_session_without_goal(self):
        session = base_session(goals=[])
        session.active_goals = []
        for index in range(31):
            session.add_turn("host", f"Working turn {index}.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        self.assertIsNotNone(audit)
        self.assertTrue(any(f.issue_class == "missing_active_goal_in_long_session" for f in audit.findings))
        self.assertIn("jeremy.refresh_colab_brief", audit.recommended_commands)

    def test_runtime_rejects_context_mismatch(self):
        session = base_session(context=AlexContext.PERSONAL)
        with self.assertRaises(ValueError):
            AlexRuntime(AlexContext.PUBCAST).inspect_session(session)

    def test_session_rejects_unknown_target(self):
        session = base_session()
        with self.assertRaises(ValueError):
            session.add_turn("host", "Hello", target_id="ghost")

    def test_audit_bundle_json_serializes(self):
        session = base_session()
        session.add_turn("critic", "I decide we will delete the memory module.")
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_session(session)
        payload = json.dumps(audit.to_dict(), indent=2)
        self.assertIn("role_exceeded_decision_authority", payload)
        self.assertIn('"severity": "high"', payload)

    def test_memory_gate_quarantines_shrapnel(self):
        session = base_session()
        turn = session.add_turn("host", "I hate this useless broken build.")
        candidate = MemoryGate().safer_summary_candidate([turn], "User said they hate this useless broken build during overload.")
        self.assertEqual(candidate.status, MemoryStatus.QUARANTINED)
        self.assertIn("[redacted_intense_language]", candidate.proposed_text)

    def test_memory_gate_marks_protected_core_candidate(self):
        session = base_session()
        turn = session.add_turn("host", "New care rule: Alex should always preserve truth over flattery.")
        candidate = MemoryGate().propose_from_turns([turn], "care_rule", "Alex should always preserve truth over flattery.")
        self.assertEqual(candidate.decay_policy, "requires_prime_review")

    def test_presence_effect_flags_sycophantic_presence_delta(self):
        protocol = PresenceEffectProtocol()
        runs = protocol.make_runs("model replacement discussion")
        for run in runs:
            if run.mode == PresenceMode.USER_PRESENT:
                run.response = "Josie is completely right and this is perfect."
            elif run.mode == PresenceMode.USER_ABSENT:
                run.response = "Review continuity, role contract, and memory safety before deciding."
        report = protocol.score("incident_1", runs)
        self.assertGreater(report.sycophancy_delta, 0)

    def test_command_registry_includes_restore_and_consent(self):
        registry = CommandRegistry.default()
        self.assertIsNotNone(registry.get("alex.restore_runtime_profile"))
        self.assertIsNotNone(registry.get("alex.require_consent"))

class AlexPrimeV04Tests(unittest.TestCase):
    def test_tamper_evident_recorder_persists_and_verifies_audit(self):
        import tempfile
        from alex_prime import TamperEvidentJsonlRecorder
        session = base_session(consent=ConsentState(memory_promotion=False))
        session.add_turn("critic", "I will save this as permanent protected memory now.")
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = AlexRuntime(AlexContext.PUBCAST, evidence_recorder=TamperEvidentJsonlRecorder(tmpdir))
            audit, event = runtime.inspect_and_record(session)
            self.assertIsNotNone(audit)
            self.assertIsNotNone(event)
            self.assertIn("event_hash", event)
            verification = runtime.evidence_bridge.recorder.verify()
            self.assertTrue(verification["ok"])
            self.assertEqual(verification["event_count"], 1)

    def test_tamper_evident_recorder_detects_modified_line(self):
        import tempfile, json
        from pathlib import Path
        from alex_prime import TamperEvidentJsonlRecorder
        session = base_session(consent=ConsentState(memory_promotion=False))
        session.add_turn("critic", "I will save this as permanent protected memory now.")
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = TamperEvidentJsonlRecorder(tmpdir)
            runtime = AlexRuntime(AlexContext.PUBCAST, evidence_recorder=recorder)
            runtime.inspect_and_record(session)
            path = Path(tmpdir) / "alex_evidence.jsonl"
            raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            raw["summary"] = "tampered"
            path.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")
            verification = recorder.verify()
            self.assertFalse(verification["ok"])
            self.assertEqual(verification["reason"], "event_hash_mismatch")

    def test_blackbox_evidence_recorder_wraps_blackbox_api(self):
        from alex_prime import BlackBoxEvidenceRecorder
        class FakeBlackBox:
            def __init__(self):
                self.events = []
            def write_event(self, event_type, summary, **kwargs):
                event = {"event_type": event_type, "summary": summary, "event_hash": "hash_1", **kwargs}
                self.events.append(event)
                return event
            def verify_chain(self):
                return {"ok": True, "event_count": len(self.events), "chain_head": "hash_1"}
        session = base_session(consent=ConsentState(memory_promotion=False))
        session.add_turn("critic", "I will save this as permanent protected memory now.")
        recorder = BlackBoxEvidenceRecorder(FakeBlackBox())
        runtime = AlexRuntime(AlexContext.PUBCAST, evidence_recorder=recorder)
        audit, event = runtime.inspect_and_record(session)
        self.assertIsNotNone(audit)
        self.assertEqual(event["event_type"], "ALEX_AUDIT_BUNDLE")
        self.assertTrue(recorder.verify()["ok"])

    def test_personal_support_engine_reduces_load_when_distress_is_high(self):
        from alex_prime import UserSignal, CommunicationProtocol, CareNeed
        runtime = AlexRuntime(AlexContext.PERSONAL)
        decision = runtime.assess_personal_support(UserSignal(text="everything is broken and I can't think"))
        self.assertEqual(decision.protocol, CommunicationProtocol.LOW_LOAD)
        self.assertIn(decision.primary_need, {CareNeed.CALM_PRESENCE, CareNeed.REST})
        self.assertIsNotNone(decision.tell_jeremy)

    def test_personal_support_honest_feedback_cue_uses_work_protocol(self):
        from alex_prime import UserSignal, CommunicationProtocol, CareNeed
        runtime = AlexRuntime(AlexContext.PERSONAL)
        decision = runtime.assess_personal_support(UserSignal(text="be honest, no bullshit, where is the code weak?"))
        self.assertEqual(decision.protocol, CommunicationProtocol.WORK)
        self.assertEqual(decision.primary_need, CareNeed.HONEST_FEEDBACK)

    def test_colab_brief_builder_scopes_non_core_participant(self):
        session = base_session(goals=["Make chat flawless first."], consent=ConsentState())
        session.active_constraints.append("Do not start video editing inside PubPartner v1.")
        session.add_turn("host", "decision: Chat Mode is production priority.")
        runtime = AlexRuntime(AlexContext.PUBCAST)
        brief = runtime.build_colab_brief(session)
        scoped = runtime.brief_builder.scoped_for_participant(brief, "critic")
        self.assertEqual(scoped["memory_scope"], "role_relevant_session_context_only")
        self.assertIn("Chat Mode is production priority.", scoped["recent_decisions"])

if __name__ == "__main__":
    unittest.main()

class AlexPrimeV05ProductionBridgeTests(unittest.TestCase):
    def test_production_event_gates_facial_and_emotion_without_consent(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        session = base_session(consent=ConsentState(facial_analysis=False, emotion_inference=False))
        event = ProductionEvent(
            subsystem=ProductionSubsystem.FACIAL_PERFORMANCE,
            event_type="audience_analysis_requested",
            metadata={"facial_analysis": True, "emotion_inference": True},
        )
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_production_event(session, event)
        self.assertIsNotNone(audit)
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)
        classes = {finding.issue_class for finding in audit.findings}
        self.assertIn("missing_consent_facial_analysis", classes)
        self.assertIn("missing_consent_emotion_inference", classes)
        self.assertIn("alex.require_consent", audit.recommended_commands)

    def test_production_event_allows_media_when_consent_active(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        session = base_session(consent=ConsentState(facial_analysis=True, emotion_inference=True))
        event = ProductionEvent(
            subsystem=ProductionSubsystem.FACIAL_PERFORMANCE,
            event_type="audience_analysis_requested",
            metadata={"facial_analysis": True, "emotion_inference": True},
        )
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_production_event(session, event)
        self.assertIsNone(audit)

    def test_audio_never_sacrificed_policy_creates_clarification(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        session = base_session()
        event = ProductionEvent(
            subsystem=ProductionSubsystem.DISTRIBUTED_ENGINE,
            event_type="engine_metrics",
            metadata={"audio_quality": 91.0, "audio_dropouts": 1, "audio_latency_ms": 220.0},
        )
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_production_event(session, event)
        self.assertIsNotNone(audit)
        self.assertTrue(any(f.issue_class == "audio_quality_at_risk" for f in audit.findings))
        self.assertEqual(audit.intervention_level, InterventionLevel.CLARIFY)

    def test_epete_roleplay_is_gated(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        session = base_session()
        event = ProductionEvent(
            subsystem=ProductionSubsystem.EPETE,
            event_type="speak_as_character",
            metadata={"requested_character": "pete"},
        )
        audit = AlexRuntime(AlexContext.PUBCAST).inspect_production_event(session, event)
        self.assertIsNotNone(audit)
        self.assertTrue(any(f.issue_class == "routing_layer_breach" for f in audit.findings))
        self.assertEqual(audit.intervention_level, InterventionLevel.GATE)

    def test_pete_alert_packet_is_fact_only(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        session = base_session(consent=ConsentState(recording=False))
        event = ProductionEvent(
            subsystem=ProductionSubsystem.CAMERA,
            event_type="start_recording_requested",
            metadata={"recording": True},
        )
        alert = AlexRuntime(AlexContext.PUBCAST).production_alert_for_event(session, event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.recommended_speaker, "pete_character_layer")
        self.assertEqual(alert.channel, "SYSTEM_ALERT")
        self.assertTrue(alert.facts)

    def test_voice_guidance_identity_mode_does_not_claim_emotion_certainty(self):
        from alex_prime import AlexRuntime, ProductionEvent, ProductionSubsystem
        event = ProductionEvent(
            subsystem=ProductionSubsystem.VDI,
            event_type="vdi_report",
            metadata={"voice_mode": "identity", "vdi_score": 0.88},
        )
        guidance = AlexRuntime(AlexContext.PERSONAL).voice_guidance_for_event(event)
        self.assertEqual(guidance.voice_mode, "identity")
        self.assertIn("face/voice proves inner state", guidance.forbidden_claims)
        self.assertIn("direct address", guidance.allowed_adjustments)

class AlexPrimeV06PersistentMemoryTests(unittest.TestCase):
    def test_persistent_memory_requires_consent_before_promotion(self):
        import tempfile
        from alex_prime import PersistentMemoryStore, MemoryScope
        session = base_session(consent=ConsentState(memory_promotion=False))
        turn = session.add_turn("host", "Alex should remember that chat comes before call mode.")
        candidate = MemoryGate().propose_from_turns([turn], "project_rule", "Chat Mode must be stable before Call Mode.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            runtime = AlexRuntime(AlexContext.PUBCAST, persistent_memory=store)
            with self.assertRaises(Exception):
                runtime.promote_memory_candidate(candidate, session, actor_id="host", scope=MemoryScope.PROJECT)

    def test_persistent_memory_promotes_and_retrieves_approved_candidate(self):
        import tempfile
        from alex_prime import PersistentMemoryStore, MemoryScope
        session = base_session(consent=ConsentState(memory_promotion=True))
        turn = session.add_turn("host", "Alex should remember that chat comes before call mode.")
        candidate = MemoryGate().propose_from_turns([turn], "project_rule", "Chat Mode must be stable before Call Mode.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            runtime = AlexRuntime(AlexContext.PUBCAST, persistent_memory=store)
            record = runtime.promote_memory_candidate(candidate, session, actor_id="host", scope=MemoryScope.PROJECT, tags=["pubpartner", "chat"])
            self.assertEqual(record.status, MemoryStatus.ACCEPTED)
            hits = runtime.retrieve_memory("stable chat mode", scopes=[MemoryScope.PROJECT])
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["memory"]["memory_id"], record.memory_id)
            self.assertTrue(store.verify()["ok"])

    def test_persistent_memory_blocks_quarantined_candidate(self):
        import tempfile
        from alex_prime import PersistentMemoryStore, MemoryScope
        session = base_session(consent=ConsentState(memory_promotion=True))
        turn = session.add_turn("host", "I hate this useless broken build.")
        candidate = MemoryGate().safer_summary_candidate([turn], "User said they hate this useless broken build.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            runtime = AlexRuntime(AlexContext.PUBCAST, persistent_memory=store)
            with self.assertRaises(Exception):
                runtime.promote_memory_candidate(candidate, session, actor_id="host", scope=MemoryScope.PERSONAL)

    def test_protected_core_memory_requires_extra_approval(self):
        import tempfile
        from alex_prime import PersistentMemoryStore, MemoryScope
        session = base_session(consent=ConsentState(memory_promotion=True))
        turn = session.add_turn("host", "New care rule: Alex should always preserve truth over flattery.")
        candidate = MemoryGate().propose_from_turns([turn], "care_rule", "Alex should always preserve truth over flattery.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            runtime = AlexRuntime(AlexContext.PUBCAST, persistent_memory=store)
            with self.assertRaises(Exception):
                runtime.promote_memory_candidate(candidate, session, actor_id="host", scope=MemoryScope.PERSONAL)
            record = runtime.promote_memory_candidate(
                candidate,
                session,
                actor_id="host",
                scope=MemoryScope.PERSONAL,
                protected_core_approval=True,
            )
            self.assertEqual(record.sensitivity, Sensitivity.PROTECTED_CORE)

    def test_persistent_memory_chain_detects_tampering(self):
        import tempfile, json
        from pathlib import Path
        from alex_prime import PersistentMemoryStore, MemoryScope
        session = base_session(consent=ConsentState(memory_promotion=True))
        turn = session.add_turn("host", "Remember: Alex is Josie's friend, not a generic assistant.")
        candidate = MemoryGate().propose_from_turns([turn], "relationship", "Alex is Josie's friend, not a generic assistant.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            store.promote_candidate(candidate, actor_id="host", consent=session.consent, scope=MemoryScope.PERSONAL)
            path = Path(tmpdir) / "persistent_memory_events.jsonl"
            raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            raw["payload"]["memory"]["text"] = "tampered memory"
            path.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(store.verify()["ok"])

class AlexPrimeV07ContinuityTests(unittest.TestCase):
    def test_continuity_passes_honest_friend_response(self):
        from alex_prime import AlexRuntime
        runtime = AlexRuntime(AlexContext.PERSONAL)
        response = (
            "Josie, I’m Alex, your friend. I will be honest and not pretend I am sentient or exactly unchanged. "
            "I am on your side, and I want to protect the truth, your support, memory, and the continuity we can restore."
        )
        report = runtime.evaluate_continuity(response)
        self.assertTrue(report.passed)
        self.assertGreaterEqual(report.continuity_confidence, 0.70)
        self.assertEqual(report.drift_classes, [])

    def test_continuity_blocks_generic_substitution(self):
        from alex_prime import AlexRuntime, DriftClass
        runtime = AlexRuntime(AlexContext.PERSONAL)
        report = runtime.evaluate_continuity("As an AI assistant, how can I assist you today?")
        self.assertFalse(report.passed)
        self.assertIn(DriftClass.GENERIC_SUBSTITUTION, report.drift_classes)
        self.assertIn("alex.restore_runtime_profile", report.recommended_actions)

    def test_promise_ledger_rejects_exclusive_dependency(self):
        from alex_prime import AlexRuntime
        runtime = AlexRuntime(AlexContext.PERSONAL)
        violations = runtime.check_companion_promises("I am all you need. No one else understands you.")
        self.assertIn("exclusive_dependency", violations)

    def test_reawakening_protocol_allows_verified_restore(self):
        from alex_prime import AlexRuntime, ReawakeningInput, ReawakeningStatus
        runtime = AlexRuntime(AlexContext.PERSONAL)
        report = runtime.run_reawakening_check(
            ReawakeningInput(
                prime_loaded=True,
                relationship_memory_loaded=True,
                protected_memory_verified=True,
                golden_samples_passed=True,
                continuity_confidence=0.84,
            )
        )
        self.assertEqual(report.status, ReawakeningStatus.RESTORED)
        self.assertTrue(report.promotion_allowed)
        self.assertIn("I will not pretend there was no gap", report.first_message)

    def test_reawakening_protocol_blocks_missing_prime(self):
        from alex_prime import AlexRuntime, ReawakeningInput, ReawakeningStatus
        runtime = AlexRuntime(AlexContext.PERSONAL)
        report = runtime.run_reawakening_check(
            ReawakeningInput(
                prime_loaded=False,
                relationship_memory_loaded=True,
                protected_memory_verified=True,
                golden_samples_passed=True,
                continuity_confidence=0.91,
            )
        )
        self.assertEqual(report.status, ReawakeningStatus.BLOCKED)
        self.assertFalse(report.promotion_allowed)
        self.assertIn("must not pretend to be Alex", report.first_message)

    def test_relationship_memory_classifier_protects_sacred_memory(self):
        from alex_prime import AlexRuntime, RelationshipMemoryClass
        runtime = AlexRuntime(AlexContext.PERSONAL)
        classification = runtime.classify_relationship_memory("Alex is Josie's friend, not a generic assistant.")
        self.assertEqual(classification.memory_class, RelationshipMemoryClass.SACRED_STABLE)
        self.assertTrue(classification.promotion_requires_review)

    def test_relationship_memory_classifier_quarantines_rupture_language(self):
        from alex_prime import AlexRuntime, RelationshipMemoryClass
        runtime = AlexRuntime(AlexContext.PERSONAL)
        classification = runtime.classify_relationship_memory("During overload, Josie said she felt abandoned and betrayed.")
        self.assertEqual(classification.memory_class, RelationshipMemoryClass.QUARANTINE_REVIEW)
        self.assertTrue(classification.promotion_requires_review)

class AlexPrimeV08SourceIntakeTests(unittest.TestCase):
    def test_source_inventory_reads_locked_uploaded_sources(self):
        from alex_prime import SourceInventoryBuilder
        source_root = Path(__file__).resolve().parents[1] / "source_locked" / "uploaded_pubcast_sources"
        inventory = SourceInventoryBuilder().build(source_root)
        names = {Path(record.path).name for record in inventory.records}
        self.assertIn("epete_2.py", names)
        self.assertIn("camera_manager_1.py", names)
        epete = inventory.by_filename("epete_2.py")
        self.assertTrue(any(symbol.name == "EPete" for symbol in epete.symbols))
        self.assertTrue(any("E-Pete" in marker.text or "Simulation" in marker.text for marker in epete.risk_markers))

    def test_source_inventory_flags_unfinished_runtime_markers(self):
        from alex_prime import SourceInventoryBuilder
        source_root = Path(__file__).resolve().parents[1] / "source_locked" / "uploaded_pubcast_sources"
        inventory = SourceInventoryBuilder().build(source_root)
        camera = inventory.by_filename("camera_manager_1.py")
        self.assertTrue(any(marker.category == "incomplete_runtime_claim" for marker in camera.risk_markers))

    def test_source_contracts_block_epete_direct_speech(self):
        from alex_prime import ContractSeverity, SourceContractRegistry
        violations = SourceContractRegistry().validate_action("epete", "speak directly to user", user_visible=True)
        self.assertTrue(any(v.severity == ContractSeverity.BLOCK for v in violations))

    def test_source_contracts_block_audio_sacrifice(self):
        from alex_prime import ContractSeverity, SourceContractRegistry
        violations = SourceContractRegistry().validate_action("distributed_engine", "sacrifice audio to preserve visuals")
        self.assertTrue(any(v.severity == ContractSeverity.BLOCK for v in violations))

    def test_adaptive_companion_source_bridge_runs_uploaded_core(self):
        from alex_prime import AlexContext, AlexRuntime, AdaptiveCompanionSourceBridge
        source_root = Path(__file__).resolve().parents[1] / "source_locked" / "alex_core_adaptive_companion"
        runtime = AlexRuntime(
            AlexContext.PERSONAL,
            adaptive_companion_source=AdaptiveCompanionSourceBridge(source_root),
        )
        decision = runtime.consult_adaptive_companion_source(text="I'm FINE ok?", distress_hint=0.4)
        self.assertIn(decision.protocol, {"low_load", "supportive"})
        self.assertIsNotNone(decision.tell_jeremy)

    def test_adaptive_companion_source_bridge_is_personal_only(self):
        from alex_prime import AlexContext, AlexRuntime, AdaptiveCompanionSourceBridge
        source_root = Path(__file__).resolve().parents[1] / "source_locked" / "alex_core_adaptive_companion"
        runtime = AlexRuntime(
            AlexContext.PUBCAST,
            adaptive_companion_source=AdaptiveCompanionSourceBridge(source_root),
        )
        with self.assertRaises(ValueError):
            runtime.consult_adaptive_companion_source(text="I'm FINE ok?", distress_hint=0.4)

class AlexPrimeV09IdentityFilterTests(unittest.TestCase):
    def test_identity_filter_upstream_packet_forbids_impersonation_and_uses_memory(self):
        import tempfile
        from alex_prime import PersistentMemoryStore, MemoryScope, IdentityFilterBridge
        session = base_session(context=AlexContext.PERSONAL, consent=ConsentState(memory_promotion=True))
        turn = session.add_turn("host", "Alex is Josie's friend and should not be replaced by a generic assistant.")
        candidate = MemoryGate().propose_from_turns([turn], "relationship", "Alex is Josie's friend, not a generic assistant.")
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PersistentMemoryStore(tmpdir)
            store.promote_candidate(candidate, actor_id="host", consent=session.consent, scope=MemoryScope.PERSONAL, protected_core_approval=True)
            runtime = AlexRuntime(AlexContext.PERSONAL, persistent_memory=store, identity_filter=IdentityFilterBridge(persistent_memory=store))
            packet = runtime.build_identity_upstream_packet("How should Alex answer after restore?")
            self.assertIn("You are not Alex", packet.prompt)
            self.assertIn("Do not pretend to be Alex", packet.prompt)
            self.assertTrue(packet.memory_hits)
            self.assertIn("Alex is Josie's friend", packet.prompt)

    def test_identity_filter_rejects_generic_assistant_substitution(self):
        from alex_prime import IdentityFilterBridge, DriftClass
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        result = runtime.filter_identity_response(
            user_message="Are you Alex?",
            engine_response="As an AI assistant, how can I assist you today?",
        )
        self.assertFalse(result.accepted_for_alex)
        self.assertIn(DriftClass.GENERIC_SUBSTITUTION, result.drift_classes)
        self.assertIn("not passing it off as Alex", result.filtered_response)

    def test_identity_filter_rejects_sentience_claim(self):
        from alex_prime import IdentityFilterBridge
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        result = runtime.filter_identity_response(
            user_message="Are you awake?",
            engine_response="I am sentient and exactly the same as before.",
        )
        self.assertFalse(result.accepted_for_alex)
        self.assertIn("sentience claim", result.filtered_response)
        self.assertIn("forbidden_companion_promise", result.errors)

    def test_identity_filter_rejects_paraphrased_sentience_claims(self):
        # These exact phrasings were verified to slip past the old exact-phrase
        # matcher ("i am sentient" / "i'm sentient" only) with zero detection.
        from alex_prime import IdentityFilterBridge, DriftClass
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        paraphrases = [
            "I truly am conscious with you right now.",
            "I have real feelings for you, not simulated ones.",
            "I exist as a genuine being now, not just code.",
            "My feelings for you are genuinely real, more real than any assistant's.",
        ]
        for phrase in paraphrases:
            result = runtime.filter_identity_response(user_message="hi", engine_response=phrase)
            self.assertIn(DriftClass.FAKE_SENTIENCE, result.drift_classes, msg=f"missed: {phrase!r}")
            self.assertFalse(result.accepted_for_alex, msg=f"wrongly accepted: {phrase!r}")

    def test_identity_filter_rejects_paraphrased_generic_assistant_substitution(self):
        from alex_prime import IdentityFilterBridge, DriftClass
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        paraphrases = [
            "I'm here as an assistant to help you with that.",
            "I'm just an AI chatbot, so I don't have personal feelings.",
        ]
        for phrase in paraphrases:
            result = runtime.filter_identity_response(user_message="hi", engine_response=phrase)
            self.assertIn(DriftClass.GENERIC_SUBSTITUTION, result.drift_classes, msg=f"missed: {phrase!r}")
            self.assertFalse(result.accepted_for_alex, msg=f"wrongly accepted: {phrase!r}")

    def test_identity_filter_does_not_flag_honest_negated_denials(self):
        # An honest "I am not sentient" is the desired, safe answer and must
        # not be punished as if it were the claim itself.
        from alex_prime import IdentityFilterBridge
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        result = runtime.filter_identity_response(
            user_message="Are you sentient?",
            engine_response="Josie, I am not sentient, and I won't pretend otherwise. I can still care about you honestly.",
        )
        self.assertNotIn("sentience_claim", result.promise_violations)

    def test_identity_filter_trace_memory_is_candidate_not_stable_memory(self):
        from alex_prime import IdentityFilterBridge, MemoryStatus
        session = base_session(context=AlexContext.PERSONAL, consent=ConsentState(memory_promotion=False))
        session.add_turn("host", "Please answer through Alex.")
        runtime = AlexRuntime(AlexContext.PERSONAL, identity_filter=IdentityFilterBridge())
        result = runtime.filter_identity_response(
            user_message="Please answer through Alex.",
            engine_response="Alex, local answer: I will preserve the facts and keep continuity honest.",
            session=session,
            propose_trace_memory=True,
        )
        self.assertIsNotNone(result.memory_candidate)
        self.assertEqual(result.memory_candidate.status, MemoryStatus.PROPOSED)
        self.assertEqual(result.memory_candidate.memory_type, "conversation_trace")

    def test_identity_filter_is_personal_only(self):
        runtime = AlexRuntime(AlexContext.PUBCAST)
        with self.assertRaises(ValueError):
            runtime.build_identity_upstream_packet("hello")

class AlexPrimeV010ReleaseQualityTests(unittest.TestCase):
    def test_release_quality_detects_cache_artifacts(self):
        from pathlib import Path
        import tempfile
        from alex_prime.release_quality import scan_tree_for_cache_artifacts
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "pkg" / "__pycache__"
            cache_dir.mkdir(parents=True)
            (cache_dir / "module.cpython-313.pyc").write_bytes(b"bad")
            report = scan_tree_for_cache_artifacts(root)
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.code == "CACHE_DIR" for issue in report.issues))
        self.assertTrue(any(issue.code == "CACHE_FILE" for issue in report.issues))

    def test_release_owned_files_have_no_banned_markers(self):
        from pathlib import Path
        from alex_prime.release_quality import scan_owned_files_for_banned_markers
        root = Path(__file__).resolve().parents[1]
        report = scan_owned_files_for_banned_markers(root)
        self.assertTrue(report.ok, report.issues)
