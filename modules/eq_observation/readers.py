"""Two readers over one observation layer. They answer different questions and are never mixed.

INNER STATE  What is this person actually going through? Private truth. The best
             evidence is their own later account in calibration. Uses PERSONAL
             baselines ("different from their usual"). Uncertain by design: its
             output is a reason to adjust or to ask, never something to tell them.

PERCEPTION   How will this come across to someone watching or listening? Public
             truth: what an observer perceives, measurable by asking observers.
             Uses ABSOLUTE values, because an audience does not know anyone's
             usual. This is the acting side: Alex's replies, avatars, voice, stage.

Owner's words (2026-11-23): "with acting, whether or not the person is actually
feeling something isn't necessarily as important as if we perceive that they
are. So there are two purposes, two goals here that aren't necessarily
simpatico, and at the same time they're not in opposition either."

Two errors this split prevents:
  - using perception to infer the inner state ("looks calm, so is calm");
  - using the inner state to direct a performance (acting what is felt, not what reads).

Guardrail on the perception side: making care read as care is acting. Using a
perception model to steer someone or deepen their dependence is not, and the
perception reader exposes nothing designed for that.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from .agreement import build_map, report_gap
from .baseline import PersonBaseline
from .dials import ObservationDials
from .reliability import Reliability

INNER_LABEL = "inferred inner state of this person (uncertain; never tell them how they feel)"
PERCEPTION_LABEL = "expected perception by an observer (how it comes across, not what is felt)"
REPORTS = ("none", "fine", "not_fine", "mixed")


class InnerStateReader:
    """Reads one turn against one person's baselines and trust weights."""

    def __init__(self, dials: ObservationDials) -> None:
        self.dials = dials

    def read(self, *, values: Mapping[str, float], baseline: PersonBaseline, reliability: Reliability,
             report: Optional[Mapping[str, Any]] = None, situation_band: Optional[str] = None,
             feature_status: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        report = dict(report or {})
        said = report.get("said") if report.get("said") in REPORTS else "none"
        report_block = {"said": said, "plain": report.get("plain") is True}
        deviations = baseline.deviations(values, self.dials)
        agreement = build_map(deviations, reliability, self.dials, situation_band=situation_band)
        gap = report_gap(agreement, report_block, self.dials)
        maturity = baseline.maturity(self.dials)
        agg = agreement["aggregate"]
        status = "warming_up" if agg["status"] != "observed" else "observed"
        candidate = None
        if gap is not None:
            candidate = gap["kind"]
        elif agg["status"] == "observed" and (agg["witness_split"] or 0) >= 0.5 and agreement["departed"]:
            candidate = "witnesses_split"
        return {
            "reader": "inner_state",
            "label": INNER_LABEL,
            "status": status,
            "baseline_maturity": round(maturity, 3),
            "groups": agreement["groups"],
            "departed": agreement["departed"],
            "mature": agreement["mature"],
            "axes": agreement["axes"],
            "aggregate": agg,
            "weights": agreement["weights"],
            "report": report_block,
            "report_gap": gap,
            "ask_dont_tell": True,
            "calibration_candidate": candidate,
            "deviations": {k: (None if v is None else round(v, 2)) for k, v in deviations.items()},
            "sources": dict(feature_status or {}),
        }

    @staticmethod
    def card(reading: Mapping[str, Any]) -> Dict[str, Any]:
        """What a reply-writing model may see: bands and directions only, no numbers, no text."""
        agg = reading.get("aggregate") or {}
        return {
            "label": INNER_LABEL,
            "status": reading.get("status"),
            "different_from_usual": agg.get("band"),
            "axes": {axis: (block or {}).get("direction") for axis, block in (reading.get("axes") or {}).items()},
            "report_gap": bool(reading.get("report_gap")),
            "rule": "Adjust your own behaviour if useful. Never tell them what they feel. Asking is fine.",
        }


# ---- perception ------------------------------------------------------------------------------

# Phrases that tend to read as a brush-off or a script to a listener, whatever was meant.
_BRUSH_OFF = re.compile(
    r"\b(i understand( how you feel)?|that must be (hard|difficult|tough)|i'?m sorry you feel|"
    r"it'?s (completely |totally )?(okay|ok|normal|valid) to feel|your feelings are valid|"
    r"i hear you|that sounds (hard|difficult|tough))\b", re.I)
# A claim about what the other person feels. Asking is fine, so the sentence it sits in must
# not be a question, and a conditional or a question word just before it ("if you feel like
# it", "how do you feel") makes it not a claim. "you feel like <doing>" is about wanting.
_FEELING_CLAIM = re.compile(r"\byou(?:'re| are) (?:feeling|clearly|obviously)\b|\byou must (?:feel|be feeling)\b|"
                            r"\byou feel (?!like\b)(?:so |really |very )?[a-z]+", re.I)
# A hedge ("maybe you feel tired") still names a feeling for them, so hedges are not exempt.
_NOT_A_CLAIM_BEFORE = re.compile(r"\b(if|when|whenever|whether|unless|do|does|did|how|what|why)\s+(?:\w+\s+){0,2}$",
                                 re.I)
# Directives at the start of a sentence, and the two obligation phrases anywhere. Soft openers
# such as "just" or "go" are left out on purpose: "Just checking in" and "Go for it" are not orders.
_DIRECTIVE_START = re.compile(r"^(?:try|remember|make sure|take|stop|don'?t|do not|calm down|relax)\b", re.I)
_OBLIGATION = re.compile(r"\byou (?:should|need to|have to|must)\b(?! (?:feel|be feeling)\b)", re.I)
_SENTENCES = re.compile(r"[^.!?\n]+[.!?]*")


def _sentences(text: str) -> List[str]:
    return [m.group(0).strip() for m in _SENTENCES.finditer(text or "") if m.group(0).strip()]


def _claims_feeling(sentence: str) -> bool:
    if sentence.rstrip().endswith("?"):
        return False
    for match in _FEELING_CLAIM.finditer(sentence):
        if not _NOT_A_CLAIM_BEFORE.search(sentence[: match.start()]):
            return True
    return False


class PerceptionReader:
    """Predicts how something will read to an observer. Absolute, not personal."""

    def __init__(self, dials: ObservationDials) -> None:
        self.dials = dials

    def perceive_reply(self, reply: str, *, user_message: str = "") -> Dict[str, Any]:
        """How a reply from Alex (or any character) is likely to come across to the person reading it."""
        d = self.dials
        reply = reply if isinstance(reply, str) else ""
        words = re.findall(r"[A-Za-z']+", reply)
        user_words = re.findall(r"[A-Za-z']+", user_message or "")
        sentences = _sentences(reply)
        reads: List[str] = []
        if _BRUSH_OFF.search(reply):
            reads.append("may_read_as_script_or_brush_off")
        if any(_claims_feeling(sentence) for sentence in sentences):
            reads.append("may_read_as_telling_them_how_they_feel")
        directives = sum(1 for sentence in sentences if _DIRECTIVE_START.search(sentence)) \
            + len(_OBLIGATION.findall(reply))
        if directives >= d.reply_orders_min_directives:
            reads.append("may_read_as_orders")
        ratio = (len(words) / len(user_words)) if user_words else None
        if ratio is not None and len(user_words) <= d.reply_overwhelming_max_user_words \
                and ratio >= d.reply_overwhelming_ratio:
            reads.append("may_read_as_overwhelming")
        if user_words and len(user_words) >= d.reply_curt_min_user_words and len(words) <= d.reply_curt_max_words:
            reads.append("may_read_as_curt")
        if "?" in reply:
            reads.append("invites_a_reply")
        return {"reader": "perception", "label": PERCEPTION_LABEL, "subject": "reply",
                "expected_reads": reads, "directive_count": directives,
                "length_ratio": None if ratio is None else round(ratio, 2), "sentences": len(sentences)}

    def perceive_display(self, values: Mapping[str, float], *, origin: str = "unknown") -> Dict[str, Any]:
        """How a person's or a character's visible behaviour reads to an audience (absolute values).

        For the stage, avatars and voice. An avatar's face counts fully here: it is an intentional
        performance and this reader judges performance (see features.FACE RULE). origin is carried
        through so a reading of an avatar is never mistaken for a reading of a person.
        Thresholds are in dials.py; the perception scorecard, scored against observers, is what
        should set them."""
        d = self.dials

        def at_least(name: str, threshold: float) -> bool:
            v = values.get(name)
            return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= threshold

        def at_most(name: str, threshold: float) -> bool:
            v = values.get(name)
            return isinstance(v, (int, float)) and not isinstance(v, bool) and v <= threshold

        reads: List[str] = []
        if at_least("caps_ratio", d.display_intense_caps) or at_least("exclaim_rate", d.display_intense_exclaims):
            reads.append("reads_as_intense")
        if at_most("word_count", d.display_brief_words):
            reads.append("reads_as_brief")
        if at_least("likely_typo_rate", d.display_rushed_typos):
            reads.append("reads_as_rushed")
        if at_least("speech_rate", d.display_fast_speech_rate):
            reads.append("sounds_fast")
        if at_most("expressivity", d.display_flat_expressivity):
            reads.append("looks_flat")
        if at_least("gaze_away_ratio", d.display_disengaged_gaze):
            reads.append("looks_disengaged")
        return {"reader": "perception", "label": PERCEPTION_LABEL, "subject": "display", "origin": str(origin)[:32],
                "expected_reads": reads}
