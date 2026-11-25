from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class MemoryAdapter:
    """
    Minimal safe memory adapter.

    In Prime, this should adapt to BlackBox / companion memory.
    Here it writes JSONL so the package is testable and standalone.

    Do not store raw secrets or private full transcripts here.
    Store safe summaries and debrief lessons only.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: List[Dict[str, Any]] = []

    def record_event(self, event: Dict[str, Any]) -> None:
        safe = self._scrub(event)
        self.events.append(safe)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")

    def latest(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.events[-n:]

    @staticmethod
    def _scrub(event: Dict[str, Any]) -> Dict[str, Any]:
        blocked = {"raw_text", "full_transcript", "token", "secret", "api_key"}
        return {k: v for k, v in event.items() if k not in blocked}
