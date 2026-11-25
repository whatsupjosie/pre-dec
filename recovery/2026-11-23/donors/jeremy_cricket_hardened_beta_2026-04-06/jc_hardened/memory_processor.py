"""
memory_processor.py — Jeremy Cricket Adaptive Awareness Suite
Storybook Memory: stores events as "Stories of Growth" in partitioned Chapters.
Enforces eviction, query timeout, and chapter-gating per current Mode.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)

# ─── Chapter Enum ─────────────────────────────────────────────────────────────

class Chapter(str, Enum):
    ESSENTIALS        = "ESSENTIALS"
    SUPPORT           = "SUPPORT"
    GROWTH            = "GROWTH"
    COMPLEX_LOGISTICS = "COMPLEX_LOGISTICS"

# ─── Memory dataclass ─────────────────────────────────────────────────────────

@dataclass
class StoryMemory:
    """A memory stored as a narrative fragment."""
    id: Optional[int]
    character_id: str
    chapter: Chapter
    headline: str          # One-line story title
    narrative: str         # The story: what happened, why it mattered
    lesson: str            # What was learned / growth note
    importance: int        # 1–10
    emotional_tag: str     # e.g. "breakthrough", "struggle", "comfort", "boundary"
    created_at: float
    accessed_at: float

    def to_story(self) -> str:
        """Human-readable story format used in recall responses."""
        return (
            f"[{self.chapter.value}] {self.headline}\n"
            f"  Story: {self.narrative}\n"
            f"  Growth note: {self.lesson}\n"
            f"  Feeling: {self.emotional_tag} (importance {self.importance}/10)"
        )

# ─── Chapter access map ───────────────────────────────────────────────────────

CHAPTER_ACCESS = {
    "AMBIENT":            [Chapter.ESSENTIALS, Chapter.SUPPORT, Chapter.GROWTH, Chapter.COMPLEX_LOGISTICS],
    "ATTENTIVE":          [Chapter.ESSENTIALS, Chapter.SUPPORT, Chapter.GROWTH],
    "CARE":               [Chapter.ESSENTIALS, Chapter.SUPPORT],
    "TOTAL_CARE_MANDATE": [Chapter.ESSENTIALS],
}

# ─── MemoryProcessor ──────────────────────────────────────────────────────────

class MemoryProcessor:
    """
    Async-safe Storybook Memory store.
    One instance per character. Backed by SQLite WAL.
    """

    def __init__(self, character_id: str, db_dir: Path, config_path: str = "config.yaml"):
        self.character_id = character_id
        self._db_path = db_dir / f"{character_id}_stories.db"
        self._lock = asyncio.Lock()
        self._write_buffer: List[StoryMemory] = []

        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        mem = cfg["memory"]
        self._max_memories     = mem["max_memories_per_character"]
        self._eviction_target  = mem["eviction_target"]
        self._recall_timeout   = mem["recall_timeout_seconds"]
        self._batch_size       = mem["write_batch_size"]

        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._sync_init)
        logger.info("MemoryProcessor[%s] initialised at %s", self.character_id, self._db_path)

    def _sync_init(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL,
                chapter      TEXT NOT NULL,
                headline     TEXT NOT NULL,
                narrative    TEXT NOT NULL,
                lesson       TEXT NOT NULL DEFAULT '',
                importance   INTEGER NOT NULL DEFAULT 5,
                emotional_tag TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                accessed_at  REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_char_chapter ON stories(character_id, chapter)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_importance ON stories(importance DESC)"
        )
        self._conn.commit()

    async def close(self) -> None:
        async with self._lock:
            await self._flush_buffer()
            await asyncio.to_thread(self._sync_close)

    def _sync_close(self) -> None:
        if self._conn:
            self._conn.execute("PRAGMA wal_checkpoint(RESTART)")
            self._conn.close()
            self._conn = None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def remember(self, memory: StoryMemory) -> None:
        """
        Buffer a memory. Flushes automatically when buffer hits batch_size.
        """
        async with self._lock:
            self._write_buffer.append(memory)
            if len(self._write_buffer) >= self._batch_size:
                await self._flush_buffer()
                await self._maybe_evict()

    async def _flush_buffer(self) -> None:
        """Write buffered memories to DB. Must be called inside lock."""
        if not self._write_buffer:
            return
        batch = list(self._write_buffer)
        self._write_buffer.clear()
        await asyncio.to_thread(self._sync_insert_batch, batch)

    def _sync_insert_batch(self, batch: List[StoryMemory]) -> None:
        now = time.time()
        rows = [
            (m.character_id, m.chapter.value, m.headline, m.narrative,
             m.lesson, m.importance, m.emotional_tag, now, now)
            for m in batch
        ]
        self._conn.executemany("""
            INSERT INTO stories
                (character_id, chapter, headline, narrative, lesson,
                 importance, emotional_tag, created_at, accessed_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, rows)
        self._conn.commit()

    # ── Eviction ──────────────────────────────────────────────────────────────

    async def _maybe_evict(self) -> None:
        """Trim DB to eviction_target if over max_memories. Called inside lock."""
        count = await asyncio.to_thread(self._sync_count)
        if count > self._max_memories:
            to_delete = count - self._eviction_target
            await asyncio.to_thread(self._sync_evict, to_delete)
            logger.info("MemoryProcessor[%s] evicted %d stories", self.character_id, to_delete)

    def _sync_count(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM stories WHERE character_id=?", (self.character_id,)
        ).fetchone()[0]

    def _sync_evict(self, n: int) -> None:
        """Delete n lowest-importance, oldest memories."""
        self._conn.execute("""
            DELETE FROM stories WHERE id IN (
                SELECT id FROM stories
                WHERE character_id=?
                ORDER BY importance ASC, accessed_at ASC
                LIMIT ?
            )
        """, (self.character_id, n))
        self._conn.commit()

    # ── Recall ────────────────────────────────────────────────────────────────

    async def recall(
        self,
        query: str,
        mode: str = "AMBIENT",
        min_importance: int = 1,
        limit: int = 10,
    ) -> List[StoryMemory]:
        """
        Retrieve relevant memories. Automatically gates chapters by mode.
        Returns [] on timeout — never hangs inference.
        """
        allowed_chapters = [c.value for c in CHAPTER_ACCESS.get(mode, CHAPTER_ACCESS["AMBIENT"])]
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync_recall, query, allowed_chapters, min_importance, limit
                ),
                timeout=self._recall_timeout,
            )
            return results
        except asyncio.TimeoutError:
            logger.warning("MemoryProcessor[%s] recall timed out (mode=%s)", self.character_id, mode)
            return []
        except Exception as e:
            logger.error("MemoryProcessor[%s] recall error: %s", self.character_id, e)
            return []

    def _sync_recall(
        self, query: str, chapters: List[str], min_importance: int, limit: int
    ) -> List[StoryMemory]:
        placeholders = ",".join("?" for _ in chapters)
        rows = self._conn.execute(f"""
            SELECT id, character_id, chapter, headline, narrative, lesson,
                   importance, emotional_tag, created_at, accessed_at
            FROM stories
            WHERE character_id=?
              AND chapter IN ({placeholders})
              AND importance >= ?
              AND (headline LIKE ? OR narrative LIKE ? OR lesson LIKE ? OR emotional_tag LIKE ?)
            ORDER BY importance DESC, accessed_at DESC
            LIMIT ?
        """, (self.character_id, *chapters, min_importance,
              f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit)
        ).fetchall()

        # Update accessed_at for returned memories
        ids = [r[0] for r in rows]
        if ids:
            ph = ",".join("?" for _ in ids)
            self._conn.execute(
                f"UPDATE stories SET accessed_at=? WHERE id IN ({ph})",
                (time.time(), *ids)
            )
            self._conn.commit()

        return [
            StoryMemory(
                id=r[0], character_id=r[1], chapter=Chapter(r[2]),
                headline=r[3], narrative=r[4], lesson=r[5],
                importance=r[6], emotional_tag=r[7],
                created_at=r[8], accessed_at=r[9],
            )
            for r in rows
        ]

    async def count(self) -> int:
        return await asyncio.to_thread(self._sync_count)
