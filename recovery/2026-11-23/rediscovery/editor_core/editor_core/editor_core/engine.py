"""
engine.py — runs the deterministic passes over a buffer of text and
returns one merged, sorted list of Annotations.

This is intentionally dumb: it does not decide *when* to run (that's the
caller's job — e.g. on pause, on commit-to-manuscript, on demand) and it
does not call any model. It is the "editor" half of the split described
in conversation: spelling + grammar + style/cadence run here, instantly,
offline, every time. The plot-hole/continuity pass is model-backed and
lives in `plothole.py`, invoked separately because it's slower and costs
a model call.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .annotations import Annotation
from .grammar import GrammarPass
from .spelling import SpellingPass


class EditorEngine:
    def __init__(
        self,
        spelling: Optional[SpellingPass] = None,
        grammar: Optional[GrammarPass] = None,
        memory_data_dir: Optional[Path] = None,
    ):
        self.spelling = spelling or SpellingPass()
        self.grammar = grammar or GrammarPass()
        self._memory_data_dir = memory_data_dir

    def check(self, text: str) -> List[Annotation]:
        results: List[Annotation] = []
        results.extend(self.spelling.check(text))
        results.extend(self.grammar.check(text))
        results.sort(key=lambda a: a.start)
        return results

    def check_and_log(
        self,
        text: str,
        *,
        session_id: str,
        project_id: str,
        user_id: str,
        room_id: str,
    ) -> List[Annotation]:
        """
        Same as `check`, but also writes a summary event into the project's
        existing memory_engine SQLite store — this is what feeds the
        long-term style/habit analytics (crutch words, passive-voice rate,
        etc.) described in the design conversation. Requires
        memory_data_dir to be set; falls back to a no-op log if the
        project's memory_engine module isn't importable in this
        environment (keeps editor_core usable standalone/for tests).
        """
        annotations = self.check(text)
        if self._memory_data_dir is None:
            return annotations
        try:
            import memory_engine  # the project's real module
        except ImportError:
            return annotations

        counts: Dict[str, int] = {}
        for a in annotations:
            counts[a.rule_id] = counts.get(a.rule_id, 0) + 1

        memory_engine.record_event(
            self._memory_data_dir,
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            room_id=room_id,
            feature_id="editor_core",
            event_type="editing_pass",
            summary=f"{len(annotations)} annotation(s) on {len(text)} chars",
            payload={
                "rule_counts": counts,
                "text_length": len(text),
                "ts": time.time(),
            },
        )
        return annotations
