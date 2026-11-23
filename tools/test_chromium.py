"""Install and verify the checkout's Playwright Chromium, then run browser tests."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".pubcast-browsers"
SCREENSHOT = ROOT / ".sandbox" / "chromium" / "smoke.png"
DEFAULT_TEST = "tests/test_production25d_browser.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install Chromium for the current Playwright version")
    parser.add_argument("--check", action="store_true", help="Verify Chromium without running pytest")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments for pytest after --")
    args = parser.parse_args()
    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    if args.check and pytest_args:
        parser.error("--check does not take pytest arguments")

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(CACHE))
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        print("Install the repository test dependencies with python -m pip install -r requirements-dev.txt.", file=sys.stderr)
        return 1

    if args.install:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=ROOT,
        )
        if result.returncode:
            return result.returncode

    SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch() as browser:
                page = browser.new_page()
                page.set_content("""
                <title>PubCast Chromium check</title>
                <button onclick="document.querySelector('output').textContent='Ready'">Check Chromium</button>
                <output>Waiting</output>
                """)
                page.get_by_role("button", name="Check Chromium").click()
                if page.locator("output").inner_text() != "Ready":
                    print("Chromium opened, but the interaction check failed.", file=sys.stderr)
                    return 1
                page.screenshot(path=str(SCREENSHOT))
                print(f"Chromium {browser.version} verified. Smoke screenshot: {SCREENSHOT}", flush=True)
    except Error as exc:
        print(f"Chromium verification failed. {exc}", file=sys.stderr)
        print("If the browser is missing, retry with --install --check.", file=sys.stderr)
        return 1

    if args.check:
        return 0
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", *(pytest_args or [DEFAULT_TEST])],
        cwd=ROOT,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
