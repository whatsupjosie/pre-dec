"""Sir Purfluous's cue cards: one deck that serves both of his modes.

The deck lives in data/characters/sir_purfluous.json under "cue_cards", the
same file as his offline craft answers. Josie edits the lines there; nothing
here holds dialogue.

Offline (no speaking model): ``compose(message, history)`` reads the message,
picks cards that fit its topic and mood, skips any card whose text he said
recently, and joins two or three of them into one line. The choice is seeded
from the message and the recent history, so the same moment gives the same
line (testable) while a new moment gives a new combination.

Online (speaking model available): ``cues_for(message, history)`` returns the
same picks as a short private stage note. The model may use them or ignore
them; they steer him, they do not script him.

When someone is hurting he uses one plain card and nothing else: no openers,
no jokes, no stage business, and never a pointer to services.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DECK_PATH = Path(__file__).resolve().parent.parent / "data" / "characters" / "sir_purfluous.json"
RECENT_WINDOW = 24

# Words that mean the person is hurting. The EQ reader adds its own judgement
# when it is importable; these keep him safe when it is not.
_HURT_WORDS = re.compile(
    r"\b(died|dead|death|passed away|funeral|grief|grieving|lost my|miss (him|her|them)|"
    r"broke up|breakup|divorce|dumped|left me|alone|lonely|nobody|no one cares|"
    r"hurt|hurting|crying|cried|can't stop crying|heartbroken|depressed|"
    r"hate myself|worthless|give up on|giving up|can't do this|cannot do this|"
    r"hit me|abused|attacked|scared of (him|her|them))\b"
)
_HURT_CONTEXTS = {"loss", "violence", "betrayal", "abandonment", "pain"}


@lru_cache(maxsize=1)
def _load(path: str = str(DECK_PATH)) -> Mapping:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    deck = data.get("cue_cards") or {}
    raw = dict(deck.get("topics", {}))
    # A card may be tagged with one of his craft intents (acting_basics,
    # audition, ...); those topics are recognised by the intent's own patterns,
    # so the two never drift apart.
    for intent in data.get("intents", []):
        raw.setdefault(intent.get("id", ""), intent.get("patterns", []))
    topics = {name: [re.compile(p, re.IGNORECASE) for p in pats] for name, pats in raw.items() if name}
    return {"topics": topics, "cards": list(deck.get("cards", [])), "slots": dict(deck.get("slots", {})),
            "priority": list(deck.get("priority_topics", [])),
            "kit": dict(deck.get("phrase_kit", {})),
            "madlib": dict(deck.get("madlib", {})),
            "segments": dict(deck.get("segments", {})),
            "angles": {topic: {name: re.compile(rx, re.IGNORECASE) for name, rx in group.items()}
                       for topic, group in deck.get("angles", {}).items()}}


def priority_topic(message: str) -> Optional[str]:
    """A topic that outranks everything else when it is raised (the Scottish play,
    his unclothed years). The runtime answers these from the cards first."""
    topics, _mood = read(message) if isinstance(message, str) and message.strip() else ([], "")
    return next((t for t in _load()["priority"] if t in topics), None)


def reload() -> None:
    """Drop the cached deck so edits to the JSON are picked up."""
    _load.cache_clear()
    _reader_and_selector.cache_clear()


# Catalog cards he never uses. Josie's ruling (2026-11-24): "Fuck the crisis
# resources." These are the catalog's crisis_support cards (hotlines, RAINN,
# "Are you safe right now?"). The catalog itself is unchanged for other bots.
_CATALOG_EXCLUDED_TYPES = {"crisis_support"}
_CATALOG_SOLO = {"fatigue", "autonomy", "identity", "interpersonal", "betrayal"}


@lru_cache(maxsize=1)
def _reader_and_selector():
    try:
        from companion_support.eq_disambiguation_engine import ContextDisambiguator
        from modules.wired.eq_card_selector import ContextAwareCardSelector
        return ContextDisambiguator(), ContextAwareCardSelector()
    except Exception as exc:
        logger.debug("EQ card catalog unavailable: %s", exc)
        return None, None


def _catalog_read(message: str) -> Tuple[str, List[dict]]:
    """Read the message with the EQ reader and return (situation, catalog cards that fit it).

    Uses the card catalog's own picker (modules/wired/eq_card_selector.py), minus
    crisis cards. Each call is read fresh, with no carried-over history.
    """
    reader, selector = _reader_and_selector()
    if reader is None:
        return "unclear", []
    try:
        result = reader.analyze(message, "purfluous_cue_cards", include_history=False)
        picks = selector.select_response(result, num_options=len(selector.library.cards))
    except Exception as exc:  # the reader is advisory; never let it break a reply
        logger.debug("EQ reader failed: %s", exc)
        return "unclear", []
    context = getattr(result.primary_context, "value", "unclear") or "unclear"
    cards = [{"id": f"catalog:{c.id}", "kind": "catalog", "topics": [context], "moods": [], "text": c.text}
             for c, _score in picks if c.response_type not in _CATALOG_EXCLUDED_TYPES]
    return context, cards


def _eq_context(message: str) -> str:
    return _catalog_read(message)[0]


def _eq_hurt(message: str) -> bool:
    return _eq_context(message) in _HURT_CONTEXTS


def read(message: str) -> Tuple[List[str], str]:
    """Return (topics, mood) for a message. Mood is hurt, setback, celebrate or neutral."""
    deck = _load()
    text = message.strip()
    topics = [name for name, pats in deck["topics"].items() if any(p.search(text) for p in pats)]
    # The emotion reader takes film words literally ("shot" reads as violence),
    # so inside a priority subject only plain hurt words count.
    priority = set(deck.get("priority", [])) & set(topics)
    if _HURT_WORDS.search(text.casefold()) or (not priority and _eq_hurt(text)):
        mood = "hurt"
    elif "setback" in topics:
        mood = "setback"
    elif "celebrate" in topics and _celebrate_words(text, deck, topics):
        mood = "celebrate"
    else:
        mood = "neutral"
    return topics, mood


def _celebrate_words(text: str, deck: Mapping, topics: List[str]) -> bool:
    """A win needs winning words. A bare '!' only counts when nothing else is going on,
    so 'Break a leg in Macbeth tonight!' stays about the Scottish play."""
    pats = deck["topics"].get("celebrate", [])
    if pats and pats[0].search(text):
        return True
    return not (set(topics) - {"celebrate"})


SANCHO_GAP = 6  # his own lines that must pass between two Sanchos


def sancho_allowed(history: Sequence[Mapping[str, str]] = ()) -> bool:
    """He calls the user Sancho at the start and now and then, not every line."""
    mine = [str(e.get("text", "")) for e in history
            if isinstance(e, Mapping) and "purfluous" in str(e.get("speaker", "")).casefold()]
    return not any("sancho" in t.casefold() for t in mine[-SANCHO_GAP:])


_SANCHO_DROPS = [
    (re.compile(r"\{Sancho\}!\s*"), ""),
    (re.compile(r",\s*\{sancho\}"), ""),
    (re.compile(r"\{sancho\},?\s*"), ""),
]
_PLAIN_SANCHO_DROPS = [
    (re.compile(r"^That, Sancho, "), "That "),
    (re.compile(r", Sancho, "), ", "),
    (re.compile(r",\s*Sancho(?=[.;:!?—,)])"), ""),
    (re.compile(r"^Sancho[,.!]\s*"), ""),
]


def limit_sancho(text: str, allowed: bool) -> str:
    """Remove 'Sancho' from a finished line when he has used it lately (or already
    in this line). Lines Josie wrote are never passed through here."""
    if allowed:
        first = text.find("Sancho")
        if first == -1:
            return text
        head, tail = text[: first + 6], text[first + 6:]
        for rx, rep in _PLAIN_SANCHO_DROPS[1:3]:
            tail = rx.sub(rep, tail)
        return head + tail
    for rx, rep in _PLAIN_SANCHO_DROPS:
        text = rx.sub(rep, text)
    return text[:1].upper() + text[1:] if text else text


def _recent_text(history: Sequence[Mapping[str, str]]) -> str:
    said = []
    for entry in list(history)[-RECENT_WINDOW:]:
        if isinstance(entry, Mapping):
            said.append(str(entry.get("text", "")))
        else:
            said.append(str(entry))
    return "\n".join(said).casefold()


def _fill(text: str, slots: Mapping[str, str], sancho: bool = True) -> str:
    if not sancho:
        for rx, rep in _SANCHO_DROPS:
            text = rx.sub(rep, text)
        text = text.strip()
        text = text[:1].upper() + text[1:] if text else text
    for key, value in slots.items():
        text = text.replace(key, value)
    return text


def _pick(cards: List[dict], seed: bytes, salt: str, recent: str, slots: Mapping[str, str]) -> Optional[dict]:
    if not cards:
        return None
    fresh = [c for c in cards if _fill(c["text"], slots).casefold() not in recent] or cards
    digest = hashlib.sha256(seed + salt.encode()).digest()
    return fresh[int.from_bytes(digest[:4], "big") % len(fresh)]


def select(message: str, history: Sequence[Mapping[str, str]] = ()) -> Dict[str, object]:
    """Choose the cards for this moment. Returns topics, mood and the chosen cards in speaking order."""
    deck = _load()
    topics, mood = read(message)
    slots = deck["slots"]
    recent = _recent_text(history)
    seed = hashlib.sha256((message.strip().casefold() + "\x00" + recent[-2000:]).encode()).digest()
    cards = deck["cards"]

    def fits(card: dict, kind: str) -> bool:
        return card["kind"] == kind and mood in card["moods"]

    context, catalog = _catalog_read(message)

    if mood == "hurt":
        pool = [c for c in cards if fits(c, "plain")] + catalog
        plain = _pick(pool, seed, "plain", recent, slots)
        return {"topics": topics, "mood": mood, "cards": [plain] if plain else []}

    if context in _CATALOG_SOLO and catalog and not (set(topics) - {"celebrate", "setback"}):
        card = _pick(catalog, seed, "catalog", recent, slots)
        return {"topics": topics, "mood": mood, "cards": [card]}

    spoken = [t for t in topics if t not in ("celebrate", "setback")] or [t for t in topics]
    first = next((t for t in _load()["priority"] if t in spoken), None)
    if first:
        spoken = [first]
    beats = []
    if mood in ("celebrate", "setback"):  # a win or a stumble outranks the subject it happened in
        beats = [c for c in cards if c["kind"] == "beat" and mood in c["topics"]]
        if mood == "celebrate":
            beats += [c for c in catalog if context in ("achievement", "milestone")]
    if not beats:
        # The most specific topic wins: "how does the green room work?" matches
        # both green_room and pubcast_how, and should get the green room card.
        by_topic = {}
        for t in spoken:
            pool = [c for c in cards if c["kind"] == "beat" and mood in c["moods"] and t in c["topics"]]
            if pool:
                by_topic[t] = pool
        if by_topic:
            beats = min(by_topic.values(), key=len)
    if not beats and "story" in spoken and deck["kit"]:
        # A story asked for, or asked to go on, with no card to hand: build one.
        # Half the time he leaves it to his longer monologues instead.
        continuing = bool(_CONTINUE.search(message))
        if continuing or seed[6] % 2 == 0:
            told = None if continuing or seed[8] % 2 else _madlib_line(deck, "story", seed, recent)
            told = told or _story_line(deck["kit"], seed, recent, continuing=continuing)
            if told:
                return {"topics": topics, "mood": mood, "cards": [told]}
    if not beats:
        return {"topics": topics, "mood": mood, "cards": []}
    # Within a big subject, the question picks the angle ("why no awards?" gets
    # the awards grievance, "isn't it just smut?" gets the craft defence).
    if len(spoken) == 1 and spoken[0] in deck["angles"]:
        wanted = [name for name, rx in deck["angles"][spoken[0]].items() if rx.search(message)]
        angled = [c for c in beats if c.get("angle") in wanted]
        if angled:
            beats = angled
    beat = _pick(beats, seed, "beat", recent, slots)
    # A story request gets a built action story half the time.
    if "story" in spoken and deck["kit"] and seed[6] % 2 == 0:
        told = _story_line(deck["kit"], seed, recent, continuing=bool(_CONTINUE.search(message)))
        if told:
            beat = told
    # One time in four, on chatty topics, a Mad Lib stands in for the card.
    if not beat.get("solo") and mood == "neutral" and seed[7] % 4 == 0:
        for t in spoken:
            built = _madlib_line(deck, t, seed, recent)
            if built:
                beat = built
                break
    # One time in three, a line built from a frame stands in for the card, so a
    # topic he has covered before still gets something new.
    kit_topic = _kit_topic(deck["kit"], spoken) if deck["kit"] else None
    if kit_topic and not beat.get("solo") and seed[5] % 3 == 0:
        framed = _frame_line(deck["kit"], kit_topic, mood, seed, recent)
        if framed:
            beat = framed
    if beat.get("solo"):  # a card that ends on its own beat (a cut-off, an exit) stands alone
        return {"topics": topics, "mood": mood, "cards": [beat]}
    chosen = []
    roll = seed[0]
    if roll % 3 != 0:  # two times in three he opens before the beat
        # An opener that only works with Sancho in it ("Sancho! Just the person.")
        # is skipped when he has used Sancho lately.
        openers = [c for c in cards if fits(c, "opener")
                   and (sancho_allowed(history) or not c["text"].startswith("{Sancho}"))]
        opener = _pick(openers, seed, "opener", recent, slots)
        if opener:
            chosen.append(opener)
    chosen.append(beat)
    tail = roll % 4
    if tail == 1:
        extra = _pick([c for c in cards if fits(c, "aside")], seed, "aside", recent, slots)
    elif tail == 2:
        extra = _pick([c for c in cards if fits(c, "business")], seed, "business", recent, slots)
    elif tail == 3:
        extra = _pick([c for c in cards if fits(c, "closer")], seed, "closer", recent, slots)
    else:
        extra = None
    if extra:
        chosen.append(extra)
    return {"topics": topics, "mood": mood, "cards": chosen}


def _kit_topic(kit: Mapping, topics: Sequence[str]) -> Optional[str]:
    fillers = kit.get("fillers", {})
    aliases = kit.get("topic_aliases", {})
    for t in topics:
        t = aliases.get(t, t)
        if t in fillers:
            return t
    return None


def _frame_line(kit: Mapping, topic: str, mood: str, seed: bytes, recent: str) -> Optional[dict]:
    """Build one line from a sentence frame and the topic's filler phrases.
    Every combination is a whole sentence; nothing is assembled word by word."""
    group = kit["fillers"][topic]
    frames = [f for f in kit.get("frames", []) if mood in f.get("moods", [])]
    if not frames:
        return None
    candidates = []
    for f in frames:
        slots = {k for k in ("thing", "quality", "doing") if "{" + k + "}" in f["text"].lower()}
        if any(not group.get(k) for k in slots):
            continue
        candidates.append(f)
    for attempt in range(8):
        h = hashlib.sha256(seed + f"frame{attempt}".encode()).digest()
        f = candidates[h[0] % len(candidates)] if candidates else None
        if f is None:
            return None
        thing = group.get("thing", [""])[h[1] % max(1, len(group.get("thing", [])))]
        quality = group.get("quality", [""])[h[2] % max(1, len(group.get("quality", [])))]
        doing = group.get("doing", [""])[h[3] % max(1, len(group.get("doing", [])))]
        text = (f["text"].replace("{Thing}", thing[:1].upper() + thing[1:]).replace("{thing}", thing)
                .replace("{quality}", quality).replace("{doing}", doing))
        if text.casefold() not in recent:
            return {"id": f"{f['id']}:{topic}", "kind": "frame", "topics": [topic], "moods": [mood], "text": text}
    return None


_CONTINUE = re.compile(r"\b(what happened (next|then)|and then what|then what happened|keep going|go on then|carry on with the story)\b", re.IGNORECASE)
_PRONOUNS = {"he", "she", "they"}


def _story_line(kit: Mapping, seed: bytes, recent: str, continuing: bool = False) -> Optional[dict]:
    """A little action story about anybody: a person (who carries its own he/him/his,
    was/were), a movement (with its past tense) and a direction, set in a story frame."""
    people, moves, dirs, frames = kit.get("people"), kit.get("moves"), kit.get("directions"), kit.get("story_frames")
    if people and continuing:
        # Carry on with whoever the last story was about, by pronoun.
        tail = recent[-600:]
        named = [p for p in people if p["who"] not in _PRONOUNS and p["who"].casefold() in tail]
        last = max(named, key=lambda p: tail.rfind(p["who"].casefold()), default=None)
        if last:
            pron = next((p for p in people if p["who"] == last["pro"]), None)
            if pron:
                people = [pron]
        else:
            # Nobody to follow (the last story was a monologue): name someone.
            people = [p for p in people if p["who"] not in _PRONOUNS]
    elif people:
        # A fresh story names its subject; "he", "she", "they" only carry on a story already told.
        people = [p for p in people if p["who"] not in _PRONOUNS]
    if not (people and moves and dirs and frames):
        return None
    for attempt in range(8):
        h = hashlib.sha256(seed + f"story{attempt}".encode()).digest()
        p, m, m2 = people[h[0] % len(people)], moves[h[1] % len(moves)], moves[h[2] % len(moves)]
        d1, d2 = dirs[h[3] % len(dirs)], dirs[h[4] % len(dirs)]
        if m2 is m:
            m2 = moves[(h[2] + 1) % len(moves)]
        if d2 == d1:
            d2 = dirs[(h[4] + 1) % len(dirs)]
        text = frames[h[5] % len(frames)]
        for key, value in (("{Who}", p["Who"]), ("{who}", p["who"]), ("{pro}", p.get("pro", p["who"])), ("{them}", p["them"]), ("{their}", p["their"]),
                           ("{was}", p["was"]), ("{went}", m["went"]), ("{went2}", m2["went"]),
                           ("{gone_pp}", m["gone"]), ("{direction}", d1), ("{direction2}", d2)):
            text = text.replace(key, value)
        text = text[:1].upper() + text[1:]
        if text.casefold() not in recent:
            return {"id": "story_frame", "kind": "frame", "topics": ["story"], "moods": ["neutral"], "text": text}
    return None


# ── Mad Libs ──────────────────────────────────────────────────────────────────
# A slot is {[a:|A:]type[n][.form]}: "a:" adds a/an, a capital first letter
# capitalises the word, a digit makes a second independent pick of the same type,
# and ".form" chooses a form the word card carries (noun.many, verb.went, person.their).

_SLOT = re.compile(r"\{(?:(a|A):)?([A-Za-z_]+?)(\d?)(?:\.([a-z_]+))?\}")
_SINGULAR_NAMED = None


def _article(word: str) -> str:
    w = word.lower()
    if w.startswith(("one", "uni", "use", "eu")):
        return "a"
    if w.startswith(("hour", "honest", "heir")):
        return "an"
    return "an" if w[:1] in "aeiou" else "a"


def _madlib_people(kit: Mapping) -> List[dict]:
    # Named, singular people only: the frames are written for one person.
    return [p for p in kit.get("people", []) if p["who"] not in _PRONOUNS and p.get("has") == "has"]


def render_madlib(frame: str, words: Mapping, people: Sequence[Mapping], seed: bytes) -> str:
    picks: Dict[str, object] = {}

    def choose(kind: str, key: str):
        if key not in picks:
            pool = people if kind == "person" else words.get(kind, [])
            if not pool:
                raise KeyError(kind)
            h = hashlib.sha256(seed + key.encode()).digest()
            picks[key] = pool[int.from_bytes(h[:4], "big") % len(pool)]
        return picks[key]

    def fill(m: "re.Match") -> str:
        art, kind_raw, n, form = m.group(1), m.group(2), m.group(3), m.group(4)
        kind = kind_raw.lower()
        word = choose(kind, kind + n)
        if isinstance(word, Mapping):
            if kind == "person":
                form = form or "who"
                text = {"is": "is" if word.get("was") == "was" else "are"}.get(form) or word.get(form) or word["who"]
            else:
                text = word.get(form or "one") or next(iter(word.values()))
        else:
            text = str(word)
        if art:
            text = f"{_article(text)} {text}"
        if kind_raw[:1].isupper() or (art == "A"):
            text = text[:1].upper() + text[1:]
        return text

    return _SLOT.sub(fill, frame)


def _madlib_line(deck: Mapping, topic: str, seed: bytes, recent: str) -> Optional[dict]:
    ml = deck.get("madlib") or {}
    if not ml or topic not in ml.get("use_on_topics", []):
        return None
    words = {k: list(v) for k, v in ml.get("words", {}).items()}
    for k, v in ml.get("topic_words", {}).get(topic, {}).items():
        words[k] = list(v) + words.get(k, [])[: len(v)]   # the topic's own words come first
    people = _madlib_people(deck.get("kit") or {})
    frames = ml.get("frames", [])
    for attempt in range(8):
        h = hashlib.sha256(seed + f"madlib{attempt}".encode()).digest()
        frame = frames[h[0] % len(frames)]
        try:
            text = render_madlib(frame, words, people, h)
        except KeyError:
            continue
        if text.casefold() not in recent:
            return {"id": "madlib", "kind": "frame", "topics": [topic], "moods": ["neutral"], "text": text}
    return None


# ── Everyday segments: talking about nearly anything ─────────────────────────

_STOP = set("""a an the i me my mine you your yours we our us he she they them his her their it its is am are was were be
been being do does did have has had of to in on at for with about from by and or but so if then than that this these
those just really very quite some any all no not can could would should will shall may might must what when where who
why how which there here like love hate enjoy get got getting into been lately recently today tonight thing things
stuff lot lots bit also too again ever never always still yeah yes ok okay oh um hey hi hello""".split())
_VERBISH = set("""is was are were has have had keeps kept broke broken died went got gets get came comes left
leaves visiting visited coming going says said wants needs called calls just again finally""".split())
_TOPIC_PATTERNS = [
    ("mine", re.compile(r"\b(?:my|our)\s+([a-z][a-z'-]*(?:\s+[a-z][a-z'-]*)?)", re.IGNORECASE)),
    ("interest", re.compile(r"\b((?:learning|practi[sc]ing|trying)\s+(?:to\s+)?[a-z]+)\b", re.IGNORECASE)),
    ("interest", re.compile(r"\b(?:went|go|going|been)\s+([a-z]+ing)\b", re.IGNORECASE)),
    ("interest", re.compile(r"\b(?:about|into)\s+((?:the\s+|a\s+)?[a-z][a-z' -]{2,40}?)(?:[.?!,]|$)", re.IGNORECASE)),
    ("interest", re.compile(r"\bi (?:love|like|adore|hate|enjoy|miss)\s+([a-z][a-z' -]{2,40}?)(?:[.?!,]|$)", re.IGNORECASE)),
]


def extract_topic(message: str):
    """(subject, kind) the person raised, in their own words, short enough to echo back.
    kind is 'person' (my sister), 'thing' (my car) or 'interest' (jazz, the election)."""
    text = message.strip()
    relations = set(_load().get("segments", {}).get("relations", []))
    for kind, rx in _TOPIC_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        words = m.group(1).strip().split()
        if kind == "mine":
            kept = []
            for w in words:
                if w.lower() in _VERBISH or w.lower().endswith("ed") or w.lower() in _STOP:
                    break
                kept.append(w.lower())
            if not kept:
                continue
            phrase = " ".join(kept)
            return phrase, ("person" if phrase in relations or kept[-1] in relations else "thing")
        while words and words[-1].lower() in _STOP:
            words.pop()
        if words and len(words) <= 4 and words[0].lower() not in _STOP - {"the", "a"}:
            return " ".join(words).lower(), "interest"
    content = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text) if w.lower() not in _STOP]
    return (content[-1].lower(), "interest") if len(content) == 1 else (None, None)


def converse(message: str, history: Sequence[Mapping[str, str]] = ()) -> Optional[str]:
    """A reply built from everyday sentence pieces about whatever the person raised.
    Never for a factual question he cannot know, never when someone is hurting."""
    deck = _load()
    seg = deck.get("segments") or {}
    if not seg or not isinstance(message, str) or not message.strip():
        return None
    if re.search(seg.get("fact_question", "^$"), message, re.IGNORECASE):
        return None
    if read(message)[1] == "hurt":
        return None
    topic, kind = extract_topic(message)
    if not topic:
        return None
    pools = dict(seg)
    pools.update(seg.get("by_kind", {}).get(kind, {}))
    recent = _recent_text(history)
    for attempt in range(8):
        h = hashlib.sha256((message.casefold() + recent[-1000:] + str(attempt)).encode()).digest()
        pick = lambda key, i: pools[key][h[i] % len(pools[key])]
        parts = [pick("reactions", 0), f"{pick('stems', 1)} {pick('opinions', 2)}"]
        if h[3] % 3 == 0:
            parts.append(pick("asides", 4))
        if h[5] % 2 == 0:
            parts.append(pick("questions", 6))
        text = " ".join(parts)
        text = text.replace("{Topic}", topic[:1].upper() + topic[1:]).replace("{topic}", topic)
        if text.casefold() not in recent:
            return limit_sancho(text, sancho_allowed(history))
    return None


def _join(parts: List[str]) -> str:
    out = ""
    for part in parts:
        part = part.strip()
        if not out:
            out = part
        elif out.endswith(",") and part[:1].isupper() and not re.match(r"I\b", part):
            out = out + " " + part[0].lower() + part[1:]
        else:
            out = f"{out} {part}"
    return out


def compose(message: str, history: Sequence[Mapping[str, str]] = ()) -> Optional[str]:
    """Build one offline line from his cards, or None if no card fits this message."""
    if not isinstance(message, str) or not message.strip():
        return None
    picked = select(message, history)
    if not picked["cards"]:
        return None
    slots = _load()["slots"]
    allowed = sancho_allowed(history)
    parts = []
    for card in picked["cards"]:
        parts.append(_fill(card["text"], slots, sancho=allowed))
        if "{sancho}" in card["text"].casefold():
            allowed = False   # once per line at most
    return _join([p for p in parts if p])


def cues_for(message: str, history: Sequence[Mapping[str, str]] = ()) -> Optional[str]:
    """A private note for the speaking model: the cards for this moment, to use or ignore."""
    if not isinstance(message, str) or not message.strip():
        return None
    picked = select(message, history)
    if not picked["cards"]:
        return None
    slots = _load()["slots"]
    lines = " | ".join(_fill(card["text"], slots) for card in picked["cards"])
    if picked["mood"] == "hurt":
        return ("Cue (private): this person is hurting. Be plain and warm, no jokes, no stage business, "
                f"do not point them to services. A line in your voice: {lines}")
    return (f"Cue cards (private; use, rephrase or ignore, never read them out as a list): {lines}")
