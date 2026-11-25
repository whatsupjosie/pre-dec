"""Witness features: what can be measured about a turn, and what it shares a cause with.

Nothing here decides what a person feels. A feature is a measurement; the
baseline turns it into "different from this person's usual"; the agreement map
looks at many of them together.

WITNESS GROUPS (one vote per group, because features with a shared cause are not
independent evidence):
  message_shape   how much they wrote and how it is broken up (one decision: writing short)
  emphasis        capitals and exclamation marks
  motor           likely typos, backspaces, typing speed, hesitation before sending
                  (hands and attention: the same cause)
  voice           speech rate, pauses, pitch movement, loudness (needs consent)
  face            expressivity, blink and tic rate, looking away (needs consent, and only a
                  live camera on the person's own face; see FACE RULE below)
  situation       what is going on in their life, from the situation reader
  report          what they say about themselves. Kept apart; never a witness against itself.

AXES (behaviour, not feelings):
  contraction  less than usual: fewer words, shorter sentences, looking away
  activation   more than usual: emphasis, speed, loudness, expressivity
  disruption   more broken than usual: typos, corrections, pauses, tics

FACE RULE (Josie, 2026-11-23): "Faces count for performance and avatar reaction. Unless we are
actually looking at somebody in a live camera, seeing their actual living face, then faces don't
count. Unless it's an avatar impersonating a human, in which case that is an intentional
performance mimicking us as naturally as they are able in the most unnatural way."
So, for the inner-state reading, a face counts only when it is a person's own living face on a
live camera (origin "live_camera"), with their consent. Any other face (an avatar, a rendered
character, a recording) is a performance: it is never evidence of what someone feels, and it goes
to the perception reader instead (performance_face below). A face never becomes an emotion label
here; like every witness it only says "different from this person's usual".

Stdlib only. Small-model friendly: a turn costs a few microseconds.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

GROUPS = ("message_shape", "emphasis", "motor", "voice", "face", "situation", "report")
AXES = ("contraction", "activation", "disruption")
CONSENTED_GROUPS = ("keyboard", "voice", "face")  # each must be switched on by the person
LIVE_FACE_ORIGIN = "live_camera"
PERFORMANCE_FACE_ORIGINS = ("avatar", "rendered", "recording")

# feature name -> (group, axis, sign). sign +1: a rise moves the axis up.
FEATURE_MAP: Dict[str, Tuple[str, str, int]] = {
    # text, always available, numbers only
    "word_count": ("message_shape", "contraction", -1),
    "sentence_words": ("message_shape", "contraction", -1),
    "caps_ratio": ("emphasis", "activation", +1),
    "exclaim_rate": ("emphasis", "activation", +1),
    "likely_typo_rate": ("motor", "disruption", +1),
    # keyboard (consent "keyboard")
    "chars_per_second": ("motor", "activation", +1),
    "backspace_ratio": ("motor", "disruption", +1),
    "pause_before_send_s": ("motor", "disruption", +1),
    "edit_count": ("motor", "disruption", +1),
    # voice (consent "voice")
    "speech_rate": ("voice", "activation", +1),
    "pause_ratio": ("voice", "disruption", +1),
    "pitch_variability": ("voice", "activation", +1),
    "loudness": ("voice", "activation", +1),
    "words_per_utterance": ("voice", "contraction", -1),
    # face (consent "face")
    "expressivity": ("face", "activation", +1),
    "blink_rate": ("face", "disruption", +1),
    "tic_rate": ("face", "disruption", +1),
    "gaze_away_ratio": ("face", "contraction", +1),
}
_BEHAVIOUR_FEATURES = {
    "keyboard": ("chars_per_second", "backspace_ratio", "pause_before_send_s", "edit_count"),
    "voice": ("speech_rate", "pause_ratio", "pitch_variability", "loudness", "words_per_utterance"),
    "face": ("expressivity", "blink_rate", "tic_rate", "gaze_away_ratio"),
}

# Measurement resolution: the smallest spread a baseline may claim for a feature. A person who
# has never used an exclamation mark has not earned a maximal deviation for using one; these
# floors say how big a change has to be before it is a change at all. They are technical
# resolution, not owner decisions (those are in dials.py). Each takes the person's mean.
FEATURE_FLOORS = {
    "word_count": lambda mean: max(2.0, 0.15 * abs(mean)),
    "sentence_words": lambda mean: max(1.5, 0.15 * abs(mean)),
    "caps_ratio": lambda mean: 0.05,
    "exclaim_rate": lambda mean: 0.25,
    "likely_typo_rate": lambda mean: 0.03,
}

def spread_floor(feature: str, mean: float) -> float:
    rule = FEATURE_FLOORS.get(feature)
    return float(rule(mean)) if rule else max(0.05, 0.10 * abs(mean))


# Short all-capital words that are ordinary writing, not raised voice.
PLAIN_CAPITALS = frozenset({"OK", "TV", "AI", "AM", "PM", "ID", "US", "UK", "EU", "DJ", "PC", "FYI", "BTW",
                            "USB", "GPU", "CPU", "RAM", "PDF", "URL", "API", "LA", "NYC", "CEO", "DM", "PS"})

_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)|\n+")
_CODE_FENCE = "```"


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


@dataclass(frozen=True)
class FeatureSet:
    """Numbers measured for one turn. status says whether each source was really observed."""
    values: Mapping[str, float]
    status: Mapping[str, str]          # source -> observed | unavailable | simulated | invalid | no_consent
    problems: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"values": dict(self.values), "status": dict(self.status), "problems": list(self.problems)}


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    """True when b is a, with one letter changed, added, removed or two neighbours swapped."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def likely_typos(words: List[str], vocabulary: Mapping[str, int], min_count: int) -> int:
    """Count words the person has never used that sit one keystroke from a word they use often.

    No dictionary: the reference is the person's own writing, so slang and their own
    spellings stop counting as mistakes once they are habitual. Words shorter than four
    letters are skipped (too many legitimate neighbours). Callers pass only lower-case
    tokens as written, so capitalised words (names, and the first word of a sentence)
    are never judged: a new name next to a known word is not a typo.
    """
    if not vocabulary:
        return 0
    known = [w for w, c in vocabulary.items() if c >= min_count and len(w) >= 3]
    if not known:
        return 0
    by_len: Dict[int, List[str]] = {}
    for w in known:
        by_len.setdefault(len(w), []).append(w)
    count = 0
    for w in words:
        if len(w) < 4 or vocabulary.get(w, 0) > 0:
            continue
        candidates = by_len.get(len(w), []) + by_len.get(len(w) - 1, []) + by_len.get(len(w) + 1, [])
        if any(_edit_distance_at_most_one(w, k) for k in candidates):
            count += 1
    return count


def text_features(text: str, vocabulary: Mapping[str, int], *, min_count: int) -> Tuple[Dict[str, float], str, List[str]]:
    """Measure the message text. Returns (values, status, words)."""
    if not isinstance(text, str) or not text.strip():
        return {}, "unavailable", []
    if _CODE_FENCE in text or len(text) > 10000:
        # Pasted code or long documents are not the person's conversational writing.
        return {}, "unavailable", []
    raw_tokens = _WORD.findall(text)
    words = [w.lower() for w in raw_tokens]
    judged = [w for w in raw_tokens if w[:1].islower()]  # see likely_typos: capitalised words are not judged
    n = len(words)
    sentences = [s for s in _SENTENCE_END.split(text) if _WORD.search(s or "")]
    letters = [ch for ch in text if ch.isalpha()]
    # A lone capital I and sentence-initial capitals are normal writing, not emphasis.
    shouted = sum(1 for tok in re.findall(r"[A-Za-z]{2,}", text) if tok.isupper() and tok not in PLAIN_CAPITALS)
    values: Dict[str, float] = {
        "word_count": float(n),
        "sentence_words": float(n) / max(1, len(sentences)),
        "caps_ratio": shouted / max(1, n),
        "exclaim_rate": text.count("!") / max(1, len(sentences)),
    }
    if n >= 3 and letters:
        values["likely_typo_rate"] = likely_typos(judged, vocabulary, min_count) / n
    return values, "observed", words


def behaviour_features(behaviour: Optional[Mapping[str, Any]]) -> Tuple[Dict[str, float], Dict[str, str], List[str]]:
    """Keyboard, voice and face measurements, each used only with the person's consent.

    Expected shape (all optional):
      {"consent": {"keyboard": true, "voice": false, "face": false},
       "keyboard": {"status": "observed", "chars_per_second": 4.2, ...},
       "voice": {...}, "face": {"origin": "live_camera", "status": "observed", ...}}
    Simulated values are refused and written down, never used. A face is used only when its origin
    is "live_camera" (see FACE RULE); an avatar, rendered or recorded face is a performance and is
    reported as such, never used as inner-state evidence.
    """
    values: Dict[str, float] = {}
    status: Dict[str, str] = {}
    problems: List[str] = []
    consent = behaviour.get("consent") if isinstance(behaviour, Mapping) else None
    consent = consent if isinstance(consent, Mapping) else {}
    for source, names in _BEHAVIOUR_FEATURES.items():
        block = behaviour.get(source) if isinstance(behaviour, Mapping) else None
        if not isinstance(block, Mapping):
            status[source] = "unavailable"
            continue
        if consent.get(source) is not True:
            status[source] = "no_consent"
            problems.append(f"{source}: values offered without the person's consent were not used")
            continue
        if source == "face" and block.get("origin") != LIVE_FACE_ORIGIN:
            origin = block.get("origin")
            if origin in PERFORMANCE_FACE_ORIGINS:
                status[source] = "performance"
                problems.append(f"face: an {origin} face is a performance; it informs perception, never the inner reading")
            else:
                status[source] = "origin_unknown"
                problems.append("face: not marked as a live camera on the person; not used")
            continue
        st = block.get("status", "observed")
        if st == "simulated":
            status[source] = "simulated"
            problems.append(f"{source}: simulated values were offered and were not used")
            continue
        if st != "observed":
            status[source] = "unavailable"
            continue
        used = 0
        for name in names:
            if name not in block:
                continue
            v = block[name]
            if not _finite(v) or float(v) < 0:
                problems.append(f"{source}.{name}: not a real, non-negative number; not used")
                continue
            values[name] = float(v)
            used += 1
        status[source] = "observed" if used else "unavailable"
    return values, status, problems


def performance_face(face: Optional[Mapping[str, Any]]) -> Tuple[Dict[str, float], str]:
    """Face measurements for the perception side (performance, avatar reaction, stage).

    Any origin counts here, an avatar included: the question is how the face comes across, not
    what anyone feels. Returns (values, origin). Values that are not real, non-negative numbers
    are dropped. A live person's face still needs their consent before it is passed in."""
    if not isinstance(face, Mapping):
        return {}, "unavailable"
    origin = face.get("origin") if face.get("origin") in (LIVE_FACE_ORIGIN, *PERFORMANCE_FACE_ORIGINS) else "unknown"
    values = {name: float(face[name]) for name in _BEHAVIOUR_FEATURES["face"]
              if name in face and _finite(face[name]) and float(face[name]) >= 0}
    return values, origin
