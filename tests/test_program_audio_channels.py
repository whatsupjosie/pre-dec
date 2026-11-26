"""Independent channels (host, guest, AI ...), solo, the effective mix, meters, and the mix kept with each take."""
import math
import struct
import subprocess
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.program_audio import ProgramAudioState, apply_audio_event
from modules.program_audio_routes import create_program_audio_router
from modules.recording_modes import wav_tail_levels


def client(state=None):
    state = state or ProgramAudioState()
    app = FastAPI()
    router = create_program_audio_router(state)
    app.include_router(router)
    return TestClient(app), state, router


def test_host_guest_and_ai_are_independent_channels_heard_through_the_dialogue_bus():
    state = ProgramAudioState()
    channels = state.mix()["channels"]
    assert {"host", "guest", "ai", "music", "sfx", "vtr", "room"} <= set(channels)
    assert {channels[c]["bus"] for c in ("host", "guest", "ai")} == {"dialogue"}
    state.set_channel("guest", {"gain": 0.5})
    channels = state.mix()["channels"]
    assert channels["guest"]["effective_gain"] == 0.5
    assert channels["host"]["effective_gain"] == 1.0 and channels["ai"]["effective_gain"] == 1.0


def test_the_effective_level_is_master_times_bus_times_channel_and_mutes_are_absolute():
    state = ProgramAudioState()
    apply_audio_event(state, {"action": "set_volume", "bus": "master", "volume": 0.8})
    apply_audio_event(state, {"action": "set_volume", "bus": "dialogue", "volume": 0.5})
    state.set_channel("host", {"gain": 1.5})
    assert state.effective_gain("host") == pytest.approx(0.8 * 0.5 * 1.5)
    assert state.mix()["channels"]["host"]["effective_db"] == pytest.approx(20 * math.log10(0.6), abs=0.01)
    state.set_channel("host", {"muted": True})
    assert state.effective_gain("host") == 0 and not state.mix()["channels"]["host"]["audible"]
    state.set_channel("host", {"muted": False})
    apply_audio_event(state, {"action": "mute", "bus": "dialogue"})
    assert state.effective_gain("host") == 0 and state.effective_gain("music") == 0.8


def test_solo_in_place_silences_everything_else_until_cleared():
    state = ProgramAudioState()
    state.set_channel("guest", {"solo": True})
    state.set_channel("music", {"solo": True})
    audible = {c for c, v in state.mix()["channels"].items() if v["audible"]}
    assert audible == {"guest", "music"} and state.status()["solo_active"]
    state.set_channel("guest", {"muted": True})                  # mute beats solo
    assert state.effective_gain("guest") == 0
    state.clear_solo()
    assert all(v["audible"] for c, v in state.mix()["channels"].items() if c != "guest")


@pytest.mark.parametrize("body", [{"gain": 2.5}, {"gain": -0.1}, {"gain": "0.5"}, {"gain": True},
                                  {"muted": "yes"}, {"solo": 1}, {"label": ""}, {"volume": 1}, {"source_id": 5}])
def test_a_bad_change_is_refused_and_changes_nothing(body):
    c, state, _ = client()
    before = state.mix()
    r = c.post("/api/program-audio/channels/host", json=body)
    assert r.status_code == 400, r.text
    assert state.mix() == before


def test_a_non_finite_gain_never_reaches_the_mix():
    state = ProgramAudioState()
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            state.set_channel("host", {"gain": bad})
    assert state.channels["host"].gain == 1.0


def test_every_change_reaches_the_players_and_the_recording():
    kept = []
    c, state, _ = client()
    state.on_mix_change = kept.append
    after = state.command_seq
    r = c.post("/api/program-audio/channels/ai", json={"gain": 0.25, "source_id": "ai_voice"})
    assert r.status_code == 200 and r.json()["mix"]["channels"]["ai"]["effective_gain"] == 0.25
    events = state.events_after(after)["events"]        # what /api/program-audio/events gives a signed-in player
    assert events[-1]["action"] == "mix" and events[-1]["mix"]["channels"]["ai"]["source_id"] == "ai_voice"
    c.post("/api/program-audio/event", json={"action": "set_volume", "bus": "master", "volume": 0.5})
    assert [m["sequence"] for m in kept] == [1, 2] and kept[-1]["master_volume"] == 0.5
    assert c.post("/api/program-audio/channels/nobody", json={"gain": 1}).status_code == 404


def test_the_old_bus_status_is_unchanged_for_existing_screens():
    status = ProgramAudioState().status()
    assert set(status["buses"]) == {"dialogue", "music", "sfx", "ui", "vtr", "room"}
    assert {"volume", "muted", "active_sources"} == set(status["buses"]["dialogue"])
    assert status["master_volume"] == 1.0 and status["dialogue_active"] == 0


def test_channels_can_be_added_for_a_second_guest_and_bad_ones_are_refused():
    c, state, _ = client()
    r = c.post("/api/program-audio/channels", json={"id": "guest-2", "label": "Second guest", "kind": "guest",
                                                    "gain": 0.9, "source_id": "peer-abc"})
    assert r.status_code == 200 and r.json()["mix"]["channels"]["guest-2"]["bus"] == "dialogue"
    for bad in ({"id": "guest-2"}, {"id": "Bad Id"}, {"id": "x", "kind": "drums"}, {"id": "y", "bus": "nowhere"},
                {"id": "z", "gain": 9}):
        assert c.post("/api/program-audio/channels", json=bad).status_code == 400, bad
    assert "z" not in state.channels


def test_meters_say_who_measured_them_and_when_and_refuse_impossible_levels():
    c, state, router = client()
    assert c.get("/api/program-audio/meters").json()["program_player"]["measured"] is False
    ok = c.post("/api/program-audio/meters", json={"program": {"rms_dbfs": -18.0, "peak_dbfs": -6.0},
                                                   "channels": {"guest": {"rms_dbfs": -24.5, "peak_dbfs": -9.0}}})
    assert ok.status_code == 200, ok.text
    meters = c.get("/api/program-audio/meters").json()["program_player"]
    assert meters["measured"] and not meters["stale"] and meters["levels"]["guest"]["rms_dbfs"] == -24.5
    for bad in ({"program": {"rms_dbfs": 3, "peak_dbfs": 0}}, {"channels": {"ghost": {"rms_dbfs": -10, "peak_dbfs": -5}}},
                {"program": {"rms_dbfs": "loud", "peak_dbfs": -1}}, {"levels": {}}):
        assert c.post("/api/program-audio/meters", json=bad).status_code == 400, bad
    router.recording_levels = lambda: [{"source_id": "beep_mic", "levels": {"peak_dbfs": -6.0}}]
    assert c.get("/api/program-audio/meters").json()["recording_inputs"][0]["source_id"] == "beep_mic"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_levels_are_read_from_a_wav_while_it_is_still_being_written(tmp_path):
    wav = tmp_path / "sound.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000:duration=1",
                    "-af", "volume=0.5", "-c:a", "pcm_s16le", str(wav)], check=True, timeout=30)
    data = bytearray(wav.read_bytes())
    at = data.index(b"data")
    data[at + 4:at + 8] = b"\x00\x00\x00\x00"           # as FFmpeg leaves it until the file is finished
    data[4:8] = b"\x00\x00\x00\x00"
    wav.write_bytes(bytes(data))
    levels = wav_tail_levels(wav)
    # FFmpeg's sine source peaks at 1/8 of full scale; volume=0.5 halves it: -24.1 dBFS peak, -27.1 dBFS RMS.
    assert levels["peak_dbfs"] == pytest.approx(-24.08, abs=0.3)
    assert levels["rms_dbfs"] == pytest.approx(-27.09, abs=0.3)
    assert levels["seconds_recorded"] == pytest.approx(1.0, abs=0.01) and not levels["clipped"]
    silent = tmp_path / "silent.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.5",
                    "-c:a", "pcm_s16le", str(silent)], check=True, timeout=30)
    assert wav_tail_levels(silent)["peak_dbfs"] == -120.0
    (tmp_path / "not.wav").write_bytes(b"this is not a wave file")
    assert wav_tail_levels(tmp_path / "not.wav") is None
    (tmp_path / "empty.wav").write_bytes(b"")                     # FFmpeg has not written its header yet
    assert wav_tail_levels(tmp_path / "empty.wav") == {"peak_dbfs": None, "rms_dbfs": None, "seconds_recorded": 0.0}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_a_meter_read_since_the_last_reading_never_misses_a_short_sound(tmp_path):
    wav = tmp_path / "beeps.wav"           # 0.1 s beep at 0.55 s, silence elsewhere: the last 0.2 s at 1 s misses it
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc=0.5*sin(2*PI*1000*t)*between(t\\,0.55\\,0.65):s=48000:d=1", "-c:a", "pcm_s16le", str(wav)],
                   check=True, timeout=30)
    assert wav_tail_levels(wav)["peak_dbfs"] == -120.0
    first = wav_tail_levels(wav, since_frame=0)
    assert first["peak_dbfs"] == pytest.approx(-6.02, abs=0.3) and first["frames"] == 48000
    again = wav_tail_levels(wav, since_frame=first["frames"])        # nothing new since: no level, not silence
    assert again["peak_dbfs"] is None and again["window_seconds"] == 0.0
