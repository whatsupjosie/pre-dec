"""
extractors/conversation.py
══════════════════════════
Conversation extractor for the Code Collector memory layer.

Captures structured context from AI chat sessions — what was built,
what was decided, what's broken, what's next — and stores it in the
index so the next session picks up where this one left off.

Currently targets Claude. Generalizes to any AI platform via platform_id.

PAYLOAD OUTPUT
──────────────
Produces standard Code Collector blocks with:
  language        = "conversation"
  content         = full turn text
  purpose_hint    = auto-summarized decision or finding
  context_before  = prior turn (what prompted this)
  context_after   = next turn (what it led to)
  detected_filename = any filename mentioned in the turn

SESSION SUMMARY
───────────────
At end of session, produces one summary block with:
  - Files touched (mentioned or captured)
  - Decisions made
  - What's broken / open questions
  - What was built
  - Recommended next steps

Rear View Foresight LLC — Feic Mo Chroí
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Patterns
# ─────────────────────────────────────────────────────────────────────────────

# Files mentioned in conversation
_FILE_PATTERN = re.compile(
    r'\b([\w\-/]+\.(py|js|ts|jsx|tsx|css|html|json|yaml|yml|md|sh|env|'
    r'toml|ini|cfg|sql|rs|go|java|rb|php|swift|kt|cpp|c|h|vue|svelte))\b',
    re.IGNORECASE,
)

# Decision markers — things that signal a conclusion was reached
_DECISION_MARKERS = [
    r'\blet\'s\s+(use|go with|do|build|add|replace|remove|switch)\b',
    r'\bwe\'ll\s+(use|go with|do|build|add|replace|remove|switch)\b',
    r'\bthe (fix|solution|approach|answer|plan) is\b',
    r'\buse\s+\w+\s+instead\b',
    r'\bchanged? (to|from)\b',
    r'\bfixed?\b',
    r'\bworking\b',
    r'\bdone\b',
    r'\bcomplete[d]?\b',
    r'\bready\b',
]
_DECISION_RE = re.compile('|'.join(_DECISION_MARKERS), re.IGNORECASE)

# Break markers — things that signal something is broken or open
_BREAK_MARKERS = [
    r'\bbroken?\b',
    r'\bbug\b',
    r'\berror\b',
    r'\bfail(s|ed|ing)?\b',
    r'\bdoesn\'t work\b',
    r'\bnot working\b',
    r'\btodo\b',
    r'\bstill need[s]?\b',
    r'\bnext step[s]?\b',
    r'\bstill missing\b',
    r'\bopen question\b',
    r'\bunresolved\b',
]
_BREAK_RE = re.compile('|'.join(_BREAK_MARKERS), re.IGNORECASE)

# Build markers — things that signal something was created
_BUILD_MARKERS = [
    r'\bbuilt?\b',
    r'\bcreated?\b',
    r'\badded?\b',
    r'\bwrote?\b',
    r'\bimplemented?\b',
    r'\bgenerated?\b',
    r'\bproduced?\b',
    r'\bnew\s+\w+\b',
]
_BUILD_RE = re.compile('|'.join(_BUILD_MARKERS), re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

# Known URL-like top-level path segments that are not real project directories.
# These appear when _FILE_PATTERN matches a filename inside a URL path.
_URL_SEGMENT_NOISE = frozenset([
    "ai", "com", "org", "net", "io", "dev", "app", "api", "www",
    "http", "https", "chat", "web", "cdn", "static", "assets",
    "public", "media", "upload", "download", "v1", "v2", "v3",
])

# System/vendor path prefixes — never project files
_SYSTEM_PREFIXES = (
    "node_modules/", "site-packages/", "/usr/", "/lib/",
    "/opt/", "/home/", ".npm/", ".cargo/", "/proc/", "/sys/",
    "dist/node_modules/",
)


def _is_project_file(path: str) -> bool:
    """
    Filter out false positives from _FILE_PATTERN:
    - URL path fragments  (ai/chat/main.py, com/api/config.json)
    - Vendor/system paths (node_modules/, site-packages/, /usr/)
    - Excessively deep paths that look like system paths
    Only keep simple filenames or shallow relative paths that look like
    real project files a developer would actually touch.
    """
    if not path:
        return False

    # Reject known system/vendor prefixes — also check for them anywhere in the path
    # e.g. "11/site-packages/requests/models.py" starts with "11/" not "site-packages/"
    # but still contains the noise segment
    if any(path.startswith(p) for p in _SYSTEM_PREFIXES):
        return False
    _SYSTEM_SEGMENTS = frozenset(["site-packages", "node_modules", "dist-packages"])
    if any((f"/{s}/" in path or path.startswith(s + "/")) for s in _SYSTEM_SEGMENTS):
        return False

    parts = path.split("/")

    # Reject paths deeper than 5 components — system/vendor paths are deep
    if len(parts) > 5:
        return False

    # Reject paths whose first segment is a known URL-like noise word
    # e.g. "ai/chat/main.py" → first segment "ai" is a TLD/URL fragment
    if len(parts) > 1 and parts[0].lower() in _URL_SEGMENT_NOISE:
        return False

    # Reject paths with domain-pattern first segment (e.g. "example.com/api/x.py")
    if len(parts) > 1 and re.match(r'^[a-z0-9-]+\.[a-z]{2,}$', parts[0], re.IGNORECASE):
        return False

    return True


@dataclass
class ConversationTurn:
    role:       str           # "user" | "assistant"
    content:    str
    timestamp:  float = field(default_factory=time.time)
    turn_index: int   = 0

    def mentions_files(self) -> List[str]:
        raw = [m.group(1) for m in _FILE_PATTERN.finditer(self.content)]
        return list(dict.fromkeys(
            f for f in raw if _is_project_file(f)
        ))

    def has_decision(self) -> bool:
        return bool(_DECISION_RE.search(self.content))

    def has_break(self) -> bool:
        return bool(_BREAK_RE.search(self.content))

    def has_build(self) -> bool:
        return bool(_BUILD_RE.search(self.content))

    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class SessionSummary:
    session_id:    str
    source_url:    str
    source_title:  str
    started_at:    float
    ended_at:      float
    platform:      str           # "claude" | "chatgpt" | "gemini" | ...
    files_touched: List[str]     = field(default_factory=list)
    decisions:     List[str]     = field(default_factory=list)
    breaks:        List[str]     = field(default_factory=list)
    builds:        List[str]     = field(default_factory=list)
    next_steps:    List[str]     = field(default_factory=list)
    turn_count:    int           = 0
    total_words:   int           = 0

    def to_context_block(self) -> Dict[str, Any]:
        """
        Format as a Code Collector payload block.
        This is what gets injected into the next session.
        """
        lines = []

        if self.builds:
            lines.append("WHAT WAS BUILT")
            for b in self.builds[:5]:
                lines.append(f"  • {b}")
            lines.append("")

        if self.decisions:
            lines.append("DECISIONS MADE")
            for d in self.decisions[:5]:
                lines.append(f"  • {d}")
            lines.append("")

        if self.breaks:
            lines.append("BROKEN / OPEN")
            for b in self.breaks[:5]:
                lines.append(f"  • {b}")
            lines.append("")

        if self.next_steps:
            lines.append("NEXT STEPS")
            for n in self.next_steps[:3]:
                lines.append(f"  • {n}")
            lines.append("")

        if self.files_touched:
            lines.append("FILES TOUCHED")
            lines.append("  " + ", ".join(self.files_touched[:10]))

        content = "\n".join(lines).strip()

        return {
            "content":            content,
            "language":           "conversation",
            "purpose_hint":       f"Session summary — {self.platform} — {len(self.decisions)} decisions, {len(self.breaks)} open",
            "context_before":     self.source_url,
            "context_after":      "",
            "detected_filename":  None,
            "session_id":         self.session_id,
            "content_hash":       hashlib.sha256(content.encode()).hexdigest()[:16],
            "platform":           self.platform,
            "captured_at":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.ended_at)),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Extractor
# ─────────────────────────────────────────────────────────────────────────────

class ConversationExtractor:
    """
    Extracts structured context from a list of conversation turns.

    Usage:
        extractor = ConversationExtractor(
            session_id  = "abc123",
            source_url  = "https://claude.ai/chat/xyz",
            source_title= "Claude",
            platform    = "claude",
        )
        extractor.ingest(turns)   # list of ConversationTurn
        summary = extractor.summarize()
        blocks  = extractor.to_blocks()
    """

    def __init__(
        self,
        session_id:   str,
        source_url:   str,
        source_title: str = "Claude",
        platform:     str = "claude",
        started_at:   Optional[float] = None,
    ) -> None:
        self.session_id   = session_id
        self.source_url   = source_url
        self.source_title = source_title
        self.platform     = platform
        self.started_at   = started_at or time.time()
        self._turns: List[ConversationTurn] = []

    def ingest(self, turns: List[ConversationTurn]) -> None:
        """Add turns to the extractor."""
        for i, t in enumerate(turns):
            t.turn_index = i
        self._turns = turns

    MAX_TURNS        = 500   # beyond this a session is pathological
    MAX_CONTENT_CHARS = 50_000  # per turn — prevents regex DoS on huge turns

    def ingest_raw(self, raw_turns: List[Dict[str, Any]]) -> None:
        """
        Ingest from raw dicts (as sent by the browser extension).
        Each dict: { "role": "user"|"assistant", "content": str, "ts": float }
        """
        if not isinstance(raw_turns, list):
            return

        turns = []
        for i, d in enumerate(raw_turns[:self.MAX_TURNS]):
            if not isinstance(d, dict):
                continue
            # content must be a string — non-string crashes regex engines downstream
            raw_content = d.get("content", "")
            content = str(raw_content) if not isinstance(raw_content, str) else raw_content
            # Cap per-turn content to prevent regex DoS on enormous turns
            content = content[:self.MAX_CONTENT_CHARS]

            role = d.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"

            turns.append(ConversationTurn(
                role       = role,
                content    = content,
                timestamp  = d.get("ts", time.time()) if isinstance(d.get("ts"), (int, float)) else time.time(),
                turn_index = i,
            ))
        self.ingest(turns)

    def summarize(self) -> SessionSummary:
        """
        Produce a SessionSummary from the ingested turns.
        Extracts files, decisions, breaks, builds, next steps.
        """
        all_files:    List[str] = []
        decisions:    List[str] = []
        breaks:       List[str] = []
        builds:       List[str] = []
        next_steps:   List[str] = []
        total_words   = 0

        for turn in self._turns:
            total_words += turn.word_count()
            all_files.extend(turn.mentions_files())

            # Only extract signal from assistant turns — user turns are prompts
            if turn.role != "assistant":
                continue

            sentences = _split_sentences(turn.content)
            for sentence in sentences:
                s = sentence.strip()
                if len(s) < 20 or len(s) > 300:
                    continue

                if _DECISION_RE.search(s):
                    decisions.append(_clean_sentence(s))
                elif _BREAK_RE.search(s):
                    breaks.append(_clean_sentence(s))
                elif _BUILD_RE.search(s):
                    builds.append(_clean_sentence(s))

                # Next steps: sentences after "Next" / "Step N" / numbered lists
                if re.match(r'^(next|step \d+|\d+\.)', s, re.IGNORECASE):
                    next_steps.append(_clean_sentence(s))

        # Deduplicate
        seen_files = dict.fromkeys(all_files)
        seen_decisions = _deduplicate_sentences(decisions)
        seen_breaks    = _deduplicate_sentences(breaks)
        seen_builds    = _deduplicate_sentences(builds)
        seen_next      = _deduplicate_sentences(next_steps)

        return SessionSummary(
            session_id    = self.session_id,
            source_url    = self.source_url,
            source_title  = self.source_title,
            platform      = self.platform,
            started_at    = self.started_at,
            ended_at      = time.time(),
            files_touched = list(seen_files.keys())[:20],
            decisions     = seen_decisions[:10],
            breaks        = seen_breaks[:10],
            builds        = seen_builds[:10],
            next_steps    = seen_next[:5],
            turn_count    = len(self._turns),
            total_words   = total_words,
        )

    def to_blocks(self) -> List[Dict[str, Any]]:
        """
        Convert turns to Code Collector payload blocks.
        One block per assistant turn with substantial content.
        Plus one summary block at the end.
        """
        blocks = []

        for i, turn in enumerate(self._turns):
            if turn.role != "assistant":
                continue
            if turn.word_count() < 30:
                continue

            prev_turn = self._turns[i - 1] if i > 0 else None
            next_turn = self._turns[i + 1] if i < len(self._turns) - 1 else None

            files = turn.mentions_files()
            content_hash = hashlib.sha256(turn.content.encode()).hexdigest()[:16]

            blocks.append({
                "content":           turn.content,
                "language":          "conversation",
                "purpose_hint":      _derive_purpose(turn),
                "context_before":    prev_turn.content[:300] if prev_turn else "",
                "context_after":     next_turn.content[:300] if next_turn else "",
                "detected_filename": files[0] if files else None,
                "session_id":        self.session_id,
                "content_hash":      content_hash,
                "platform":          self.platform,
                "captured_at":       time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(turn.timestamp)
                ),
            })

        # Append session summary block
        summary = self.summarize()
        blocks.append(summary.to_context_block())

        return blocks

    def to_payload(self, target: str = "primary") -> Dict[str, Any]:
        """
        Full Code Collector POST payload — ready to send to /collect.
        """
        return {
            "source_url":   self.source_url,
            "source_title": self.source_title,
            "captured_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target":       target,
            "session_id":   self.session_id,
            "blocks":       self.to_blocks(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    """Split text into sentences. Handles markdown and code blocks gracefully."""
    # Remove code blocks — they're captured separately
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+|(?<=\n)[-•*]\s*', text)
    return [s.strip() for s in sentences if s.strip()]


def _clean_sentence(s: str) -> str:
    """Trim markdown, bullets, numbering from a sentence."""
    # Strip inline markup FIRST — before the leading-bullet regex runs.
    # The bullet stripper uses ^[-•*\d\.]+ which eats the opening ** of bold
    # markup, leaving orphaned ** that the bold regex can never match.
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)  # **bold**
    s = re.sub(r'\*([^*]+)\*',    r'\1', s)  # *italic*
    s = re.sub(r'`([^`]+)`',      r'\1', s)  # `code`
    # Strip leading bullets/numbers.
    # Include * as bullet only when NOT followed by * (** would be bold, already handled).
    # Pattern: [-•\d\.]+ handles dash/bullet/number, \* handles single-star bullets.
    s = re.sub(r'^(?:[-•\d\.]+|\*(?!\*))\s*', '', s)
    return s.strip()


def _derive_purpose(turn: ConversationTurn) -> str:
    """Derive a short purpose hint from a turn."""
    if turn.has_decision():
        return "decision"
    if turn.has_build():
        return "build"
    if turn.has_break():
        return "break / open issue"
    # Fall back to first non-empty sentence
    sentences = _split_sentences(turn.content)
    for s in sentences:
        if len(s) > 20:
            return _clean_sentence(s)[:80]
    return "assistant response"


def _deduplicate_sentences(sentences: List[str]) -> List[str]:
    """Deduplicate by normalized content."""
    seen = {}
    for s in sentences:
        key = re.sub(r'\s+', ' ', s.lower().strip())[:60]
        if key and key not in seen:
            seen[key] = s
    return list(seen.values())


# ─────────────────────────────────────────────────────────────────────────────
# CLI — for testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Quick smoke test
    turns = [
        ConversationTurn(role="user",      content="What's the best way to fix the import error in bots.py?"),
        ConversationTurn(role="assistant", content="The import on line 12 is wrong. Let's use `from jeremy_cricket import JeremyCricket, create_jeremy_cricket, JeremyConfig` instead. That's the fix."),
        ConversationTurn(role="user",      content="ok what about the nudge method"),
        ConversationTurn(role="assistant", content="The nudge() method in bots.py is broken — it targets the wrong object structure. I built a corrected version that works with BotSession objects. The fix is ready in nudge_corrected.py."),
        ConversationTurn(role="user",      content="what still needs doing"),
        ConversationTurn(role="assistant", content="Next steps: 1. Wire watch_room() into room creation. 2. Add Jeremy initialization to main.py. 3. Fix the bot- vs bot_ prefix on line 214 of jeremy_cricket.py. The hub.get_recent_history fix is still open too."),
    ]

    extractor = ConversationExtractor(
        session_id   = uuid.uuid4().hex[:12],
        source_url   = "https://claude.ai/chat/test",
        source_title = "Claude",
        platform     = "claude",
    )
    extractor.ingest(turns)

    summary = extractor.summarize()
    print("=== SUMMARY ===")
    print(f"Files:     {summary.files_touched}")
    print(f"Decisions: {summary.decisions}")
    print(f"Breaks:    {summary.breaks}")
    print(f"Builds:    {summary.builds}")
    print(f"Next:      {summary.next_steps}")
    print()
    print("=== CONTEXT BLOCK ===")
    print(summary.to_context_block()["content"])
