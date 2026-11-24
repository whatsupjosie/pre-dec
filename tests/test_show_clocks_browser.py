"""Show clocks on the real screens: real host, real timeline routes, real Chromium.

Josie's design (handoffs/STUDIO_ASSEMBLY_2026-11-23.md, 6 and 6b): the top clock is how far into the
show you are, the bottom is how much is left, only for a show with a set length; HH:MM:SS:FF at the
show's frame rate (24 by default); top green and bottom blue by default; each switchable among blue,
green, yellow and red; the choice belongs to the screen it was made on.

Run: python -m pytest -q tests/test_show_clocks_browser.py
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
SCREENS = ("/static/control_room.html", "/static/stage.html", "/static/stage_3d.html", "/static/stage_panoramic.html")
GREEN, BLUE, RED = "rgb(61, 220, 132)", "rgb(77, 163, 255)", "rgb(255, 77, 77)"


def _timeline(name, set_length):
    return {"name": name, "duration": 1500, "frame_rate": 24, "set_length": set_length,
            "events": [{"t": 1490, "type": "custom", "label": "end"}]}


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    root = tmp_path_factory.mktemp("show-clocks")
    timelines = root / "data" / "timelines"
    timelines.mkdir(parents=True)
    (timelines / "slot.json").write_text(json.dumps(_timeline("slot", 1450)), encoding="utf-8")
    (timelines / "open_ended.json").write_text(json.dumps(_timeline("open_ended", None)), encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "PUBCAST_DATA_DIR": str(root / "data"), "PUBCAST_ENFORCE_AUTH": "1",
           "PUBCAST_JWT_SECRET": secrets.token_urlsafe(48)}
    base = f"http://127.0.0.1:{port}"
    with (root / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
                                    "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, timeout=5, trust_env=False) as api:
                deadline = time.monotonic() + 60
                while True:
                    try:
                        if api.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        pytest.fail("Backend did not start: " + (root / "server.log").read_text()[-6000:])
                    time.sleep(.1)
                password = secrets.token_urlsafe(24) + "A9!"
                setup = api.post("/api/auth/setup", json={"username": "director", "password": password,
                                                         "confirm_password": password})
                assert setup.status_code == 201, setup.text
                auth = setup.json()
                api.headers["Authorization"] = "Bearer " + auth["access_token"]
                yield base, auth, api
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            chromium = p.chromium.launch(args=["--no-sandbox"],
                                         executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"))
        except pw.Error as exc:
            pytest.skip("Chromium unavailable: " + str(exc).splitlines()[0])
        yield chromium
        chromium.close()


@pytest.fixture
def screen(host, browser):
    base, auth, _ = host
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    context.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(auth["access_token"]) + ");"
                            "sessionStorage.setItem('pubcast_user',"
                            + json.dumps(json.dumps({"username": "director", "role": "owner"})) + ");")

    def open_screen(path):
        page = context.new_page()
        page.goto(base + path)
        page.wait_for_selector("#pubcast-show-clocks", timeout=15000)
        return page
    yield open_screen
    context.close()


def load(api, name):
    api.post("/api/timeline/stop")
    assert api.post("/api/timeline/load", json={"name": name}).status_code == 200


def face(page, row):
    return page.locator(f'[data-clock-face="{row}"]')


def wait_time(page, row, text):
    page.wait_for_function(
        "([row, text]) => document.querySelector(`[data-clock-face='${row}']`)?.getAttribute('data-time') === text",
        arg=[row, text], timeout=5000)


@pytest.mark.parametrize("path", SCREENS)
def test_every_screen_shows_both_clocks_at_the_position_and_set_length(host, screen, path):
    _, _, api = host
    load(api, "slot")
    assert api.post("/api/timeline/seek", params={"time": 20.5}).status_code == 200
    page = screen(path)
    wait_time(page, "top", "00:00:20:12")
    wait_time(page, "bottom", "00:23:49:12")
    assert face(page, "top").evaluate("e => getComputedStyle(e).color") == GREEN
    assert face(page, "bottom").evaluate("e => getComputedStyle(e).color") == BLUE


def test_running_show_counts_up_and_down_smoothly(host, screen):
    _, _, api = host
    load(api, "slot")
    page = screen("/static/control_room.html")
    wait_time(page, "top", "00:00:00:00")
    assert api.post("/api/timeline/play").status_code == 200
    try:
        page.wait_for_timeout(1300)
        top = face(page, "top").get_attribute("data-time")
        bottom = face(page, "bottom").get_attribute("data-time")
        assert "00:00:01:00" <= top <= "00:00:02:23", top
        assert "00:24:08:00" <= bottom <= "00:24:09:00", bottom
        first = top
        page.wait_for_timeout(120)  # between two host reads (every 500 ms) the screen still advances
        assert face(page, "top").get_attribute("data-time") > first
    finally:
        api.post("/api/timeline/stop")


def test_a_show_with_no_set_length_has_no_time_left_clock(host, screen):
    _, _, api = host
    load(api, "open_ended")
    page = screen("/static/stage.html")
    wait_time(page, "top", "00:00:00:00")
    assert page.locator('[data-clock="bottom"]').is_hidden()


def test_each_clock_colour_is_kept_for_the_screen_it_was_chosen_on(host, screen):
    _, _, api = host
    load(api, "slot")
    page = screen("/static/control_room.html")
    wait_time(page, "top", "00:00:00:00")
    page.locator('[data-clock="top"] [data-color="red"]').click()
    assert face(page, "top").evaluate("e => getComputedStyle(e).color") == RED
    assert face(page, "bottom").evaluate("e => getComputedStyle(e).color") == BLUE
    page.reload()
    page.wait_for_selector("#pubcast-show-clocks")
    assert face(page, "top").evaluate("e => getComputedStyle(e).color") == RED
    other = screen("/static/stage.html")
    assert face(other, "top").evaluate("e => getComputedStyle(e).color") == GREEN


def test_the_panel_never_takes_clicks_meant_for_the_page(host, screen):
    _, _, api = host
    load(api, "slot")
    page = screen("/static/stage_3d.html")
    box = page.locator("#pubcast-show-clocks").bounding_box()
    hit = page.evaluate("([x, y]) => document.elementFromPoint(x, y)?.closest('#pubcast-show-clocks') ? 'clock' : 'page'",
                        [box["x"] + 20, box["y"] + box["height"] / 2])
    assert hit == "page"


def test_when_the_host_cannot_be_read_the_clocks_are_dark_not_guessing(host, browser):
    base, auth, _ = host
    context = browser.new_context()
    context.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(auth["access_token"]) + ");")
    page = context.new_page()
    page.route("**/api/timeline/status", lambda route: route.fulfill(status=503, body="down"))
    page.goto(base + "/static/stage.html")
    page.wait_for_selector("#pubcast-show-clocks")
    page.wait_for_timeout(700)
    assert face(page, "top").get_attribute("data-time") == ""
    assert page.locator('[data-clock="bottom"]').is_hidden()
    context.close()
