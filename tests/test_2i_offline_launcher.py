"""The offline 2i launcher (2i/open_2i.py) serves the editor and the typewriter the studio desk embeds.

Runs the real launcher handler on a loopback port; no browser and no PubCast server.
"""
from __future__ import annotations

import http.client
import importlib.util
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_launcher():
    spec = importlib.util.spec_from_file_location("open_2i_under_test", ROOT / "2i" / "open_2i.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launcher():
    module = _load_launcher()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.TwoiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()


def _get(port: int, path: str, host: str | None = None) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("GET", path, skip_host=True)
    conn.putheader("Host", host or f"127.0.0.1:{port}")
    conn.endheaders()
    response = conn.getresponse()
    response.read()
    conn.close()
    return response.status, response.getheader("Content-Type") or ""


# Everything static/typewriter_console.html loads over http (it reads its map with fetch, not
# from the inline copy it uses for file://).
TYPEWRITER_FILES = [
    ("/typewriter-console?embedded=2i", "text/html"),
    ("/static/console_hotspot_renderer.css", "text/css"),
    ("/static/console_hotspot_renderer.js", "text/javascript"),
    ("/static/studio_console_hotspots.js", "text/javascript"),
    ("/static/typewriter_console_demo.js", "text/javascript"),
    ("/static/typewriter_sound.js", "text/javascript"),
    ("/static/typewriter_console_hotspot_manifest.json", "application/json"),
    ("/static/typewriter_keys.webp", "image/webp"),
]


def test_editor_page_is_served(launcher):
    status, kind = _get(launcher, "/standalone")
    assert status == 200 and kind.startswith("text/html")


@pytest.mark.parametrize("path,kind", TYPEWRITER_FILES)
def test_desk_typewriter_and_its_files_are_served(launcher, path, kind):
    status, served = _get(launcher, path)
    assert status == 200, path
    assert served.startswith(kind), (path, served)


def test_every_file_the_typewriter_page_names_is_on_the_list():
    module = _load_launcher()
    page = (ROOT / "static" / "typewriter_console.html").read_text(encoding="utf-8")
    import re

    named = set(re.findall(r'"\.\./static/([^"]+)"', page))
    assert named, "the typewriter page no longer names its files the way this test reads them"
    assert named <= module.STATIC_FILES, sorted(named - module.STATIC_FILES)


@pytest.mark.parametrize("path", ["/static/main.py", "/static/../main.py", "/typewriter-console/../../main.py", "/"])
def test_nothing_outside_the_list_is_served(launcher, path):
    assert _get(launcher, path)[0] == 404


def test_other_hosts_are_refused(launcher):
    assert _get(launcher, "/typewriter-console", host="evil.example")[0] == 403
