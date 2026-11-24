"""Per-person persistence for the observation layer.

Layout, one folder per person under data/pubpartner/eq_observation/:
  state.json        baselines, trust weights, scorecards, verdict history, the person's
                    vocabulary (each word they have used and how many times, for typo
                    spotting), and bookkeeping. Rewritten atomically (write, fsync, rename).
  readings.jsonl    one reading per turn: numbers and ids, no message text. Append-only.
  perception.jsonl  perception predictions and the observer feedback on them. Append-only.

Append-only streams keep each turn's disk write small. A stream that grows past twice
its keep limit is rewritten atomically with only the newest rows. A torn last line
(power cut mid-append) is skipped on read, never fatal.

The folder name is a readable slug plus a digest of the exact user id, so two ids that
clean to the same slug ("a/b" and "a_b") can never share a folder. The exact id is also
stored and checked on every load.

Privacy: whole messages and word order are never stored here; the originals stay in
the Verbatim Vault. The vocabulary is still the person's own words, so this folder is
private runtime data. Nothing here is written to Alex Core or used for anyone else.
forget() removes the person's folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "pubcast.eq_observation.person.v2"
STREAMS = ("readings", "perception")


def person_folder_name(user_id: str) -> str:
    raw = str(user_id)
    slug = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw)[:80].strip(".") or "anon"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def _fsync_dir(path: Path) -> None:
    """Make a rename durable where the platform allows it (not available on Windows)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


class PersonStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir) / "pubpartner" / "eq_observation"
        self._locks: Dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    # ---- locking -------------------------------------------------------------------------------
    def lock(self, user_id: str) -> threading.RLock:
        """One lock per person. Re-entrant, so a locked operation may call another."""
        key = person_folder_name(user_id)
        with self._guard:
            return self._locks.setdefault(key, threading.RLock())

    # ---- paths ---------------------------------------------------------------------------------
    def folder(self, user_id: str) -> Path:
        return self.root / person_folder_name(user_id)

    def _state_path(self, user_id: str) -> Path:
        return self.folder(user_id) / "state.json"

    def _stream_path(self, user_id: str, stream: str) -> Path:
        if stream not in STREAMS:
            raise ValueError(f"unknown stream {stream!r}")
        return self.folder(user_id) / f"{stream}.jsonl"

    # ---- state ---------------------------------------------------------------------------------
    def load_state(self, user_id: str) -> Dict[str, Any]:
        fresh = {"schema": SCHEMA, "user_id": str(user_id)}
        path = self._state_path(user_id)
        if not path.exists():
            return fresh
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged file must never block a turn. Keep it for inspection and start neutral.
            try:
                path.replace(path.with_name(path.name + ".damaged-" + uuid.uuid4().hex[:8]))
            except OSError:
                pass
            return {**fresh, "recovered_from_damage": True}
        if not isinstance(data, dict) or data.get("user_id") != str(user_id):
            return fresh
        return data

    def save_state(self, user_id: str, document: Dict[str, Any]) -> None:
        document = {**document, "schema": SCHEMA, "user_id": str(user_id)}
        _atomic_write_text(self._state_path(user_id),
                           json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False))

    # ---- streams -------------------------------------------------------------------------------
    def append(self, user_id: str, stream: str, row: Dict[str, Any]) -> None:
        path = self._stream_path(user_id, stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_stream(self, user_id: str, stream: str) -> List[Dict[str, Any]]:
        path = self._stream_path(user_id, stream)
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a torn line from an interrupted append
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    def compact(self, user_id: str, stream: str, keep: int) -> int:
        """Rewrite a stream with only its newest `keep` rows. Returns the rows kept."""
        rows = self.read_stream(user_id, stream)[-max(1, int(keep)):]
        text = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n" for r in rows)
        _atomic_write_text(self._stream_path(user_id, stream), text)
        return len(rows)

    # ---- removal -------------------------------------------------------------------------------
    def forget(self, user_id: str) -> bool:
        """Remove everything this layer holds about one person, at their request."""
        with self.lock(user_id):
            folder = self.folder(user_id)
            if not folder.exists():
                return False
            shutil.rmtree(folder)
            return True
