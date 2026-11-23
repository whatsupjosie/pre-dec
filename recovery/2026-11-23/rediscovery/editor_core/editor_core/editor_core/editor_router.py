"""
editor_router.py — routes an on-demand editor command to the right tool.

Deliberately copies the exact scoring pattern already used in
`switchblade_router.py` (keyword-set counting -> highest score wins) so the
two routers are consistent and a future intent-classifier upgrade can
replace both the same way at the same time.

This router is for EXPLICIT commands the writer triggers ("synonym for
X", "does this rhyme with X", "check continuity") — it is separate from
EditorEngine, which always runs spelling+grammar automatically and needs
no routing at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

THESAURUS_TERMS = {"synonym", "synonyms", "thesaurus", "another word", "rephrase", "reword"}
RHYME_TERMS = {"rhyme", "rhymes", "rhyming", "meter", "scan", "syllable"}
CONTINUITY_TERMS = {"continuity", "contradiction", "plot hole", "consistent", "consistency", "earlier said", "already established"}
SPELLING_GRAMMAR_TERMS = {"spelling", "spelled", "grammar", "typo", "syntax", "proofread"}


@dataclass(frozen=True)
class EditorRouteDecision:
    tool: str          # "thesaurus" | "rhyme" | "continuity" | "grammar" | "unclear"
    reason: str
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {"tool": self.tool, "reason": self.reason, "confidence": self.confidence}


def _score(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def route_editor_command(message: str) -> EditorRouteDecision:
    scores = {
        "thesaurus": _score(message, THESAURUS_TERMS),
        "rhyme": _score(message, RHYME_TERMS),
        "continuity": _score(message, CONTINUITY_TERMS),
        "grammar": _score(message, SPELLING_GRAMMAR_TERMS),
    }
    best_tool = max(scores, key=lambda k: scores[k])
    if scores[best_tool] == 0:
        return EditorRouteDecision("unclear", "no_matching_terms", 0.0)
    confidence = min(0.95, 0.5 + scores[best_tool] * 0.15)
    return EditorRouteDecision(best_tool, f"{best_tool}_terms_matched", confidence)
