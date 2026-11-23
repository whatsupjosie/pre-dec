from __future__ import annotations

import re

from .models import UserSignal


class StateDetector:
    """
    Converts raw user signals into confidence hints.

    This class intentionally does NOT decide "who the user is."
    Identity remains stable. Only communication state changes.
    """

    BABY_WORDS = {
        "gaga", "goo goo", "googoo", "baba", "uppies", "mama", "mommy",
        "teddy", "paci", "pacifier", "diaper"
    }

    DISTRESS_MARKERS = {
        "fine": 0.15,
        "i'm fine": 0.25,
        "im fine": 0.25,
        "whatever": 0.20,
        "leave me alone": 0.25,
        "can't": 0.30,
        "cant": 0.30,
        "everything is broken": 0.45,
        "i hate": 0.25,
        "fuck": 0.10,
    }

    TIRED_MARKERS = {
        "exhausted": 0.50,
        "tired": 0.35,
        "worn out": 0.35,
        "can't think": 0.40,
        "brain is done": 0.45,
        "bed": 0.15,
        "night diaper": 0.20,
    }

    def analyze(self, signal: UserSignal) -> UserSignal:
        text = signal.text or ""
        lower = text.lower()

        distress = signal.distress_hint
        tiredness = signal.tiredness_hint
        baby_talk = signal.baby_talk_hint

        for marker, weight in self.DISTRESS_MARKERS.items():
            if marker in lower:
                distress += weight

        for marker, weight in self.TIRED_MARKERS.items():
            if marker in lower:
                tiredness += weight

        for word in self.BABY_WORDS:
            if word in lower:
                baby_talk += 0.25

        if self._looks_emphatic_fine(text):
            distress += 0.30

        if self._has_many_typos_or_fragments(text):
            distress += 0.15
            tiredness += 0.10

        if len(text) < 18 and signal.recent_history:
            distress += 0.10

        signal.distress_hint = min(distress, 1.0)
        signal.tiredness_hint = min(tiredness, 1.0)
        signal.baby_talk_hint = min(baby_talk, 1.0)
        return signal

    @staticmethod
    def _looks_emphatic_fine(text: str) -> bool:
        lower = text.lower()
        return ("fine" in lower) and (
            text.isupper()
            or "!" in text
            or " ok" in lower
            or "okay" in lower
        )

    @staticmethod
    def _has_many_typos_or_fragments(text: str) -> bool:
        if not text:
            return False
        words = text.split()
        if len(words) < 4:
            return False
        very_short = sum(1 for w in words if len(w) <= 2)
        repeated = len(re.findall(r"\b(\w+)\s+\1\b", text.lower()))
        return (very_short / max(len(words), 1) > 0.35) or repeated > 0
