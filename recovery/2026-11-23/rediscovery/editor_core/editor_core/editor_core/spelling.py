"""
spelling.py — deterministic offline spelling pass.

Backed by `pyspellchecker`, which ships its frequency-based dictionary as
package data (no network call at runtime, works fully offline the moment
it's pip-installed). This is intentionally NOT model-backed: spelling is a
solved lookup problem and burning a Gemma call on it would be wasteful and
slower than a dict lookup.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from spellchecker import SpellChecker

from .annotations import Annotation, AnnotationKind, Severity

_WORD_RE = re.compile(r"[A-Za-z']+")


class SpellingPass:
    def __init__(
        self,
        language: str = "en",
        custom_dictionary: Sequence[str] | None = None,
        max_suggestions: int = 3,
    ):
        self._checker = SpellChecker(language=language)
        if custom_dictionary:
            # Character/place names, invented words, house terms — anything
            # the writer has told the system is intentional gets added here
            # so it stops getting flagged every pass.
            self._checker.word_frequency.load_words(
                [w.lower() for w in custom_dictionary]
            )
        self.max_suggestions = max_suggestions

    def add_known_words(self, words: Iterable[str]) -> None:
        self._checker.word_frequency.load_words([w.lower() for w in words])

    def check(self, text: str) -> List[Annotation]:
        annotations: List[Annotation] = []
        for match in _WORD_RE.finditer(text):
            word = match.group(0)
            bare = word.strip("'")
            if not bare or bare.isupper():  # skip acronyms like NASA
                continue
            if self._checker.unknown([bare.lower()]):
                candidates = list(self._checker.candidates(bare.lower()) or [])
                candidates.sort(key=lambda c: -self._checker.word_usage_frequency(c))
                annotations.append(
                    Annotation(
                        kind=AnnotationKind.SPELLING,
                        severity=Severity.WARNING,
                        message=f'"{word}" is not a recognized word.',
                        start=match.start(),
                        end=match.end(),
                        span_text=word,
                        suggestions=candidates[: self.max_suggestions],
                        rule_id="spelling/unknown_word",
                    )
                )
        return annotations
