"""The shared observation layer: one entry point for the live path and for calibration.

Status: SHADOW. It observes, records and scores. It does not change any reply, any
move or any judgment. Its output is attached to the turn record under
"eq_observation" (and "eq_perception" for replies) with influence "none", so it can
be compared against outcomes before anything is allowed to act on it.

Flow per turn:
  1. measure the text (and keyboard, voice, face only with the person's consent)
  2. read against the person's baselines BEFORE updating them (a message is never
     compared with itself), each witness weighted by the trust it has earned
  3. update baselines and the person's vocabulary
  4. keep the reading (numbers and ids, no message text) for calibration and scoring

Calibration closes the loop: moments are chosen where witnesses split or the report
parted from them; the person's approved account moves trust and scores the inner
reader. Observer feedback scores the perception reader.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .baseline import PersonBaseline
from .dials import DEFAULT_DIALS, ObservationDials
from .features import GROUPS, FeatureSet, behaviour_features, text_features
from .readers import InnerStateReader, PerceptionReader
from .reliability import VERDICTS, Reliability, apply_verdict
from .scorecards import Scorecard, score_inner, score_perception, summaries
from .store import PersonStore

SHADOW = "none (shadow: observed and recorded only)"
INTERVIEWER_RULE = ("Ask one open question about this moment, in your own words. You may describe what was "
                    "observed in their behaviour. Never name a feeling for them, and accept whatever they say.")
SITUATION_BANDS = ("quiet", "noticed", "strong")
MAX_OBSERVED_READS = 16

_WHY = {
    ("message_shape", "up"): "messages were shorter than usual",
    ("message_shape", "down"): "messages were longer than usual",
    ("emphasis", "up"): "more capitals or exclamation marks than usual",
    ("emphasis", "down"): "fewer capitals or exclamation marks than usual",
    ("motor", "up"): "more typos or corrections than usual",
    ("motor", "down"): "fewer typos or corrections than usual",
}
_GROUP_AXIS = {"message_shape": "contraction", "emphasis": "activation", "motor": "disruption"}


class ObservationError(ValueError):
    """A request the layer refuses (bad answer, already answered, unknown turn)."""


def _stored_reading(reading: Mapping[str, Any]) -> Dict[str, Any]:
    """The reading as kept on disk: constant labels dropped, everything measured kept."""
    return {k: v for k, v in reading.items() if k not in ("reader", "label", "ask_dont_tell")}


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
        if situation_band is not None and situation_band not in SITUATION_BANDS:
            situation_band = None
        with self.store.lock(user_id):
            state = self.store.load_state(user_id)
            baseline = PersonBaseline.from_dict(state.get("baselines"))
            reliability = Reliability.from_dict(state.get("reliability"))
            vocabulary: Dict[str, int] = {str(k): v for k, v in (state.get("vocabulary") or {}).items()
                                          if isinstance(v, int) and not isinstance(v, bool) and v > 0}

            text_values, text_status, words = text_features(text, vocabulary,
                                                            min_count=self.dials.vocabulary_min_count)
            beh_values, beh_status, problems = behaviour_features(behaviour)
            features = FeatureSet(values={**text_values, **beh_values}, status={"text": text_status, **beh_status},
                                  problems=tuple(problems))

            reading = self.inner.read(values=features.values, baseline=baseline, reliability=reliability,
                                      report=report, situation_band=situation_band, feature_status=features.status)
            reading["problems"] = list(features.problems)
            if state.get("recovered_from_damage"):
                reading["problems"].append("this person's saved state was damaged and was set aside; starting neutral")

            baseline.update(features.values, self.dials)
            for w in words:
                vocabulary[w] = vocabulary.get(w, 0) + 1
            # Trim with headroom so the sort runs once in a while, not on every turn.
            if len(vocabulary) > self.dials.vocabulary_limit * 1.1:
                vocabulary = dict(sorted(vocabulary.items(), key=lambda kv: (-kv[1], kv[0]))
                                  [: self.dials.vocabulary_limit])

            self.store.append(user_id, "readings", {
                "turn_id": str(turn_id), "session_id": str(session_id), "source_id": str(source_id),
                "at": now, "reading": _stored_reading(reading)})
            lines = dict(state.get("stream_lines") or {})
            lines["readings"] = int(lines.get("readings", 0)) + 1
            if lines["readings"] > 2 * self.dials.readings_kept:
                lines["readings"] = self.store.compact(user_id, "readings", self.dials.readings_kept)
            state.pop("recovered_from_damage", None)
            state.update({"baselines": baseline.to_dict(), "reliability": reliability.to_dict(),
                          "vocabulary": vocabulary, "stream_lines": lines})
            self.store.save_state(user_id, state)
        return reading

    @staticmethod
    def shadow_view(reading: Mapping[str, Any]) -> Dict[str, Any]:
        """What goes on the turn record: bands and directions, plus the explicit shadow status."""
        return {"schema": "pubcast.eq_observation.shadow.v1", "influence": SHADOW,
                "inner_state": InnerStateReader.card(reading),
                "calibration_candidate": reading.get("calibration_candidate"),
                "sources": dict(reading.get("sources") or {}), "problems": list(reading.get("problems") or [])}

    def perceive_reply(self, *, user_id: str, turn_id: str, reply: str, user_message: str = "",
                       now: Optional[float] = None) -> Dict[str, Any]:
        result = self.perception.perceive_reply(reply, user_message=user_message)
        prediction_id = uuid.uuid4().hex
        with self.store.lock(user_id):
            state = self.store.load_state(user_id)
            self.store.append(user_id, "perception", {
                "kind": "prediction", "id": prediction_id, "turn_id": str(turn_id), "subject": "reply",
                "expected_reads": list(result["expected_reads"]), "at": time.time() if now is None else float(now)})
            lines = dict(state.get("stream_lines") or {})
            lines["perception"] = int(lines.get("perception", 0)) + 1
            if lines["perception"] > 2 * self.dials.readings_kept:
                lines["perception"] = self.store.compact(user_id, "perception", self.dials.readings_kept)
            state["stream_lines"] = lines
            self.store.save_state(user_id, state)
        return {**result, "prediction_id": prediction_id, "influence": SHADOW}

    # ---- calibration ---------------------------------------------------------------------------
    def _reading_rows(self, user_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.store.read_stream(user_id, "readings")
                if isinstance(r.get("reading"), dict) and r.get("turn_id")]

    def calibration_moments(self, *, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Moments worth asking about, most informative first, with evidence the calibration store accepts."""
        limit = self.dials.calibration_moments if limit is None else max(1, min(10, int(limit)))
        with self.store.lock(user_id):
            asked = set((self.store.load_state(user_id).get("asked") or []))
            rows = self._reading_rows(user_id)
        scored = []
        for row in rows:
            reading = row["reading"]
            if row["turn_id"] in asked or not reading.get("calibration_candidate"):
                continue
            agg = reading.get("aggregate") or {}
            score = (2.0 if reading.get("report_gap") else 0.0) + float(agg.get("witness_split") or 0.0) \
                + float(agg.get("score") or 0.0)
            scored.append((score, float(row.get("at") or 0.0), row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [self._moment(row) for _, _, row in scored[:limit]]

    def moment_notes(self, *, user_id: str, turn_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """For turns another list already shows (the calibration screen's recent exchanges): what this
        layer noticed about each, keyed by turn id. Turns it did not flag are left out."""
        wanted = {str(t) for t in turn_ids if t}
        if not wanted:
            return {}
        with self.store.lock(user_id):
            asked = set((self.store.load_state(user_id).get("asked") or []))
            rows = self._reading_rows(user_id)
        notes = {}
        for row in rows:
            if row["turn_id"] in wanted and row["reading"].get("calibration_candidate"):
                moment = self._moment(row)
                notes[row["turn_id"]] = {"why": moment["why"], "kind": moment["kind"],
                                         "answered": row["turn_id"] in asked}
        return notes

    def _moment(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        reading = row["reading"]
        return {"turn_id": row["turn_id"], "at": row.get("at"),
                "evidence": {"session_id": row.get("session_id", ""), "turn_id": row["turn_id"],
                             "source_id": row.get("source_id", "")},
                "why": self._why(reading), "kind": reading.get("calibration_candidate"),
                "interviewer_rule": INTERVIEWER_RULE}

    @staticmethod
    def _why(reading: Mapping[str, Any]) -> List[str]:
        """Plain words for what was observed. Behaviour only; never a feeling."""
        out: List[str] = []
        axes = reading.get("axes") or {}
        groups = reading.get("groups") or {}
        for group, state in groups.items():
            if state != "departed":
                continue
            if group == "situation":
                out.append("something was going on in their life at the time")
            elif group == "voice":
                out.append("their voice was different from usual")
            elif group == "face":
                out.append("their expression was different from usual")
            elif group in _GROUP_AXIS:
                block = axes.get(_GROUP_AXIS[group]) or {}
                direction = "down" if group in (block.get("down") or []) else "up"
                out.append(_WHY[(group, direction)])
        said = (reading.get("report") or {}).get("said")
        if said == "fine":
            out.append("they said they were fine")
        elif said == "not_fine":
            out.append("they said they were not okay")
        return out

    def apply_calibration_verdict(self, *, user_id: str, turn_id: str, verdict: Mapping[str, Any],
                                  now: Optional[float] = None) -> Dict[str, Any]:
        """The person's approved account of one moment, from the calibration interview.

        verdict: {"answer": "something_was_going_on" | "nothing_was_going_on" | "partly",
                  "approved": True, "calm": True | False | None, "interview_id": optional}
        The delay is measured here, from when the moment was read, not taken from the caller.
        One verdict per moment: a second one is refused, so trust cannot be moved twice."""
        answer = verdict.get("answer")
        if answer not in VERDICTS:
            raise ObservationError("answer must be one of " + ", ".join(VERDICTS))
        if verdict.get("approved") is not True:
            raise ObservationError("only an account the person approved can be recorded")
        calm = verdict.get("calm")
        if calm not in (True, False, None):
            raise ObservationError("calm must be true, false or null")
        now = time.time() if now is None else float(now)
        with self.store.lock(user_id):
            state = self.store.load_state(user_id)
            asked = list(state.get("asked") or [])
            if str(turn_id) in asked:
                raise ObservationError("this moment already has an approved account")
            row = next((r for r in reversed(self._reading_rows(user_id)) if r["turn_id"] == str(turn_id)), None)
            if row is None:
                raise LookupError("no recorded reading for that turn")
            reliability = Reliability.from_dict(state.get("reliability"))
            notes = apply_verdict(reliability, row["reading"], {"answer": answer, "approved": True}, self.dials)
            inner_card = Scorecard(state.get("inner_scorecard"))
            score_inner(inner_card, row["reading"], answer)
            asked.append(str(turn_id))
            history = list(state.get("verdicts") or [])
            history.append({"turn_id": str(turn_id), "answer": answer,
                            "delay_s": round(max(0.0, now - float(row.get("at") or now)), 1),
                            "calm": calm, "interview_id": str(verdict.get("interview_id") or "")[:64], "at": now})
            state.update({"reliability": reliability.to_dict(), "inner_scorecard": inner_card.to_dict(),
                          "verdicts": history[-self.dials.verdicts_kept:],
                          "asked": asked[-self.dials.verdicts_kept:]})
            self.store.save_state(user_id, state)
        return {"notes": notes, "trust": reliability.to_dict()["weights"]}

    def record_perception_feedback(self, *, user_id: str, prediction_id: str,
                                   observed_reads: Iterable[str]) -> Dict[str, Any]:
        """An observer said how something actually came across (System Calibration or an audience).
        One feedback per prediction; a second is refused."""
        clean = sorted({str(r).strip()[:64] for r in observed_reads if isinstance(r, str) and r.strip()})
        if len(clean) > MAX_OBSERVED_READS:
            raise ObservationError(f"at most {MAX_OBSERVED_READS} observed reads")
        with self.store.lock(user_id):
            rows = self.store.read_stream(user_id, "perception")
            prediction = next((r for r in rows if r.get("kind") == "prediction" and r.get("id") == prediction_id), None)
            if prediction is None:
                raise LookupError("no recorded prediction with that id")
            if any(r.get("kind") == "feedback" and r.get("prediction_id") == prediction_id for r in rows):
                raise ObservationError("this prediction already has feedback")
            state = self.store.load_state(user_id)
            card = Scorecard(state.get("perception_scorecard"))
            score_perception(card, prediction.get("expected_reads") or [], clean)
            self.store.append(user_id, "perception", {"kind": "feedback", "prediction_id": prediction_id,
                                                      "observed_reads": clean, "at": time.time()})
            lines = dict(state.get("stream_lines") or {})
            lines["perception"] = int(lines.get("perception", 0)) + 1
            state.update({"perception_scorecard": card.to_dict(), "stream_lines": lines})
            self.store.save_state(user_id, state)
        return card.summary()

    # ---- owner view ----------------------------------------------------------------------------
    def summary(self, *, user_id: str) -> Dict[str, Any]:
        with self.store.lock(user_id):
            state = self.store.load_state(user_id)
            readings = len(self._reading_rows(user_id))
        trust = Reliability.from_dict(state.get("reliability")).to_dict()
        return {"status": "shadow", "influence": SHADOW,
                "baseline_maturity": round(PersonBaseline.from_dict(state.get("baselines")).maturity(self.dials), 3),
                "readings_kept": readings,
                "trust": {g: trust["weights"].get(g, self.dials.neutral_reliability)
                          for g in (*[g for g in GROUPS if g != "report"], "report_in_moment")},
                "trust_evidence": trust["evidence_counts"],
                "scorecards": summaries(Scorecard(state.get("inner_scorecard")),
                                        Scorecard(state.get("perception_scorecard"))),
                "verdicts": len(state.get("verdicts") or [])}

    def forget(self, *, user_id: str) -> bool:
        return self.store.forget(user_id)
