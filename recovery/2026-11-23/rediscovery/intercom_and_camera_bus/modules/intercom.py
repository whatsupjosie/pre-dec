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
"""
from __future__ import annotations

import io
import logging
import math
import struct
import time
import wave
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("pubcast.intercom")

# Role at or above which intercom is automatic (no grant needed)
INTERCOM_MIN_ROLE = "mod"

# Sentinel meaning "every room"
ALL_ROOMS = "*"


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
        }


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "announcement_id": self.announcement_id,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "text": self.text,
            "rooms": self.rooms,
            "at": self.at,
            "had_audio": self.had_audio,
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
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            n_channels = w.getnchannels()
            sampwidth  = w.getsampwidth()
            framerate  = w.getframerate()
            n_frames   = w.getnframes()
            raw        = w.readframes(n_frames)

        if sampwidth != 2:
            logger.debug("PA filter: expected 16-bit PCM, got %d-byte samples", sampwidth)
            return wav_bytes

        count = len(raw) // 2
        samples = list(struct.unpack(f"<{count}h", raw))

        # ── Stage 1: bandpass ────────────────────────────────────────────────
        # One-pole highpass then one-pole lowpass. Not surgical, but the
        # gentle slope is actually closer to a real horn than a brick wall.
        dt = 1.0 / framerate

        rc_hp = 1.0 / (2 * math.pi * low_hz)
        a_hp  = rc_hp / (rc_hp + dt)
        prev_in = 0.0
        prev_out = 0.0
        hp: List[float] = []
        for s in samples:
            out = a_hp * (prev_out + s - prev_in)
            hp.append(out)
            prev_in = s
            prev_out = out

        rc_lp = 1.0 / (2 * math.pi * high_hz)
        a_lp  = dt / (rc_lp + dt)
        prev = 0.0
        band: List[float] = []
        for s in hp:
            prev = prev + a_lp * (s - prev)
            band.append(prev)

        # ── Stage 2 + 3: compression and saturation ──────────────────────────
        peak = max((abs(s) for s in band), default=1.0) or 1.0

        out_samples: List[int] = []
        for s in band:
            x = s / peak                      # normalise to -1..1
            # Soft-knee compression via power curve — pulls quiet parts up
            sign = 1.0 if x >= 0 else -1.0
            x = sign * (abs(x) ** compression)
            # Saturation — tanh gives a smooth, valve-ish clip
            x = math.tanh(x * drive)
            # Back to int16 with a little headroom so it doesn't hard-clip
            v = int(max(-1.0, min(1.0, x)) * 30000)
            out_samples.append(v)

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


# ── The intercom itself ────────────────────────────────────────────────────────

class Intercom:
    """
    PA system. Holds grants, checks permission, fans announcements out.

    Does not own the hub or TTS — they're passed in, so this stays testable
    and doesn't care how audio actually reaches people.
    """

    def __init__(self, hub: Any = None, tts_engine: Any = None) -> None:
        self._hub = hub
        self._tts = tts_engine
        self._grants: Dict[str, IntercomGrant] = {}
        self._history: List[Announcement] = []
        self._max_history = 200

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
        g = IntercomGrant(
            user_id=user_id,
            granted_by=granted_by,
            granted_at=time.time(),
            rooms=set(rooms) if rooms else {ALL_ROOMS},
            note=note,
        )
        self._grants[user_id] = g
        logger.info("Intercom granted to %s by %s (rooms=%s)",
                    user_id, granted_by, sorted(g.rooms))
        return g

    def revoke(self, user_id: str, revoked_by: str) -> bool:
        """Take intercom access away. Returns False if they didn't have it."""
        g = self._grants.get(user_id)
        if not g or not g.active:
            return False
        g.revoked_at = time.time()
        logger.info("Intercom revoked from %s by %s", user_id, revoked_by)
        return True

    def list_grants(self, include_revoked: bool = False) -> List[Dict[str, Any]]:
        return [
            g.to_dict() for g in self._grants.values()
            if include_revoked or g.active
        ]

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
            raise ValueError("Announcement text is required")

        target_rooms = self._resolve_rooms(rooms)

        ann = Announcement(
            announcement_id=f"pa_{int(time.time() * 1000)}",
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            text=text,
            rooms=target_rooms,
            at=time.time(),
        )

        # ── Audio first, so the chat line and the sound land together ────────
        audio_b64: Optional[str] = None
        duration = 0.0
        if with_audio and self._tts is not None:
            try:
                result = await self._tts.synthesize(
                    text=text, character_id=voice_id, language="en", speed=1.0,
                )
                if result.get("ok") and result.get("audio"):
                    filtered = apply_pa_filter(result["audio"])
                    import base64
                    audio_b64 = base64.b64encode(filtered).decode("ascii")
                    duration = round(result.get("duration", 0.0), 2)
                    ann.had_audio = True
                else:
                    logger.debug("Intercom: TTS produced no audio (%s)",
                                 result.get("error", "no voice"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Intercom TTS failed, text-only announcement: %s", exc)

        # ── Fan out to every targeted room ───────────────────────────────────
        if self._hub is not None:
            for room in target_rooms:
                # 1. The PA event — clients play this with the horn UI
                try:
                    await self._hub._broadcast(room, {
                        "type": "intercom",
                        "payload": {
                            "announcement_id": ann.announcement_id,
                            "speaker_id": speaker_id,
                            "speaker_name": speaker_name,
                            "text": text,
                            "room": room,
                            "all_rooms": rooms is None,
                            "audio_b64": audio_b64,
                            "duration": duration,
                            "at": ann.at,
                        },
                    })
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Intercom broadcast to %s failed: %s", room, exc)

                # 2. The chat transcription — every announcement is on record
                try:
                    await self._hub.post_chat_message(
                        room, "__intercom__", f"📢 {speaker_name}: {text}",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Intercom chat post to %s failed: %s", room, exc)

        self._history.append(ann)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info("📢 INTERCOM [%s] → %s: %s",
                    speaker_name, ",".join(target_rooms), text[:60])
        return ann

    def _resolve_rooms(self, rooms: Optional[List[str]]) -> List[str]:
        """None or ['*'] means every live room."""
        if rooms and ALL_ROOMS not in rooms:
            return list(rooms)
        if self._hub is not None and getattr(self._hub, "rooms", None):
            return sorted(self._hub.rooms.keys())
        return []

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._history[-limit:]]

    def set_tts(self, tts_engine: Any) -> None:
        self._tts = tts_engine

    def set_hub(self, hub: Any) -> None:
        self._hub = hub
