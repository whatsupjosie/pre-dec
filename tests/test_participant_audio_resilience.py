"""A guest's microphone survives a long recording: bursts after a stall, and a desk that is slow for a moment.

Before 2026-11-26 either one ended the guest's connection: a one-second window allowed at most 1.2 s of audio
(every catch-up after a hiccup of about a second exceeded it), and a send to the desk that took over a second
raised inside the guest's own handler.
"""
import asyncio
import struct

import pytest
from starlette.websockets import WebSocketDisconnect

from modules.participant_audio import BURST_SECONDS, HostOutbox
from tests.test_participant_audio import endpoint, fixture, ws_headers

RATE = 48000
FRAME_SAMPLES = 960                          # 20 ms
PCM = struct.pack("<" + "h" * FRAME_SAMPLES, *([1000, -1000] * (FRAME_SAMPLES // 2)))


def frame(seq):
    return struct.pack("<I", seq) + PCM


def connect(client, actor):
    host = client.post("/api/participant-audio/rooms").json()
    h = client.websocket_connect(endpoint(host) + "/media", headers=ws_headers())
    hs = h.__enter__()
    hs.send_json({"key": host["key"], "sample_rate": RATE})
    assert hs.receive_json() == {"ok": True}
    actor["user_id"] = "guest"
    guest = client.post(f"/api/participant-audio/rooms/{host['room']}/peers", json={"consent": True}).json()
    g = client.websocket_connect(endpoint(guest) + "/media", headers=ws_headers("guest"))
    gs = g.__enter__()
    gs.send_json({"key": guest["key"], "sample_rate": RATE})
    assert gs.receive_json() == {"ok": True}
    assert hs.receive_json()["type"] == "source"
    return h, hs, g, gs, guest


def test_a_three_second_backlog_after_a_stall_catches_up_in_order():
    client, actor, now = fixture()
    h, hs, g, gs, guest = connect(client, actor)
    try:
        backlog = int(3.0 / 0.02)                       # 3 s of audio arriving at once, the clock standing still
        for seq in range(backlog):
            gs.send_bytes(frame(seq))
        prefix = bytes.fromhex(guest["peer"])
        for seq in range(backlog):
            got = hs.receive_bytes()
            assert got[:16] == prefix and struct.unpack_from("<I", got, 16)[0] == seq
    finally:
        g.__exit__(None, None, None)
        h.__exit__(None, None, None)


def test_an_hour_of_real_time_with_regular_bursts_never_disconnects():
    client, actor, now = fixture()
    h, hs, g, gs, guest = connect(client, actor)
    try:
        seq = received = 0
        for second in range(3600):
            if second % 300 == 299:
                now[0] += 2.0                           # a 2 s stall: nothing arrives, then all of it at once
                for _ in range(150):
                    gs.send_bytes(frame(seq)); seq += 1
                continue
            now[0] += 1.0
            for _ in range(50):
                gs.send_bytes(frame(seq)); seq += 1
            if second % 60 == 59:                       # the desk, as the real one does: keeps alive and listens
                hs.send_text("ping")
                gs.send_text("ping")
                while received < seq:
                    assert struct.unpack_from("<I", hs.receive_bytes(), 16)[0] == received
                    received += 1
        while received < seq:
            assert struct.unpack_from("<I", hs.receive_bytes(), 16)[0] == received
            received += 1
        assert received == (3600 - 12) * 50 + 12 * 150   # every frame of the hour, in order (12 stalls of 150)
    finally:
        g.__exit__(None, None, None)
        h.__exit__(None, None, None)


def test_a_sender_that_keeps_flooding_is_still_cut_off():
    client, actor, now = fixture()
    h, hs, g, gs, guest = connect(client, actor)
    try:
        with pytest.raises(WebSocketDisconnect):
            for seq in range(int((BURST_SECONDS + 2) / 0.02)):  # 7 s of audio with no time passing
                gs.send_bytes(frame(seq))
            gs.receive_json()
        while True:                                     # the audio queued before the cut-off, then the notice
            message = hs.receive()
            if message.get("text"):
                assert message["text"] == '{"type":"left","peer":"%s"}' % guest["peer"] or \
                    '"left"' in message["text"]
                break
    finally:
        h.__exit__(None, None, None)


class SlowSocket:
    def __init__(self, delay):
        self.delay, self.got = delay, []

    async def send_bytes(self, data):
        await asyncio.sleep(self.delay)
        self.got.append(data)

    async def send_json(self, data):
        await asyncio.sleep(self.delay)
        self.got.append(data)


def test_a_stalled_desk_loses_its_oldest_audio_never_the_guest_or_a_control_message():
    async def run():
        sock = SlowSocket(0.05)
        box = HostOutbox(lambda: sock, limit=10 * len(frame(0)) + 1000, timeout=5.0)
        peer = bytes.fromhex("aa" * 16)
        box.put({"type": "source", "peer": "aa" * 16})
        loop = asyncio.get_running_loop()
        started = loop.time()
        for seq in range(40):
            box.put(peer + frame(seq))                 # never waits for the desk
        assert loop.time() - started < 0.05
        box.put({"type": "left", "peer": "aa" * 16})
        while box.items or box.dropped:
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.1)
        await box.close()
        return sock.got

    got = asyncio.run(run())
    assert got[0] == {"type": "source", "peer": "aa" * 16}
    gaps = [m for m in got if isinstance(m, dict) and m.get("type") == "gap"]
    assert gaps and sum(sum(g["dropped_frames"].values()) for g in gaps) > 0
    audio = [struct.unpack_from("<I", m, 16)[0] for m in got if isinstance(m, bytes)]
    assert audio == sorted(audio) and audio[-1] == 39             # newest audio kept, order kept
    dropped = sum(sum(g["dropped_frames"].values()) for g in gaps)
    assert len(audio) + dropped == 40
    assert got[-1] == {"type": "left", "peer": "aa" * 16}


def test_a_send_that_times_out_is_counted_and_the_next_one_still_goes():
    async def run():
        class Flaky(SlowSocket):
            calls = 0
            async def send_bytes(self, data):
                Flaky.calls += 1
                if Flaky.calls == 1:
                    await asyncio.sleep(1.0)            # longer than the timeout below
                self.got.append(data)
        sock = Flaky(0)
        box = HostOutbox(lambda: sock, timeout=0.1)
        peer = bytes.fromhex("bb" * 16)
        box.put(peer + frame(0))
        box.put(peer + frame(1))
        await asyncio.sleep(0.5)
        await box.close()
        return sock.got, box.stalls

    got, stalls = asyncio.run(run())
    assert stalls == 1
    assert {"type": "gap", "dropped_frames": {"bb" * 16: 1}} in got
    assert any(isinstance(m, bytes) and struct.unpack_from("<I", m, 16)[0] == 1 for m in got)
