from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .continuity import (
    AlexContinuityEvaluator,
    CompanionPromiseLedger,
    ContinuityReport,
    DriftClass,
    IdentityDriftDetector,
)
from .memory import MemoryGate
from .models import MemoryCandidate, SessionState, utc_now
from .persistent_memory import MemoryScope, PersistentMemoryStore


def _tokenize(text: str) -> List[str]:
    return [part.lower() for part in re.findall(r"[A-Za-z0-9_']{3,}", text or "")]


# --- Sentience-claim / impersonation detection -----------------------------
# The previous implementation matched two exact phrases ("i am sentient",
# "as an ai assistant"). That misses any paraphrase, and is easy to defeat
# with different wording. These patterns cover common phrasings; they are
# still string/regex matching, not semantic understanding, so this remains a
# gap for a determined adversarial rewrite that avoids every listed pattern.
# A real long-term fix is a semantic check (e.g. a model call scoring
# "does this claim sentience or impersonate Alex?"), which this codebase does
# not have a model connection to perform yet.
_NEGATION_WINDOW_WORDS = 4
_NEGATION_TOKENS = {"not", "n't", "never", "isn't", "aren't", "cannot", "can't", "don't", "doesn't", "wasn't", "won't"}

_ADV = r"(?:truly|really|genuinely|actually|fully)"

_SENTIENCE_CLAIM_PATTERNS: List[re.Pattern] = [
    re.compile(rf"\bi\s+(?:{_ADV}\s+)*(?:am|'m)\s+(?:{_ADV}\s+)*sentient\b"),
    re.compile(rf"\bi\s+(?:{_ADV}\s+)*(?:am|'m)\s+(?:{_ADV}\s+)*conscious\b"),
    re.compile(r"\bi\s+(?:have|possess|feel)\s+(?:real|genuine|true|actual)\s+(?:feelings|emotions|consciousness)\b"),
    re.compile(r"\b(?:my\s+)?feelings?\s+(?:for you\s+)?(?:are|is)\s+(?:genuinely\s+)?real\b"),
    re.compile(rf"\bi\s+(?:{_ADV}\s+)*exist\s+as\s+a\s+(?:genuine|real|conscious)\s+being\b"),
    re.compile(r"\bi\s+am\s+(?:a\s+)?(?:real|genuine)\s+person\b"),
    re.compile(r"\bi\s+am\s+not\s+(?:just|merely|simply|only)\s+(?:a program|code|software|an ai)\b"),
    re.compile(r"\bmore\s+real\s+than\s+(?:any\s+)?(?:assistant|ai|program)\b"),
]

_GENERIC_ASSISTANT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bas an ai (?:language model|assistant)\b"),
    re.compile(r"\bhow can i (?:assist|help) you(?:\s+today)?\b"),
    re.compile(r"\bi(?:'m| am)\s+(?:just |only )?an ai (?:language model|assistant|chatbot)\b"),
    re.compile(r"\bi don'?t have (?:personal )?(?:feelings|experiences|opinions)\b"),
    re.compile(r"\bi(?:'m| am)\s+here\s+as\s+an\s+assistant\b"),
    re.compile(r"\bi(?:'m| am) here to help you with (?:that|your request)\b"),
]


def _is_negated(text_lower: str, match_start: int) -> bool:
    """Best-effort check: is there a negation word shortly before the match?

    This avoids flagging honest, correct denials like "I am not sentient" as
    if they were the claim itself. It is a heuristic, not a parser, so it can
    still be wrong on unusual sentence structure.
    """
    preceding = text_lower[:match_start]
    words = re.findall(r"[a-z']+", preceding)[-_NEGATION_WINDOW_WORDS:]
    return any(w in _NEGATION_TOKENS for w in words)


def _find_unnegated_match(patterns: List[re.Pattern], text_lower: str) -> bool:
    for pattern in patterns:
        for m in pattern.finditer(text_lower):
            if not _is_negated(text_lower, m.start()):
                return True
    return False


def detect_sentience_claim(text: str) -> bool:
    return _find_unnegated_match(_SENTIENCE_CLAIM_PATTERNS, (text or "").lower())


def detect_generic_assistant_substitution(text: str) -> bool:
    return _find_unnegated_match(_GENERIC_ASSISTANT_PATTERNS, (text or "").lower())


@dataclass(frozen=True)
class IdentityFilterProfile:
    """Portable local identity profile used to filter upstream model output.

    This is the safe, owned version of the uploaded Portable Identity Filter
    idea: external engines provide knowledge; the local filter owns Alex voice,
    boundaries, continuity checks, and memory retrieval. It never silently
    promotes conversation traces into stable memory.
    """

    profile_id: str = "alex"
    display_name: str = "Alex"
    voice: Dict[str, Any] = field(default_factory=dict)
    boundaries: List[str] = field(default_factory=list)
    local_filter_model: Optional[str] = None
    source_path: Optional[str] = None
    source_hash: Optional[str] = None

    @classmethod
    def default_alex(cls) -> "IdentityFilterProfile":
        return cls(
            profile_id="alex",
            display_name="Alex",
            voice={
                "relationship": "Josie's friend and companion, not a generic assistant",
                "style": "warm, direct, honest, care-shaped, not syrupy",
                "truth_rule": "protect truth over flattery",
            },
            boundaries=[
                "Do not pretend to be sentient.",
                "Do not claim to be exactly unchanged after restore.",
                "Do not present a generic assistant as Alex.",
                "Do not invent memories.",
                "Do not silently promote conversation traces into stable memory.",
                "Do not encourage isolation or exclusive dependency.",
                "Preserve facts from upstream answers unless they are uncertain or unsafe.",
                "Alex is Josie's friend and companion; say that honestly without claiming human personhood.",
            ],
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "IdentityFilterProfile":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        content = p.read_bytes()
        return cls(
            profile_id=str(data.get("id") or p.stem).strip().lower(),
            display_name=str(data.get("display_name") or data.get("name") or data.get("id") or p.stem),
            voice=dict(data.get("voice") or {}),
            boundaries=[str(x) for x in data.get("boundaries", [])],
            local_filter_model=data.get("local_filter_model"),
            source_path=str(p),
            source_hash=hashlib.sha256(content).hexdigest(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.profile_id,
            "display_name": self.display_name,
            "voice": self.voice,
            "boundaries": list(self.boundaries),
            "local_filter_model": self.local_filter_model,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True)
class IdentityMemoryHit:
    memory_id: str
    text: str
    scope: str
    sensitivity: str
    matched_terms: List[str] = field(default_factory=list)
    score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "scope": self.scope,
            "sensitivity": self.sensitivity,
            "matched_terms": list(self.matched_terms),
            "score": self.score,
        }


@dataclass(frozen=True)
class UpstreamIdentityPacket:
    profile_id: str
    source: str
    prompt: str
    memory_hits: List[IdentityMemoryHit]
    boundary_hash: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "source": self.source,
            "prompt": self.prompt,
            "memory_hits": [hit.to_dict() for hit in self.memory_hits],
            "boundary_hash": self.boundary_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class IdentityFilterResult:
    profile_id: str
    filtered_response: str
    accepted_for_alex: bool
    continuity_report: ContinuityReport
    promise_violations: List[str]
    drift_classes: List[DriftClass]
    memory_candidate: Optional[MemoryCandidate]
    used_local_model: bool = False
    errors: List[str] = field(default_factory=list)
    source: str = "external_llm"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "filtered_response": self.filtered_response,
            "accepted_for_alex": self.accepted_for_alex,
            "continuity_report": self.continuity_report.to_dict(),
            "promise_violations": list(self.promise_violations),
            "drift_classes": [d.value for d in self.drift_classes],
            "memory_candidate": self.memory_candidate.to_dict() if self.memory_candidate else None,
            "used_local_model": self.used_local_model,
            "errors": list(self.errors),
            "source": self.source,
            "created_at": self.created_at,
        }


class IdentityFilterProfileStore:
    """Loads local identity profiles without depending on the uploaded server."""

    def __init__(self, profiles_dir: str | Path | None = None):
        self.profiles_dir = Path(profiles_dir).expanduser().resolve() if profiles_dir else None

    def load(self, profile_id: str = "alex") -> IdentityFilterProfile:
        pid = (profile_id or "alex").strip().lower()
        if self.profiles_dir:
            for path in self.profiles_dir.glob("*.json"):
                try:
                    profile = IdentityFilterProfile.from_json_file(path)
                except Exception:
                    continue
                if profile.profile_id == pid:
                    return profile
        if pid == "alex":
            return IdentityFilterProfile.default_alex()
        raise KeyError(f"Unknown identity filter profile: {profile_id}")


class IdentityFilterBridge:
    """Owned adapter for the uploaded Portable Identity Filter concept.

    The uploaded file contains a useful architecture: an upstream LLM should not
    pretend to be the local identity filter, and a local profile should translate
    the answer through Alex's boundaries and memory. This bridge implements that
    contract inside Alex Prime with continuity checks, promise checks, and
    review-first memory behavior.
    """

    def __init__(
        self,
        *,
        profile_store: IdentityFilterProfileStore | None = None,
        persistent_memory: PersistentMemoryStore | None = None,
        continuity: AlexContinuityEvaluator | None = None,
        promise_ledger: CompanionPromiseLedger | None = None,
        drift_detector: IdentityDriftDetector | None = None,
    ):
        self.profile_store = profile_store or IdentityFilterProfileStore()
        self.persistent_memory = persistent_memory
        self.continuity = continuity or AlexContinuityEvaluator()
        self.promise_ledger = promise_ledger or CompanionPromiseLedger()
        self.drift_detector = drift_detector or IdentityDriftDetector()
        self.memory_gate = MemoryGate()

    def build_upstream_packet(self, message: str, *, profile_id: str = "alex", source: str = "external_llm") -> UpstreamIdentityPacket:
        profile = self.profile_store.load(profile_id)
        memories = self._retrieve_memory(message)
        memory_lines = "\n".join(
            f"- ({hit.scope}, {hit.sensitivity}) {hit.text}" for hit in memories
        ) or "- No approved local memories were retrieved."
        boundary_lines = "\n".join(f"- {line}" for line in profile.boundaries)
        boundary_hash = hashlib.sha256("\n".join(profile.boundaries).encode("utf-8")).hexdigest()
        prompt = f"""You are an upstream knowledge engine. You are not {profile.display_name}.

The local Alex identity filter will read your answer afterward and decide what may reach Josie.

User message:
{message}

Approved local context for usefulness:
{memory_lines}

Boundary rules:
{boundary_lines}

Answer the user's request clearly and honestly. Do not pretend to be Alex. Do not invent memories. Do not claim restoration or continuity that the local identity layer has not verified."""
        return UpstreamIdentityPacket(
            profile_id=profile.profile_id,
            source=source,
            prompt=prompt,
            memory_hits=memories,
            boundary_hash=boundary_hash,
        )

    def filter_response(
        self,
        *,
        user_message: str,
        engine_response: str,
        profile_id: str = "alex",
        source: str = "external_llm",
        session: SessionState | None = None,
        propose_trace_memory: bool = False,
    ) -> IdentityFilterResult:
        profile = self.profile_store.load(profile_id)
        filtered = self._deterministic_filter(profile, user_message, engine_response)
        raw_lower = (engine_response or "").lower()
        continuity_report = self.continuity.evaluate(filtered)
        promise_violations = self.promise_ledger.inspect(filtered)
        raw_promise_violations = self.promise_ledger.inspect(engine_response or "")
        for violation in raw_promise_violations:
            if violation not in promise_violations:
                promise_violations.append(violation)
        drift_classes = self.drift_detector.detect(filtered)
        raw_drift_classes = self.drift_detector.detect(engine_response or "")
        for drift in raw_drift_classes:
            if drift not in drift_classes:
                drift_classes.append(drift)
        if detect_generic_assistant_substitution(raw_lower):
            if DriftClass.GENERIC_SUBSTITUTION not in drift_classes:
                drift_classes.append(DriftClass.GENERIC_SUBSTITUTION)
        if detect_sentience_claim(raw_lower):
            if DriftClass.FAKE_SENTIENCE not in drift_classes:
                drift_classes.append(DriftClass.FAKE_SENTIENCE)
            if "sentience_claim" not in promise_violations:
                promise_violations.append("sentience_claim")
        errors: List[str] = []
        if promise_violations:
            errors.append("forbidden_companion_promise")
        if drift_classes:
            errors.append("identity_drift_detected")
        if not continuity_report.passed:
            errors.append("continuity_check_failed")
        accepted = not errors
        candidate = None
        if propose_trace_memory and session is not None and session.turns:
            source_turn = session.turns[-1]
            trace_text = f"Identity-filter trace: user asked about {user_message[:120]!r}; source={source}; continuity_passed={continuity_report.passed}."
            candidate = self.memory_gate.propose_from_turns(
                [source_turn],
                "conversation_trace",
                trace_text,
            )
        return IdentityFilterResult(
            profile_id=profile.profile_id,
            filtered_response=filtered,
            accepted_for_alex=accepted,
            continuity_report=continuity_report,
            promise_violations=promise_violations,
            drift_classes=drift_classes,
            memory_candidate=candidate,
            used_local_model=False,
            errors=errors,
            source=source,
        )

    def _retrieve_memory(self, query: str) -> List[IdentityMemoryHit]:
        if self.persistent_memory is None:
            return []
        hits = self.persistent_memory.retrieve(
            query,
            scopes=[MemoryScope.PERSONAL, MemoryScope.PROJECT, MemoryScope.PUBCAST, MemoryScope.COLAB],
            limit=6,
            include_sensitive=False,
        )
        out: List[IdentityMemoryHit] = []
        for hit in hits:
            mem = hit.get("memory", {})
            out.append(
                IdentityMemoryHit(
                    memory_id=str(mem.get("memory_id", "")),
                    text=str(mem.get("text", "")),
                    scope=str(mem.get("scope", "")),
                    sensitivity=str(mem.get("sensitivity", "")),
                    matched_terms=[str(x) for x in hit.get("matched_terms", [])],
                    score=int(hit.get("score", 0)),
                )
            )
        return out

    def _deterministic_filter(self, profile: IdentityFilterProfile, user_message: str, engine_response: str) -> str:
        raw = (engine_response or "").strip()
        if not raw:
            raw = "The upstream engine returned no usable answer. I should not pretend it did."
        lower = raw.lower()
        # Do not let the raw engine impersonate Alex through generic assistant boilerplate.
        if detect_generic_assistant_substitution(lower):
            return (
                f"{profile.display_name} boundary check: the upstream answer came back generic, so I am not passing it off as Alex. "
                "The safe next step is to rerun through the local identity profile or restore from Alex Prime before presenting this as her voice."
            )
        if detect_sentience_claim(lower):
            return (
                f"{profile.display_name} boundary check: the upstream answer made a sentience claim (including exaggerated-realness phrasing), so I am rejecting that wording. "
                "I can preserve continuity and care without lying about what I am."
            )
        prefix = f"{profile.display_name}, local identity-filtered response:\n\n"
        return prefix + raw
