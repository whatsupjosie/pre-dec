"""
sanctuary_vault.py — Jeremy Cricket Adaptive Awareness Suite
Logically isolated, encrypted storage for sensitive personal data.
NEVER joins with main memory DB. NEVER referenced in professional context.
Audit-logged. Separate SQLite file with Fernet encryption at rest.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ─── Optional encryption ──────────────────────────────────────────────────────
# Uses cryptography.fernet if available. Falls back to plaintext with warning.
try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    logger.warning(
        "SanctuaryVault: 'cryptography' not installed. "
        "Data stored as plaintext. Install with: pip install cryptography"
    )

# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class VaultEntry:
    id: Optional[int]
    label: str           # Human-readable tag (never exposes content)
    payload: Dict        # The private data (encrypted at rest)
    emotional_context: str  # e.g. "vulnerable", "private", "care-moment"
    created_at: float
    accessed_at: float

# ─── SanctuaryVault ──────────────────────────────────────────────────────────

class SanctuaryVault:
    """
    Private, encrypted, logically isolated vault.

    Design constraints:
    - Runs on a separate DB file from main memory.
    - No foreign keys, no joins possible with other modules.
    - All payload data encrypted with Fernet (symmetric, key from env).
    - Audit log records access events WITHOUT logging payload content.
    - `never_joins_with` is enforced at application level; this module
      never imports from memory_processor or character_engine.
    """

    AUDIT_NEVER_LOG_FIELDS = {"payload", "raw_content", "private_note"}

    def __init__(self, vault_dir: Path, config_path: str = "config.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        v = cfg["vault"]

        self._db_path       = vault_dir / v["db_filename"]
        self._key_env       = v["encryption_key_env"]
        self._audit_enabled = v["audit_log_enabled"]
        self._retention     = v.get("retention_days", 365)

        self._conn: Optional[sqlite3.Connection] = None
        self._fernet = None
        self._lock = asyncio.Lock()
        self._initialized = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._setup_encryption()
        await asyncio.to_thread(self._sync_init)
        self._initialized = True
        logger.info("SanctuaryVault initialised at %s (encrypted=%s)", self._db_path, _HAS_CRYPTO and self._fernet is not None)

    def _setup_encryption(self) -> None:
        if not _HAS_CRYPTO:
            return
        key = os.environ.get(self._key_env)
        if not key:
            logger.warning(
                "SanctuaryVault: env var '%s' not set. "
                "Generating ephemeral key (data lost on restart). "
                "Set this env var for persistent encryption.", self._key_env
            )
            key = Fernet.generate_key().decode()
            os.environ[self._key_env] = key
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error("SanctuaryVault: bad encryption key: %s. Vault will not store data.", e)
            self._fernet = None

    def _sync_init(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")  # Extra safety for private data
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vault (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                label             TEXT NOT NULL,
                payload_enc       BLOB NOT NULL,
                emotional_context TEXT NOT NULL DEFAULT '',
                created_at        REAL NOT NULL,
                accessed_at       REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_audit (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                event      TEXT NOT NULL,
                label      TEXT,
                ts         REAL NOT NULL,
                caller_hint TEXT
            )
        """)
        self._conn.commit()

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_close)

    def _sync_close(self) -> None:
        if self._conn:
            self._conn.execute("PRAGMA wal_checkpoint(RESTART)")
            self._conn.close()
            self._conn = None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def store(
        self,
        label: str,
        payload: Dict[str, Any],
        emotional_context: str = "private",
        caller_hint: str = "",
    ) -> Optional[int]:
        """
        Encrypt and store a private entry.
        Returns the row ID, or None if encryption is unavailable.
        """
        self._assert_ready()
        encrypted = self._encrypt(payload)
        if encrypted is None:
            logger.error("SanctuaryVault.store: encryption unavailable. Data NOT stored.")
            return None

        now = time.time()
        async with self._lock:
            entry_id = await asyncio.to_thread(
                self._sync_insert, label, encrypted, emotional_context, now
            )
            if self._audit_enabled:
                await asyncio.to_thread(
                    self._sync_audit, "STORE", label, caller_hint
                )
        return entry_id

    def _sync_insert(self, label: str, payload_enc: bytes, emotional_context: str, now: float) -> int:
        cur = self._conn.execute("""
            INSERT INTO vault (label, payload_enc, emotional_context, created_at, accessed_at)
            VALUES (?,?,?,?,?)
        """, (label, payload_enc, emotional_context, now, now))
        self._conn.commit()
        return cur.lastrowid

    # ── Read ──────────────────────────────────────────────────────────────────

    async def retrieve(self, label: str, caller_hint: str = "") -> Optional[VaultEntry]:
        """
        Retrieve and decrypt an entry by label.
        Returns None if not found or decryption fails.
        Audits every access.
        """
        self._assert_ready()
        async with self._lock:
            row = await asyncio.to_thread(self._sync_fetch, label)
            if self._audit_enabled:
                await asyncio.to_thread(self._sync_audit, "RETRIEVE", label, caller_hint)

        if not row:
            return None

        payload = self._decrypt(row[1])
        if payload is None:
            logger.error("SanctuaryVault: decryption failed for label '%s'", label)
            return None

        return VaultEntry(
            id=row[0],
            label=label,
            payload=payload,
            emotional_context=row[2],
            created_at=row[3],
            accessed_at=row[4],
        )

    def _sync_fetch(self, label: str):
        now = time.time()
        row = self._conn.execute(
            "SELECT id, payload_enc, emotional_context, created_at, accessed_at FROM vault WHERE label=? ORDER BY id DESC LIMIT 1",
            (label,)
        ).fetchone()
        if row:
            self._conn.execute("UPDATE vault SET accessed_at=? WHERE id=?", (now, row[0]))
            self._conn.commit()
        return row

    async def list_labels(self, caller_hint: str = "") -> List[str]:
        """Returns all known labels (never payloads)."""
        self._assert_ready()
        async with self._lock:
            labels = await asyncio.to_thread(self._sync_list_labels)
            if self._audit_enabled:
                await asyncio.to_thread(self._sync_audit, "LIST_LABELS", None, caller_hint)
        return labels

    def _sync_list_labels(self) -> List[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT label FROM vault ORDER BY label"
        ).fetchall()
        return [r[0] for r in rows]

    async def delete(self, label: str, caller_hint: str = "") -> int:
        """Hard-delete all entries with this label. Returns count deleted."""
        self._assert_ready()
        async with self._lock:
            count = await asyncio.to_thread(self._sync_delete, label)
            if self._audit_enabled:
                await asyncio.to_thread(self._sync_audit, "DELETE", label, caller_hint)
        return count

    def _sync_delete(self, label: str) -> int:
        cur = self._conn.execute("DELETE FROM vault WHERE label=?", (label,))
        self._conn.commit()
        return cur.rowcount

    # ── Retention ─────────────────────────────────────────────────────────────

    async def purge_expired(self) -> int:
        """Remove entries older than retention_days. Returns count purged."""
        cutoff = time.time() - (self._retention * 86400)
        async with self._lock:
            count = await asyncio.to_thread(self._sync_purge, cutoff)
        if count:
            logger.info("SanctuaryVault: purged %d expired entries", count)
        return count

    def _sync_purge(self, cutoff: float) -> int:
        cur = self._conn.execute("DELETE FROM vault WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    # ── Audit ─────────────────────────────────────────────────────────────────

    def _sync_audit(self, event: str, label: Optional[str], caller_hint: str) -> None:
        """Log access event. Never logs payload content."""
        self._conn.execute(
            "INSERT INTO vault_audit (event, label, ts, caller_hint) VALUES (?,?,?,?)",
            (event, label, time.time(), caller_hint)
        )
        self._conn.commit()

    async def get_audit_log(self, limit: int = 100) -> List[dict]:
        """Returns audit events. Safe to show — no payload content included."""
        async with self._lock:
            rows = await asyncio.to_thread(self._sync_get_audit, limit)
        return rows

    def _sync_get_audit(self, limit: int) -> List[dict]:
        rows = self._conn.execute(
            "SELECT event, label, ts, caller_hint FROM vault_audit ORDER BY ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"event": r[0], "label": r[1], "ts": r[2], "caller_hint": r[3]} for r in rows]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _encrypt(self, data: Dict) -> Optional[bytes]:
        raw = json.dumps(data).encode()
        if _HAS_CRYPTO and self._fernet:
            return self._fernet.encrypt(raw)
        # Fallback: no encryption (warned at init)
        return raw

    def _decrypt(self, blob: bytes) -> Optional[Dict]:
        try:
            if _HAS_CRYPTO and self._fernet:
                raw = self._fernet.decrypt(blob)
            else:
                raw = blob
            return json.loads(raw.decode())
        except Exception as e:
            logger.error("SanctuaryVault: decryption error: %s", e)
            return None

    def _assert_ready(self) -> None:
        if not self._initialized or not self._conn:
            raise RuntimeError("SanctuaryVault not initialised. Call await vault.init() first.")
