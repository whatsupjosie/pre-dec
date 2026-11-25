"""
input_scorer.py — Jeremy Cricket Adaptive Awareness Suite
Converts raw user text → VarianceSignal(complexity_score, emotional_velocity).

No ML dependencies. Runs on any Python 3.9+ install.
Fast enough to call every turn without adding latency.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List

from character_engine import VarianceSignal

# ─── Word lists ───────────────────────────────────────────────────────────────

# Technical terms that increase complexity score
TECHNICAL_WORDS = {
    "server", "database", "deploy", "error", "crash", "timeout", "exception",
    "migration", "api", "endpoint", "authentication", "token", "ssl", "cert",
    "pipeline", "build", "docker", "kubernetes", "config", "module", "import",
    "function", "class", "async", "await", "thread", "memory", "cpu", "disk",
    "query", "index", "schema", "rollback", "commit", "branch", "merge", "pr",
    "regression", "dependency", "package", "version", "release", "production",
    "staging", "incident", "alert", "monitor", "log", "trace", "debug",
}

# High-intensity markers that increase velocity score
HIGH_INTENSITY_MARKERS = {
    # Urgency
    "urgent", "emergency", "now", "immediately", "asap", "critical", "broken",
    "down", "failed", "failing", "disaster", "panic", "help", "stuck", "lost",
    # Distress
    "cant", "can't", "won't", "wont", "nothing", "everything", "always",
    "never", "hate", "terrible", "awful", "horrible", "wrong", "ruined",
    # Overwhelm
    "too much", "overwhelming", "confused", "don't understand", "dont understand",
    "what do i", "i don't know", "i dont know", "no idea", "give up",
}

# Calm markers that decrease velocity score
CALM_MARKERS = {
    "okay", "ok", "fine", "thanks", "thank you", "got it", "understood",
    "makes sense", "sounds good", "will do", "no problem", "all good",
    "ready", "done", "finished", "fixed",
    # NOTE: "working" intentionally excluded — "nothing is working" is distress, not calm
}


# ─── Scorer ───────────────────────────────────────────────────────────────────

class InputScorer:
    """
    Stateful scorer. Tracks recent history to detect velocity (rate of change),
    not just current-turn intensity.
    """

    def __init__(self, history_window: int = 5):
        self._history: List[float] = []   # Recent combined scores
        self._window = history_window

    def score(self, text: str) -> VarianceSignal:
        """
        Score a single user turn. Returns a VarianceSignal ready for
        CharacterEngine.ingest_signal().
        """
        complexity  = self._score_complexity(text)
        raw_intensity = self._score_raw_intensity(text)
        velocity    = self._score_velocity(raw_intensity)

        # Update history
        combined = (complexity * 0.4) + (raw_intensity * 0.6)
        self._history.append(combined)
        if len(self._history) > self._window:
            self._history.pop(0)

        return VarianceSignal(
            timestamp=time.time(),
            complexity_score=round(complexity, 3),
            emotional_velocity=round(velocity, 3),
            raw_text=text,
        )

    def reset_history(self) -> None:
        """Call this when starting a new session or after a stability handshake."""
        self._history.clear()

    # ── Complexity ────────────────────────────────────────────────────────────

    def _score_complexity(self, text: str) -> float:
        """
        Measures cognitive load of the input.
        Combines: sentence length, technical vocabulary, structural complexity.
        """
        if not text.strip():
            return 0.0

        words = text.lower().split()
        if not words:
            return 0.0

        # 1. Sentence length (longer = more complex, caps at 50 words)
        length_score = min(len(words) / 50.0, 1.0)

        # 2. Technical vocabulary density
        tech_count = sum(1 for w in words if re.sub(r"[^a-z]", "", w) in TECHNICAL_WORDS)
        tech_score = min(tech_count / max(len(words) * 0.3, 1), 1.0)

        # 3. Punctuation complexity (colons, semicolons, parens, brackets = nested thought)
        structural_chars = len(re.findall(r"[;:()\[\]{}\-—/\\]", text))
        structural_score = min(structural_chars / 10.0, 1.0)

        # 4. Question stacking (multiple ? = confusion/overwhelm)
        question_count = text.count("?")
        question_score = min(question_count / 3.0, 1.0)

        # Weighted combination
        score = (
            length_score     * 0.30 +
            tech_score       * 0.35 +
            structural_score * 0.20 +
            question_score   * 0.15
        )
        return min(score, 1.0)

    # ── Raw Intensity ─────────────────────────────────────────────────────────

    def _score_raw_intensity(self, text: str) -> float:
        """
        Measures emotional intensity of this single turn.
        """
        if not text.strip():
            return 0.0

        lower = text.lower()
        words = lower.split()
        score = 0.0

        # 1. High-intensity keyword hits
        intensity_hits = sum(
            1 for marker in HIGH_INTENSITY_MARKERS
            if marker in lower
        )
        keyword_score = min(intensity_hits / 4.0, 1.0)

        # 2. CAPS LOCK ratio (shouting / overwhelm)
        alpha_chars = [c for c in text if c.isalpha()]
        if alpha_chars:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            # Ignore if the whole thing is uppercase by convention (acronyms etc)
            caps_score = caps_ratio if len(alpha_chars) > 5 else 0.0
        else:
            caps_score = 0.0

        # 3. Punctuation intensity (!!! ??? ...)
        exclamations = min(text.count("!") / 3.0, 1.0)
        ellipsis     = min(text.count("...") / 2.0, 1.0)
        punct_score  = (exclamations * 0.6) + (ellipsis * 0.4)

        # 4. Calm marker suppression
        calm_hits = sum(1 for marker in CALM_MARKERS if marker in lower)
        calm_suppression = min(calm_hits * 0.25, 0.5)

        # 5. Repetition (same word 3+ times = spiral / distress)
        word_counts = {}
        for w in words:
            w = re.sub(r"[^a-z]", "", w)
            if w:
                word_counts[w] = word_counts.get(w, 0) + 1
        repetition = any(v >= 3 for v in word_counts.values())
        repetition_score = 0.3 if repetition else 0.0

        raw = (
            keyword_score   * 0.45 +
            caps_score      * 0.25 +
            punct_score     * 0.15 +
            repetition_score * 0.15
        ) - calm_suppression

        return max(0.0, min(raw, 1.0))

    # ── Velocity ──────────────────────────────────────────────────────────────

    def _score_velocity(self, current_intensity: float) -> float:
        """
        Velocity = rate of change in intensity, not just current intensity.
        A sudden spike from calm is more concerning than sustained elevation.
        """
        if len(self._history) < 2:
            return current_intensity  # Not enough history — use raw

        prev_avg = sum(self._history[-3:]) / len(self._history[-3:])
        delta = current_intensity - prev_avg

        # Positive delta (escalating) weighs heavier than negative (de-escalating)
        if delta > 0:
            velocity = current_intensity + (delta * 0.5)
        else:
            velocity = current_intensity + (delta * 0.25)  # De-escalation is slower

        return max(0.0, min(velocity, 1.0))


# ─── Quick demo ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    from character_engine import CharacterEngine

    async def demo():
        scorer = InputScorer()
        engine = CharacterEngine("config.yaml")

        test_turns = [
            "Hey, things are going well today.",
            "Quick question about the database migration timeline.",
            "The server crashed and the deployment pipeline is broken and I don't know what to do",
            "NOTHING IS WORKING and I've tried everything and I'm stuck I'm stuck I'm stuck",
            "okay. I think I need a minute.",
            "okay",
            "okay",
            "okay",
            "okay",
        ]

        print("=" * 60)
        print("JEREMY CRICKET — INPUT SCORER DEMO")
        print("=" * 60)

        for turn in test_turns:
            signal = scorer.score(turn)
            mode = await engine.ingest_signal(signal)
            response_prefix = engine.apply_tone("")

            print(f"\nINPUT:      {turn[:60]}")
            print(f"complexity: {signal.complexity_score:.2f}  velocity: {signal.emotional_velocity:.2f}")
            print(f"MODE:       {mode.value}")
            if response_prefix.strip():
                print(f"TONE:       {response_prefix.strip()}")

        print("\n" + "=" * 60)
        print("Submitting stability handshake (3x)...")
        for i in range(3):
            result = await engine.submit_stability_handshake()
            print(f"  Handshake {i+1}: {'ACCEPTED — lock released' if result else 'logged, more needed'}")
        print(f"Final mode: {engine.current_mode.value}")

    asyncio.run(demo())
