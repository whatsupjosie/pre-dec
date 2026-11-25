"""
grammar.py — deterministic rule-based grammar/syntax pass.

Every rule here is a plain regex or a small function over the sentence —
no model call, no external service. This intentionally does NOT try to be
a full grammar engine (that's what LanguageTool exists for, and it can be
bolted on later as an additional rule source behind the same Annotation
contract). What's here catches the specific, well-known error classes that
account for most real writing mistakes:

  - commonly confused homophones (their/there/they're, its/it's, etc.)
  - accidental word doubling ("the the")
  - run-on / very long sentences (cadence, not strictly "wrong")
  - passive voice detection (flagged as a notice, not an error)
  - sentence-initial lowercase
  - double punctuation / spacing

Each rule is self-contained so new ones can be added without touching the
others, and each carries a stable `rule_id` so the UI or the writer's
"ignore this rule" preference can target it precisely.
"""
from __future__ import annotations

import re
from typing import Callable, List

from .annotations import Annotation, AnnotationKind, Severity

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")

# word -> (correct-context hint, likely confusions)
_CONFUSABLES = {
    "their": "possessive ('their house') — not a place or a contraction of 'they are'.",
    "there": "a place or 'there is/are' — not possessive, not 'they are'.",
    "they're": "contraction of 'they are' — not possessive, not a place.",
    "your": "possessive ('your book') — not a contraction of 'you are'.",
    "you're": "contraction of 'you are' — not possessive.",
    "its": "possessive ('its tail') — not a contraction of 'it is'.",
    "it's": "contraction of 'it is' or 'it has' — not possessive.",
    "then": "sequence in time ('then he left') — not a comparison.",
    "than": "comparison ('faster than') — not sequence in time.",
    "affect": "usually a verb ('this will affect him').",
    "effect": "usually a noun ('the effect was clear').",
    "who's": "contraction of 'who is' — not possessive.",
    "whose": "possessive — not a contraction.",
    "loose": "not tight — adjective.",
    "lose": "to misplace / fail to win — verb.",
}
_CONFUSABLE_GROUPS = [
    {"their", "there", "they're"},
    {"your", "you're"},
    {"its", "it's"},
    {"then", "than"},
    {"affect", "effect"},
    {"who's", "whose"},
    {"loose", "lose"},
]


def _group_for(word: str) -> set[str] | None:
    lw = word.lower()
    for group in _CONFUSABLE_GROUPS:
        if lw in group:
            return group
    return None


_PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+(\w+ed|"
    r"born|done|gone|known|made|seen|shown|taken|written|given|held|"
    r"caught|brought|bought|thought|sold|told|sent|built)\b",
    re.IGNORECASE,
)

_DOUBLE_PUNCT_RE = re.compile(r"([!?.,])\1{1,}")
_DOUBLE_SPACE_RE = re.compile(r"[^\S\n]{2,}")


def _rule_confusables(text: str) -> List[Annotation]:
    out: List[Annotation] = []
    for match in _WORD_RE.finditer(text):
        word = match.group(0)
        group = _group_for(word)
        if not group:
            continue
        others = sorted(group - {word.lower()})
        hint = _CONFUSABLES.get(word.lower(), "")
        out.append(
            Annotation(
                kind=AnnotationKind.GRAMMAR,
                severity=Severity.NOTICE,
                message=f'"{word}" — commonly confused with {", ".join(others)}. {hint}',
                start=match.start(),
                end=match.end(),
                span_text=word,
                suggestions=others,
                rule_id="grammar/confusable_homophone",
            )
        )
    return out


def _rule_doubled_word(text: str) -> List[Annotation]:
    out: List[Annotation] = []
    for match in re.finditer(r"\b([A-Za-z']+)\s+\1\b", text, re.IGNORECASE):
        out.append(
            Annotation(
                kind=AnnotationKind.GRAMMAR,
                severity=Severity.WARNING,
                message=f'Word repeated: "{match.group(1)} {match.group(1)}".',
                start=match.start(),
                end=match.end(),
                span_text=match.group(0),
                suggestions=[match.group(1)],
                rule_id="grammar/doubled_word",
            )
        )
    return out


def _rule_sentence_initial_lowercase(text: str) -> List[Annotation]:
    out: List[Annotation] = []
    pos = 0
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sentence, pos)
        if start == -1:
            start = pos
        pos = start + len(sentence)
        stripped = sentence.lstrip()
        if not stripped:
            continue
        first = stripped[0]
        if first.isalpha() and first.islower():
            offset = start + (len(sentence) - len(stripped))
            out.append(
                Annotation(
                    kind=AnnotationKind.GRAMMAR,
                    severity=Severity.NOTICE,
                    message="Sentence starts with a lowercase letter.",
                    start=offset,
                    end=offset + 1,
                    span_text=first,
                    suggestions=[first.upper()],
                    rule_id="grammar/sentence_initial_lowercase",
                )
            )
    return out


def _rule_long_sentence(text: str, max_words: int = 40) -> List[Annotation]:
    out: List[Annotation] = []
    pos = 0
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sentence, pos)
        if start == -1:
            start = pos
        pos = start + len(sentence)
        word_count = len(_WORD_RE.findall(sentence))
        if word_count > max_words:
            out.append(
                Annotation(
                    kind=AnnotationKind.CADENCE,
                    severity=Severity.INFO,
                    message=f"This sentence runs {word_count} words — might drag when read aloud.",
                    start=start,
                    end=start + len(sentence),
                    span_text=sentence.strip(),
                    suggestions=[],
                    rule_id="cadence/long_sentence",
                    meta={"word_count": word_count},
                )
            )
    return out


def _rule_passive_voice(text: str) -> List[Annotation]:
    out: List[Annotation] = []
    for match in _PASSIVE_RE.finditer(text):
        out.append(
            Annotation(
                kind=AnnotationKind.STYLE,
                severity=Severity.INFO,
                message=f'Possible passive voice: "{match.group(0)}". Consider an active-voice rewrite.',
                start=match.start(),
                end=match.end(),
                span_text=match.group(0),
                suggestions=[],
                rule_id="style/passive_voice",
            )
        )
    return out


def _rule_punctuation_spacing(text: str) -> List[Annotation]:
    out: List[Annotation] = []
    for match in _DOUBLE_PUNCT_RE.finditer(text):
        # Allow intentional ellipses / emphasis like "!!" or "..." to pass
        # quietly if it's exactly an ellipsis; otherwise flag as notice.
        if match.group(0) == "...":
            continue
        out.append(
            Annotation(
                kind=AnnotationKind.GRAMMAR,
                severity=Severity.INFO,
                message=f'Repeated punctuation: "{match.group(0)}".',
                start=match.start(),
                end=match.end(),
                span_text=match.group(0),
                suggestions=[match.group(1)],
                rule_id="grammar/repeated_punctuation",
            )
        )
    for match in _DOUBLE_SPACE_RE.finditer(text):
        out.append(
            Annotation(
                kind=AnnotationKind.GRAMMAR,
                severity=Severity.INFO,
                message="Multiple consecutive spaces.",
                start=match.start(),
                end=match.end(),
                span_text=match.group(0),
                suggestions=[" "],
                rule_id="grammar/double_space",
            )
        )
    return out


class GrammarPass:
    """
    Runs the configured set of deterministic rules over a text and returns
    a flat, sorted list of Annotations. Rules are plain functions of
    `text -> List[Annotation]` so adding a new one is a one-line change,
    and any rule can be disabled per-writer via `disabled_rule_ids`.
    """

    _ALL_RULES: List[Callable[[str], List[Annotation]]] = [
        _rule_confusables,
        _rule_doubled_word,
        _rule_sentence_initial_lowercase,
        _rule_long_sentence,
        _rule_passive_voice,
        _rule_punctuation_spacing,
    ]

    def __init__(self, disabled_rule_ids: set[str] | None = None, max_sentence_words: int = 40):
        self.disabled_rule_ids = disabled_rule_ids or set()
        self.max_sentence_words = max_sentence_words

    def check(self, text: str) -> List[Annotation]:
        results: List[Annotation] = []
        for rule in self._ALL_RULES:
            if rule is _rule_long_sentence:
                found = _rule_long_sentence(text, max_words=self.max_sentence_words)
            else:
                found = rule(text)
            results.extend(a for a in found if a.rule_id not in self.disabled_rule_ids)
        results.sort(key=lambda a: a.start)
        return results
