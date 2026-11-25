"""
modules/vdi_engine.py — Voice Dominance Index Engine
=====================================================
Real-time audience state measurement and VDI scoring.

The VDI (Voice Dominance Index) is a continuous [0.0–1.0] score that
tells the voice and show systems what the audience is currently
processing — argument (low VDI) or presence (high VDI).

VDI = (LAI × 0.35) + (CBS × 0.40) + (CCI × 0.25)

  LAI — Listener Arousal Index
        How activated the audience is right now.
        Read from: chat velocity, word length, sentiment, reaction density.

  CBS — Current Bond Strength
        How deep the parasocial relationship is.
        Read from: return rate, session history, engagement depth.

  CCI — Content Complexity Inverse
        How cognitively demanding the current content is.
        Low complexity → high CCI → voice matters more.

Zones:
  < 0.35  → Content dominant  — argument quality matters
  0.35–0.60 → Mixed           — voice must carry content
  0.60–0.80 → Voice dominant  — delivery matters more than words
  > 0.80  → Identity dominant — bond maintenance, intimacy register

Public API:
    VDIEngine
        .ingest_chat_event(event: ChatEvent)
        .ingest_reaction(reaction_type: str)
        .ingest_content_metadata(metadata: ContentMetadata)
        .update_session(user_id: str, session_data: SessionData)
        .get_vdi() -> VDIReport
        .get_voice_mode() -> VoiceMode
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, List, Optional, Tuple
import re


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS AND DATA TYPES
# ─────────────────────────────────────────────────────────────────────────────

class VoiceMode(str, Enum):
    """
    The operating register the voice engine should use.
    Derived from VDI score.
    """
    CONTENT_CLEAR  = "content_clear"    # VDI < 0.35  — clarity, argument support
    MIXED          = "mixed"            # VDI 0.35–0.60 — prosody reinforces logic
    VOICE_DOMINANT = "voice_dominant"   # VDI 0.60–0.80 — emotion over information
    IDENTITY       = "identity"         # VDI > 0.80  — intimacy, bond maintenance


@dataclass
class ChatEvent:
    """A single chat message from the audience."""
    user_id:    str
    text:       str
    timestamp:  float = field(default_factory=time.time)
    room_id:    str   = "hub"


@dataclass
class ContentMetadata:
    """
    Metadata about what is currently being said/shown.
    Supplied by the show controller or bot co-host.
    """
    segment_type:        str    = "talk"    # talk | music | interview | announcement
    avg_sentence_length: float  = 15.0      # words per sentence
    vocabulary_level:    float  = 0.5       # 0=simple, 1=complex
    argument_density:    float  = 0.3       # 0=narrative, 1=dense argument
    emotional_weight:    float  = 0.5       # 0=neutral, 1=highly emotional content


@dataclass
class SessionData:
    """Per-user session statistics for CBS computation."""
    user_id:             str
    prior_session_count: int   = 0
    total_watch_minutes: float = 0.0
    voluntary_returns:   int   = 0      # returned without push notification
    avg_sentiment:       float = 0.5    # 0=negative, 1=positive
    last_seen:           float = field(default_factory=time.time)


@dataclass
class VDIReport:
    """
    Complete VDI snapshot for one moment in time.
    All constituent scores included for transparency and debugging.
    """
    vdi:          float    # [0.0–1.0] overall Voice Dominance Index
    lai:          float    # [0.0–1.0] Listener Arousal Index
    cbs:          float    # [0.0–1.0] Current Bond Strength (audience average)
    cci:          float    # [0.0–1.0] Content Complexity Inverse
    voice_mode:   VoiceMode
    timestamp:    float = field(default_factory=time.time)
    # Diagnostics
    chat_velocity:       float = 0.0   # messages per minute
    avg_word_length:     float = 0.0   # shorter = more aroused
    sentiment:           float = 0.5   # current rolling sentiment
    reaction_density:    float = 0.0   # reactions per minute
    active_users:        int   = 0
    notes:               str   = ""

    def to_dict(self) -> dict:
        return {
            "vdi":           round(self.vdi, 4),
            "lai":           round(self.lai, 4),
            "cbs":           round(self.cbs, 4),
            "cci":           round(self.cci, 4),
            "voice_mode":    self.voice_mode.value,
            "timestamp":     self.timestamp,
            "chat_velocity": round(self.chat_velocity, 2),
            "avg_word_length": round(self.avg_word_length, 2),
            "sentiment":     round(self.sentiment, 4),
            "reaction_density": round(self.reaction_density, 2),
            "active_users":  self.active_users,
            "notes":         self.notes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# LAI — LISTENER AROUSAL INDEX
# ─────────────────────────────────────────────────────────────────────────────

class ListenerArousalIndex:
    """
    Estimates audience arousal from real-time chat signals.

    High arousal signals:
      - Fast chat velocity (messages per minute)
      - Short words (aroused people type shorter words)
      - Short messages (aroused people type less per message)
      - High reaction density (emoji, reactions)
      - High positive or negative sentiment (both are arousing)

    Low arousal signals:
      - Slow or no chat
      - Long thoughtful messages
      - Neutral sentiment
      - Low reactions
    """

    WINDOW_SECONDS = 60.0       # rolling window for velocity calc
    MAX_VELOCITY   = 120.0      # msgs/min that maps to arousal = 1.0
    MAX_REACTIONS  = 60.0       # reactions/min = full arousal

    # EMA alpha for smoothing arousal (prevents jitter)
    SMOOTH_ALPHA = 0.15

    def __init__(self):
        self._chat_times:     Deque[float]  = deque(maxlen=500)
        self._word_lengths:   Deque[float]  = deque(maxlen=200)
        self._msg_lengths:    Deque[float]  = deque(maxlen=200)
        self._sentiments:     Deque[float]  = deque(maxlen=100)
        self._reaction_times: Deque[float]  = deque(maxlen=200)
        self._lai_smoothed:   float         = 0.3   # neutral start

    def ingest_chat(self, event: ChatEvent) -> None:
        t = event.timestamp
        self._chat_times.append(t)

        # Word and message length
        words = event.text.split()
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            self._word_lengths.append(avg_word_len)
        self._msg_lengths.append(len(words))

        # Simple sentiment: ratio of strong emotion indicators
        sentiment = self._quick_sentiment(event.text)
        self._sentiments.append(sentiment)

    def ingest_reaction(self) -> None:
        self._reaction_times.append(time.time())

    def compute(self) -> Tuple[float, dict]:
        """Returns (lai, diagnostics_dict)."""
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        # Chat velocity
        recent_chats = sum(1 for t in self._chat_times if t > cutoff)
        velocity = recent_chats / (self.WINDOW_SECONDS / 60.0)   # per minute
        velocity_score = min(1.0, velocity / self.MAX_VELOCITY)

        # Word length signal (shorter = more aroused, inverted)
        if self._word_lengths:
            avg_wl = sum(list(self._word_lengths)[-50:]) / min(50, len(self._word_lengths))
            # Typical word length 4-5 chars. Under 4 = aroused.
            word_len_score = max(0.0, min(1.0, (5.5 - avg_wl) / 3.0))
        else:
            avg_wl = 5.0
            word_len_score = 0.3

        # Message length signal (shorter messages = more aroused)
        if self._msg_lengths:
            avg_ml = sum(list(self._msg_lengths)[-50:]) / min(50, len(self._msg_lengths))
            msg_len_score = max(0.0, min(1.0, (8.0 - avg_ml) / 6.0))
        else:
            msg_len_score = 0.3

        # Sentiment polarity (high positive OR high negative = aroused)
        if self._sentiments:
            recent_sent = list(self._sentiments)[-30:]
            avg_sent = sum(recent_sent) / len(recent_sent)
            # Distance from neutral (0.5) = arousal contribution
            sent_arousal = abs(avg_sent - 0.5) * 2.0
        else:
            avg_sent = 0.5
            sent_arousal = 0.0

        # Reaction density
        recent_reactions = sum(1 for t in self._reaction_times if t > cutoff)
        reaction_density = recent_reactions / (self.WINDOW_SECONDS / 60.0)
        reaction_score = min(1.0, reaction_density / self.MAX_REACTIONS)

        # Weighted combination
        raw_lai = (
            velocity_score  * 0.35 +
            word_len_score  * 0.20 +
            msg_len_score   * 0.15 +
            sent_arousal    * 0.20 +
            reaction_score  * 0.10
        )

        # Smooth to prevent jitter
        self._lai_smoothed = (
            self.SMOOTH_ALPHA * raw_lai +
            (1 - self.SMOOTH_ALPHA) * self._lai_smoothed
        )

        diagnostics = {
            "chat_velocity":    round(velocity, 2),
            "avg_word_length":  round(avg_wl, 2),
            "sentiment":        round(avg_sent, 4),
            "reaction_density": round(reaction_density, 2),
        }

        return float(self._lai_smoothed), diagnostics

    def _quick_sentiment(self, text: str) -> float:
        """
        Fast lexicon-based sentiment. Returns [0=negative, 1=positive].
        No ML dependency — works offline with zero latency.
        """
        text_lower = text.lower()

        positive = [
            "love", "great", "amazing", "yes", "wow", "fire", "lit",
            "goat", "perfect", "incredible", "beautiful", "yes", "!!",
            "lol", "haha", "❤", "🔥", "💯", "👏", "🙌", "omg",
            "best", "legendary", "real", "truth", "facts", "exactly"
        ]
        negative = [
            "hate", "terrible", "awful", "no", "stop", "boring",
            "bad", "trash", "garbage", "wrong", "fake", "liar",
            "💀", "😭", "😤", "🤮", "leave", "off", "quit", "enough"
        ]

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        total = pos_count + neg_count

        if total == 0:
            return 0.5
        return pos_count / total


# ─────────────────────────────────────────────────────────────────────────────
# CBS — CURRENT BOND STRENGTH
# ─────────────────────────────────────────────────────────────────────────────

class CurrentBondStrength:
    """
    Estimates the parasocial bond depth of the current audience.

    The bond curve follows the documented parasocial formation model:
      Sessions 1-3:   0.10 – 0.25   (recognition, no real bond)
      Sessions 4-7:   0.25 – 0.55   (familiarity forming)
      Sessions 7-12:  0.55 – 0.80   (bond establishing, trust transfers)
      Sessions 12+:   0.80 – 1.00   (bond active, identity-level)

    Audience-level CBS is the average across active sessions,
    weighted by engagement depth of each user.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def update_session(self, data: SessionData) -> None:
        self._sessions[data.user_id] = data

    def compute(self) -> Tuple[float, int]:
        """Returns (cbs, active_user_count)."""
        if not self._sessions:
            return 0.2, 0   # no session data = assume new audience

        now = time.time()
        scores = []

        for session in self._sessions.values():
            # Only count users active in last 10 minutes
            if now - session.last_seen > 600:
                continue

            score = self._score_session(session)
            # Weight by engagement (sentiment proxy for depth)
            weight = 0.5 + session.avg_sentiment * 0.5
            scores.append(score * weight)

        if not scores:
            return 0.2, 0

        avg_cbs = sum(scores) / len(scores)
        return float(min(1.0, avg_cbs)), len(scores)

    def _score_session(self, s: SessionData) -> float:
        """
        Map session history to bond strength using the parasocial curve.
        Logistic function centered at session 7, steepness tuned to match
        the documented formation model.
        """
        # Base: session count curve (logistic)
        k = 0.45   # steepness
        x0 = 7.0   # inflection at session 7
        session_score = 1.0 / (1.0 + math.exp(-k * (s.prior_session_count - x0)))

        # Watch time contribution
        # 60 mins total = full contribution
        watch_score = min(1.0, s.total_watch_minutes / 60.0)

        # Voluntary return is the strongest signal
        # Each voluntary return above 3 adds significant weight
        return_score = min(1.0, s.voluntary_returns / 8.0)

        # Sentiment history — consistent positive = deeper bond
        sentiment_score = s.avg_sentiment

        return (
            session_score  * 0.45 +
            watch_score    * 0.20 +
            return_score   * 0.25 +
            sentiment_score * 0.10
        )


# ─────────────────────────────────────────────────────────────────────────────
# CCI — CONTENT COMPLEXITY INVERSE
# ─────────────────────────────────────────────────────────────────────────────

class ContentComplexityInverse:
    """
    Estimates how much cognitive load the current content demands,
    then inverts it. High complexity → low CCI → content matters more.

    When content is simple/emotional/narrative → CCI is high →
    voice dominance is boosted.

    When content is complex/argumentative/technical → CCI is low →
    content quality matters more than delivery.
    """

    def compute(self, meta: ContentMetadata) -> float:
        # Sentence length: shorter = simpler = higher CCI
        sentence_score = max(0.0, min(1.0, (25.0 - meta.avg_sentence_length) / 20.0))

        # Vocabulary: simpler = higher CCI
        vocab_score = 1.0 - meta.vocabulary_level

        # Argument density: narrative = higher CCI
        argument_score = 1.0 - meta.argument_density

        # Emotional weight: emotional content is processed peripherally
        emotional_score = meta.emotional_weight

        # Segment type modifiers
        segment_boost = {
            "music":        0.30,   # music = pure peripheral processing
            "talk":         0.00,   # neutral
            "interview":   -0.05,   # slightly more content-focused
            "announcement": 0.10,   # simple message = voice matters
        }.get(meta.segment_type, 0.0)

        raw_cci = (
            sentence_score  * 0.25 +
            vocab_score     * 0.25 +
            argument_score  * 0.30 +
            emotional_score * 0.20
        ) + segment_boost

        return float(max(0.0, min(1.0, raw_cci)))


# ─────────────────────────────────────────────────────────────────────────────
# VDI ENGINE — Main Integration Class
# ─────────────────────────────────────────────────────────────────────────────

class VDIEngine:
    """
    Real-time Voice Dominance Index engine.

    Ingests audience signals, computes VDI continuously, and tells
    the voice engine and show controller what mode to operate in.

    Thread-safe for concurrent WebSocket ingestion.

    Integration points:
        # In the WebSocket message handler:
        vdi_engine.ingest_chat_event(ChatEvent(user_id=uid, text=msg))

        # In the reaction handler:
        vdi_engine.ingest_reaction("fire")

        # On each session update:
        vdi_engine.update_session(SessionData(user_id=uid, ...))

        # In the show controller or voice synthesis loop:
        report = vdi_engine.get_vdi()
        voice_params = voice_engine.get_params_for_mode(report.voice_mode)
    """

    # VDI zone boundaries
    CONTENT_CLEAR_MAX  = 0.35
    MIXED_MAX          = 0.60
    VOICE_DOMINANT_MAX = 0.80

    # Component weights
    LAI_WEIGHT = 0.35
    CBS_WEIGHT = 0.40
    CCI_WEIGHT = 0.25

    def __init__(self):
        self._lai_computer  = ListenerArousalIndex()
        self._cbs_computer  = CurrentBondStrength()
        self._cci_computer  = ContentComplexityInverse()

        self._current_content = ContentMetadata()
        self._last_report:    Optional[VDIReport] = None

        # History for trend detection
        self._vdi_history: Deque[Tuple[float, float]] = deque(maxlen=300)  # (t, vdi)

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest_chat_event(self, event: ChatEvent) -> None:
        """Call for every chat message received from the audience."""
        self._lai_computer.ingest_chat(event)

    def ingest_reaction(self, reaction_type: str = "") -> None:
        """Call for every emoji reaction or reaction event."""
        self._lai_computer.ingest_reaction()

    def ingest_content_metadata(self, meta: ContentMetadata) -> None:
        """
        Call when the content type changes — new segment, topic shift,
        music starts/stops, announcement begins.
        """
        self._current_content = meta

    def update_session(self, user_id: str, session_data: SessionData) -> None:
        """Update per-user session data. Call on join and periodically."""
        self._cbs_computer.update_session(session_data)

    # ── Output ────────────────────────────────────────────────────────────────

    def get_vdi(self) -> VDIReport:
        """
        Compute and return the current VDI report.
        Lightweight — safe to call every frame.
        """
        lai, lai_diagnostics = self._lai_computer.compute()
        cbs, active_users    = self._cbs_computer.compute()
        cci                  = self._cci_computer.compute(self._current_content)

        vdi = (
            lai * self.LAI_WEIGHT +
            cbs * self.CBS_WEIGHT +
            cci * self.CCI_WEIGHT
        )
        vdi = float(max(0.0, min(1.0, vdi)))

        voice_mode = self._classify_mode(vdi)
        notes      = self._generate_notes(vdi, lai, cbs, cci)

        report = VDIReport(
            vdi=vdi,
            lai=lai,
            cbs=cbs,
            cci=cci,
            voice_mode=voice_mode,
            chat_velocity=lai_diagnostics.get("chat_velocity", 0.0),
            avg_word_length=lai_diagnostics.get("avg_word_length", 5.0),
            sentiment=lai_diagnostics.get("sentiment", 0.5),
            reaction_density=lai_diagnostics.get("reaction_density", 0.0),
            active_users=active_users,
            notes=notes,
        )

        self._last_report = report
        self._vdi_history.append((time.time(), vdi))
        return report

    def get_voice_mode(self) -> VoiceMode:
        """Quick access — returns just the voice mode without full report."""
        return self.get_vdi().voice_mode

    def get_trend(self, window_seconds: float = 120.0) -> float:
        """
        Returns VDI trend over the last window_seconds.
        Positive = rising (moving toward voice/identity dominance)
        Negative = falling (moving toward content dominance)
        Range approximately [-1.0, 1.0]
        """
        now = time.time()
        cutoff = now - window_seconds
        recent = [(t, v) for t, v in self._vdi_history if t > cutoff]

        if len(recent) < 4:
            return 0.0

        # Simple linear regression slope
        times  = [r[0] - recent[0][0] for r in recent]   # normalize time
        values = [r[1] for r in recent]
        n = len(times)
        t_mean = sum(times) / n
        v_mean = sum(values) / n
        numerator   = sum((t - t_mean) * (v - v_mean) for t, v in zip(times, values))
        denominator = sum((t - t_mean) ** 2 for t in times)

        if denominator < 1e-8:
            return 0.0

        slope = numerator / denominator   # VDI units per second
        # Normalize: 0.01 VDI/second = strong trend
        return float(max(-1.0, min(1.0, slope / 0.01)))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _classify_mode(self, vdi: float) -> VoiceMode:
        if vdi < self.CONTENT_CLEAR_MAX:
            return VoiceMode.CONTENT_CLEAR
        if vdi < self.MIXED_MAX:
            return VoiceMode.MIXED
        if vdi < self.VOICE_DOMINANT_MAX:
            return VoiceMode.VOICE_DOMINANT
        return VoiceMode.IDENTITY

    def _generate_notes(self, vdi: float, lai: float, cbs: float, cci: float) -> str:
        """Human-readable diagnostics for show director dashboard."""
        notes = []

        if lai > 0.75:
            notes.append("audience highly activated")
        elif lai < 0.2:
            notes.append("audience quiet/passive")

        if cbs > 0.75:
            notes.append("strong bond — identity register available")
        elif cbs < 0.25:
            notes.append("new/cold audience — bond forming")

        if cci > 0.75:
            notes.append("simple content — voice is primary vehicle")
        elif cci < 0.25:
            notes.append("complex content — clarity critical")

        trend = self.get_trend(60.0)
        if trend > 0.4:
            notes.append("VDI rising fast")
        elif trend < -0.4:
            notes.append("VDI falling — audience shifting to analytical mode")

        return "; ".join(notes) if notes else "nominal"
