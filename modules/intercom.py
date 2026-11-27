"""
intercom.py — PubCast PA / Intercom System
═══════════════════════════════════════════

The director's loudspeaker. "Five minutes to set." "Quiet on the set."

WHAT IT DOES:
  - Host (mod+) can make announcements that cut through everything
  - Announcements can target ONE room or ALL rooms simultaneously
  - Host can GRANT intercom access to specific individuals
  - Grants are revocable and can be scoped to specific rooms
  - Every announcement is transcribed into all targeted chat boxes
  - Audio gets a loudspeaker filter (band-limited, compressed, slight clip)

PERMISSION MODEL:
  mod+ role          → always has intercom access, can grant to others
  explicit grant     → a named user gets access, optionally room-scoped
  everyone else      → denied

  A grant does NOT let the grantee grant others. Only mod+ can grant.

THE FILTER:
  Real PA systems sound the way they do because of physics: a small horn
  driver rolls off below ~400Hz and above ~4kHz, and the amp compresses
  hard so everything sits at the same loudness. We reproduce that with
  a bandpass + soft-knee compression + light saturation.

Rear View Foresight LLC — Feic Mo Chroí — 2026-08-24

Provenance and changes (2026-11-27, Claude, branch finish/control-room-engine):
  Ported from the NowCurtsey pubcast_run_bundle (2026-08-24), parked in this repo at
  recovery/2026-11-23/rediscovery/intercom_and_camera_bus/modules/intercom.py. The permission model,
  the filter and the fan-out are that file's. Changed here, each for a reason:
  - Grants are kept on disk (atomic replace), so a restart does not silently re-open or close the PA.
  - Private rooms (direct messages) are never targets: "all rooms" skips them and naming one is refused.
  - The transcript line goes to chat without waking the AI cast (hub.post_chat_message notify_ai=False);
    otherwise every "Quiet on the set" would make the bots answer it.
  - The filter treats stereo as two channels (the original filtered interleaved samples as one stream),
    and it runs off the event loop.
  - Text has a length limit, each speaker a short minimum interval, and every announcement a unique id.
  - The result says which rooms it reached and which it did not, rather than assuming all.
  Recording: every take that is recording show data keeps each announcement as a production event
  ("intercom": who spoke, the text, the rooms, which were reached, whether it had audio), whatever rooms it went to.
  The hub message itself enters show data only from rooms the privacy table allows, like any room message. The PA's
  audio is not kept in show data and is not mixed into a reconstruction's program sound: talkback stays off the
  record unless that is chosen later.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import math
import os
import re
import struct
import tempfile
import threading
import time
import uuid
import wave
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("pubcast.intercom")

# Role at or above which intercom is automatic (no grant needed)
INTERCOM_MIN_ROLE = "mod"

# Sentinel meaning "every room"
ALL_ROOMS = "*"

MAX_TEXT = 500                 # characters; a PA line, not a speech (TTS itself allows 2000)
MIN_INTERVAL_SECONDS = 2.0     # per speaker
MAX_HISTORY = 200
MAX_FILTER_WAV_BYTES = 16 * 1024 * 1024
_ROOM_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,128}$")
_PRIVATE_PREFIXES = ("dm____", "dmv2_")   # the hub's direct-message rooms (modules/hub.py)


class IntercomError(Exception):
    """A request the intercom refuses; ``status`` is the HTTP status that fits it."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def is_private_room(room: str) -> bool:
    return room.startswith(_PRIVATE_PREFIXES)


@dataclass
class IntercomGrant:
    """A single user's permission to use the intercom."""
    user_id: str
    granted_by: str
    granted_at: float
    # Which rooms this user may announce into. ALL_ROOMS = everywhere.
    rooms: Set[str] = field(default_factory=lambda: {ALL_ROOMS})
    note: str = ""
    revoked_at: Optional[float] = None
    revoked_by: Optional[str] = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    def may_announce_to(self, room: str) -> bool:
        if not self.active:
            return False
        return ALL_ROOMS in self.rooms or room in self.rooms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "rooms": sorted(self.rooms),
            "note": self.note,
            "active": self.active,
            "revoked_at": self.revoked_at,
            "revoked_by": self.revoked_by,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IntercomGrant":
        return cls(user_id=str(d["user_id"]), granted_by=str(d.get("granted_by", "")),
                   granted_at=float(d.get("granted_at", 0.0)), rooms=set(d.get("rooms") or [ALL_ROOMS]),
                   note=str(d.get("note", "")), revoked_at=d.get("revoked_at"), revoked_by=d.get("revoked_by"))


@dataclass
class Announcement:
    """A record of something said over the PA."""
    announcement_id: str
    speaker_id: str
    speaker_name: str
    text: str
    rooms: List[str]
    at: float
    had_audio: bool = False
    audio_note: str = ""
    delivered: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "announcement_id": self.announcement_id,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "text": self.text,
            "rooms": self.rooms,
            "at": self.at,
            "had_audio": self.had_audio,
            "audio_note": self.audio_note,
            "delivered": self.delivered,
            "failed": self.failed,
        }


# ── The loudspeaker filter ─────────────────────────────────────────────────────

def apply_pa_filter(
    wav_bytes: bytes,
    *,
    low_hz: float = 400.0,
    high_hz: float = 4000.0,
    compression: float = 0.7,
    drive: float = 1.6,
) -> bytes:
    """
    Make speech sound like it's coming out of a ceiling horn.

    Three stages, matching what actually happens in a real PA:
      1. Bandpass — a small horn driver can't reproduce bass or air.
         Everything below ~400Hz and above ~4kHz simply isn't there.
      2. Compression — PA amps squash dynamics so a whisper and a shout
         arrive at the same volume. This is what makes it sound "announced"
         rather than "spoken."
      3. Soft saturation — cheap amps clip. A little of this is the
         difference between "recording" and "loudspeaker."

    Pure stdlib — no numpy/scipy dependency. Operates on 16-bit PCM WAV.
    Returns WAV bytes. On any failure, returns the input unchanged, because
    an unfiltered announcement is far better than a silent one.
    """
    try:
        if len(wav_bytes) > MAX_FILTER_WAV_BYTES:
            logger.warning("PA filter: %d bytes is over its limit; sending unfiltered", len(wav_bytes))
            return wav_bytes
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            n_channels = w.getnchannels()
            sampwidth  = w.getsampwidth()
            framerate  = w.getframerate()
            n_frames   = w.getnframes()
            raw        = w.readframes(n_frames)

        if sampwidth != 2:
            logger.debug("PA filter: expected 16-bit PCM, got %d-byte samples", sampwidth)
            return wav_bytes
        if n_channels < 1 or framerate <= 0:
            return wav_bytes

        count = (len(raw) // (2 * n_channels)) * n_channels
        if count == 0:
            return wav_bytes
        interleaved = struct.unpack(f"<{count}h", raw[:count * 2])
        # Each channel is its own signal: a filter's memory must not run from left into right.
        channels = [list(interleaved[c::n_channels]) for c in range(n_channels)]

        dt = 1.0 / framerate
        rc_hp = 1.0 / (2 * math.pi * low_hz)
        a_hp  = rc_hp / (rc_hp + dt)
        rc_lp = 1.0 / (2 * math.pi * high_hz)
        a_lp  = dt / (rc_lp + dt)

        bands: List[List[float]] = []
        for samples in channels:
            # ── Stage 1: bandpass ────────────────────────────────────────────
            # One-pole highpass then one-pole lowpass. Not surgical, but the
            # gentle slope is actually closer to a real horn than a brick wall.
            prev_in = 0.0
            prev_out = 0.0
            hp: List[float] = []
            for s in samples:
                out = a_hp * (prev_out + s - prev_in)
                hp.append(out)
                prev_in = s
                prev_out = out
            prev = 0.0
            band: List[float] = []
            for s in hp:
                prev = prev + a_lp * (s - prev)
                band.append(prev)
            bands.append(band)

        # ── Stage 2 + 3: compression and saturation ──────────────────────────
        # One peak for all channels, so the stereo image keeps its balance.
        peak = max((abs(s) for band in bands for s in band), default=1.0) or 1.0

        def shape(s: float) -> int:
            x = s / peak                      # normalise to -1..1
            # Soft-knee compression via power curve — pulls quiet parts up
            sign = 1.0 if x >= 0 else -1.0
            x = sign * (abs(x) ** compression)
            # Saturation — tanh gives a smooth, valve-ish clip
            x = math.tanh(x * drive)
            # Back to int16 with a little headroom so it doesn't hard-clip
            return int(max(-1.0, min(1.0, x)) * 30000)

        shaped = [[shape(s) for s in band] for band in bands]
        out_samples = [shaped[c][i] for i in range(len(shaped[0])) for c in range(n_channels)]

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(n_channels)
            w.setsampwidth(2)
            w.setframerate(framerate)
            w.writeframes(struct.pack(f"<{len(out_samples)}h", *out_samples))
        return buf.getvalue()

    except Exception as exc:  # noqa: BLE001 — never lose an announcement
        logger.warning("PA filter failed, sending unfiltered: %s", exc)
        return wav_bytes


# ── Grants on disk ─────────────────────────────────────────────────────────────

class GrantStore:
    """The grant list as one JSON file, replaced atomically on every change."""

    def __init__(self, path: Optional[Path]):
        self.path = Path(path) if path else None

    def load(self) -> Dict[str, IntercomGrant]:
        if self.path is None or not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {g["user_id"]: IntercomGrant.from_dict(g) for g in data.get("grants", [])}
        except Exception as exc:  # noqa: BLE001
            # A damaged file must not open the PA to anyone; it keeps the copy and starts with no grants.
            damaged = self.path.with_name(self.path.name + f".damaged-{int(time.time())}")
            try:
                self.path.replace(damaged)
            except OSError:
                pass
            logger.error("Intercom grants file unreadable (%s); kept as %s, starting with no grants", exc, damaged)
            return {}

    def save(self, grants: Dict[str, IntercomGrant]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"schema": "pubcast.intercom.grants.v1",
                              "grants": [g.to_dict() for g in grants.values()]}, indent=1)
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


# ── The intercom itself ────────────────────────────────────────────────────────

class Intercom:
    """
    PA system. Holds grants, checks permission, fans announcements out.

    Does not own the hub or TTS — they're passed in, so this stays testable
    and doesn't care how audio actually reaches people. ``tts`` may be the engine
    or a function returning it (the engine is built after the routes are mounted).
    """

    def __init__(self, hub: Any = None, tts_engine: Any = None, *, grants_path: Optional[Path] = None,
                 clock: Callable[[], float] = time.monotonic,
                 record: Optional[Callable[[str, Any], Any]] = None) -> None:
        self._hub = hub
        self._record = record          # recording_modes.record_event: keeps the announcement in takes now recording
        self._tts = tts_engine
        self._store = GrantStore(grants_path)
        self._grants: Dict[str, IntercomGrant] = self._store.load()
        self._history: deque = deque(maxlen=MAX_HISTORY)
        self._last_spoke: Dict[str, float] = {}
        self._clock = clock
        self._lock = threading.Lock()

    # ═══ PERMISSION ═══════════════════════════════════════════════════════════

    def may_use(self, user_id: str, role: str, room: str = ALL_ROOMS) -> bool:
        """
        True if this user can announce into `room`.

        mod+ always may. Otherwise they need an active grant covering the room.
        """
        from modules.auth import role_gte
        if role_gte(role, INTERCOM_MIN_ROLE):
            return True
        grant = self._grants.get(user_id)
        return bool(grant and grant.may_announce_to(room))

    def grant(
        self,
        user_id: str,
        granted_by: str,
        rooms: Optional[List[str]] = None,
        note: str = "",
    ) -> IntercomGrant:
        """
        Give a user intercom access. rooms=None means everywhere.

        Re-granting an existing user replaces their grant (and un-revokes it),
        which is the behaviour a host expects when they re-add someone.
        """
        user_id = str(user_id or "").strip()
        if not user_id or len(user_id) > 128:
            raise IntercomError("user_id is required (at most 128 characters)")
        room_set = self._check_rooms(rooms) if rooms else {ALL_ROOMS}
        g = IntercomGrant(
            user_id=user_id,
            granted_by=granted_by,
            granted_at=time.time(),
            rooms=room_set,
            note=str(note or "")[:200],
        )
        with self._lock:
            previous = self._grants.get(user_id)
            self._grants[user_id] = g
            try:
                self._store.save(self._grants)
            except Exception:
                # Not saved means not granted: memory and disk must agree after a restart.
                if previous is None:
                    self._grants.pop(user_id, None)
                else:
                    self._grants[user_id] = previous
                raise
        logger.info("Intercom granted to %s by %s (rooms=%s)",
                    user_id, granted_by, sorted(g.rooms))
        return g

    def revoke(self, user_id: str, revoked_by: str) -> bool:
        """Take intercom access away. Returns False if they didn't have it."""
        with self._lock:
            g = self._grants.get(user_id)
            if not g or not g.active:
                return False
            g.revoked_at, g.revoked_by = time.time(), revoked_by
            try:
                self._store.save(self._grants)
            except Exception:
                g.revoked_at = g.revoked_by = None
                raise
        logger.info("Intercom revoked from %s by %s", user_id, revoked_by)
        return True

    def list_grants(self, include_revoked: bool = False) -> List[Dict[str, Any]]:
        return [
            g.to_dict() for g in self._grants.values()
            if include_revoked or g.active
        ]

    def check_permission(self, user_id: str, role: str, rooms: Optional[List[str]]) -> None:
        """Every targeted room must be covered: a partial grant must not reach a room it was not given."""
        targets = [ALL_ROOMS] if not rooms or ALL_ROOMS in rooms else list(self._check_rooms(rooms))
        for room in targets:
            if not self.may_use(user_id, role, room):
                label = "every room" if room == ALL_ROOMS else f"room '{room}'"
                raise IntercomError(f"No intercom access for {label}", 403)

    # ═══ ANNOUNCING ═══════════════════════════════════════════════════════════

    async def announce(
        self,
        *,
        speaker_id: str,
        speaker_name: str,
        text: str,
        rooms: Optional[List[str]] = None,
        with_audio: bool = True,
        voice_id: str = "default",
    ) -> Announcement:
        """
        Make an announcement.

        rooms=None → every room the hub knows about.
        Text always goes to chat. Audio is best-effort: if TTS is unavailable
        or has no voice, the announcement still lands as text. A PA that
        prints but doesn't speak is degraded; one that does neither is broken.
        """
        text = (text or "").strip()
        if not text:
            raise IntercomError("Announcement text is required")
        if len(text) > MAX_TEXT or "\0" in text:
            raise IntercomError(f"Announcement text is limited to {MAX_TEXT} characters", 413)
        everywhere = not rooms or ALL_ROOMS in rooms
        target_rooms = self._resolve_rooms(None if everywhere else rooms)
        if not target_rooms:
            raise IntercomError("No live room to announce into", 409)

        now = self._clock()
        with self._lock:
            last = self._last_spoke.get(speaker_id)
            if last is not None and now - last < MIN_INTERVAL_SECONDS:
                raise IntercomError("One announcement at a time: wait a moment before the next", 429)
            self._last_spoke[speaker_id] = now

        ann = Announcement(
            announcement_id=f"pa_{uuid.uuid4().hex}",
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            text=text,
            rooms=target_rooms,
            at=time.time(),
        )

        # ── Audio first, so the chat line and the sound land together ────────
        audio_b64: Optional[str] = None
        duration = 0.0
        tts = self._tts() if callable(self._tts) and not hasattr(self._tts, "synthesize") else self._tts
        if not with_audio:
            ann.audio_note = "text only, as asked"
        elif tts is None:
            ann.audio_note = "no speech engine is running; text only"
        else:
            try:
                kwargs: Dict[str, Any] = {"text": text, "character_id": "default", "language": "en", "speed": 1.0}
                if voice_id and voice_id != "default":
                    kwargs["voice_id"] = voice_id
                result = await tts.synthesize(**kwargs)
                if result.get("ok") and result.get("audio"):
                    filtered = await asyncio.to_thread(apply_pa_filter, result["audio"])
                    audio_b64 = base64.b64encode(filtered).decode("ascii")
                    duration = round(float(result.get("duration", 0.0) or 0.0), 2)
                    ann.had_audio = True
                else:
                    ann.audio_note = f"speech engine gave no audio ({result.get('error') or 'no voice'}); text only"
                    logger.debug("Intercom: TTS produced no audio (%s)",
                                 result.get("error", "no voice"))
            except Exception as exc:  # noqa: BLE001
                ann.audio_note = f"speech failed ({type(exc).__name__}); text only"
                logger.warning("Intercom TTS failed, text-only announcement: %s", exc)

        # ── Fan out to every targeted room ───────────────────────────────────
        async def reach(room: str) -> None:
            # 1. The PA event — clients play this with the horn UI
            await self._hub._broadcast(room, {
                "type": "intercom",
                "payload": {
                    "announcement_id": ann.announcement_id,
                    "speaker_id": speaker_id,
                    "speaker_name": speaker_name,
                    "text": text,
                    "room": room,
                    "all_rooms": everywhere,
                    "audio_b64": audio_b64,
                    "duration": duration,
                    "at": ann.at,
                },
            })
            # 2. The chat transcription — every announcement is on record.
            # The AI cast is not woken: an announcement is direction, not conversation.
            await self._hub.post_chat_message(room, "__intercom__", f"📢 {speaker_name}: {text}", notify_ai=False)

        if self._hub is not None:
            results = await asyncio.gather(*(reach(r) for r in target_rooms), return_exceptions=True)
            for room, res in zip(target_rooms, results):
                if isinstance(res, BaseException):
                    ann.failed[room] = f"{type(res).__name__}: {res}"[:200]
                    logger.warning("Intercom delivery to %s failed: %s", room, res)
                else:
                    ann.delivered.append(room)

        self._history.append(ann)
        if self._record is not None:
            try:
                self._record("intercom", {k: v for k, v in ann.to_dict().items()})
            except Exception:  # noqa: BLE001 — the announcement has been made; the record is secondary
                logger.exception("Intercom announcement %s could not be kept in the recording", ann.announcement_id)
        logger.info("📢 INTERCOM [%s] → %s: %s",
                    speaker_name, ",".join(target_rooms), text[:60])
        return ann

    def _check_rooms(self, rooms: List[str]) -> Set[str]:
        if not isinstance(rooms, list) or not rooms or len(rooms) > 64:
            raise IntercomError("rooms must be a list of 1 to 64 room ids")
        out: Set[str] = set()
        for room in rooms:
            if room == ALL_ROOMS:
                out.add(ALL_ROOMS)
                continue
            if not isinstance(room, str) or not _ROOM_ID.fullmatch(room):
                raise IntercomError(f"Invalid room id: {room!r}")
            if is_private_room(room):
                raise IntercomError("Private conversations are never intercom targets", 403)
            out.add(room)
        return out

    def _resolve_rooms(self, rooms: Optional[List[str]]) -> List[str]:
        """None means every live room, except private conversations."""
        if rooms:
            return sorted(self._check_rooms(rooms))
        live = getattr(self._hub, "rooms", None) if self._hub is not None else None
        return sorted(r for r in (live or {}) if not is_private_room(r))

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), MAX_HISTORY))
        return [a.to_dict() for a in list(self._history)[-limit:]]

    def status(self) -> Dict[str, Any]:
        tts = self._tts() if callable(self._tts) and not hasattr(self._tts, "synthesize") else self._tts
        return {"available": True, "speech": tts is not None, "active_grants": len(self.list_grants()),
                "announcements_kept": len(self._history), "grants_persisted": self._store.path is not None}

    def set_tts(self, tts_engine: Any) -> None:
        self._tts = tts_engine

    def set_hub(self, hub: Any) -> None:
        self._hub = hub
