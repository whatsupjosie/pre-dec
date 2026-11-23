"""The control room's REC button must say so when a camera's capture fails.

Loads static/director_switcher.html in Chromium and runs its real toggleRecord()
with the studio action stubbed to return what the backend returns: capture_errors
(a list of {source_id, error}) when a take starts, and capture_report (a list with
per-source warnings) when it stops. Nothing here talks to a server.
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "static" / "director_switcher.html"


@pytest.fixture()
def page():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        context.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
        page = context.new_page()
        page.goto(PAGE.as_uri())
        page.wait_for_function("typeof toggleRecord === 'function' && typeof setTruthCard === 'function'")
        page.evaluate("""() => {
          window.__calls = [];
          cameraById(program).sourceId = 'cam_main';   // a live Program source
          window.__reply = {};
          runStudioAction = async (name, payload) => { window.__calls.push(name); return window.__reply[name] || null; };
          recording = false; activeRecordingSessionId = '';
        }""")
        yield page
        browser.close()


def _card(page):
    return page.evaluate("""() => { const c = document.getElementById('truthRecording');
      return [c.querySelector('.truth-value')?.textContent || '', c.textContent]; }""")


def _rec(page):
    page.evaluate("toggleRecord(document.getElementById('recordBtn'))")
    page.wait_for_timeout(150)


def test_a_clean_take_still_says_rec_confirmed(page):
    page.evaluate("__reply['recording.start'] = {result: {session_id: 's1'}}; __reply['recording.stop'] = {result: {capture_report: [{source_id: 'cam_main', warnings: []}]}}")
    _rec(page)
    assert "Backend REC" in _card(page)[1]
    _rec(page)
    text = _card(page)[1]
    assert "Incomplete take" not in text and "Idle" in text


def test_a_camera_that_failed_to_start_is_named_at_once(page):
    page.evaluate("__reply['recording.start'] = {result: {session_id: 's1', capture_errors: [{source_id: 'cam_main', error: 'device busy'}]}}")
    _rec(page)
    text = _card(page)[1]
    assert "Incomplete take" in text and "cam_main" in text, text
    assert "0" not in text.replace("cam_main", ""), "the source names must be the cameras, not list positions"


def test_warnings_in_the_stop_report_make_it_an_incomplete_take_and_it_stays_that_way(page):
    page.evaluate("""__reply['recording.start'] = {result: {session_id: 's1'}};
      __reply['recording.stop'] = {result: {capture_report: [
        {source_id: 'cam_main', warnings: []},
        {source_id: 'cam_two', warnings: ['No media was written for this source']}]}}""")
    _rec(page)
    _rec(page)
    text = _card(page)[1]
    assert "Incomplete take" in text and "cam_two" in text and "cam_main" not in text.split("Incomplete take", 1)[1], text
    # The periodic status refresh must not paper over it with "Idle".
    page.evaluate("""() => { if (failedRecordingSources.length) setTruthCard('truthRecording', 'bad', 'Incomplete take', 'x'); }""")
    assert page.evaluate("failedRecordingSources") == ["cam_two"]


def test_the_next_take_starts_clean(page):
    page.evaluate("""__reply['recording.start'] = {result: {session_id: 's1', capture_errors: [{source_id: 'cam_main', error: 'x'}]}};
      __reply['recording.stop'] = {result: {capture_report: []}}""")
    _rec(page)
    _rec(page)
    assert page.evaluate("failedRecordingSources") == ["cam_main"]
    page.evaluate("__reply['recording.start'] = {result: {session_id: 's2'}}")
    _rec(page)
    assert page.evaluate("failedRecordingSources") == []
    assert "Backend REC" in _card(page)[1]
