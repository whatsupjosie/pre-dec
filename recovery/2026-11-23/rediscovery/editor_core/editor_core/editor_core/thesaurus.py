"""
thesaurus.py — offline thesaurus backed by WordNet.

WordNet ships as a downloadable NLTK corpus (~10MB, one-time download from
raw.githubusercontent.com/nltk/nltk_data, then fully offline forever after).
This is deliberately not model-backed: synonym lookup is a solved lookup
problem, and a 2B local model is a worse, slower thesaurus than a real
lexical database.

WordNet doesn't carry a "gritty / poetic / clinical / archaic" register tag
out of the box (that was aspirational framing from the earlier design
conversation) — what it DOES give us, honestly:
  - synonyms grouped by sense/definition (so "happy" -> "felicitous" only
    shows up under the "marked by good fortune" sense, not the "glad" sense)
  - antonyms
  - part of speech
This module is the honest version of that idea: sense-grouped synonyms
instead of a flat undifferentiated list, which is the main thing that
makes a thesaurus lookup actually useful for a writer instead of noise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

try:
    from nltk.corpus import wordnet as wn
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "nltk is required for ThesaurusLookup. `pip install nltk` then "
        "`python -m nltk.downloader wordnet`."
    ) from exc


_POS_LABEL = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",  # satellite adjective
    "r": "adverb",
}


@dataclass(slots=True)
class SenseGroup:
    definition: str
    part_of_speech: str
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)


class ThesaurusLookup:
    def __init__(self, ensure_downloaded: bool = True):
        if ensure_downloaded:
            self._ensure_wordnet()

    @staticmethod
    def _ensure_wordnet() -> None:
        import nltk

        try:
            nltk.data.find("corpora/wordnet")
        except LookupError:
            nltk.download("wordnet", quiet=True)

    def lookup(self, word: str, max_senses: int = 6, max_per_sense: int = 8) -> List[SenseGroup]:
        word = word.strip().lower()
        groups: List[SenseGroup] = []
        for syn in wn.synsets(word)[:max_senses]:
            synonyms: List[str] = []
            antonyms: List[str] = []
            for lemma in syn.lemmas():
                name = lemma.name().replace("_", " ")
                if name.lower() != word and name not in synonyms:
                    synonyms.append(name)
                for ant in lemma.antonyms():
                    ant_name = ant.name().replace("_", " ")
                    if ant_name not in antonyms:
                        antonyms.append(ant_name)
            if not synonyms:
                continue
            groups.append(
                SenseGroup(
                    definition=syn.definition(),
                    part_of_speech=_POS_LABEL.get(syn.pos(), syn.pos()),
                    synonyms=synonyms[:max_per_sense],
                    antonyms=antonyms[:max_per_sense],
                )
            )
        return groups

    def flat_synonyms(self, word: str, limit: int = 12) -> List[str]:
        """Convenience: a single deduped list, for quick inline suggestions."""
        seen: Dict[str, None] = {}
        for group in self.lookup(word):
            for syn in group.synonyms:
                seen.setdefault(syn, None)
        return list(seen.keys())[:limit]
