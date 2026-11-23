"""Cartridge identity and memory must reach FCP1 without crossing users/rooms."""
from __future__ import annotations

from pathlib import Path

import pytest

from modules.pubpartner_cartridge_context import (
    CartridgeContextBridge,
    CartridgeContextError,
)
from modules.pubpartner_profiles import PubPartnerProfileStore
from modules.pubpartner_core import PubPartnerSpine
from pubpartner.cartridge import init_cartridge, load_cartridge


def _make(tmp_path: Path, owner: str = "author") -> Path:
    cart_dir = tmp_path / "pubpartner" / "cartridges" / "nova"
    init_cartridge(cart_dir, "Nova", "A curious radio host", "slow and crisp", "radio slang")
    (cart_dir / "character.yaml").write_text(
        "name: Nova\nsummary: A curious radio host\nvalues:\n  - Never invent a guest's history\n"
        "boundaries:\n  - Do not fabricate memories\ntendencies:\n  - Ask about music\n", encoding="utf-8"
    )
    with load_cartridge(cart_dir) as cartridge:
        cartridge.memory.add("Nova once discovered a rare synth in the attic.", "episodic", importance=0.9)
        cartridge.memory.add("Nova loves 1940s radio plays.", "semantic", importance=0.7)
    profiles = PubPartnerProfileStore(tmp_path)
    profiles.save_profile("friend", "nova", {
        "id": "nova", "display_name": "Nova", "self_concept": "A curious radio host",
        "tone": ["warm"], "cadence": ["slow"], "boundaries": ["Respect the user"],
        "cartridge": {"id": "nova", "format": "pubpartner-cartridge",
                      "path": "pubpartner/cartridges/nova", "created_by": owner},
    })
    return cart_dir


def test_registered_cartridge_recalls_identity_voice_and_memories(tmp_path):
    _make(tmp_path)
    bridge = CartridgeContextBridge(tmp_path)
    recall = bridge.resolve(friend_id="nova", user_id="author", query="synth", audience="private")
    assert recall and recall.owner_matched
    assert recall.cartridge["summary"] == "A curious radio host"
    assert recall.cartridge["voice"]["vocabulary"] == "radio slang"
    assert recall.cartridge["values"] == ["Never invent a guest's history"]
    assert recall.memories and recall.memories[0]["id"].startswith("cartridge:nova:")
    assert recall.memories[0]["source"] == "character_cartridge"
    enriched = bridge.enrich_friend({"boundaries": ["Respect the user"]}, recall)
    assert "Respect the user" in enriched["boundaries"]
    assert "Do not fabricate memories" in enriched["boundaries"]
    assert "Value: Never invent a guest's history" in enriched["principles"]


@pytest.mark.parametrize("request_user,audience", [
    ("stranger", "private"), ("author", "shared"), ("author", "public")
])
def test_cartridge_memories_not_exposed_to_others_or_public_rooms(tmp_path, request_user, audience):
    _make(tmp_path)
    recall = CartridgeContextBridge(tmp_path).resolve(
        friend_id="nova", user_id=request_user, query="synth", audience=audience
    )
    assert recall and recall.memories == ()
    assert recall.cartridge["id"] == "nova"


def test_missing_or_unregistered_cartridge_is_not_injected(tmp_path):
    profiles = PubPartnerProfileStore(tmp_path)
    assert CartridgeContextBridge(tmp_path).resolve(
        friend_id="alex", user_id="author", query="synth", audience="private"
    ) is None
    profiles.save_profile("friend", "bad", {
        "id": "bad", "cartridge": {"id": "nova", "format": "pubpartner-cartridge", "path": "../nova"}
    })
    with pytest.raises(CartridgeContextError, match="registration mismatch"):
        CartridgeContextBridge(tmp_path).resolve(friend_id="bad", user_id="author", query="", audience="private")


def test_rejects_unsafe_file_links(tmp_path):
    cart_dir = _make(tmp_path)
    (cart_dir / "memories.jsonl").unlink()
    (cart_dir / "memories.jsonl").symlink_to(tmp_path / "out_of_folder")
    with pytest.raises(CartridgeContextError, match="symlink"):
        CartridgeContextBridge(tmp_path).resolve(friend_id="nova", user_id="author", query="", audience="private")


@pytest.mark.asyncio
async def test_main_spine_includes_cartridge_in_fcp1_and_keeps_vault(tmp_path):
    _make(tmp_path)
    spine = PubPartnerSpine(tmp_path, companion_advisory_enabled=False)
    result = await spine.build_turn_packet(
        user_id="author", session_id="test_session", message="Tell me about the synth",
        friend="nova", room_id="pubpartner", log_turn=False,
    )
    packet = result["fcp1"]
    assert result["cartridge_context"]["status"] == "ok"
    assert packet["cartridge"]["id"] == "nova"
    assert "Never invent a guest's history" in packet["cartridge"]["values"]
    assert any(m["src"] == "character_cartridge" for m in packet["m"])
    assert "cartridge=" in result["llm_prompt_text"]
    restored = spine.vault.load(user_id="author", session_id="test_session", source_id=result["source"]["id"])
    assert restored.text == "Tell me about the synth"
    other = await spine.build_turn_packet(
        user_id="other", session_id="test_other", message="Tell me about the synth",
        friend="nova", room_id="pubpartner", log_turn=False,
    )
    assert not any(m["src"] == "character_cartridge" for m in other["fcp1"]["m"])
