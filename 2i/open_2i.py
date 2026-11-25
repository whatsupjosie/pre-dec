"""Launch the same 2i editor used by Foresight through an offline loopback server."""
from __future__ import annotations

import argparse
import mimetypes
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

APP = Path(__file__).resolve().parent
STATIC = APP.parent / "static"
STATIC_FILES = frozenset({
    "2i_studio_bridge.js",
    "foresight_files.js",
    "production_notes.js",
    "program_audio_runtime.js",
    "reach_auth.js",
    "speech_client.js",
    "world/rooms/dressing_typewriter_sitting.png",
})


class TwoiHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".wasm": "application/wasm"}

    def send_head(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_error(403)
            return None

        path = unquote(urlsplit(self.path).path)
        if path == "/standalone":
            root, name = APP, "writers-room-v22.html"
        elif path.startswith("/2i-assets/"):
            root, name = APP / "2i-assets", path.removeprefix("/2i-assets/")
        elif path.startswith("/static/") and path.removeprefix("/static/") in STATIC_FILES:
            root, name = STATIC, path.removeprefix("/static/")
        else:
            self.send_error(404)
            return None

        try:
            asset = (root / name).resolve()
            if not asset.is_relative_to(root.resolve()) or not asset.is_file():
                self.send_error(404)
                return None
            data = asset.open("rb")
        except (OSError, ValueError):
            self.send_error(404)
            return None

        self.send_response(200)
        content_type = self.extensions_map.get(asset.suffix) or mimetypes.guess_type(asset.name)[0]
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(asset.stat().st_size))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=28742)
    parser.add_argument("--no-browser", action="store_true")
    options = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", options.port), TwoiHandler)
    except OSError as error:
        parser.exit(1, f"Could not start 2i on port {options.port}: {error}\n")

    with server:
        url = f"http://127.0.0.1:{server.server_port}/standalone"
        print(f"2i is open at {url}. Keep this window open while writing.", flush=True)
        if not options.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
