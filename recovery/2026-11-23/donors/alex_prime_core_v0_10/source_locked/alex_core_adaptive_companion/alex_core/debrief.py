from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .models import DebriefRecord


class DebriefEngine:
    """
    Converts after-the-fact feedback into EQ learning.

    Alex must be ready to be wrong. Debrief is where the user corrects:
    - what Alex thought was happening,
    - what actually helped,
    - what hurt,
    - what should change next time.
    """

    def summarize_lessons(self, record: DebriefRecord) -> Dict[str, Any]:
        lessons = list(record.lessons)

        if record.corrected_need:
            lessons.append(f"Corrected need: {record.corrected_need.value}")

        if record.corrected_protocol:
            lessons.append(f"Corrected protocol: {record.corrected_protocol.value}")

        for item in record.what_helped:
            lessons.append(f"Do more of: {item}")

        for item in record.what_hurt:
            lessons.append(f"Do less of: {item}")

        return {
            "kind": "alex_debrief",
            "event_id": record.event_id,
            "lessons": lessons,
            "record": asdict(record),
        }
