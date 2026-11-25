from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .serialization import to_jsonable


class AdaptiveCompanionBridgeError(Exception):
    """Raised when the source-locked Alex adaptive companion cannot be used."""


@dataclass(frozen=True)
class AdaptiveCompanionSourceDecision:
    protocol: str
    primary_need: str
    response: str
    confidence: float
    tell_jeremy: Optional[Dict[str, Any]]
    memory_event: Optional[Dict[str, Any]]
    internal_notes: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return to_jsonable(self)


class AdaptiveCompanionSourceBridge:
    """Thin compatibility bridge for the uploaded alex_core_adaptive_companion source.

    This keeps the source companion engine as a consulted source layer. Alex Prime
    remains the governing runtime; the uploaded companion code can contribute care
    decisions, Jeremy packets, and private support mode hints.
    """

    def __init__(self, source_root: Path | str, profile: Dict[str, Any] | None = None):
        self.source_root = Path(source_root).expanduser().resolve()
        if not self.source_root.exists():
            raise AdaptiveCompanionBridgeError(f"source root does not exist: {self.source_root}")
        self.profile = profile or {}
        self._orchestrator = None
        self._user_signal_cls = None

    def load(self) -> None:
        package_parent = self.source_root
        if (package_parent / "alex_core").is_dir():
            import_root = package_parent
        elif (package_parent / "alex_core_adaptive_companion" / "alex_core").is_dir():
            import_root = package_parent / "alex_core_adaptive_companion"
        else:
            raise AdaptiveCompanionBridgeError("could not find alex_core package under source root")

        sys.path.insert(0, str(import_root))
        try:
            alex_core = importlib.import_module("alex_core")
            self._user_signal_cls = getattr(alex_core, "UserSignal")
            orchestrator_cls = getattr(alex_core, "AlexOrchestrator")
            self._orchestrator = orchestrator_cls(profile=self.profile)
        finally:
            try:
                sys.path.remove(str(import_root))
            except ValueError:
                pass

    def decide(
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
        if self._orchestrator is None or self._user_signal_cls is None:
            self.load()
        signal = self._user_signal_cls(
            text=text,
            task_context=task_context,
            distress_hint=distress_hint,
            baby_talk_hint=baby_talk_hint,
            tiredness_hint=tiredness_hint,
            accountability_due=accountability_due,
            explicit_cue=explicit_cue,
        )
        decision = self._orchestrator.handle(signal)
        return AdaptiveCompanionSourceDecision(
            protocol=decision.protocol.value,
            primary_need=decision.primary_need.value,
            response=decision.response,
            confidence=float(decision.confidence),
            tell_jeremy=decision.tell_jeremy,
            memory_event=decision.memory_event,
            internal_notes=list(decision.internal_notes),
        )
