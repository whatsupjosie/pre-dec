"""Exercise 2i Chat recovery against the packaged Reach host."""
from __future__ import annotations

import secrets

import httpx
import pytest

from tests.test_data_checkpoint_host_recovery import Host


def test_2i_chat_recovers_delivery_and_restarts_live_updates(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    data = tmp_path / "data"
    data.mkdir()
    host = Host(data, tmp_path / "chat-host.log")
    host.start()
    try:
        username, password = "chat-owner", secrets.token_urlsafe(24) + "Aa9!"
        with httpx.Client(base_url=host.base, trust_env=False) as client:
            setup = client.post("/api/auth/setup", json={
                "username": username, "password": password, "confirm_password": password,
            })
            assert setup.status_code == 201, setup.text
            client.headers["Authorization"] = "Bearer " + setup.json()["access_token"]

            with playwright.sync_playwright() as runtime, runtime.chromium.launch() as browser:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.goto(host.base + "/login?next=/writers-room")
                page.fill("#loginUser", username)
                page.fill("#loginPass", password)
                page.click("#loginBtn")
                page.wait_for_url("**/writers-room")
                page.get_by_role("link", name="Chat", exact=True).click()
                page.wait_for_url("**/2i/chat")
                status = page.locator("[data-world-status]")
                composer = page.get_by_role("textbox", name="Message the world")
                send = page.get_by_role("button", name="Send", exact=True)
                log = page.get_by_role("log", name="World Chat messages")
                playwright.expect(status).to_contain_text(" · live")

                text = "Keep the message through a lost receipt"
                sent_ids = []

                def lose_receipt_once(route):
                    sent_ids.append(route.request.post_data_json["client_message_id"])
                    if len(sent_ids) == 1:
                        # Keep the real server receipt, then drop it before the browser sees it.
                        assert route.fetch().ok
                        route.abort()
                    else:
                        route.continue_()

                page.route("**/api/chat/rooms/world/send", lose_receipt_once)
                composer.fill(text)
                send.click()
                playwright.expect(status).to_contain_text("Delivery unconfirmed")
                # A successful room refresh must display the message and keep the warning.
                playwright.expect(log.get_by_text(text, exact=True)).to_be_visible()
                playwright.expect(status).to_contain_text("Delivery unconfirmed")
                playwright.expect(composer).to_have_value(text)
                page.reload()
                playwright.expect(composer).to_have_value(text)
                with page.expect_response("**/api/chat/rooms/world/send") as retried:
                    send.click()
                assert retried.value.json()["duplicate"] is True
                assert sent_ids[0] == sent_ids[1]
                playwright.expect(composer).to_have_value("")
                playwright.expect(log.get_by_text(text, exact=True)).to_have_count(1)

                # Deliver the browser's restoration events deterministically. The socket
                # handshake and incoming message after those events both use the real host.
                with page.expect_websocket(predicate=lambda socket: "/ws/chat/world?" in socket.url):
                    page.evaluate("""() => {
                        window.dispatchEvent(new PageTransitionEvent("pagehide", {persisted: true}));
                        window.dispatchEvent(new PageTransitionEvent("pageshow", {persisted: true}));
                    }""")
                recovery = "Visible after restoring Chat"
                assert client.post("/api/chat/rooms/world/send", json={"text": recovery}).is_success
                playwright.expect(log.get_by_text(recovery, exact=True)).to_be_visible()

                # Reach redirects an expired session to login. Reauthentication
                # must restore the text and its original submission key.
                page.unroute("**/api/chat/rooms/world/send", lose_receipt_once)
                expired_ids = []

                def expire_session_once(route):
                    expired_ids.append(route.request.post_data_json["client_message_id"])
                    if len(expired_ids) == 1:
                        route.fulfill(status=401, json={"detail": "Test session expired"})
                    else:
                        route.continue_()

                page.route("**/api/chat/rooms/world/send", expire_session_once)
                retry_text = "Keep this draft through sign-in"
                composer.fill(retry_text)
                send.click()
                page.wait_for_url("**/login?next=*")
                page.fill("#loginUser", username)
                page.fill("#loginPass", password)
                page.click("#loginBtn")
                page.wait_for_url("**/2i/chat")
                playwright.expect(composer).to_have_value(retry_text)
                send.click()
                playwright.expect(log.get_by_text(retry_text, exact=True)).to_be_visible()
                playwright.expect(composer).to_have_value("")
                assert len(expired_ids) == 2 and expired_ids[0] == expired_ids[1]

                page.unroute("**/api/chat/rooms/world/send", expire_session_once)
                stalled = "A stalled reply must release Send"

                def stall_reply(route):
                    # The browser's timeout should win even after server commit.
                    assert route.fetch().ok

                page.route("**/api/chat/rooms/world/send", stall_reply)
                composer.fill(stalled)
                send.click()
                playwright.expect(send).to_be_disabled()
                playwright.expect(status).to_contain_text("Delivery unconfirmed", timeout=16000)
                playwright.expect(send).to_be_enabled()
                playwright.expect(composer).to_have_value(stalled)
                page.unroute("**/api/chat/rooms/world/send", stall_reply)
                with page.expect_response("**/api/chat/rooms/world/send") as recovered:
                    send.click()
                assert recovered.value.json()["duplicate"] is True
                playwright.expect(log.get_by_text(stalled, exact=True)).to_have_count(1)
                playwright.expect(composer).to_have_value("")
    finally:
        host.stop()
