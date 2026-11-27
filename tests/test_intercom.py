"""The director's PA: permission, grants that survive a restart, the loudspeaker filter, fan-out and the routes."""
import asyncio
import base64
import io
import json
import math
import struct
import wave

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import auth
from modules.intercom import (ALL_ROOMS, MIN_INTERVAL_SECONDS, Intercom, IntercomError, apply_pa_filter)
from modules.intercom_routes import create_intercom_router


# ── helpers ──────────────────────────────────────────────────────────────────────

def tone_wav(freqs, seconds=0.5, rate=16000, channels=1, amp=8000):
    n = int(seconds * rate)
    frames = []
    for i in range(n):
        v = int(sum(amp * math.sin(2 * math.pi * f * i / rate) for f in freqs) / len(freqs))
        frames.extend([v] * channels)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(frames)}h", *frames))
    return buf.getvalue()


def read_wav(data):
    with wave.open(io.BytesIO(data), "rb") as w:
        ch, rate, raw = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    s = struct.unpack(f"<{len(raw) // 2}h", raw)
    return ch, rate, [s[c::ch] for c in range(ch)]


def level_at(samples, freq, rate):
    """Strength of one frequency in a signal (a single-bin DFT over the second half, past the filter's start-up)."""
    x = samples[len(samples) // 2:]
    re_ = sum(v * math.cos(2 * math.pi * freq * i / rate) for i, v in enumerate(x))
    im_ = sum(v * math.sin(2 * math.pi * freq * i / rate) for i, v in enumerate(x))
    return math.hypot(re_, im_) / len(x)


class FakeHub:
    def __init__(self, rooms=("studio", "lobby", "dm____alice__bob"), fail=()):
        self.rooms = {r: set() for r in rooms}
        self.user_display_name = {"dir": "The Director"}
        self.fail = set(fail)
        self.broadcasts, self.chats = [], []

    async def _broadcast(self, room, msg, _observed=False):
        if room in self.fail:
            raise ConnectionError("socket gone")
        self.broadcasts.append((room, msg))

    async def post_chat_message(self, room, user_id, text, client_message_id=None, notify_ai=True):
        self.chats.append((room, user_id, text, notify_ai))
        return {}


class FakeTTS:
    def __init__(self, ok=True, raises=False):
        self.ok, self.raises, self.calls = ok, raises, []

    async def synthesize(self, **kw):
        self.calls.append(kw)
        if self.raises:
            raise RuntimeError("engine crashed")
        if not self.ok:
            return {"ok": False, "error": "no voice"}
        return {"ok": True, "audio": tone_wav([1000], 0.3), "duration": 0.3}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def run(coro):
    return asyncio.run(coro)


# ── the filter ───────────────────────────────────────────────────────────────────

def test_filter_keeps_the_voice_band_and_cuts_bass_and_air():
    rate = 16000
    src = tone_wav([100, 1000, 7000], 0.6, rate)
    _, _, (before,) = read_wav(src)
    _, _, (after,) = read_wav(apply_pa_filter(src))
    rel = lambda sig, f: level_at(sig, f, rate) / level_at(sig, 1000, rate)
    assert rel(after, 100) < 0.5 * rel(before, 100)      # bass rolled off
    assert rel(after, 7000) < 0.7 * rel(before, 7000)    # air rolled off
    assert max(abs(v) for v in after) <= 30000           # headroom, never a hard clip


def test_filter_treats_stereo_as_two_channels_and_keeps_the_format():
    src = tone_wav([1000], 0.2, 22050, channels=2)
    out = apply_pa_filter(src)
    assert out != src                                     # it was filtered, not passed through
    ch, rate, (left, right) = read_wav(out)
    assert (ch, rate) == (2, 22050) and len(left) == len(right) == int(0.2 * 22050)
    assert left == right                                  # identical input channels stay identical
    # a voice on the left only must not leak into a silent right channel
    rate, n = 22050, 4410
    frames = []
    for i in range(n):
        frames += [int(8000 * math.sin(2 * math.pi * 1000 * i / rate)), 0]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(frames)}h", *frames))
    _, _, (left, right) = read_wav(apply_pa_filter(buf.getvalue()))
    assert max(abs(v) for v in left) > 10000 and set(right) == {0}


def test_filter_never_loses_an_announcement():
    assert apply_pa_filter(b"not a wav") == b"not a wav"
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:                       # 8-bit audio is passed through, not mangled
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(b"\x80" * 800)
    assert apply_pa_filter(buf.getvalue()) == buf.getvalue()


# ── permission and grants ────────────────────────────────────────────────────────

def test_mod_and_above_always_may_and_others_need_a_grant(tmp_path):
    ic = Intercom(grants_path=tmp_path / "g.json")
    assert ic.may_use("m", "mod") and ic.may_use("o", "owner", "studio")
    assert not ic.may_use("v", "viewer", "studio") and not ic.may_use("g", "guest")


def test_a_room_scoped_grant_reaches_only_its_rooms_and_never_everywhere(tmp_path):
    ic = Intercom(grants_path=tmp_path / "g.json")
    ic.grant("stage_mgr", "dir", rooms=["studio"])
    assert ic.may_use("stage_mgr", "viewer", "studio")
    assert not ic.may_use("stage_mgr", "viewer", "lobby")
    assert not ic.may_use("stage_mgr", "viewer", ALL_ROOMS)
    ic.check_permission("stage_mgr", "viewer", ["studio"])
    with pytest.raises(IntercomError) as err:
        ic.check_permission("stage_mgr", "viewer", ["studio", "lobby"])
    assert err.value.status == 403 and "lobby" in str(err.value)
    with pytest.raises(IntercomError):
        ic.check_permission("stage_mgr", "viewer", None)


def test_grants_and_revocations_survive_a_restart(tmp_path):
    path = tmp_path / "g.json"
    ic = Intercom(grants_path=path)
    ic.grant("a", "dir", rooms=["studio"], note="floor manager")
    ic.grant("b", "dir")
    assert ic.revoke("b", "dir") and not ic.revoke("b", "dir") and not ic.revoke("nobody", "dir")
    again = Intercom(grants_path=path)
    assert again.may_use("a", "viewer", "studio") and not again.may_use("b", "viewer", "studio")
    revoked = {g["user_id"]: g for g in again.list_grants(include_revoked=True)}
    assert revoked["b"]["revoked_by"] == "dir" and revoked["a"]["note"] == "floor manager"
    again.grant("b", "dir")                                # re-granting un-revokes
    assert Intercom(grants_path=path).may_use("b", "viewer", "lobby")


def test_a_damaged_grants_file_opens_the_pa_to_no_one_and_is_kept(tmp_path):
    path = tmp_path / "g.json"
    path.write_text("{ not json")
    ic = Intercom(grants_path=path)
    assert ic.list_grants() == [] and not ic.may_use("anyone", "viewer", "studio")
    assert list(tmp_path.glob("g.json.damaged-*"))


def test_a_grant_that_cannot_be_saved_is_not_granted(tmp_path, monkeypatch):
    ic = Intercom(grants_path=tmp_path / "g.json")
    monkeypatch.setattr(ic._store, "save", lambda grants: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        ic.grant("a", "dir")
    assert not ic.may_use("a", "viewer", "studio")


def test_private_conversations_are_never_targets(tmp_path):
    ic = Intercom(FakeHub(), grants_path=tmp_path / "g.json")
    with pytest.raises(IntercomError) as err:
        ic.grant("a", "dir", rooms=["dm____alice__bob"])
    assert err.value.status == 403
    with pytest.raises(IntercomError):
        run(ic.announce(speaker_id="dir", speaker_name="D", text="hi", rooms=["dm____alice__bob"]))


# ── announcing ───────────────────────────────────────────────────────────────────

def test_announce_everywhere_reaches_every_live_room_but_private_ones_with_filtered_audio(tmp_path):
    hub, tts = FakeHub(), FakeTTS()
    ic = Intercom(hub, lambda: tts, grants_path=tmp_path / "g.json")
    ann = run(ic.announce(speaker_id="dir", speaker_name="The Director", text="Five minutes to set."))
    assert ann.rooms == ["lobby", "studio"] and sorted(ann.delivered) == ["lobby", "studio"] and not ann.failed
    assert ann.had_audio and tts.calls and tts.calls[0]["text"] == "Five minutes to set."
    sent = {room: msg for room, msg in hub.broadcasts}
    assert set(sent) == {"lobby", "studio"}
    pay = sent["studio"]["payload"]
    assert sent["studio"]["type"] == "intercom" and pay["all_rooms"] and pay["text"] == "Five minutes to set."
    audio = base64.b64decode(pay["audio_b64"])
    assert audio != tone_wav([1000], 0.3) and read_wav(audio)[0] == 1    # it went through the horn
    # transcripts: one per room, as the intercom, and the AI cast is not woken
    assert sorted((r, u, n) for r, u, _, n in hub.chats) == [("lobby", "__intercom__", False), ("studio", "__intercom__", False)]
    assert all(t == "📢 The Director: Five minutes to set." for _, _, t, _ in hub.chats)


def test_speech_failing_still_lands_the_text(tmp_path):
    for tts, note in ((FakeTTS(ok=False), "no voice"), (FakeTTS(raises=True), "speech failed"), (None, "no speech engine")):
        hub = FakeHub()
        ic = Intercom(hub, (lambda t=tts: t), grants_path=tmp_path / "g.json")
        ann = run(ic.announce(speaker_id="dir", speaker_name="D", text="Quiet on the set.", rooms=["studio"]))
        assert not ann.had_audio and note in ann.audio_note and ann.delivered == ["studio"]
        assert hub.broadcasts[0][1]["payload"]["audio_b64"] is None and len(hub.chats) == 1


def test_a_failed_room_is_reported_not_assumed(tmp_path):
    hub = FakeHub(fail={"lobby"})
    ic = Intercom(hub, None, grants_path=tmp_path / "g.json")
    ann = run(ic.announce(speaker_id="dir", speaker_name="D", text="Places.", with_audio=False))
    assert ann.delivered == ["studio"] and "lobby" in ann.failed and "socket gone" in ann.failed["lobby"]


def test_text_limits_and_one_announcement_at_a_time(tmp_path):
    clock = Clock()
    ic = Intercom(FakeHub(), None, grants_path=tmp_path / "g.json", clock=clock)
    for bad in ("", "   ", "x" * 501, "a\0b"):
        with pytest.raises(IntercomError):
            run(ic.announce(speaker_id="dir", speaker_name="D", text=bad, rooms=["studio"]))
    run(ic.announce(speaker_id="dir", speaker_name="D", text="One.", rooms=["studio"], with_audio=False))
    with pytest.raises(IntercomError) as err:
        run(ic.announce(speaker_id="dir", speaker_name="D", text="Two.", rooms=["studio"], with_audio=False))
    assert err.value.status == 429
    run(ic.announce(speaker_id="other", speaker_name="O", text="Mine.", rooms=["studio"], with_audio=False))
    clock.t += MIN_INTERVAL_SECONDS
    run(ic.announce(speaker_id="dir", speaker_name="D", text="Two.", rooms=["studio"], with_audio=False))
    assert [a["text"] for a in ic.history()] == ["One.", "Mine.", "Two."]


def test_no_live_room_is_refused(tmp_path):
    ic = Intercom(FakeHub(rooms=("dm____a__b",)), None, grants_path=tmp_path / "g.json")
    with pytest.raises(IntercomError) as err:
        run(ic.announce(speaker_id="dir", speaker_name="D", text="Anyone?"))
    assert err.value.status == 409


# ── routes, with authentication enforced ─────────────────────────────────────────

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    hub = FakeHub()
    ic = Intercom(hub, lambda: None, grants_path=tmp_path / "g.json")
    app = FastAPI()
    app.include_router(create_intercom_router(ic, display_name=lambda u: hub.user_display_name.get(u, u)))
    client = TestClient(app)

    def as_(user, role):
        return {"Authorization": "Bearer " + auth.create_access_token({"sub": user, "role": role}, expires_minutes=5)}
    return client, hub, ic, as_


def test_routes_enforce_who_may_announce_and_who_may_grant(api):
    client, hub, ic, as_ = api
    body = {"text": "Five minutes.", "rooms": ["studio"], "audio": False}
    assert client.post("/api/intercom/announce", json=body).status_code == 401
    assert client.post("/api/intercom/announce", json=body, headers=as_("viewer1", "viewer")).status_code == 403
    r = client.post("/api/intercom/announce", json=body, headers=as_("dir", "mod"))
    assert r.status_code == 200 and r.json()["ok"] and r.json()["speaker_name"] == "The Director"
    # a viewer cannot grant; a mod can, and the grant works for its room only
    assert client.post("/api/intercom/grant", json={"user_id": "viewer1"}, headers=as_("viewer2", "viewer")).status_code == 403
    r = client.post("/api/intercom/grant", json={"user_id": "viewer1", "rooms": ["studio"]}, headers=as_("dir", "mod"))
    assert r.status_code == 200 and r.json()["grant"]["rooms"] == ["studio"]
    ok = client.post("/api/intercom/announce", json=body, headers=as_("viewer1", "viewer"))
    assert ok.status_code == 200
    far = client.post("/api/intercom/announce", json={**body, "rooms": ["lobby"]}, headers=as_("viewer1", "viewer"))
    assert far.status_code == 403 and "lobby" in far.json()["detail"]
    every = client.post("/api/intercom/announce", json={**body, "rooms": None}, headers=as_("viewer1", "viewer"))
    assert every.status_code == 403
    # a grantee cannot grant others
    assert client.post("/api/intercom/grant", json={"user_id": "x"}, headers=as_("viewer1", "viewer")).status_code == 403
    # lists need mod
    assert client.get("/api/intercom/grants", headers=as_("viewer1", "viewer")).status_code == 403
    assert [g["user_id"] for g in client.get("/api/intercom/grants", headers=as_("dir", "mod")).json()["grants"]] == ["viewer1"]
    assert len(client.get("/api/intercom/history", headers=as_("dir", "mod")).json()["announcements"]) == 2
    # revoke
    assert client.post("/api/intercom/revoke", json={"user_id": "viewer1"}, headers=as_("dir", "mod")).json()["revoked"] == "viewer1"
    assert client.post("/api/intercom/revoke", json={"user_id": "viewer1"}, headers=as_("dir", "mod")).status_code == 404


def test_routes_refuse_bad_bodies(api):
    client, hub, ic, as_ = api
    h = as_("dir", "mod")
    assert client.post("/api/intercom/announce", content="nope", headers={**h, "content-type": "application/json"}).status_code == 400
    assert client.post("/api/intercom/announce", json=["x"], headers=h).status_code == 400
    assert client.post("/api/intercom/announce", json={"text": "hi", "rooms": "studio"}, headers=h).status_code == 400
    assert client.post("/api/intercom/announce", json={"text": "hi", "audio": "yes"}, headers=h).status_code == 400
    assert client.post("/api/intercom/announce", json={"text": "", "rooms": ["studio"]}, headers=h).status_code == 400
    assert client.post("/api/intercom/announce", json={"text": "x" * 600, "rooms": ["studio"]}, headers=h).status_code == 413
    assert client.post("/api/intercom/announce", json={"text": "hi", "rooms": ["dm____a__b"]}, headers=h).status_code == 403
    assert client.post("/api/intercom/grant", json={"user_id": ""}, headers=h).status_code == 400
    st = client.get("/api/intercom/status", headers=as_("viewer9", "viewer")).json()
    assert st["available"] and not st["you_may_announce"] and st["grants_persisted"]


def test_each_announcement_is_kept_by_the_recording_without_its_audio(tmp_path):
    kept = []
    ic = Intercom(FakeHub(), lambda: FakeTTS(), grants_path=tmp_path / "g.json", record=lambda k, d: kept.append((k, d)))
    ann = run(ic.announce(speaker_id="dir", speaker_name="D", text="Rolling.", rooms=["studio"]))
    assert ann.had_audio and [k for k, _ in kept] == ["intercom"]
    data = kept[0][1]
    assert data["text"] == "Rolling." and data["delivered"] == ["studio"] and data["had_audio"]
    assert "audio_b64" not in data
    # a recorder that fails does not undo the announcement
    ic2 = Intercom(FakeHub(), None, grants_path=tmp_path / "h.json", record=lambda k, d: 1 / 0)
    assert run(ic2.announce(speaker_id="dir", speaker_name="D", text="Still here.", rooms=["studio"])).delivered == ["studio"]
