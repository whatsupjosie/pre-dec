"""Two scorecards, because the two readers have two different kinds of truth.

inner       a reading of a person vs that person's approved later account (calibration verdict)
perception  an expected read vs what an observer reported it actually came across as
            (System Calibration, or an audience reaction). The observer's report is the truth here.

Numbers only; no message text is kept.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


class Scorecard:
    def __init__(self, data: Any = None) -> None:
        data = data if isinstance(data, Mapping) else {}
        self.cells: Dict[str, Dict[str, int]] = {}
        for k, v in (data.get("cells") or {}).items():
            if isinstance(v, Mapping):
                self.cells[str(k)] = {"hit": int(v.get("hit", 0) or 0), "miss": int(v.get("miss", 0) or 0)}

    def record(self, key: str, hit: bool) -> None:
        cell = self.cells.setdefault(key, {"hit": 0, "miss": 0})
        cell["hit" if hit else "miss"] += 1

    def summary(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, cell in sorted(self.cells.items()):
            n = cell["hit"] + cell["miss"]
            out[key] = {"n": n, "hit_rate": round(cell["hit"] / n, 3) if n else None}
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {"cells": self.cells}


def score_inner(card: Scorecard, reading: Mapping[str, Any], answer: str) -> None:
    """Was the band right? A quiet band is right when nothing was going on, and vice versa."""
    if answer not in ("something_was_going_on", "nothing_was_going_on"):
        return
    went_on = answer == "something_was_going_on"
    band = (reading.get("aggregate") or {}).get("band")
    if band in ("quiet", "noticed", "strong"):
        # A reading with too few witnesses made no prediction, so it is neither a hit nor a miss.
        card.record(f"band:{band}", (band != "quiet") == went_on)
    gap = reading.get("report_gap")
    if gap:
        card.record(f"gap:{gap.get('kind')}", went_on if gap.get("kind") == "says_fine_witnesses_differ" else not went_on)


def score_perception(card: Scorecard, expected_reads: Iterable[str], observed_reads: Iterable[str]) -> None:
    """Each expected read is a hit if the observer reported it; each reported read we missed is a miss."""
    expected, observed = set(expected_reads), set(observed_reads)
    for read in expected:
        card.record(f"predicted:{read}", read in observed)
    for read in observed - expected:
        card.record(f"missed:{read}", False)


def summaries(inner: Scorecard, perception: Scorecard) -> Dict[str, Any]:
    return {"inner": inner.summary(), "perception": perception.summary()}
