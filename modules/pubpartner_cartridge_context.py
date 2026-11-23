"""Bridge authored PubPartner cartridges into the FCP1 live-turn pathway.

Cartridge files remain the authority for character identity and voice. The
cartridge's SQLite store is only read here; user-specific relationship facts
remain in RelationshipEngine / the owner's vessel, never in a shared cartridge.
No database schema migration or replacement is performed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_CARTRIDGE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")
_MAX_FILE_BYTES = 64 * 1024
_MAX_MEMORIES = 6
_MAX_SUMMARY = 480
_MAX_FIELD = 240


class CartridgeContextError(RuntimeError):
    """A registered cartridge is broken or its files are inaccessible."""


@dataclass(frozen=True)
class CartridgeRecall:
    cartridge: dict[str, Any]
    memories: tuple[dict[str, Any], ...]
    owner_matched: bool


class CartridgeContextBridge:
    """Read-only turn context for an existing, registered character cartridge.

    There is intentionally no code here to learn from conversations. Verbatim
    archival, explicit lessons, work notes, and user-owned memory already have
    their own authors and retention/authorization policies in PubPartner.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).resolve()
        self.root = (self.data_dir / "pubpartner" / "cartridges").resolve()
        self.profile_root = (self.data_dir / "pubpartner" / "profiles" / "friends").resolve()

    def _profile(self, friend_id: str) -> Optional[dict[str, Any]]:
        if not _CARTRIDGE_ID.fullmatch(friend_id):
            return None
        path = self.profile_root / f"{friend_id}.json"
        if not path.is_file() or path.is_symlink():
            return None
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise CartridgeContextError("registered friend profile is too large")
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise CartridgeContextError("registered friend profile is unreadable") from exc
        if not isinstance(result, dict):
            raise CartridgeContextError("registered friend profile must be an object")
        registration = result.get("cartridge")
        if not isinstance(registration, dict):
            return None
        if registration.get("id") != friend_id or registration.get("format") != "pubpartner-cartridge":
            raise CartridgeContextError("friend-to-cartridge registration mismatch")
        if registration.get("path") != f"pubpartner/cartridges/{friend_id}":
            raise CartridgeContextError("friend cartridge path is not canonical")
        return result

    def resolve(
        self,
        *,
        friend_id: str,
        user_id: str,
        query: str,
        audience: str,
        max_memories: int = 4,
    ) -> Optional[CartridgeRecall]:
        profile = self._profile(str(friend_id))
        if profile is None:
            return None
        folder = self.root / friend_id
        if not folder.is_dir() or folder.is_symlink() or folder.resolve().parent != self.root:
            raise CartridgeContextError("registered cartridge folder is missing or unsafe")
        for name in ("character.yaml", "voice_profile.yaml", "appearance.yaml", "memories.db", "memories.jsonl"):
            target = folder / name
            if target.is_symlink():
                raise CartridgeContextError(f"cartridge contains symlink: {name}")
        for name in ("character.yaml", "voice_profile.yaml", "appearance.yaml", "memories.jsonl"):
            target = folder / name
            if target.is_file() and target.stat().st_size > _MAX_FILE_BYTES:
                raise CartridgeContextError(f"cartridge file exceeds allowed size: {name}")
        # Only the authenticated creator can receive memories from the
        # cartridge's shared SQLite file. Other users can see the public
        # character definition without receiving its stored recollections.
        registration = profile["cartridge"]
        owner = str(registration.get("created_by") or "")
        owner_matched = bool(owner) and owner == str(user_id)
        # The existing loader is authoritative for validation and its SQLite
        # retrieval algorithm. Reusing it avoids another competing ranker.
        from pubpartner.cartridge import CartridgeValidationError, load_cartridge

        try:
            cartridge = load_cartridge(folder)
        except (CartridgeValidationError, OSError, ValueError, RuntimeError) as exc:
            raise CartridgeContextError(f"cartridge load failed: {type(exc).__name__}") from exc
        try:
            d = cartridge.definition
            kernel = {
                "id": friend_id,
                "name": d.identity.name[:80],
                "summary": d.identity.summary[:_MAX_SUMMARY],
                "values": [v[:_MAX_FIELD] for v in d.identity.values[:16]],
                "boundaries": [v[:_MAX_FIELD] for v in d.identity.boundaries[:16]],
                "tendencies": [v[:_MAX_FIELD] for v in d.identity.tendencies[:16]],
                "voice": {
                    "cadence": d.voice.cadence[:_MAX_FIELD],
                    "vocabulary": d.voice.vocabulary[:_MAX_FIELD],
                    "verbal_tics": [v[:_MAX_FIELD] for v in d.voice.verbal_tics[:16]],
                    "sentence_length": d.voice.sentence_length[:_MAX_FIELD],
                    "formality": d.voice.formality[:_MAX_FIELD],
                },
                "appearance": {
                    "description": d.appearance.description[:_MAX_SUMMARY],
                    "details": [v[:_MAX_FIELD] for v in d.appearance.details[:16]],
                },
                "memory_policy": "creator_only_private_turns",
            }
            rows = []
            count = min(max(0, int(max_memories)), _MAX_MEMORIES)
            if owner_matched and audience == "private" and count:
                for scored in cartridge.memory.query(str(query), top_k=count):
                    m = scored.memory
                    rows.append({
                        "id": f"cartridge:{friend_id}:{m.id}",
                        "kind": str(m.memory_type),
                        "text": m.text,
                        "importance": max(1, min(10, round(m.importance * 10))),
                        "source": "character_cartridge",
                    })
            return CartridgeRecall(kernel, tuple(rows), owner_matched)
        finally:
            cartridge.close()

    @staticmethod
    def enrich_friend(friend: dict[str, Any], recalled: CartridgeRecall) -> dict[str, Any]:
        """Preserve an authored friend profile while supplying cartridge laws.

        The full cartridge is also included independently in the FCP1 packet;
        merged values here reach older provider prompts that only read f.
        """
        out = dict(friend)
        c = recalled.cartridge
        out.setdefault("self_concept", c["summary"])
        out.setdefault("display_name", c["name"])
        base = list(out.get("principles") or out.get("law") or [])
        for value in c["values"]:
            entry = "Value: " + value
            if entry not in base:
                base.append(entry)
        for value in c["tendencies"]:
            entry = "Tendency: " + value
            if entry not in base:
                base.append(entry)
        out["principles"] = base[:16]
        boundaries = list(out.get("boundaries") or out.get("bound") or [])
        for value in c["boundaries"]:
            if value not in boundaries:
                boundaries.append(value)
        out["boundaries"] = boundaries[:16]
        cadence = list(out.get("cadence") or out.get("cad") or [])
        for entry in (c["voice"]["cadence"], "Vocabulary: " + c["voice"]["vocabulary"]):
            if entry and entry not in cadence:
                cadence.append(entry)
        out["cadence"] = cadence[:16]
        return out
