"""Per-person persistence for the observation layer.

One file per person under data/pubpartner/eq_observation/. It holds numbers
(baselines, trust weights, scorecards, readings with turn and source ids) and
the person's vocabulary: each word they have used and how many times, for typo
spotting (capped by the vocabulary dial). It does not hold whole messages or
word order; the original messages stay in the Verbatim Vault. The vocabulary is
still the person's own words, so this file is private runtime data.

Privacy: this is the person's own data. Nothing here is written to Alex Core,
shared, or used for anyone else. forget() removes the whole file.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict

SCHEMA = "pubcast.eq_observation.person.v1"


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", str(value))[:96] or "anon"


class PersonStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir) / "pubpartner" / "eq_observation"
        self._locks: Dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def lock(self, user_id: str) -> threading.Lock:
        key = _slug(user_id)
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def path(self, user_id: str) -> Path:
        return self.root / (_slug(user_id) + ".json")

    def load(self, user_id: str) -> Dict[str, Any]:
        path = self.path(user_id)
        if not path.exists():
            return {"schema": SCHEMA, "user_id": str(user_id)}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged file must never block a turn. Keep it for inspection and start neutral.
            try:
                path.replace(path.with_name(path.name + ".damaged-" + uuid.uuid4().hex[:8]))
            except OSError:
                pass
            return {"schema": SCHEMA, "user_id": str(user_id), "recovered_from_damage": True}
        if not isinstance(data, dict) or data.get("user_id") != str(user_id):
            return {"schema": SCHEMA, "user_id": str(user_id)}
        return data

    def save(self, user_id: str, document: Dict[str, Any]) -> None:
        path = self.path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {**document, "schema": SCHEMA, "user_id": str(user_id)}
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("x", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()

    def forget(self, user_id: str) -> bool:
        path = self.path(user_id)
        with self.lock(user_id):
            if path.exists():
                path.unlink()
                return True
        return False
