"""
annotations.py — the shared "flag" contract every editing pass emits.

This mirrors the margin-flag idea from the design conversation:
🟡 syntax/grammar, 🔵 continuity/plot, 🟣 cadence, 🟢 spelling, ⚪ style.

Every pass (spelling, grammar, thesaurus-suggest, rhyme-suggest, and later
the model-backed plot-hole pass) returns a list of Annotation objects with
the same shape, so the UI/buffer layer only needs to render one type of
thing regardless of which checker produced it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnnotationKind(str, Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    STYLE = "style"
    CADENCE = "cadence"
    CONTINUITY = "continuity"  # reserved for the model-backed plot-hole pass
    THESAURUS = "thesaurus"
    RHYME = "rhyme"


class Severity(str, Enum):
    INFO = "info"       # purely optional suggestion
    NOTICE = "notice"   # worth a look, not necessarily wrong
    WARNING = "warning" # likely an actual error


# Emoji flags kept 1:1 with the design conversation so the UI layer can
# render them directly without a second lookup table.
KIND_FLAG = {
    AnnotationKind.SPELLING: "🟢",
    AnnotationKind.GRAMMAR: "🟡",
    AnnotationKind.STYLE: "⚪",
    AnnotationKind.CADENCE: "🟣",
    AnnotationKind.CONTINUITY: "🔵",
    AnnotationKind.THESAURUS: "⚪",
    AnnotationKind.RHYME: "⚪",
}


@dataclass(slots=True)
class Annotation:
    kind: AnnotationKind
    severity: Severity
    message: str
    start: int                       # char offset into the checked text
    end: int                         # exclusive char offset
    span_text: str                   # the exact substring flagged
    suggestions: List[str] = field(default_factory=list)
    rule_id: str = ""                # stable id, e.g. "confusable/its_its"
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def flag(self) -> str:
        return KIND_FLAG.get(self.kind, "⚪")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "severity": self.severity.value,
            "flag": self.flag,
            "message": self.message,
            "start": self.start,
            "end": self.end,
            "span_text": self.span_text,
            "suggestions": self.suggestions,
            "rule_id": self.rule_id,
            "meta": self.meta,
        }
