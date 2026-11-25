"""
rhyme.py — offline rhyming and phonetic-stress dictionary backed by CMUdict.

CMUdict ships as package data via the `cmudict` pypi package — no network
call at runtime. ~126k pronunciations, ARPAbet phoneme notation with stress
markers (0 = unstressed, 1 = primary stress, 2 = secondary stress).

Rhyme classes implemented, matching the design conversation:
  - perfect:      stressed vowel through end of word matches exactly
  - slant/assonance: stressed vowel matches, trailing consonants differ
  - consonance:   trailing consonants match, stressed vowel differs
  - multi_syllable: perfect match spanning the last 2+ syllables
    ("blink rhymes" / "double rhymes", e.g. "gravity" / "depravity")

Also exposes a per-line stress pattern (0/1/2 per syllable) so a caller can
render a meter guide (iambic, trochaic, etc.) alongside the text.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import cmudict

_VOWEL_PHONES = {
    "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY",
    "IH", "IY", "OW", "OY", "UH", "UW",
}


def _is_vowel(phone: str) -> bool:
    return phone.rstrip("012") in _VOWEL_PHONES


def _stress(phone: str) -> int:
    for ch in phone[::-1]:
        if ch.isdigit():
            return int(ch)
    return -1  # not a vowel phone


@dataclass(slots=True)
class RhymeMatch:
    word: str
    rhyme_type: str  # perfect | slant | consonance | multi_syllable


class RhymeDictionary:
    def __init__(self):
        self._dict: Dict[str, List[List[str]]] = cmudict.dict()
        self._by_last_stressed: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        self._by_final_consonants: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        self._index_built = False

    # ── public lookups ──────────────────────────────────────────────────

    def pronunciations(self, word: str) -> List[List[str]]:
        return self._dict.get(word.strip().lower(), [])

    def syllable_count(self, word: str) -> int:
        prons = self.pronunciations(word)
        if not prons:
            return 0
        return sum(1 for p in prons[0] if _is_vowel(p))

    def stress_pattern(self, word: str) -> List[int]:
        """e.g. 'PUBCAST' style two-syllable word -> [1, 0] for a trochee."""
        prons = self.pronunciations(word)
        if not prons:
            return []
        return [_stress(p) for p in prons[0] if _is_vowel(p)]

    def line_stress_pattern(self, line: str) -> List[Tuple[str, List[int]]]:
        """Per-word stress patterns across a whole line, for a meter guide."""
        out = []
        for raw in line.split():
            word = "".join(ch for ch in raw if ch.isalpha() or ch == "'")
            if not word:
                continue
            out.append((word, self.stress_pattern(word)))
        return out

    def classify(self, word_a: str, word_b: str) -> str | None:
        """Classify the rhyme relationship between two specific words."""
        a = self._rhyme_key(word_a)
        b = self._rhyme_key(word_b)
        if a is None or b is None:
            return None
        if word_a.lower() == word_b.lower():
            return None
        if a["last_two_syllables"] == b["last_two_syllables"] and a["syllables_from_stress"] >= 2:
            return "multi_syllable"
        if a["from_stressed_vowel"] == b["from_stressed_vowel"]:
            return "perfect"
        if a["stressed_vowel"] == b["stressed_vowel"]:
            return "slant"
        if a["final_consonants"] == b["final_consonants"] and a["final_consonants"]:
            return "consonance"
        return None

    def find_rhymes(
        self,
        word: str,
        max_per_type: int = 15,
        types: Sequence[str] = ("perfect", "multi_syllable", "slant", "consonance"),
    ) -> Dict[str, List[str]]:
        """
        Scan the full ~126k word dictionary for rhyme matches. This is a
        linear scan (fine for an offline desktop tool at this dict size —
        well under 100ms); an index can be added later if it needs to run
        per-keystroke rather than on demand.
        """
        key = self._rhyme_key(word)
        results: Dict[str, List[str]] = {t: [] for t in types}
        if key is None:
            return results
        target = word.strip().lower()
        for candidate in self._dict:
            if candidate == target:
                continue
            rhyme_type = self.classify(word, candidate)
            if rhyme_type in results and len(results[rhyme_type]) < max_per_type:
                results[rhyme_type].append(candidate)
        return results

    # ── internals ────────────────────────────────────────────────────────

    def _rhyme_key(self, word: str) -> dict | None:
        prons = self.pronunciations(word)
        if not prons:
            return None
        phones = prons[0]
        vowel_indices = [i for i, p in enumerate(phones) if _is_vowel(p)]
        if not vowel_indices:
            return None
        # last syllable carrying primary (1) or secondary (2) stress; fall
        # back to the last vowel if the word has no marked stress (rare).
        stressed_idx = None
        for i in reversed(vowel_indices):
            if _stress(phones[i]) in (1, 2):
                stressed_idx = i
                break
        if stressed_idx is None:
            stressed_idx = vowel_indices[-1]

        from_stressed_vowel = tuple(p.rstrip("012") for p in phones[stressed_idx:])
        stressed_vowel = phones[stressed_idx].rstrip("012")
        # trailing consonants after the very last vowel in the word
        last_vowel_idx = vowel_indices[-1]
        final_consonants = tuple(p.rstrip("012") for p in phones[last_vowel_idx + 1:])

        # last two syllables (for multi-syllable / "blink" rhyme matching)
        syl_starts = vowel_indices
        if len(syl_starts) >= 2:
            second_last_vowel_idx = syl_starts[-2]
            last_two_syllables = tuple(p.rstrip("012") for p in phones[second_last_vowel_idx:])
            syllables_from_stress = len(vowel_indices) - vowel_indices.index(stressed_idx) if stressed_idx in vowel_indices else 1
        else:
            last_two_syllables = from_stressed_vowel
            syllables_from_stress = 1

        return {
            "from_stressed_vowel": from_stressed_vowel,
            "stressed_vowel": stressed_vowel,
            "final_consonants": final_consonants,
            "last_two_syllables": last_two_syllables,
            "syllables_from_stress": max(syllables_from_stress, 1),
        }
