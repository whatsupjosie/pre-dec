"""The PA through the real host: run_reach.py, real auth, a real room socket, a take recording show data, a restart.

What is proved:
* an owner's announcement reaches a listener in the room as an intercom message, followed by its chat transcript;
* a take that records show data keeps the announcement;
* the transcript does not make the AI cast answer (no bot speaks in the room afterwards);
* a viewer with no grant is refused; a grant scoped to one room survives a restart of the host, and a revocation does too.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import websockets

ROOT = Path(__file__).resolve().parents[1]
SECRET = secrets.token_urlsafe(48)     # the host signs with this, so the test can mint a second user's token


def _mint(sub, role):
    """A token the host accepts, for a user that has no password (the host has no route that creates users)."""
    code = ("import sys, modules.auth as a; "
            "print(a.create_access_token({'sub': sys.argv[1], 'role': sys.argv[2]}, expires_minutes=10))")
    out = subprocess.run([sys.executable, "-c", code, sub, role], cwd=str(ROOT), capture_output=True, text=True,
                         env={**os.environ, "PUBCAST_JWT_SECRET": SECRET}, check=True)
    return out.stdout.strip().splitlines()[-1]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(data: Path, password: str, first: bool):
    port = _free_port()
    log = open(data / f"host-{port}.log", "w", encoding="utf-8")
    env = {**os.environ, "PUBCAST_ASSETS_DIR": str(data / "assets"), "PUBCAST_JWT_SECRET": SECRET}
    proc = subprocess.Popen([sys.executable, "run_reach.py", "--port", str(port), "--data-dir", str(data / "data"),
                             "--no-browser", "--no-legacy-2i"], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            log.flush()
            raise AssertionError("run_reach.py exited during startup:\n" + Path(log.name).read_text()[-4000:])
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(0.3)
    else:
        raise AssertionError("host did not start within 120 s")
    if first:
        r = httpx.post(base + "/api/auth/setup", json={"username": "owner", "password": password,
                                                       "confirm_password": password}, timeout=10)
        assert r.status_code in (200, 201), r.text
    login = httpx.post(base + "/api/auth/login", json={"username": "owner", "password": password}, timeout=10)
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    client = httpx.Client(base_url=base, headers={"Authorization": "Bearer " + token}, timeout=120)
    return SimpleNamespace(base=base, port=port, client=client, proc=proc, log=log, token=token, data=data / "data")


def _stop(h):
    h.client.close()
    h.proc.terminate()
    try:
        h.proc.wait(20)
    except subprocess.TimeoutExpired:
        h.proc.kill()
        h.proc.wait(5)
    h.log.close()


def test_the_pa_through_the_real_host(tmp_path):
    (tmp_path / "assets").mkdir()
    password = secrets.token_urlsafe(20)
    h = _start(tmp_path, password, first=True)
    try:
        room = "main"
        take = h.client.post("/api/recording/start", json={"mode": "data_only", "countdown_seconds": 0,
                                                           "session_id": "pa_take", "record_data": True})
        assert take.status_code == 200, take.text

        async def scenario():
            async with websockets.connect(f"ws://127.0.0.1:{h.port}/ws/{room}",
                                          additional_headers={"Authorization": "Bearer " + h.token}) as ws:
                await asyncio.sleep(0.5)          # joined before the announcement is made
                r = await asyncio.to_thread(h.client.post, "/api/intercom/announce",
                                            json={"text": "Five minutes to set.", "rooms": [room]})
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["delivered"] == [room] and body["ok"], body
                got, deadline = [], time.time() + 15
                while time.time() < deadline:
                    try:
                        got.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.time())))
                    except asyncio.TimeoutError:
                        break
                    if any(m.get("type") == "chat" and "Five minutes" in str(m) for m in got):
                        # keep listening a few seconds: no bot may answer the PA
                        end = time.time() + 4
                        while time.time() < end:
                            try:
                                got.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=end - time.time())))
                            except asyncio.TimeoutError:
                                break
                        break
                return body, got

        body, got = asyncio.run(scenario())
        intercom = [m for m in got if m.get("type") == "intercom"]
        chats = [m["payload"] for m in got if m.get("type") == "chat"]
        assert len(intercom) == 1 and intercom[0]["payload"]["text"] == "Five minutes to set."
        assert intercom[0]["payload"]["announcement_id"] == body["announcement_id"]
        assert [c["user_id"] for c in chats] == ["__intercom__"], chats       # nobody answered the PA
        assert chats[0]["text"].endswith("Five minutes to set.")
        assert got.index(intercom[0]) < next(i for i, m in enumerate(got) if m.get("type") == "chat")

        stopped = h.client.post("/api/recording/pa_take/stop")
        assert stopped.status_code == 200, stopped.text
        shows = list((h.data / "recordings" / "pa_take").glob("*show_data*.jsonl.gz"))
        assert shows, list((h.data / "recordings" / "pa_take").iterdir())
        events = [json.loads(line) for line in gzip.open(shows[0])][1:-1]
        kept = [e for e in events if e.get("kind") == "intercom"]
        assert len(kept) == 1, [e.get("kind") for e in events]
        assert kept[0]["data"]["text"] == "Five minutes to set." and kept[0]["data"]["delivered"] == [room]
        assert "audio_b64" not in json.dumps(kept[0])                     # talkback audio stays off the record

        # a viewer without a grant is refused; a mod grant scoped to the room lets them in there only
        vid = "stage_mgr"
        vh = {"Authorization": "Bearer " + _mint(vid, "viewer")}
        time.sleep(2.1)
        no = httpx.post(h.base + "/api/intercom/announce", headers=vh, json={"text": "Hello?", "rooms": [room]}, timeout=30)
        assert no.status_code == 403, no.text
        g = h.client.post("/api/intercom/grant", json={"user_id": vid, "rooms": [room], "note": "floor manager"})
        assert g.status_code == 200, g.text
        yes = httpx.post(h.base + "/api/intercom/announce", headers=vh, json={"text": "Places.", "rooms": [room]}, timeout=30)
        assert yes.status_code == 200, yes.text
        assert httpx.post(h.base + "/api/intercom/announce", headers=vh, json={"text": "Everyone.", "rooms": None},
                          timeout=30).status_code == 403
    finally:
        _stop(h)

    # the grant survives a restart of the host
    h = _start(tmp_path, password, first=False)
    try:
        grants = h.client.get("/api/intercom/grants").json()["grants"]
        assert [(g["user_id"], g["rooms"], g["note"]) for g in grants] == [(vid, [room], "floor manager")]
        assert h.client.post("/api/intercom/revoke", json={"user_id": vid}).status_code == 200
    finally:
        _stop(h)
    h = _start(tmp_path, password, first=False)
    try:
        assert h.client.get("/api/intercom/grants").json()["grants"] == []
    finally:
        _stop(h)
