"""The agreement map: which independent witnesses differ from this person's usual, and how.

There is no single emotion label here. Each witness group gets one vote, weighted
by how much it has earned this person's trust; the map says where the groups
agree, where they split, and where nothing is known yet. "None of these things
are especially reliable alone. That's why we look at them all in aggregate."
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .dials import ObservationDials
from .features import AXES, FEATURE_MAP
from .reliability import Reliability

BEHAVIOUR_GROUPS = ("message_shape", "emphasis", "motor", "voice", "face")
SITUATION_BAND_SCORE = {"quiet": 0.0, "noticed": 0.5, "strong": 1.0}


def _band(score: float, dials: ObservationDials) -> str:
    return "strong" if score >= dials.band_strong else "noticed" if score >= dials.band_noticed else "quiet"


def build_map(deviations: Mapping[str, Optional[float]], reliability: Reliability, dials: ObservationDials, *,
              situation_band: Optional[str] = None) -> Dict[str, Any]:
    """deviations: feature -> z (None while warming up). situation_band: from the situation reader, if wired."""
    groups: Dict[str, str] = {}
    strength: Dict[str, float] = {}
    axis_votes: Dict[str, Dict[str, float]] = {axis: {} for axis in AXES}

    for group in BEHAVIOUR_GROUPS:
        zs = [(name, z) for name, z in deviations.items() if name in FEATURE_MAP and FEATURE_MAP[name][0] == group]
        if not zs:
            continue
        mature = [(name, z) for name, z in zs if z is not None]
        if not mature:
            groups[group] = "warming_up"
            continue
        peak = max(abs(z) for _, z in mature)
        groups[group] = "departed" if peak >= dials.deviation_threshold else "steady"
        strength[group] = min(1.0, peak / 3.0) if peak >= dials.deviation_threshold else 0.0
        for axis in AXES:
            on_axis = [FEATURE_MAP[name][2] * z for name, z in mature if FEATURE_MAP[name][1] == axis]
            if on_axis:
                axis_votes[axis][group] = max(on_axis, key=abs)  # one vote per group: its strongest

    if situation_band in SITUATION_BAND_SCORE:
        groups["situation"] = "departed" if situation_band != "quiet" else "steady"
        strength["situation"] = SITUATION_BAND_SCORE[situation_band]

    axes: Dict[str, Any] = {}
    for axis, votes in axis_votes.items():
        if not votes:
            axes[axis] = {"direction": "unknown", "up": [], "down": [], "steady": []}
            continue
        up = sorted(g for g, v in votes.items() if v >= dials.deviation_threshold)
        down = sorted(g for g, v in votes.items() if v <= -dials.deviation_threshold)
        steady = sorted(g for g in votes if g not in up and g not in down)
        w_up = sum(reliability.weight(g, dials) for g in up)
        w_down = sum(reliability.weight(g, dials) for g in down)
        if up and down:
            direction = "mixed"
        elif w_up > 0:
            direction = "up"
        elif w_down > 0:
            direction = "down"
        else:
            direction = "steady"
        axes[axis] = {"direction": direction, "up": up, "down": down, "steady": steady}

    mature_groups = [g for g, s in groups.items() if s in ("departed", "steady")]
    departed = [g for g in mature_groups if groups[g] == "departed"]
    if len(mature_groups) >= dials.aggregate_min_groups:
        total_w = sum(reliability.weight(g, dials) for g in mature_groups)
        score = sum(reliability.weight(g, dials) * strength.get(g, 0.0) for g in mature_groups) / max(total_w, 1e-9)
        split = 1.0 - abs(len(departed) - (len(mature_groups) - len(departed))) / len(mature_groups)
        aggregate: Dict[str, Any] = {"status": "observed", "score": round(score, 3), "band": _band(score, dials),
                                     "witness_split": round(split, 3)}
    else:
        aggregate = {"status": "not_enough_witnesses", "score": None, "band": None, "witness_split": None}

    return {"groups": groups, "axes": axes, "departed": departed, "mature": mature_groups, "aggregate": aggregate,
            "weights": {g: round(reliability.weight(g, dials), 3) for g in mature_groups}}


def report_gap(agreement: Mapping[str, Any], report: Mapping[str, Any], dials: ObservationDials) -> Optional[Dict[str, Any]]:
    """Where what they say and what the independent witnesses show part ways.

    Never announced to the person. It is a reason to adjust quietly and, later, a
    moment to ask about in calibration. It never discounts the report by itself."""
    said = report.get("said")
    departed: List[str] = list(agreement.get("departed") or [])
    mature: List[str] = list(agreement.get("mature") or [])
    if said == "fine" and report.get("plain") is True and len(departed) >= dials.report_conflict_min_groups:
        return {"kind": "says_fine_witnesses_differ", "witnesses": departed}
    if said == "not_fine" and len(mature) >= dials.report_conflict_min_groups and not departed:
        return {"kind": "says_not_fine_witnesses_steady", "witnesses": mature}
    return None
