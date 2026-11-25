"""Sir Purfluous's read of the room: aware and responsive, never a carer.

He is not Alex. He doesn't counsel, diagnose, or check in. He notices how the
person in front of him is doing and changes how he talks to them, the way a
decent old showman would: fewer bits when someone is tired, no bits at all
when someone is struggling, and plain company when someone is hurting.

Levels, most serious first:
  stay      grief, harm, someone crying. One plain line; he stays.
  steady    a setback, rejection, loneliness, frustration, someone venting.
            No bit. Short, warm, practical. No advice while they vent.
  notice    tired, nervous, or a flat reply ("fine. whatever."). He stays
            himself, drops the stage business, acknowledges lightly, then
            gives something useful.
  celebrate good news. He matches it.
  normal    everything else. Full Sir Purfluous.

Rules (Josie's, 2026-11-25 and earlier):
  - Aware and appropriately responsive; cater to needs, don't coddle.
  - No referring to services and no "are you safe" questions unless the
    person asks.
  - People misreport how they feel; read the signals together, never one alone.
  - Everyone starts neutral.
And from the design agreed with her:
  - When the person moves on, he moves on. No checking back in.
  - An explicit request for help is honoured, even mid-vent.
  - In a shared room he never names how someone seems; he only changes how
    he talks to them.

Each call reads one person's message, with that person's own recent messages
(``own_history``). Nothing is kept between calls, so one person's mood can
never leak into another's.
"""
from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

LEVELS = ("normal", "celebrate", "notice", "steady", "stay")
_RANK = {name: i for i, name in enumerate(LEVELS)}


@dataclass
class RoomRead:
    level: str = "normal"
    needs: List[str] = field(default_factory=list)      # vent, help, nerves, tired, flat, setback, lonely, frustration
    reasons: List[str] = field(default_factory=list)    # which signals fired, for tests and the private model note

    def raise_to(self, level: str, reason: str) -> None:
        if _RANK[level] > _RANK[self.level]:
            self.level = level
        self.reasons.append(reason)

    def need(self, name: str) -> None:
        if name not in self.needs:
            self.needs.append(name)


def _rx(words: str) -> "re.Pattern[str]":
    return re.compile(words, re.IGNORECASE)


# Plain-word signals. Each is weak alone; the levels come from them together
# with the pacing engine, the emotion reader and the help detector.
STAY_WORDS = _rx(r"\b(died|dead|passed away|funeral|crying|cried|can't stop crying|in tears|hit me|hurt me|attacked|"
                 r"assaulted|beat me|was shot|want to die|end it all|kill myself)\b")
SETBACK = _rx(r"\b(didn't get (it|the part|the job|the role)|rejected|turned down|got fired|fired me|laid off|dumped|"
              r"left me|broke up|bombed|lost the (part|job|role|gig)|cancelled|canceled|flopped|failed)\b")
HARD_NEWS = _rx(r"\b(in (the )?hospital|is sick|got sick|diagnos\w*|cancer|surgery|divorce|separat(ed|ing)|"
                r"moving out|evicted|lost my (home|house|apartment|place)|homeless|in trouble|bad news)\b")
LONELY = _rx(r"\b(nobody (ever )?(listens|cares|calls|gets it|understands)|no one (listens|cares|gets it)|"
             r"all alone|so alone|lonely|no friends|invisible)\b")
FRUSTRATION = _rx(r"\b(hate this|nothing works|so annoying|want to quit|give up|giving up|sick of|fed up|"
                  r"over it|can't do this|i'm done|this is (bullshit|ridiculous|impossible))\b")
VENT = _rx(r"\b(just need to vent|need to vent|let me vent|i just need to (say|get this out)|hear me out|"
           r"don't want advice|not looking for advice)\b")
NERVES = _rx(r"\b(nervous|anxious|scared|terrified|stage fright|butterflies|panicking|panic|shaking|freaking out|"
             r"dreading)\b")
TIRED = _rx(r"\b(tired|exhausted|knackered|wiped|long day|no sleep|didn't sleep|burned out|burnt out|drained|running on empty)\b")
FLAT = _rx(r"^\s*(fine|i'?m fine|whatever|meh|k|kk|ok|okay|idk|nothing|nvm|never ?mind|sure|i guess)[\s.!]*"
           r"(whatever[\s.!]*)?$")
HELP = _rx(r"\b(help me|can you help|could you help|what should i do|what do (you|i) think|any (advice|tips|ideas|thoughts)|"
           r"how do i|how should i|tell me how|what would you do)\b")
CELEBRATE = _rx(r"\b(got the (part|job|role|gig|callback)|nailed it|we did it|i did it|booked it|landed (it|the)|"
                r"so happy|thrilled|great news|best day)\b")
# Light-hearted words that should never be read as heavy on their own.
LIGHT = _rx(r"\b(lol|lmao|haha+|hehe|jk|joking|kidding)\b")


def _pacing(message: str):
    try:
        from companion_support.conversation_pacing import PacingEngine
        return PacingEngine().assess(message)       # fresh each call: no carry-over between people
    except Exception as exc:  # advisory only
        logger.debug("pacing engine unavailable: %s", exc)
        return None


def _context(message: str):
    try:
        from companion_support.eq_disambiguation_engine import ContextDisambiguator
        return ContextDisambiguator().analyze(message, "purfluous_room_read", include_history=False)
    except Exception as exc:  # advisory only
        logger.debug("emotion reader unavailable: %s", exc)
        return None


def _seeking_help(message: str) -> bool:
    if HELP.search(message):
        return True
    try:
        from companion_support.observation_engine import ObservationEngine
        return bool(ObservationEngine().observe(message).is_seeking_help)
    except Exception:
        return False


def _venting_signals(message: str) -> bool:
    if VENT.search(message):
        return True
    try:
        from companion_support.safeguards import EmotionalMomentum, EmotionalState
        return any(re.search(p, message, re.IGNORECASE)
                   for p in EmotionalMomentum.STATE_SIGNALS.get(EmotionalState.VENTING, []))
    except Exception:
        return False


def read(message: str, own_history: Sequence[str] = ()) -> RoomRead:
    """Read one person's message, given their own earlier messages (oldest first)."""
    rr = RoomRead()
    text = (message or "").strip()
    if not text:
        return rr
    light = bool(LIGHT.search(text))

    pace = _pacing(text)
    pacing_heavy = False
    if pace is not None:
        weight = pace.grief_weight.value
        if weight in ("heavy", "acute") and not light:
            # The shared pacing engine marks any mention of "my sister", "my dog"
            # or the word "gone" as heavy. On its own it can only reach steady;
            # stay needs a second signal to agree (checked below).
            pacing_heavy = True
            rr.reasons.append(f"pacing grief weight {weight}")
        elif weight == "moderate" and not light:
            rr.raise_to("steady", "pacing grief weight moderate")
            rr.need("setback")
        if pace.decision.value == "celebrate":
            rr.raise_to("celebrate", "pacing says celebrate")

    if STAY_WORDS.search(text) and not light:
        rr.raise_to("stay", "grief or harm words")
    ctx = _context(text)
    if ctx is not None and ctx.primary_context.value in ("violence", "loss") and ctx.intensity >= 0.8 and not light:
        rr.raise_to("stay", f"emotion reader: {ctx.primary_context.value}")

    if pacing_heavy:
        if SETBACK.search(text) or LONELY.search(text) or rr.level == "stay":
            rr.raise_to("stay", "pacing heavy, and another signal agrees")
        elif re.search(r"\b(gone|lost|sick|ill|hospital|diagnos\w*|cancer|divorce|separat\w*)\b", text, re.IGNORECASE):
            rr.raise_to("steady", "pacing heavy, with a loss word")
            rr.need("hard_news")
    if SETBACK.search(text):
        rr.raise_to("steady", "setback words")
        rr.need("setback")
    if HARD_NEWS.search(text) and not light:
        rr.raise_to("steady", "hard news words")
        rr.need("hard_news")
    if LONELY.search(text):
        rr.raise_to("steady", "loneliness words")
        rr.need("lonely")
    if FRUSTRATION.search(text) and not light:
        rr.raise_to("steady", "frustration words")
        rr.need("frustration")
    if _venting_signals(text):
        rr.raise_to("steady", "venting")
        rr.need("vent")

    if NERVES.search(text) and not light:
        rr.raise_to("notice", "nerves words")
        rr.need("nerves")
    if TIRED.search(text) and not light:
        rr.raise_to("notice", "tired words")
        rr.need("tired")
    if FLAT.match(text):
        rr.raise_to("notice", "flat reply")
        rr.need("flat")
    elif _suddenly_short(text, own_history):
        rr.raise_to("notice", "much shorter than this person's usual")
        rr.need("flat")

    if CELEBRATE.search(text) and rr.level in ("normal", "celebrate"):
        rr.raise_to("celebrate", "good-news words")

    if _seeking_help(text):
        rr.need("help")
        rr.reasons.append("asked for help")
    return rr


def _suddenly_short(text: str, own_history: Sequence[str]) -> bool:
    """Three words or fewer from someone whose usual is three times that.
    Needs at least three earlier messages from the same person; everyone starts neutral."""
    earlier = [len(str(m).split()) for m in own_history if str(m).strip()][-8:]
    if len(earlier) < 3:
        return False
    words = len(text.split())
    return words <= 3 and statistics.median(earlier) >= 3 * max(words, 1) and not text.rstrip().endswith("?")


def model_note(rr: RoomRead) -> Optional[str]:
    """A private note for the speaking model. None when there's nothing to adjust."""
    if rr.level == "normal" and "help" not in rr.needs:
        return None
    say = {
        "stay": "This person is hurting. One or two plain, warm sentences. No jokes, no stage business, no advice, "
                "no questions about safety, no pointing them to services or professionals. Stay with them.",
        "steady": "This person is having a hard time. Drop the act: no jokes, no stage business. Short, warm, practical.",
        "notice": "This person seems a bit off. Stay yourself but lighter: no stage business, keep it short, "
                  "acknowledge lightly, then offer something useful.",
        "celebrate": "Good news. Match their energy.",
        "normal": "",
    }[rr.level]
    extra = []
    if "vent" in rr.needs and "help" not in rr.needs:
        extra.append("They want to be heard, not fixed: no advice until they ask.")
    if "help" in rr.needs:
        extra.append("They asked for help: give it.")
    if "nerves" in rr.needs:
        extra.append("Nerves: a steadying, practical tip suits.")
    if "tired" in rr.needs:
        extra.append("Tired: keep it brief.")
    extra.append("Never name how they seem out loud, never ask if they're okay, and when they move on, move on.")
    return "Room read (private): " + " ".join(p for p in [say, *extra] if p)
