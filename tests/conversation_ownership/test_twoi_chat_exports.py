import asyncio
import io
import json
import re
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.auth import create_access_token
from modules.character_service import CharacterTranscriptStore, _private_thread
from modules.chat_rooms import create_chat_router, dm_room_id
from modules.conversation_routes import create_conversation_router
from modules.hub import Hub
from modules.pubpartner_core import PubPartnerSpine
from modules.route_security import current_identity
from modules.writers_room import create_writers_room_router


def auth(user, role="guest"):
    return {"Authorization": "Bearer " + create_access_token({"sub": user, "role": role})}


def test_complete_archive_obeys_account_room_and_dm_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    hub = Hub(tmp_path)
    spine = PubPartnerSpine(tmp_path)
    app = FastAPI()
    app.include_router(create_chat_router(hub, current_identity))
    app.include_router(create_conversation_router(tmp_path, lambda: hub, lambda: spine))
    app.include_router(create_writers_room_router(tmp_path))
    client = TestClient(app)
    alice, bob, outsider = auth("alice"), auth("bob"), auth("outsider")

    def room_message(room, text, headers):
        assert client.post(f"/api/chat/rooms/{room}/send", headers=headers, json={"text": text}).is_success

    exact = "  One idea — here.\nAnother idea.  "
    room_message("world", exact, alice)
    room_message("studio", "crew only", auth("lead", "crew"))
    grant = client.post("/api/chat/dm/request", headers=alice, json={"to_user": "bob"}).json()
    assert client.post("/api/chat/dm/accept/" + grant["request_id"], headers=bob).is_success
    room = dm_room_id("alice", "bob")
    # Persist through the same committed archive used by the authenticated WebSocket.
    asyncio.run(hub.post_chat_message(
        room, "alice", exact, client_message_id="6d1cb2b6-b5ef-46f9-81d5-377f55f0d80a",
    ))
    dm_url = f"/api/chat/dm/{room}/export"
    assert client.get(dm_url).status_code == 401
    assert client.get(dm_url, headers=outsider).status_code == 404
    assert json.loads(client.get(dm_url, headers=bob).text)["text"] == exact

    cid = client.post("/api/conversations", headers=alice, json={"title": "My chat"}).json()["conversation_id"]
    assert client.post(f"/api/conversations/{cid}/messages", headers=alice,
                       json={"speaker": "Alice", "exact_text": exact}).is_success
    assert client.put("/api/writers-room/documents/draft", headers=alice, json={
        "title": "Draft", "expected_revision": 0,
        "state": {"committed": ["PRIVATE MANUSCRIPT"],
                  "conversations": {"alex": [{"role": "user", "content": exact}]}},
    }).is_success
    characters = CharacterTranscriptStore(tmp_path)
    characters.register_thread("alice", "pete", "story")
    characters.append(_private_thread("alice", "pete", "story"), "alice", exact)
    source = spine.vault.store(user_id="alice", session_id="production", text=exact)
    spine._append_turn("alice", "production", {
        "live_loop": True, "turn_id": "turn-1", "source": source.ref(),
        "provider_result": {"ok": True}, "friend_response": "An exact reply.",
        "fcp1": {"f": {"id": "alex"}}, "llm_prompt_text": "INTERNAL PROMPT",
    })

    narrative = spine.vault.store(user_id="alice", session_id="narrative_fixture", text="MANUSCRIPT GENERATION")
    spine._append_turn("alice", "narrative_fixture", {
        "live_loop": True, "source": narrative.ref(), "fcp1": {"proj": {"room": "writers-room"}},
        "provider_result": {"ok": True}, "friend_response": "A manuscript passage.",
    })

    archive_url = "/api/conversations/exports/all"
    assert client.post(archive_url + "/zip").status_code == 401
    for actor in (alice, outsider):
        export = client.post(archive_url + "/zip", headers=actor)
        assert export.is_success, export.text[:200]
        with zipfile.ZipFile(io.BytesIO(export.content)) as bundle:
            assert bundle.testzip() is None
            files = bundle.namelist()
            assert "Rooms/studio.jsonl" not in files
            assert json.loads(bundle.read("Rooms/world.jsonl"))["text"] == exact
            if actor == alice:
                assert any(name.startswith("Chats/") for name in files)
                assert json.loads(bundle.read(f"DirectMessages/{room}.jsonl"))["text"] == exact
                assert json.loads(bundle.read("WritersRoom/transcripts.json"))[0]["messages"][0]["content"] == exact
                assert b"PRIVATE MANUSCRIPT" not in bundle.read("WritersRoom/transcripts.json")
                assert json.loads(bundle.read("PubPartner/transcripts.json"))[0]["turns"][0]["user_text"] == exact
                assert b"INTERNAL PROMPT" not in bundle.read("PubPartner/transcripts.json")
                assert b"MANUSCRIPT GENERATION" not in bundle.read("PubPartner/transcripts.json")
                assert json.loads(bundle.read("PrivateCharacters/transcripts.json"))["threads"][0]["messages"][0]["text"] == exact
            else:
                assert not any(name.startswith("Chats/") for name in files)
                assert f"DirectMessages/{room}.jsonl" not in files
                assert json.loads(bundle.read("WritersRoom/transcripts.json")) == []
                assert json.loads(bundle.read("PubPartner/transcripts.json")) == []
                assert json.loads(bundle.read("PrivateCharacters/transcripts.json"))["threads"] == []

    raw = client.post(archive_url + "/raw", headers=alice)
    assert raw.is_success and raw.json()["verified"]
    saved = tmp_path / "exports" / "conversation_ownership" / "Library" / raw.json()["export_name"]
    assert (saved / "Rooms" / "world.jsonl").is_file()
    assert client.post("/api/chat/dm/revoke", headers=bob, json={"other_user": "alice"}).is_success
    assert client.get(dm_url, headers=alice).status_code == 404


def test_2i_archive_download_save_and_share_preparation(tmp_path):
    import secrets

    import httpx
    import pytest

    from tests.test_data_checkpoint_host_recovery import GL_ARGS, Host

    playwright = pytest.importorskip("playwright.sync_api")
    data = tmp_path / "data"
    data.mkdir()
    host = Host(data, tmp_path / "host.log")
    host.start()
    try:
        password = secrets.token_urlsafe(24) + "Aa9!"
        exact = "  Preserve these lines.\nAnd this idea.  "
        with httpx.Client(base_url=host.base, trust_env=False) as api:
            setup = api.post("/api/auth/setup", json={
                "username": "chat-owner", "password": password, "confirm_password": password,
            })
            assert setup.is_success
            seeded = api.post("/api/chat/rooms/world/send", json={"text": exact},
                              headers={"Authorization": "Bearer " + setup.json()["access_token"]})
            assert seeded.is_success

        with playwright.sync_playwright() as runtime, runtime.chromium.launch(args=GL_ARGS) as browser:
            page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
            page.set_default_timeout(10000)
            page.goto(host.base + "/login?next=/2i/chat")
            page.fill("#loginUser", "chat-owner")
            page.fill("#loginPass", password)
            page.click("#loginBtn")
            page.wait_for_url("**/2i/chat")
            page.get_by_role("link", name="Chat Archive").click()
            page.wait_for_url("**/2i/chat/archive")
            selected = page.get_by_label("Conversation")
            selected.select_option(label="World")
            page.get_by_role("button", name="Prepare to share").click()
            with page.expect_download() as pending:
                page.get_by_role("button", name="Download file", exact=True).click()
            assert json.loads(pending.value.path().read_text(encoding="utf-8"))["text"] == exact

            # The platform picker is unavailable in headless Chromium.
            # Observe the exact attachment passed by the real page handler.
            page.evaluate("""() => {
                Object.defineProperty(navigator, 'canShare', {value: ({files}) => files.length === 1});
                Object.defineProperty(navigator, 'share', {value: async ({files}) => {
                    window.sharedTranscript = await files[0].text();
                }});
            }""")
            page.get_by_role("button", name="Prepare to share").click()
            assert page.evaluate("window.sharedTranscript") is None
            page.get_by_role("button", name="Share file", exact=True).click()
            page.wait_for_function("typeof window.sharedTranscript === 'string'")
            assert json.loads(page.evaluate("window.sharedTranscript"))["text"] == exact

            selected.select_option(label="All my available chats")
            with page.expect_download() as pending:
                page.get_by_role("button", name="Download export", exact=True).click()
            with zipfile.ZipFile(pending.value.path()) as bundle:
                assert json.loads(bundle.read("Rooms/world.jsonl"))["text"] == exact
            page.get_by_role("button", name="Save all on host", exact=True).click()
            playwright.expect(page.locator("#archive-status")).to_contain_text("Archive saved on the PubCast host")
            assert list((data / "exports" / "conversation_ownership" / "Library").glob("*/Rooms/world.jsonl"))

            for path in ("/general-chat", "/pub-partner-chat", "/pubpartner", "/static/human_contacts.html"):
                page.goto(host.base + path)
                page.get_by_role("link", name="Chat Archive", exact=True).click()
                page.wait_for_url("**/2i/chat/archive")
                playwright.expect(page.get_by_role("heading", name="Chat Archive")).to_be_visible()

            page.set_viewport_size({"width": 1050, "height": 720})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(host.base + "/foresight-counter?fresh")
            assert page.locator("#menubar .menu-btn").count(), errors
            page.get_by_role("button", name=re.compile(r"^Me(?:$|:)")).click()
            page.get_by_role("menuitem", name="Chat Archive", exact=True).click()
            frame_selector = 'iframe[src="/2i/chat/archive"]'
            archive = page.frame_locator(frame_selector)
            playwright.expect(archive.get_by_role("heading", name="Chat Archive")).to_be_visible()
            archive.get_by_label("Conversation").select_option(label="World")
            with page.expect_download() as tray_download:
                archive.get_by_role("button", name="Download export", exact=True).click()
            assert json.loads(tray_download.value.path().read_text(encoding="utf-8"))["text"] == exact
    finally:
        host.stop()
