"""Exercise the actual Director page, adapter, confirmation and recording tracker.
Host API responses are test doubles. No live encoding or backend is claimed.
"""
import functools
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def origin():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def studio(origin):
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--no-sandbox"],
                                        executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"))
        except pw.Error as exc:
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        context.add_init_script("""sessionStorage.setItem('pubcast_user',
          JSON.stringify({username:'director',user_id:'director',role:'owner'}));
          sessionStorage.setItem('pubcast_token','test-token');""")
        state = {"sessions": {}, "starts": 0, "stops": 0,
                 "start_errors": [], "stop_reports": [], "drop_start_reply": False}
        camera = {"id": "cam_main", "name": "Main camera", "transport": "local"}
        def route_handler(route):
            request = route.request
            url = request.url.split("?", 1)[0]
            path = url[len(origin):]
            if not path.startswith("/api/") and path != "/health":
                return route.continue_()
            body = request.post_data_json if request.method == "POST" and request.post_data else {}
            data = {}
            if path == "/api/switcher/state":
                data = {"program": "cam_main", "preview": "cam_main", "sources": [camera]}
            elif path == "/api/recording/preflight":
                data = {"ready": True, "ok": True, "issues": [], "warnings": [], "sources": body.get("sources", [])}
            elif path == "/api/recording/sessions":
                data = list(state["sessions"].values())
            elif path == "/api/studio/actions/recording.start":
                assert body.get("confirm") is True
                state["starts"] += 1
                sid = body["session_id"]
                assert sid not in state["sessions"]
                row = {"session_id": sid, "operator": "director", "state": "active",
                       "sources": body["sources"], "mode": body["mode"]}
                state["sessions"][sid] = row
                if state["drop_start_reply"]:
                    return route.abort("failed")
                # Deliberately omit the warning from later list replies to test cumulative evidence.
                data = {"ok": True, "result": {**row, "capture_errors": state["start_errors"]}}
            elif path == "/api/studio/actions/recording.stop":
                assert body.get("confirm") is True
                state["stops"] += 1
                row = state["sessions"][body["session_id"]]
                row["state"] = "stopped"
                data = {"ok": True, "result": {**row, "capture_report": state["stop_reports"]}}
            elif path == "/api/state/production":
                data = {"blackout": False, "preview_bars": False, "panic_seq": 0, "blackout_seq": 0}
            elif path == "/api/timeline/status":
                data = {"state": "idle", "elapsed": 0, "timeline_name": None, "duration": None}
            elif path == "/api/timeline/list":
                data = {"timelines": []}
            elif path == "/api/program-audio/status":
                data = {"ok": True, "status": {"buses": {}, "master_volume": 1}}
            elif path == "/api/studio/actions":
                data = {"actions": []}
            elif path == "/health":
                data = {"ok": True}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        context.route(origin + "/**", route_handler)
        page = context.new_page()
        try:
            page.goto(origin + "/static/director_switcher.html", wait_until="domcontentloaded")
        except pw.Error as exc:
            if "ERR_BLOCKED_BY_ADMINISTRATOR" in str(exc):
                pytest.skip("Browser policy blocks localhost navigation")
            raise
        page.wait_for_function("typeof sessionTracker !== 'undefined' && typeof toggleRecord === 'function'")
        page.wait_for_function("cameras.some(c=>c.sourceId==='cam_main')")
        try:
            yield page, state
        finally:
            context.close()
            browser.close()


def card(page):
    return page.locator("#truthRecording").inner_text()


def record_action(page, expected):
    page.locator("#recordBtn").click()
    page.locator("[data-confirm-ok]").click()
    page.wait_for_function("(s)=>sessionTracker.view().state===s && !sessionTracker.view().busy", arg=expected)


def test_a_clean_take_still_says_rec_confirmed(studio):
    page, state = studio
    record_action(page, "active")
    assert "Backend REC" in card(page)
    assert state["starts"] == 1
    record_action(page, "stopped")
    assert "Idle (closed)" in card(page)
    assert state["stops"] == 1


def test_a_camera_that_failed_to_start_is_named_at_once(studio):
    page, state = studio
    state["start_errors"] = [{"source_id": "cam_main", "error": "device busy"}]
    record_action(page, "active")
    assert "Incomplete take" in card(page)
    assert "cam_main" in card(page)
    page.wait_for_timeout(1800)
    assert "Incomplete take" in card(page)


def test_warnings_in_the_stop_report_make_it_an_incomplete_take_and_it_stays_that_way(studio):
    page, state = studio
    state["stop_reports"] = [{"source_id": "cam_main", "warnings": []},
                             {"source_id": "cam_two", "warnings": ["No media written"]}]
    record_action(page, "active")
    record_action(page, "stopped")
    assert "Incomplete take" in card(page) and "cam_two" in card(page)
    page.wait_for_timeout(1800)
    assert page.evaluate("failedRecordingSources") == ["cam_two"]


def test_the_next_take_starts_clean(studio):
    page, state = studio
    state["start_errors"] = [{"source_id": "cam_main", "error": "offline"}]
    record_action(page, "active")
    record_action(page, "stopped")
    assert page.evaluate("failedRecordingSources") == ["cam_main"]
    state["start_errors"] = []
    record_action(page, "active")
    assert page.evaluate("failedRecordingSources") == []
    assert "Backend REC" in card(page)


def test_a_lost_start_reply_recovers_the_exact_take_after_reload(studio):
    page, state = studio
    state["drop_start_reply"] = True
    record_action(page, "active")
    sid = page.evaluate("sessionTracker.view().id")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("(id)=>typeof sessionTracker!=='undefined' && sessionTracker.view().id===id && sessionTracker.view().verified", arg=sid)
    assert state["starts"] == 1
    record_action(page, "stopped")
    assert state["stops"] == 1


def test_enter_on_default_cancel_does_not_roll(studio):
    page, state = studio
    page.locator("#recordBtn").click()
    page.locator("[data-confirm-cancel]").wait_for()
    assert page.locator("[data-confirm-cancel]").evaluate("(e)=>e===document.activeElement")
    page.keyboard.press("Enter")
    page.wait_for_function("!sessionTracker.view().busy && !sessionTracker.view().id")
    assert state["starts"] == 0
