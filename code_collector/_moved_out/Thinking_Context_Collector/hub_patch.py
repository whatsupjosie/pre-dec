"""
hub_patch.py
════════════
Patch for hub.py — fixes Break 4 from the handoff doc.

hub.get_recent_history() reads JSONL files synchronously inside an async
method. Jeremy's watcher calls this every 5 seconds per room. On a busy
server with multiple rooms this blocks the event loop noticeably.

HOW TO USE:
  1. Open hub.py.
  2. Find get_recent_history() — it currently reads files directly.
  3. Replace the entire method with the two methods below (one async, one sync).
  4. Make sure `import asyncio` and `import json` are at the top of hub.py.

Rear View Foresight LLC — Feic Mo Chroí
"""

# ── Paste both methods into your Hub class ────────────────────────────────────

import asyncio
import json
from pathlib import Path


class _HubStub:
    """Stub wrapper — extract the two methods and paste into your real Hub."""

    async def get_recent_history(self, room: str, limit: int = 12) -> list:
        """
        Return the most recent `limit` messages from the room's JSONL log.
        Runs file I/O in a thread executor so the event loop stays unblocked.
        """
        history_path = self._log_path(room)
        if not history_path.exists():
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._read_history_sync, history_path, limit
        )

    def _read_history_sync(self, path: Path, limit: int) -> list:
        """Synchronous JSONL reader — runs in a thread pool via run_in_executor."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []

        recent = lines[-limit:] if len(lines) > limit else lines
        result = []
        for line in recent:
            line = line.strip()
            if not line:
                continue
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return result


# ── Notes ─────────────────────────────────────────────────────────────────────
#
# If your Hub doesn't have _log_path(), it probably computes the path inline.
# Just pull that logic into a helper first:
#
#     def _log_path(self, room: str) -> Path:
#         return self._log_dir / f"{room}.jsonl"
#
# Then the two methods above will work as-is.
#
# ─────────────────────────────────────────────────────────────────────────────
