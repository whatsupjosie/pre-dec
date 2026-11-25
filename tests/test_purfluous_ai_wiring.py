"""AI Sir Purfluous wiring (2026-11-24).

Covers: his whole canon reaches the speaking model word for word; the system
prompt is sent once, not twice; he stays out of the waiting room and airlock;
he always answers when addressed and paces his uninvited lines; the room is
told once when he drops to offline lines; and his voice tests grade him
against his canon, not the older template.
"""
import asyncio
import json
import pathlib
import time

import pytest

from modules.bots import BotManager, REPLY_WAS_OFFLINE
from modules.character_engine import get_prompt_template
from modules.character_profiles import SIR_PURFLUOUS_PROFILE, compose_full_prompt
from modules.models import BotConfig
from modules.sir_purfluous_character_profile import BORROWED_LINES, MONOLOGUE_POOL, PURFLUOUS_PROFILE
from modules.sir_purfluous_runtime import OFFLINE_NOTE

BOT_FILE = pathlib.Path(__file__).parents[1] / "data" / "bots" / "sir_purfluous.json"


def _config(**overrides):
    data = json.loads(BOT_FILE.read_text(encoding="utf-8"))
    data.update(overrides)
    return BotConfig(**data)


class FakeHub:
    def __init__(self, history=None):
        self.history = {} if history is None else history
        self.posted = []

    async def get_recent_history(self, room, limit=12):
        return list(self.history.get(room, []))[-limit:]

    async def post_chat_message(self, room, user_id, text, client_message_id=None):
        self.posted.append((room, user_id, text))
        self.history.setdefault(room, []).append({"user_id": user_id, "text": text})
        return {"message_id": f"m{len(self.posted)}"}


def _manager(hub):
    mgr = BotManager.__new__(BotManager)
    mgr.hub = hub
    mgr._last_interjection = {}
    mgr._offline_rooms = {}
    mgr._background_bursts = {}
    return mgr


# ── canon reaches the model ──────────────────────────────────────────────────

def test_authored_prompt_comes_first_unchanged():
    assert SIR_PURFLUOUS_PROFILE.system_prompt.startswith(PURFLUOUS_PROFILE.system_prompt.strip())


@pytest.mark.parametrize("field", ["behavioral_rules", "canonical_facts", "relationship_notes"])
def test_every_list_item_is_sent_verbatim(field):
    prompt = SIR_PURFLUOUS_PROFILE.system_prompt
    missing = [item for item in getattr(PURFLUOUS_PROFILE, field) if item not in prompt]
    assert not missing


def test_every_monologue_and_borrowed_line_is_sent_verbatim():
    prompt = SIR_PURFLUOUS_PROFILE.system_prompt
    assert all(m.text in prompt for m in MONOLOGUE_POOL)
    assert all(b["line"] in prompt for b in BORROWED_LINES)


def test_his_look_reaches_the_model():
    prompt = SIR_PURFLUOUS_PROFILE.system_prompt.lower()
    for prop in ("velvet", "cane", "monocle"):
        assert prop in prompt


def test_profile_lists_are_still_kept_as_data():
    assert list(SIR_PURFLUOUS_PROFILE.behavioral_rules) == list(PURFLUOUS_PROFILE.behavioral_rules)
    assert list(SIR_PURFLUOUS_PROFILE.canonical_facts) == list(PURFLUOUS_PROFILE.canonical_facts)


def test_compose_with_no_lists_is_just_the_prompt():
    assert compose_full_prompt("  Hello.  ") == "Hello."


def test_bot_manager_hands_the_model_the_composed_prompt():
    cfg = BotManager._enrich_from_profile(_config())
    assert cfg.system_prompt == SIR_PURFLUOUS_PROFILE.system_prompt


# ── prompt sent once ─────────────────────────────────────────────────────────

def test_transcript_no_longer_repeats_the_system_prompt():
    cfg = _config(system_prompt="UNIQUE-SYSTEM-MARKER")
    mgr = _manager(FakeHub())
    prompt = mgr._build_prompt(cfg, [{"user": "Josie", "text": "hello"}], None)
    assert "UNIQUE-SYSTEM-MARKER" not in prompt
    assert "System instruction:" not in prompt
    assert prompt.rstrip().endswith(f"{cfg.name}:")


def test_ollama_direct_call_sends_system_and_his_window(monkeypatch):
    import httpx
    import modules.llm_orchestrator as orch

    captured = {}

    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "Indeed, Sancho."}

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **k):
            captured["url"] = url
            captured.update(json or {})
            return Resp()

    def no_orchestrator():
        raise RuntimeError("orchestrator unavailable")

    monkeypatch.setattr(orch, "get_orchestrator", no_orchestrator)
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    cfg = _config(provider="ollama", model="llama3", system_prompt="SYS")
    out = asyncio.run(_manager(FakeHub())._call_ollama(cfg, "User: hi\nSir Purfluous:"))
    assert out == "Indeed, Sancho."
    assert captured["url"].endswith("/api/generate")
    assert captured["system"] == "SYS"
    assert captured["options"]["num_ctx"] == 8192
    assert captured["options"]["num_predict"] == 400


def test_orchestrator_route_gets_his_window(monkeypatch):
    import modules.llm_orchestrator as orch

    seen = {}

    class Result:
        text = "Indeed, Sancho."

    class Fake:
        async def generate(self, prompt, **kwargs):
            seen.update(kwargs)
            return Result()

    monkeypatch.setattr(orch, "get_orchestrator", lambda: Fake())
    cfg = _config(provider="ollama", model="llama3", system_prompt="SYS")
    assert asyncio.run(_manager(FakeHub())._call_ollama(cfg, "User: hi")) == "Indeed, Sancho."
    assert seen["num_ctx"] == 8192 and seen["max_tokens"] == 400
    assert seen["context"].system_prompt == "SYS"


def test_orchestrator_studio_window_defaults_to_2048_and_accepts_more(monkeypatch):
    import httpx
    import modules.llm_orchestrator as orch

    windows = []

    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "ok"}}

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **k):
            windows.append(json["options"]["num_ctx"])
            return Resp()

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    o = orch.LLMOrchestrator.__new__(orch.LLMOrchestrator)
    o._studio_calls = 0
    o._studio_model = "m"
    asyncio.run(o._studio("hi", orch.ContextPacket(system_prompt="S"), 0.5, 10))
    asyncio.run(o._studio("hi", orch.ContextPacket(system_prompt="S"), 0.5, 10, num_ctx=8192))
    assert windows == [2048, 8192]


# ── rooms ────────────────────────────────────────────────────────────────────

def test_not_in_waiting_room_or_airlock():
    rooms = json.loads(BOT_FILE.read_text(encoding="utf-8"))["rooms"]
    assert "waiting_room" not in rooms and "airlock" not in rooms
    assert {"greenroom", "studio", "palace_theater"} <= set(rooms)


# ── being addressed ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Sir Purfluous, what do you think?",
    "@Sir Purfluous hello",
    "what do you reckon, purfluous?",
    "Hey Sir P, tell us a tale",
    "PURFLUOUS!",
])
def test_addressed_by_any_of_his_names(text):
    assert _manager(FakeHub())._is_mention(_config(), text)


@pytest.mark.parametrize("text", ["superfluous detail", "sir pete is here", "the purfluousness of it", "hello all"])
def test_not_addressed_by_lookalikes(text):
    assert not _manager(FakeHub())._is_mention(_config(), text)


# ── pacing of uninvited lines ────────────────────────────────────────────────

def test_first_uninvited_line_allowed_then_held_for_cooldown():
    mgr = _manager(FakeHub())
    cfg = _config()
    assert asyncio.run(mgr._may_interject(cfg, "studio")) is True
    assert asyncio.run(mgr._may_interject(cfg, "studio")) is False


def test_cooldown_is_per_room():
    mgr = _manager(FakeHub())
    cfg = _config()
    assert asyncio.run(mgr._may_interject(cfg, "studio")) is True
    assert asyncio.run(mgr._may_interject(cfg, "greenroom")) is True


def test_allowed_again_after_cooldown():
    mgr = _manager(FakeHub())
    cfg = _config()
    mgr._last_interjection[(cfg.bot_id, "studio")] = time.time() - 241
    assert asyncio.run(mgr._may_interject(cfg, "studio")) is True


def test_quiet_while_his_own_line_is_among_the_last_three():
    cfg = _config()
    me = f"bot-{cfg.bot_id}"
    hub = FakeHub({"studio": [{"user_id": me}, {"user_id": "u1"}, {"user_id": "u2"}]})
    assert asyncio.run(_manager(hub)._may_interject(cfg, "studio")) is False
    hub.history["studio"].append({"user_id": "u3"})
    assert asyncio.run(_manager(hub)._may_interject(cfg, "studio")) is True


def test_refused_interjection_does_not_start_the_cooldown():
    cfg = _config()
    me = f"bot-{cfg.bot_id}"
    hub = FakeHub({"studio": [{"user_id": me}]})
    mgr = _manager(hub)
    assert asyncio.run(mgr._may_interject(cfg, "studio")) is False
    assert (cfg.bot_id, "studio") not in mgr._last_interjection


def test_bots_without_the_setting_are_unchanged():
    cfg = _config(bot_id="someone_else", settings={})
    assert asyncio.run(_manager(FakeHub())._may_interject(cfg, "studio")) is True
    assert asyncio.run(_manager(FakeHub())._may_interject(cfg, "studio")) is True


def test_bad_settings_mean_quiet_not_a_crash():
    cfg = _config(settings={"interject_cooldown_s": "soon"})
    assert asyncio.run(_manager(FakeHub())._may_interject(cfg, "studio")) is False


def test_on_chat_message_answers_mentions_but_paces_the_rest():
    cfg = _config()
    hub = FakeHub()
    mgr = _manager(hub)
    mgr._lock = asyncio.Lock()

    class Session:
        busy = False
        config = cfg

    mgr._configs = {cfg.bot_id: cfg}
    mgr._sessions = {cfg.bot_id: Session()}
    scheduled = []

    async def schedule(session, payload):
        scheduled.append(payload["text"])

    mgr._schedule_reply = schedule

    async def run():
        hub.is_user_in_room = lambda *a: asyncio.sleep(0, True)
        for text in ["nice set", "lovely lights", "Sir Purfluous, a word?", "and the music"]:
            await mgr.on_chat_message({"room": "studio", "user_id": "u1", "text": text})

    asyncio.run(run())
    assert scheduled == ["nice set", "Sir Purfluous, a word?"]


def test_answering_his_line_counts_as_talking_to_him():
    cfg = _config()
    me = f"bot-{cfg.bot_id}"
    hub = FakeHub({"studio": [{"message_id": "a", "user_id": me, "text": "And you, Sancho?"},
                              {"message_id": "b", "user_id": "u1", "text": "me? a pint"}]})
    assert asyncio.run(_manager(hub)._answers_bot(cfg, "studio", {"message_id": "b"})) is True


def test_message_after_someone_else_is_not_a_reply_to_him():
    cfg = _config()
    me = f"bot-{cfg.bot_id}"
    hub = FakeHub({"studio": [{"message_id": "a", "user_id": me}, {"message_id": "x", "user_id": "u2"},
                              {"message_id": "b", "user_id": "u1"}]})
    assert asyncio.run(_manager(hub)._answers_bot(cfg, "studio", {"message_id": "b"})) is False


def test_direct_replies_are_opt_in():
    cfg = _config(bot_id="someone_else", settings={})
    hub = FakeHub({"studio": [{"message_id": "a", "user_id": "bot-someone_else"}, {"message_id": "b", "user_id": "u1"}]})
    assert asyncio.run(_manager(hub)._answers_bot(cfg, "studio", {"message_id": "b"})) is False


def test_reply_without_his_name_is_answered_despite_cooldown():
    cfg = _config()
    me = f"bot-{cfg.bot_id}"
    hub = FakeHub({"studio": [{"message_id": "a", "user_id": me, "text": "Your drink, Sancho?"}]})
    mgr = _manager(hub)
    mgr._lock = asyncio.Lock()
    mgr._last_interjection[(cfg.bot_id, "studio")] = time.time()

    class Session:
        busy = False
        config = cfg

    mgr._configs = {cfg.bot_id: cfg}
    mgr._sessions = {cfg.bot_id: Session()}
    scheduled = []

    async def schedule(session, payload):
        scheduled.append(payload["text"])

    mgr._schedule_reply = schedule

    async def say(mid, text):
        hub.history["studio"].append({"message_id": mid, "user_id": "u1", "text": text})
        await mgr.on_chat_message({"room": "studio", "user_id": "u1", "text": text, "message_id": mid})

    async def run():
        await say("b", "whiskey, thanks")
        await say("c", "anyway, the lights")

    asyncio.run(run())
    assert scheduled == ["whiskey, thanks"]


# ── offline notice ───────────────────────────────────────────────────────────

def test_room_told_once_when_he_goes_offline_then_again_after_recovery():
    hub = FakeHub()
    mgr = _manager(hub)
    cfg = _config()
    asyncio.run(mgr._announce_offline_change(cfg, "studio", True))
    asyncio.run(mgr._announce_offline_change(cfg, "studio", True))
    assert [t for _, _, t in hub.posted] == [OFFLINE_NOTE]
    asyncio.run(mgr._announce_offline_change(cfg, "studio", False))
    assert len(hub.posted) == 1
    asyncio.run(mgr._announce_offline_change(cfg, "studio", True))
    assert len(hub.posted) == 2
    assert hub.posted[0][1] == f"bot-{cfg.bot_id}"


def test_offline_notice_is_per_room():
    hub = FakeHub()
    mgr = _manager(hub)
    cfg = _config()
    asyncio.run(mgr._announce_offline_change(cfg, "studio", True))
    asyncio.run(mgr._announce_offline_change(cfg, "greenroom", True))
    assert [r for r, _, _ in hub.posted] == ["studio", "greenroom"]


def test_no_notice_for_bots_without_an_offline_runtime():
    hub = FakeHub()
    asyncio.run(_manager(hub)._announce_offline_change(_config(bot_id="nobody"), "studio", True))
    assert hub.posted == []


def test_offline_note_is_his_existing_line():
    assert OFFLINE_NOTE == ("My full powers wait on the speaking model, Sancho. Offline I keep to the door, "
                            "the craft, and my own history.")


# ── voice tests use his canon ────────────────────────────────────────────────

@pytest.mark.parametrize("bot_id", ["purfluous", "sir_purfluous"])
def test_voice_template_is_his_canon(bot_id):
    template = get_prompt_template(bot_id)
    assert template["system"] == SIR_PURFLUOUS_PROFILE.system_prompt
    assert "sancho" in template["voice_markers"]
    assert template["max_tokens"] >= 300


def test_other_templates_untouched():
    from modules.character_engine import PROMPT_TEMPLATES
    assert get_prompt_template("pete") is PROMPT_TEMPLATES["pete"]
    assert PROMPT_TEMPLATES["purfluous"]["max_tokens"] == 100  # old entry kept as history


# ── canon settled with the owner on 2026-11-24 ───────────────────────────────

OWNER_SPEECH = (
    "But you see, Sancho, I'm not a knight. And guess what? Sean Connery wasn't a spy. And there is no "
    "red-headed mermaid who had a happily ever after with a prince or a little boy who threw a spaceman in "
    "his basket and flew across the moon. None of that matters. But when we were younger, especially, nothing "
    "mattered more. Nothing mattered more than our imagination. What if? What could be? And that was magical. "
    "And I never really wanted to let go of that. It may seem silly. I mean, it may all seem like playing "
    "pretend. But how lucky are we that we come to this place and we dream for a living? We get to play, dress "
    "up and pretend and let our imaginations run wild. And maybe, just maybe, somebody sees our art, our ideas, "
    "a piece of our heart laid bare. And maybe, just maybe, that person suddenly doesn't feel so alone. All "
    "because we decided to live a life where, instead of giving up on our dreams, we fostered them for a better "
    "life. And just maybe, in some small and significant way, a better world. Because in such a bitter, cold "
    "place, one more reason to smile or to feel hope or comfort or one more reason to believe in love. Isn't "
    "that worth more than any number some studio accountant could scribble on a check? Goodnight, Sancho."
)


def test_imagination_speech_is_the_owners_approved_text():
    mono = next(m for m in MONOLOGUE_POOL if m.monologue_id == "m60_imagination")
    assert mono.text == OWNER_SPEECH
    assert OWNER_SPEECH in PURFLUOUS_PROFILE.system_prompt
    assert "that's treasure" not in PURFLUOUS_PROFILE.system_prompt.lower()
    assert "grandfatherly exit" in PURFLUOUS_PROFILE.system_prompt


@pytest.mark.parametrize("needle", [
    "You'll never know just when or where, but it shall strike. The tiny chair.",
    "unexamined chair",
    "army brat",
    "Royal Shakespeare Company",
    "skipped town",
    "Horace",
    "Vortex Bar",
    "the Scottish play",
    "probably isn't a ghost",
    "overdressed by about 20 percent",
    "early 60s",
    "floor director",
])
def test_settled_canon_reaches_the_model(needle):
    assert needle in SIR_PURFLUOUS_PROFILE.system_prompt


def test_retired_canon_is_gone():
    prompt = SIR_PURFLUOUS_PROFILE.system_prompt
    for old in ("mid-60s", "sweeping floors, coiling cables", "She is financially fine", "17 years ago"):
        assert old not in prompt
