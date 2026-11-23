"""
editor_core — deterministic, offline-first editing layer for the
collaborative writing engine.

Design principle (per project decision): most of what makes a good editor
is lookup tables and rule engines, not a language model. Spelling, grammar,
thesaurus, and rhyme lookups all run here with zero model calls, zero
network dependency at runtime, and zero latency worth mentioning. The one
pass that genuinely needs a model (plot-hole / continuity reasoning) is
kept separate in `plothole.py` and is the only file in this package that
is allowed to call out to a model profile.
"""

from .annotations import Annotation, AnnotationKind, Severity
from .spelling import SpellingPass
from .grammar import GrammarPass
from .thesaurus import ThesaurusLookup
from .rhyme import RhymeDictionary
from .engine import EditorEngine

__all__ = [
    "Annotation",
    "AnnotationKind",
    "Severity",
    "SpellingPass",
    "GrammarPass",
    "ThesaurusLookup",
    "RhymeDictionary",
    "EditorEngine",
]
