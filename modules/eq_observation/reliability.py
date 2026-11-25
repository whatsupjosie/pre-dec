"""How much each witness has earned trust, for each person.

Every witness group starts neutral for every person and moves slowly, and only
when an APPROVED calibration verdict says what was really going on at a moment
that was read. A disagreement on its own changes nothing: it becomes a moment
to ask about. "That remains to be seen until the verdict is in."

The person's report has two separate records:
  report_in_moment     what they said at the time (people are poor reporters in the moment)
  report_retrospective what they say later in calibration. This is the reference the
                       others are scored against, so it is not scored itself; each
                       verdict keeps the delay and whether they were calm, so the
                       person's own data can later show whether delay helps or hurts them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .dials import ObservationDials
from .features import GROUPS

REPORT_KINDS = ("report_in_moment", "report_retrospective")


@dataclass
class Reliability:
    weights: Dict[str, float] = field(default_factory=dict)
    evidence_counts: Dict[str, int] = field(default_factory=dict)

    def weight(self, group: str, dials: ObservationDials) -> float:
        return self.weights.get(group, dials.neutral_reliability)

    def nudge(self, group: str, was_right: bool, dials: ObservationDials) -> None:
        current = self.weight(group, dials)
        target = 1.0 if was_right else 0.0
        updated = current + dials.reliability_learning_rate * (target - current)
        self.weights[group] = max(dials.reliability_floor, min(dials.reliability_ceiling, updated))
        self.evidence_counts[group] = self.evidence_counts.get(group, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        return {"weights": dict(self.weights), "evidence_counts": dict(self.evidence_counts)}

    @classmethod
    def from_dict(cls, data: Any) -> "Reliability":
        if not isinstance(data, Mapping):
            return cls()
        weights = {}
        for k, v in (data.get("weights") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0:
                weights[str(k)] = float(v)
        counts = {str(k): int(v) for k, v in (data.get("evidence_counts") or {}).items()
                  if isinstance(v, int) and not isinstance(v, bool) and v >= 0}
        return cls(weights=weights, evidence_counts=counts)


VERDICTS = ("something_was_going_on", "nothing_was_going_on", "partly")


def apply_verdict(rel: Reliability, reading: Mapping[str, Any], verdict: Mapping[str, Any],
                  dials: ObservationDials) -> List[str]:
    """Update trust from one approved verdict about one recorded reading.

    reading: the stored reading of that turn (see readers.InnerStateReader).
    verdict: {"answer": one of VERDICTS, "approved": True, "delay_s": float|None, "calm": True|False|None}
    Returns plain notes of what changed. A verdict that is not approved changes nothing.
    """
    notes: List[str] = []
    if verdict.get("approved") is not True:
        return ["verdict not approved by the person: nothing changed"]
    answer = verdict.get("answer")
    if answer not in VERDICTS or answer == "partly":
        # "partly" is kept in the history but moves no weight: it is neither right nor wrong.
        return [f"answer {answer!r}: recorded, no weight moved"]
    went_on = answer == "something_was_going_on"
    for group, state in (reading.get("groups") or {}).items():
        if group not in GROUPS or group == "report" or state not in ("departed", "steady"):
            continue
        rel.nudge(group, (state == "departed") == went_on, dials)
        notes.append(f"{group}: {'right' if (state == 'departed') == went_on else 'wrong'}")
    said = (reading.get("report") or {}).get("said")
    if said in ("fine", "not_fine"):
        rel.nudge("report_in_moment", (said == "not_fine") == went_on, dials)
        notes.append(f"report_in_moment: {'right' if (said == 'not_fine') == went_on else 'wrong'}")
    return notes
