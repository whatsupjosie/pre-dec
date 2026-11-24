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
# Telling someone what they feel reads as presumption (asking is fine; a question mark ends it).
_TELLING = re.compile(r"\b(you('re| are) (feeling|clearly|obviously)|you must (feel|be feeling)|"
                      r"you feel (so |really |very )?\w+)\b[^?]*?(?:[.!]|$)", re.I)
_DIRECTIVE = re.compile(r"(?:^|[.!?]\s+)(try|remember|make sure|take|go|stop|just|don'?t)\b|\byou should\b|\byou need to\b",
                        re.I)
_SENTENCE = re.compile(r"[.!?]+(?:\s|$)|\n+")


class PerceptionReader:
    """Predicts how something will read to an observer. Absolute, not personal."""

    def __init__(self, dials: ObservationDials) -> None:
        self.dials = dials

    def perceive_reply(self, reply: str, *, user_message: str = "") -> Dict[str, Any]:
        """How a reply from Alex (or any character) is likely to come across to the person reading it."""
        reply = reply if isinstance(reply, str) else ""
        words = re.findall(r"[A-Za-z']+", reply)
        user_words = re.findall(r"[A-Za-z']+", user_message or "")
        sentences = [s for s in _SENTENCE.split(reply) if s.strip()]
        reads: List[str] = []
        if _BRUSH_OFF.search(reply):
            reads.append("may_read_as_script_or_brush_off")
        if _TELLING.search(reply):
            reads.append("may_read_as_telling_them_how_they_feel")
        directives = len(_DIRECTIVE.findall(reply))
        if directives >= 2:
            reads.append("may_read_as_orders")
        ratio = (len(words) / max(1, len(user_words))) if user_words else None
        if ratio is not None and len(user_words) <= 12 and ratio >= 6:
            reads.append("may_read_as_overwhelming")
        if ratio is not None and len(user_words) >= 60 and len(words) <= 8:
            reads.append("may_read_as_curt")
        if "?" in reply:
            reads.append("invites_a_reply")
        return {"reader": "perception", "label": PERCEPTION_LABEL, "subject": "reply",
                "expected_reads": reads, "directive_count": directives,
                "length_ratio": None if ratio is None else round(ratio, 2), "sentences": len(sentences)}

    def perceive_display(self, values: Mapping[str, float]) -> Dict[str, Any]:
        """How a person's or a character's visible behaviour reads to an audience (absolute values).

        For the stage, avatars and voice. These thresholds are first proposals: the
        perception scorecard, scored against observers, is what will set them."""
        reads: List[str] = []
        caps = values.get("caps_ratio")
        exclaims = values.get("exclaim_rate")
        if (caps is not None and caps >= 0.3) or (exclaims is not None and exclaims >= 1.0):
            reads.append("reads_as_intense")
        wc = values.get("word_count")
        if wc is not None and wc <= 3:
            reads.append("reads_as_brief")
        typos = values.get("likely_typo_rate")
        if typos is not None and typos >= 0.15:
            reads.append("reads_as_rushed")
        rate = values.get("speech_rate")
        if rate is not None and rate >= 3.5:  # words per second
            reads.append("sounds_fast")
        expressivity = values.get("expressivity")
        if expressivity is not None and expressivity <= 0.15:
            reads.append("looks_flat")
        gaze = values.get("gaze_away_ratio")
        if gaze is not None and gaze >= 0.6:
            reads.append("looks_disengaged")
        return {"reader": "perception", "label": PERCEPTION_LABEL, "subject": "display", "expected_reads": reads}
