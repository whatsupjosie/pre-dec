"""The shared observation layer: one entry point for the live path and for calibration.

Status: SHADOW. It observes, records and scores. It does not change any reply,
any move or any judgment. Its output is attached to the turn record under
"eq_observation" with influence "none", so it can be compared against outcomes
(Gate 0) before anything is allowed to act on it.

Flow per turn:
  1. measure the text (and keyboard, voice, face only with consent)
  2. read against the person's baselines BEFORE updating them (a message is never
     compared with itself), with each witness weighted by earned trust
  3. update baselines and the person's vocabulary
  4. keep the reading (numbers and ids, no message text) for calibration and scoring

Calibration closes the loop: moments are chosen where witnesses split or the
report parted from them; the person's approved account moves trust and scores
the inner reader. Observer feedback scores the perception reader.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .baseline import PersonBaseline
from .dials import DEFAULT_DIALS, ObservationDials
from .features import FeatureSet, behaviour_features, text_features
from .readers import InnerStateReader, PerceptionReader
from .reliability import VERDICTS, Reliability, apply_verdict
from .scorecards import Scorecard, score_inner, score_perception, summaries
from .store import PersonStore

INTERVIEWER_RULE = ("Ask one open question about this moment, in your own words. You may describe what was "
                    "observed in their behaviour. Never name a feeling for them, and accept whatever they say.")

_WHY = {
    ("message_shape", "up"): "messages were shorter than usual",
    ("message_shape", "down"): "messages were longer than usual",
    ("emphasis", "up"): "more capitals or exclamation marks than usual",
    ("emphasis", "down"): "fewer capitals or exclamation marks than usual",
    ("motor", "up"): "more typos or corrections than usual",
    ("motor", "down"): "fewer typos or corrections than usual",
    ("voice", "up"): "voice was different from usual",
    ("voice", "down"): "voice was different from usual",
    ("face", "up"): "expression was different from usual",
    ("face", "down"): "expression was different from usual",
}
_GROUP_AXIS = {"message_shape": "contraction", "emphasis": "activation", "motor": "disruption"}


class ObservationLayer:
    def __init__(self, data_dir: Path, *, dials: ObservationDials = DEFAULT_DIALS) -> None:
        self.dials = dials
        self.store = PersonStore(data_dir)
        self.inner = InnerStateReader(dials)
        self.perception = PerceptionReader(dials)

    # ---- per turn ----------------------------------------------------------------------------
    def observe_turn(self, *, user_id: str, session_id: str, turn_id: str, source_id: str, text: str,
                     behaviour: Optional[Mapping[str, Any]] = None, report: Optional[Mapping[str, Any]] = None,
                     situation_band: Optional[str] = None, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else float(now)
        with self.store.lock(user_id):
            doc = self.store.load(user_id)
            baseline = PersonBaseline.from_dict(doc.get("baselines"))
            reliability = Reliability.from_dict(doc.get("reliability"))
            vocabulary: Dict[str, int] = {str(k): int(v) for k, v in (doc.get("vocabulary") or {}).items()
                                          if isinstance(v, int) and not isinstance(v, bool) and v > 0}

            text_values, text_status, words = text_features(text, vocabulary, min_count=self.dials.vocabulary_min_count)
            beh_values, beh_status, problems = behaviour_features(behaviour)
            features = FeatureSet(values={**text_values, **beh_values}, status={"text": text_status, **beh_status},
                                  problems=tuple(problems))

            reading = self.inner.read(values=features.values, baseline=baseline, reliability=reliability,
                                      report=report, situation_band=situation_band, feature_status=features.status)
            reading["problems"] = list(features.problems)

            baseline.update(features.values, self.dials)
            for w in words:
                vocabulary[w] = vocabulary.get(w, 0) + 1
            if len(vocabulary) > self.dials.vocabulary_limit:
                keep = sorted(vocabulary.items(), key=lambda kv: kv[1], reverse=True)[: self.dials.vocabulary_limit]
                vocabulary = dict(keep)

            readings: List[Dict[str, Any]] = list(doc.get("readings") or [])
            readings.append({"turn_id": str(turn_id), "session_id": str(session_id), "source_id": str(source_id),
                             "at": now, "asked": False, "reading": reading})
            doc.update({"baselines": baseline.to_dict(), "reliability": reliability.to_dict(),
                        "vocabulary": vocabulary, "readings": readings[-self.dials.readings_kept:]})
            self.store.save(user_id, doc)
        return reading

    def shadow_view(self, reading: Mapping[str, Any]) -> Dict[str, Any]:
        """What goes on the turn record: bands and directions, plus the explicit shadow status."""
        return {"schema": "pubcast.eq_observation.shadow.v1", "influence": "none (shadow: observed and recorded only)",
                "inner_state": InnerStateReader.card(reading),
                "calibration_candidate": reading.get("calibration_candidate"),
                "sources": dict(reading.get("sources") or {}), "problems": list(reading.get("problems") or [])}

    def perceive_reply(self, *, user_id: str, turn_id: str, reply: str, user_message: str = "",
                       now: Optional[float] = None) -> Dict[str, Any]:
        result = self.perception.perceive_reply(reply, user_message=user_message)
        prediction_id = uuid.uuid4().hex
        with self.store.lock(user_id):
            doc = self.store.load(user_id)
            rows = list(doc.get("perception_predictions") or [])
            rows.append({"id": prediction_id, "turn_id": str(turn_id), "subject": "reply",
                         "expected_reads": list(result["expected_reads"]), "at": time.time() if now is None else now})
            doc["perception_predictions"] = rows[-self.dials.readings_kept:]
            self.store.save(user_id, doc)
        return {**result, "prediction_id": prediction_id, "influence": "none (shadow: observed and recorded only)"}

    # ---- calibration ---------------------------------------------------------------------------
    def calibration_moments(self, *, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Moments worth asking about, most informative first, with evidence the calibration store accepts."""
        limit = self.dials.calibration_moments if limit is None else max(1, min(10, int(limit)))
        doc = self.store.load(user_id)
        scored = []
        for row in doc.get("readings") or []:
            reading = row.get("reading") or {}
            if row.get("asked") or not reading.get("calibration_candidate"):
                continue
            agg = reading.get("aggregate") or {}
            score = (2.0 if reading.get("report_gap") else 0.0) + float(agg.get("witness_split") or 0.0) \
                + float(agg.get("score") or 0.0)
            scored.append((score, row))
        scored.sort(key=lambda pair: (pair[0], pair[1].get("at", 0)), reverse=True)
        moments = []
        for _, row in scored[:limit]:
            reading = row["reading"]
            moments.append({"turn_id": row["turn_id"], "at": row["at"],
                            "evidence": {"session_id": row["session_id"], "turn_id": row["turn_id"],
                                         "source_id": row["source_id"]},
                            "why": self._why(reading), "kind": reading.get("calibration_candidate"),
                            "interviewer_rule": INTERVIEWER_RULE})
        return moments

    def _why(self, reading: Mapping[str, Any]) -> List[str]:
        out: List[str] = []
        axes = reading.get("axes") or {}
        for group in reading.get("groups") or {}:
            if (reading["groups"].get(group)) != "departed":
                continue
            axis = _GROUP_AXIS.get(group)
            block = axes.get(axis) or {} if axis else {}
            direction = "up" if group in (block.get("up") or []) else "down" if group in (block.get("down") or []) else "up"
            if group == "situation":
                out.append("something was going on in their life at the time")
            elif (group, direction) in _WHY:
                out.append(_WHY[(group, direction)])
        said = (reading.get("report") or {}).get("said")
        if said == "fine":
            out.append("they said they were fine")
        elif said == "not_fine":
            out.append("they said they were not okay")
        return out

    def apply_calibration_verdict(self, *, user_id: str, turn_id: str, verdict: Mapping[str, Any]) -> Dict[str, Any]:
        """An approved account of one moment, from the calibration interview.

        verdict: {"answer": "something_was_going_on" | "nothing_was_going_on" | "partly",
                  "approved": True, "delay_s": seconds since the moment (optional),
                  "calm": True | False | None (were they calm when answering), "interview_id": optional}"""
        if verdict.get("answer") not in VERDICTS:
            raise ValueError("answer must be one of " + ", ".join(VERDICTS))
        with self.store.lock(user_id):
            doc = self.store.load(user_id)
            row = next((r for r in doc.get("readings") or [] if r.get("turn_id") == str(turn_id)), None)
            if row is None:
                raise LookupError("no recorded reading for that turn")
            reliability = Reliability.from_dict(doc.get("reliability"))
            notes = apply_verdict(reliability, row["reading"], verdict, self.dials)
            inner_card = Scorecard(doc.get("inner_scorecard"))
            if verdict.get("approved") is True:
                score_inner(inner_card, row["reading"], str(verdict.get("answer")))
                row["asked"] = True
            history = list(doc.get("verdicts") or [])
            delay = verdict.get("delay_s")
            history.append({"turn_id": str(turn_id), "answer": verdict.get("answer"),
                            "approved": verdict.get("approved") is True,
                            "delay_s": float(delay) if isinstance(delay, (int, float)) and not isinstance(delay, bool) else None,
                            "calm": verdict.get("calm") if verdict.get("calm") in (True, False) else None,
                            "interview_id": str(verdict.get("interview_id") or "")[:64], "at": time.time()})
            doc.update({"reliability": reliability.to_dict(), "inner_scorecard": inner_card.to_dict(),
                        "verdicts": history[-self.dials.verdicts_kept:]})
            self.store.save(user_id, doc)
        return {"notes": notes, "weights": reliability.to_dict()["weights"]}

    def record_perception_feedback(self, *, user_id: str, prediction_id: str, observed_reads: List[str]) -> Dict[str, Any]:
        """An observer said how something actually came across (System Calibration or an audience)."""
        clean = sorted({str(r)[:64] for r in observed_reads if isinstance(r, str) and r.strip()})
        with self.store.lock(user_id):
            doc = self.store.load(user_id)
            row = next((r for r in doc.get("perception_predictions") or [] if r.get("id") == prediction_id), None)
            if row is None:
                raise LookupError("no recorded prediction with that id")
            card = Scorecard(doc.get("perception_scorecard"))
            score_perception(card, row.get("expected_reads") or [], clean)
            row["observed_reads"] = clean
            doc["perception_scorecard"] = card.to_dict()
            self.store.save(user_id, doc)
        return card.summary()

    # ---- owner view ----------------------------------------------------------------------------
    def summary(self, *, user_id: str) -> Dict[str, Any]:
        doc = self.store.load(user_id)
        baseline = PersonBaseline.from_dict(doc.get("baselines"))
        return {"baseline_maturity": round(baseline.maturity(self.dials), 3),
                "readings_kept": len(doc.get("readings") or []),
                "trust": Reliability.from_dict(doc.get("reliability")).to_dict(),
                "neutral_trust": self.dials.neutral_reliability,
                "scorecards": summaries(Scorecard(doc.get("inner_scorecard")), Scorecard(doc.get("perception_scorecard"))),
                "verdicts": len(doc.get("verdicts") or [])}

    def forget(self, *, user_id: str) -> bool:
        return self.store.forget(user_id)
