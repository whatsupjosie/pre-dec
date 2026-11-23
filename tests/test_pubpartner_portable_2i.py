"""Portable 2i host contract: reuse the newer editor and chat, no studio boot.

This exercises route registration, local manuscript storage, and existing
World Chat REST transport without a configured language model.
"""
from pathlib import Path

from fastapi.testclient import TestClient


def test_portable_2i_editor_chat_and_manuscript_routes(tmp_path, monkeypatch):
    import pubpartner_app

    monkeypatch.setattr(pubpartner_app, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "0")

    with TestClient(pubpartner_app.app) as client:
        routes = set(pubpartner_app.app.openapi()["paths"])
        assert "/api/writers-room/documents" in routes
        assert "/api/pubpartner/manuscript/commit" in routes
        assert "/api/chat/rooms/{room_id}" in routes
        assert "/api/chat/rooms/{room_id}/send" in routes

        editor = client.get("/2i")
        assert editor.status_code == 200
        assert "Writer's Room" in editor.text
        assert "/2i-assets" in editor.text or "2i-assets/" in editor.text

        chat = client.get("/2i/chat")
        assert chat.status_code == 200
        assert "2i · Chat" in chat.text
        assert "World Chat" in chat.text

        assert client.get("/2i/chat/archive").status_code == 200
        assert client.get("/2i-assets/reach.js").status_code == 200

        owner = {"X-Client-Id": "owner"}
        config = client.get("/api/writers-room/config", headers=owner)
        assert config.status_code == 200
        assert config.json()["documents"] == "server"

        world = client.get("/api/chat/rooms/world?limit=10", headers=owner)
        assert world.status_code == 200
        assert world.json()["room_id"] == "world"

        assert client.get("/api/pubpartner/app-health").json()["optional_pubcast_studio_started"] is False


def test_portable_2i_is_not_an_old_editor_copy():
    from pubpartner_app import ROOT
    newer = (ROOT / "2i" / "writers-room-v22.html").read_text(encoding="utf-8")
    chat = (ROOT / "static" / "world_chat.html").read_text(encoding="utf-8")
    assert 'href="/2i/chat"' in newer
    assert 'data-world-chat' in chat
    assert (ROOT / "2i" / "2i-assets" / "narrative-room.js").is_file()
    assert (ROOT / "2i" / "2i-assets" / "typewriter-input.js").is_file()
