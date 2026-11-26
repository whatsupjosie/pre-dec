"""Program audio contract helpers for PubCast.

This is a dependency-free server-side companion for the browser program audio
runtime. It validates audio events and produces a small status/action model for
menus, recovery, and the Pub Manager.
"""
from __future__ import annotations

from collections import deque
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional

AudioBus = Literal["dialogue", "music", "sfx", "ui", "vtr", "room"]
VALID_BUSES = {"dialogue", "music", "sfx", "ui", "vtr", "room"}
VALID_ACTIONS = {"play", "stop", "stop_all", "set_volume", "mute", "unmute", "status"}



# ---------------------------------------------------------------------------------------------------------
# Independent channels (added 2026-11-26, finish/control-room-engine)
#
# A bus groups sound for the browser players (dialogue, music, ...). A channel is one input: the host's
# microphone, a guest, an AI performer's voice, the music player. Several recovered console controls are
# aliases of the dialogue *bus*; they move every voice at once. Channels are the independent faders:
# host, guest and AI each have their own gain, mute and solo, and are heard through the dialogue bus.
#
#   effective = master x bus volume (0 if the bus is muted) x channel gain x (0 if muted) x solo gate
#   solo gate = 1 when no channel is soloed; otherwise 1 only for soloed channels (solo in place)
#
# The server works the effective level out once, so every player and every recording agree on the mix.
# ---------------------------------------------------------------------------------------------------------
CHANNEL_KINDS = {"host", "guest", "ai", "music", "sfx", "vtr", "room", "other"}
KIND_BUS = {"host": "dialogue", "guest": "dialogue", "ai": "dialogue", "music": "music", "sfx": "sfx",
            "vtr": "vtr", "room": "room", "other": "sfx"}
MAX_CHANNEL_GAIN = 2.0          # +6 dB of make-up on a quiet source
MAX_CHANNELS = 32
_CHANNEL_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
DEFAULT_CHANNELS = (("host", "Host", "host"), ("guest", "Guest", "guest"), ("ai", "AI performer", "ai"),
                    ("music", "Music", "music"), ("sfx", "Sound effects", "sfx"), ("vtr", "VTR", "vtr"),
                    ("room", "Room / environment", "room"))


@dataclass
class Channel:
    id: str
    label: str
    kind: str
    bus: str
    gain: float = 1.0
    muted: bool = False
    solo: bool = False
    source_id: Optional[str] = None     # the camera, microphone or participant this channel carries, if known


def _default_channels() -> Dict[str, Channel]:
    return {cid: Channel(cid, label, kind, KIND_BUS[kind]) for cid, label, kind in DEFAULT_CHANNELS}


def _gain(value: Any, name: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not 0.0 <= number <= maximum:
        raise ValueError(f"{name} must be between 0 and {maximum:g}")
    return number


def _flag(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def db(linear: float) -> Optional[float]:
    return None if linear <= 0 else round(20 * math.log10(linear), 2)


@dataclass
class MeterReading:
    levels: Dict[str, Dict[str, Any]]
    measured_by: str
    received_at: float


@dataclass
class ProgramAudioState:
    bus_volumes: Dict[str, float] = field(default_factory=lambda: {bus: 1.0 for bus in VALID_BUSES})
    muted_buses: set[str] = field(default_factory=set)
    master_volume: float = 1.0  # One shared program master, used by all studio environments
    active_sources: Dict[str, int] = field(default_factory=lambda: {bus: 0 for bus in VALID_BUSES})
    dialogue_active: int = 0
    command_seq: int = 0
    commands: Any = field(default_factory=lambda: deque(maxlen=256), repr=False)
    channels: Dict[str, Channel] = field(default_factory=_default_channels)
    meters: Optional[MeterReading] = field(default=None, repr=False)
    # Called with the mix after every change (the recording side keeps it in each live take's show data).
    on_mix_change: Optional[Callable[[Dict[str, Any]], Any]] = field(default=None, repr=False)
    mix_seq: int = 0

    def publish(self, event):
        self.command_seq += 1
        item = {**event, 'sequence': self.command_seq, 'event_id': uuid.uuid4().hex}
        self.commands.append(item)
        return item

    def events_after(self, sequence):
        # New players start at the live edge, never replay old speech on entry.
        if sequence < 0:
            return {'sequence': self.command_seq, 'events': [], 'gap': False}
        gap = bool(self.commands and sequence < self.commands[0]['sequence'] - 1)
        return {'sequence': self.command_seq,
                'events': [] if gap else [dict(e) for e in self.commands if e['sequence'] > sequence],
                'gap': gap}


    def status(self) -> Dict[str, Any]:
        return {
            "master_volume": self.master_volume,
            "buses": {
                bus: {
                    "volume": self.bus_volumes.get(bus, 1.0),
                    "muted": bus in self.muted_buses,
                    "active_sources": self.active_sources.get(bus, 0),
                }
                for bus in sorted(VALID_BUSES)
            },
            "dialogue_active": self.dialogue_active,
            "channels": self.channel_status(),
            "solo_active": any(c.solo for c in self.channels.values()),
            "mix_sequence": self.mix_seq,
        }

    # -- channels ----------------------------------------------------------------------------------------
    def effective_gain(self, channel_id: str) -> float:
        channel = self.channels[channel_id]
        if channel.muted or channel.bus in self.muted_buses:
            return 0.0
        if any(c.solo for c in self.channels.values()) and not channel.solo:
            return 0.0
        return self.master_volume * self.bus_volumes.get(channel.bus, 1.0) * channel.gain

    def channel_status(self) -> Dict[str, Dict[str, Any]]:
        out = {}
        for cid, channel in self.channels.items():
            effective = self.effective_gain(cid)
            out[cid] = {**asdict(channel), "effective_gain": round(effective, 6), "effective_db": db(effective),
                        "audible": effective > 0}
        return out

    def mix(self) -> Dict[str, Any]:
        """The whole Program mix as it stands: what show data keeps and players apply."""
        return {"sequence": self.mix_seq, "master_volume": self.master_volume,
                "buses": {bus: {"volume": self.bus_volumes.get(bus, 1.0), "muted": bus in self.muted_buses}
                          for bus in sorted(VALID_BUSES)},
                "channels": self.channel_status()}

    def mix_changed(self) -> Dict[str, Any]:
        self.mix_seq += 1
        mix = self.mix()
        if self.on_mix_change is not None:
            try:
                self.on_mix_change(mix)
            except Exception:
                pass                         # a recording problem never changes what is heard
        return mix

    def set_channel(self, channel_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Change one channel. Every field is checked first; a bad request changes nothing."""
        if channel_id not in self.channels:
            raise KeyError(channel_id)
        allowed = {"gain", "muted", "solo", "label", "source_id"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError("unknown channel fields: " + ", ".join(sorted(unknown)))
        checked: Dict[str, Any] = {}
        if "gain" in changes:
            checked["gain"] = _gain(changes["gain"], "gain", MAX_CHANNEL_GAIN)
        for key in ("muted", "solo"):
            if key in changes:
                checked[key] = _flag(changes[key], key)
        if "label" in changes:
            label = changes["label"]
            if not isinstance(label, str) or not 0 < len(label.strip()) <= 48:
                raise ValueError("label must be 1 to 48 characters")
            checked["label"] = label.strip()
        if "source_id" in changes:
            source = changes["source_id"]
            if source is not None and (not isinstance(source, str) or not 0 < len(source) <= 128):
                raise ValueError("source_id must be a string or null")
            checked["source_id"] = source
        channel = self.channels[channel_id]
        for key, value in checked.items():
            setattr(channel, key, value)
        return self.mix_changed()

    def add_channel(self, body: Dict[str, Any]) -> Dict[str, Any]:
        cid, kind = body.get("id"), body.get("kind", "other")
        if not isinstance(cid, str) or not _CHANNEL_ID.fullmatch(cid):
            raise ValueError("id must be 1 to 48 lowercase letters, digits, - or _")
        if cid in self.channels:
            raise ValueError(f"channel {cid} already exists")
        if len(self.channels) >= MAX_CHANNELS:
            raise ValueError(f"at most {MAX_CHANNELS} channels")
        if kind not in CHANNEL_KINDS:
            raise ValueError("kind must be one of " + ", ".join(sorted(CHANNEL_KINDS)))
        bus = body.get("bus", KIND_BUS[kind])
        if bus not in VALID_BUSES:
            raise ValueError("bus must be one of " + ", ".join(sorted(VALID_BUSES)))
        label = body.get("label") or cid
        self.channels[cid] = Channel(cid, str(label)[:48], kind, bus)
        rest = {k: v for k, v in body.items() if k in ("gain", "muted", "solo", "source_id")}
        try:
            return self.set_channel(cid, rest) if rest else self.mix_changed()
        except (ValueError, KeyError):
            self.channels.pop(cid, None)
            raise

    def clear_solo(self) -> Dict[str, Any]:
        for channel in self.channels.values():
            channel.solo = False
        return self.mix_changed()

    # -- meters ------------------------------------------------------------------------------------------
    def take_meters(self, body: Dict[str, Any], *, measured_by: str, now: Optional[float] = None) -> Dict[str, Any]:
        """Levels measured by the player that renders Program (it hears what the audience hears).

        body: {"program": {"rms_dbfs", "peak_dbfs"}, "channels": {id: {"rms_dbfs", "peak_dbfs"}}}; dBFS in -120..0,
        "clipped" optional. Unknown channels are refused, so a meter can never show a channel that is not there.
        """
        if not isinstance(body, dict) or set(body) - {"program", "channels"}:
            raise ValueError("meters: send program and channels")
        def reading(value: Any, where: str) -> Dict[str, Any]:
            if not isinstance(value, dict) or set(value) - {"rms_dbfs", "peak_dbfs", "clipped"}:
                raise ValueError(f"{where}: rms_dbfs, peak_dbfs, clipped")
            out: Dict[str, Any] = {}
            for key in ("rms_dbfs", "peak_dbfs"):
                v = value.get(key)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not -120 <= v <= 0:
                    raise ValueError(f"{where}.{key} must be a number of dBFS between -120 and 0")
                out[key] = float(v)
            if "clipped" in value:
                out["clipped"] = _flag(value["clipped"], f"{where}.clipped")
            return out
        levels: Dict[str, Dict[str, Any]] = {}
        if "program" in body:
            levels["program"] = reading(body["program"], "program")
        for cid, value in (body.get("channels") or {}).items():
            if cid not in self.channels:
                raise ValueError(f"no channel {cid}")
            levels[cid] = reading(value, cid)
        self.meters = MeterReading(levels, measured_by, time.monotonic() if now is None else now)
        return {"ok": True, "channels": len(levels)}

    def meter_status(self, *, now: Optional[float] = None, stale_after: float = 1.0) -> Dict[str, Any]:
        if self.meters is None:
            return {"measured": False, "reason": "No player has reported levels yet"}
        age = (time.monotonic() if now is None else now) - self.meters.received_at
        return {"measured": True, "measured_by": self.meters.measured_by, "age_seconds": round(age, 3),
                "stale": age > stale_after, "levels": self.meters.levels}


def clamp_volume(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    if number != number:
        return 1.0
    return max(0.0, min(1.0, number))


def validate_audio_event(event: Dict[str, Any]) -> Dict[str, Any]:
    action = str(event.get("action") or "status")
    if action not in VALID_ACTIONS:
        raise ValueError(f"unsupported audio action: {action}")
    bus = str(event.get("bus") or "sfx")
    if action not in {"stop_all", "status"} and bus not in VALID_BUSES and not (action == "set_volume" and bus == "master"):
        raise ValueError(f"unsupported audio bus: {bus}")
    if 'director_announcement' in event and not isinstance(event['director_announcement'], bool):
        raise ValueError('director_announcement must be a boolean')
    out = dict(event)
    out["action"] = action
    out["bus"] = bus
    if "volume" in out:
        out["volume"] = clamp_volume(out["volume"])
    if "position" in out and not isinstance(out["position"], dict):
        out.pop("position", None)
    return out


def apply_audio_event(state: ProgramAudioState, event: Dict[str, Any]) -> Dict[str, Any]:
    event = validate_audio_event(event)
    action = event["action"]
    bus = event.get("bus", "sfx")
    if action == "set_volume":
        if bus == "master":
            state.master_volume = clamp_volume(event.get("volume", 1.0))
        else:
            state.bus_volumes[bus] = clamp_volume(event.get("volume", 1.0))
        state.mix_changed()
    elif action == "mute":
        state.muted_buses.add(bus)
        state.mix_changed()
    elif action == "unmute":
        state.muted_buses.discard(bus)
        state.mix_changed()
    elif action == "play":
        state.active_sources[bus] = state.active_sources.get(bus, 0) + 1
        if bus == "dialogue":
            state.dialogue_active += 1
    elif action == "stop":
        state.active_sources[bus] = max(0, state.active_sources.get(bus, 0) - 1)
        if bus == "dialogue":
            state.dialogue_active = max(0, state.dialogue_active - 1)
    elif action == "stop_all":
        for key in list(state.active_sources):
            state.active_sources[key] = 0
        state.dialogue_active = 0
    return state.status()


def issue_recovery_actions() -> list[Dict[str, str]]:
    return [
        {"id": "program_audio.stop_all", "label": "Stop all sounds", "safety": "safe"},
        {"id": "program_audio.clear_dialogue", "label": "Clear dialogue queue", "safety": "safe"},
        {"id": "program_audio.disable_tts_autoplay", "label": "Disable TTS autoplay", "safety": "safe"},
    ]


__all__ = [
    "CHANNEL_KINDS", "Channel", "ProgramAudioState", "VALID_ACTIONS", "VALID_BUSES", "apply_audio_event", "clamp_volume",
    "issue_recovery_actions", "validate_audio_event",
]
