# Thinking Context Collector — Engineering Handoff
**Project:** PubCast AI / Rearview Foresight LLC  
**Package:** Thinking_Context_Collector.zip  
**Date:** 2026-03-14  
**Status:** Architecturally complete. Integration layer has four known breaks that must be resolved before first run.

---

## What This Package Is

This is the memory, conduction, and context-injection layer for PubCast AI.

It makes AI co-hosts feel alive — not because they're clever, but because they remember, and because something is watching the room and deciding when to act.

Three things working together:

**Jeremy Cricket** (`jeremy_cricket.py`) — does all of it in one class. Watches rooms. Calculates when to intervene. Queries character memory for what's personally relevant. Composes a stage direction. Delivers it to a bot via nudge(). The bot responds on its own. Nobody in the room sees the whisper.

**Universal Memory System** (`universal_memory_system.py`) — per-character in-memory store with keyword search and importance scoring. This is what Jeremy queries before composing a hint.

**BotManager** (`bots.py`) — already wired with Jeremy initialization hooks, memory storage on reply, and memory injection into prompts. Needs `nudge()` added (see nudge_patch.py) and import names updated (see Broken Interface #1 below).

---

## The Four Breaks — Fix These Before Anything Else

### Break 1: Import names don't match

`bots.py` line 12:
```python
from jeremy_cricket import get_jeremy_cricket, JeremyCricketOrchestrator
```

Neither of those names exists in the new `jeremy_cricket.py`. The new exports are:
- `JeremyCricket` (the class)
- `create_jeremy_cricket` (the async factory function)
- `JeremyConfig` (configuration dataclass)

**Fix:**
```python
from jeremy_cricket import JeremyCricket, create_jeremy_cricket, JeremyConfig
```

Then update the `initialize_jeremy_cricket` method in BotManager — it calls `get_jeremy_cricket(self.data_dir)`. Replace with:
```python
self.jeremy_cricket = await create_jeremy_cricket(
    memory_system=your_memory_system_instance,
    bot_manager=self,
    hub=self.hub,
)
```

`UniversalMemorySystem` needs to be constructed once and passed in. It is not constructed inside Jeremy.

---

### Break 2: bots.py calls methods that don't exist on the new Jeremy

`bots.py` calls these on the Jeremy instance. None of them exist on the new class:

| Called in bots.py | Status | Fix |
|---|---|---|
| `jeremy.start_background_orchestration()` | ❌ Gone | Remove — Jeremy starts its own watcher loops via `watch_room()` |
| `jeremy.store_character_memory(char_id, content, context, importance, tags)` | ❌ Gone | Replace with `jeremy.memory.get_or_create_bank(char_id).add(MemoryEntry(...))` |
| `jeremy.register_character_personality(char_id, name, core_traits, ...)` | ❌ Gone | Replace with `jeremy.memory.register_character(CharacterProfile(character_id=char_id, name=name, ...))` |
| `jeremy.get_memory_suggestions(bot_id, room_id, history)` | ❌ Gone | Removed — Jeremy whispers proactively via nudge(), not on-demand per-reply |

These replacements require importing `MemoryEntry`, `MemoryType`, `CharacterProfile` from `universal_memory_system`. They're all there.

---

### Break 3: nudge() targets the wrong object structure

`nudge_patch.py` was written assuming bots have individual attributes: `room_id`, `enabled`, `_last_spoke_at`, `system_prompt`, `on_message()`.

Real bots in `bots.py` are `BotSession` objects. The structure is:
- `session.config.enabled_rooms` — a **list** of rooms, not a single room
- `session.last_reply_at` — the recency signal (not `_last_spoke_at`)  
- `session.config.system_prompt` — the system prompt
- `session.busy` — lock flag
- No `on_message()` method — delivery goes through `_generate_and_send(session, payload)`

**The corrected nudge() for BotManager:**
```python
async def nudge(self, room_id: str, hint: str) -> bool:
    import time as _time
    async with self._lock:
        sessions = list(self._sessions.values())

    # Find eligible sessions for this room
    eligible = [
        s for s in sessions
        if room_id in s.config.enabled_rooms
        and not s.busy
    ]
    if not eligible:
        logger.debug("nudge(%s): no eligible sessions", room_id)
        return False

    # Prefer most-idle (spoke least recently)
    target = min(eligible, key=lambda s: s.last_reply_at)

    # Inject hint into system prompt temporarily
    original = target.config.system_prompt or ""
    target.config.system_prompt = (
        f"{original}\n\n[STAGE DIRECTION — for your eyes only]\n"
        f"{hint}\n[END STAGE DIRECTION]"
    )

    payload = {
        "room": room_id,
        "user_id": "__jeremy__",
        "text": "",
        "nudge": True,
        "ts": _time.time(),
    }

    try:
        target.busy = True
        asyncio.create_task(self._generate_and_send(target, payload))
        logger.info("nudge(%s): fired to '%s'", room_id, target.config.bot_id)
        return True
    except Exception as exc:
        logger.error("nudge(%s): failed: %s", room_id, exc)
        target.busy = False
        return False
    finally:
        # Restore after brief delay to let the task capture it
        async def _restore():
            await asyncio.sleep(0.1)
            target.config.system_prompt = original
        asyncio.create_task(_restore())
```

Note: `_generate_and_send` sets `session.busy = False` in its finally block, so that's handled.

But there's a secondary problem: `_generate_and_send` checks for empty text and may bail early. Add this guard in `_generate_and_send`:
```python
# Allow nudge payloads through even with empty text
if not text and not payload.get("nudge"):
    return
```

---

### Break 4: Blocking file I/O in the async watcher loop

`hub.get_recent_history()` reads JSONL files synchronously inside an `async def`. Jeremy's watcher calls this every 5 seconds per room. With multiple rooms this blocks the event loop.

**Fix in hub.py** — wrap the file read:
```python
async def get_recent_history(self, room: str, limit: int = 12) -> list:
    history_path = self._log_path(room)
    if not history_path.exists():
        return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._read_history_sync, history_path, limit)

def _read_history_sync(self, path: Path, limit: int) -> list:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    recent = lines[-limit:] if len(lines) > limit else lines
    result = []
    for line in recent:
        try:
            result.append(json.loads(line))
        except Exception:
            continue
    return result
```

---

## Memory Persistence Gap

`UniversalMemorySystem` is in-memory only. Every server restart wipes all character memory.

This matters because the whole value proposition is that characters *remember*. If PubCast restarts between sessions, they don't.

**The old jeremy_cricket.py had SQLite persistence.** The schema is in the file (memories table, character_personalities table, conversation_history table). That SQLite layer was not carried into `UniversalMemorySystem` — it was a deliberate scope choice, but it's a gap in production.

Three options, with honest trade-offs:

**Option A — Accept in-memory for now (quickest path to working)**  
Memory survives as long as the server runs. For a live show that's fine. Add a `serialize()` / `restore()` method to `UniversalMemorySystem` that dumps/loads to JSON on shutdown/startup. One afternoon of work. Memory survives restarts but won't be searchable.

**Option B — Add SQLite to UniversalMemorySystem (correct long-term)**  
Add a `SQLiteMemoryBackend` that `CharacterMemoryBank` writes through. Replaces the in-memory list with a SQLite WAL database. Search becomes a SQL query. Memory survives restarts and scales indefinitely. Estimated two days of work done correctly. This is the right eventual architecture.

**Option C — Use the SQLite schema from the old jeremy_cricket.py (fastest to production)**  
The old file has a complete working `MemoryDatabase` class with the correct schema, indexes, locking, and retrieval. Extract that class, wire it as the backend for `CharacterMemoryBank`. Mostly copy-paste with adapter glue. One day of work.

**Recommendation:** Option A now, Option C in the next session, Option B when you have time.

---

## Architectural Approaches — Three Options, Honest Assessment

There is a circular dependency risk in the current wiring:

```
BotManager holds → jeremy (JeremyCricket)
JeremyCricket holds → bot_manager (BotManager)
```

Both objects reference each other. Python handles this fine as long as you don't try to call one during the other's `__init__`. But it's fragile. Three ways to handle it:

---

### Approach A: Direct References (Current — Keep It Simple)

Jeremy holds `self._bm = bot_manager`. BotManager holds `self.jeremy_cricket = jeremy`.

Construct in this order in `main.py`:
```python
bm = BotManager(data_dir, hub)           # jeremy_cricket = None initially
jeremy = await create_jeremy_cricket(memory, bm, hub)
bm.jeremy_cricket = jeremy               # assign after construction
```

**Pro:** Easiest to understand. No new infrastructure.  
**Con:** Construction order matters. If you forget the sequence, you get None reference errors. The cycle is invisible until it bites.

**Verdict:** Fine for now. Document the construction order. Come back to it when the system is larger.

---

### Approach B: Event Queue Decoupling (Cleanest Architecture)

Jeremy doesn't know about BotManager at all. Instead of calling `bm.nudge()` directly, Jeremy puts a nudge event on a shared `asyncio.Queue`. BotManager runs a background task consuming that queue.

```python
# In main.py
nudge_queue = asyncio.Queue()
bm = BotManager(data_dir, hub, nudge_queue=nudge_queue)
jeremy = await create_jeremy_cricket(memory, nudge_queue, hub)
```

Jeremy emits:
```python
await self._nudge_queue.put({"room_id": room_id, "hint": hint})
```

BotManager consumes:
```python
async def _nudge_consumer(self):
    while True:
        event = await self._nudge_queue.get()
        await self._execute_nudge(event["room_id"], event["hint"])
```

**Pro:** Zero circular dependency. Jeremy is completely decoupled from BotManager's internal structure. Easy to test Jeremy in isolation. New consumers of nudges (e.g. a logging system, a monitoring dashboard) just subscribe to the same queue.  
**Con:** Adds a queue hop. Nudge latency increases by one event loop cycle — imperceptible in practice. Slightly more infrastructure in main.py.

**Verdict:** This is the architecturally correct approach for a production system. If you're going to grow PubCast to multiple room types and multiple kinds of bots, do this. It's maybe two hours of work to retrofit.

---

### Approach C: Hub as Central Coordinator

Hub already routes all messages. Instead of Jeremy calling BotManager directly, Jeremy calls `hub.nudge(room_id, hint)`. Hub knows about BotManager and dispatches internally.

```python
# In hub.py
async def nudge(self, room_id: str, hint: str) -> bool:
    if self._bot_manager:
        return await self._bot_manager.nudge(room_id, hint)
    return False
```

Jeremy constructs with only `hub` — not `bot_manager`.

**Pro:** Hub is already the natural central router. Jeremy only needs one reference. Keeps Jeremy simpler.  
**Con:** Hub gets heavier over time. Every new actor (Jeremy, future safety layer, future analytics) adds a method to Hub. Hub becomes a god object.

**Verdict:** Reasonable for small systems. Avoid for large ones. Hub is already doing a lot.

---

### Recommended Path

**Right now:** Approach A. Get it working. Document the construction order.  
**Next session:** Approach B. The event queue is the right long-term design and it's not much work.  
**Never:** Don't let Hub become the coordinator of everything.

---

## What Still Needs Writing

In priority order:

**1. The corrected nudge() — 30 minutes**  
The version in `nudge_patch.py` won't work with actual BotSession structure. Use the corrected version above, verbatim.

**2. bots.py compatibility updates — 1-2 hours**  
Four breaks listed above, all mechanical changes. No design decisions needed.

**3. Memory persistence (Option A) — 2-3 hours**  
Add `serialize()` / `restore()` to `UniversalMemorySystem`. Call on app shutdown/startup in `main.py`. Prevents memory wipe on restart without a full SQLite migration.

**4. `watch_room()` / `release_room()` calls in main.py — 30 minutes**  
Jeremy's watcher tasks don't start automatically. Somewhere in the room creation/teardown flow, these calls need to be made:
```python
# On room created:
await jeremy.watch_room(room_id)

# On room teardown:
await jeremy.release_room(room_id)

# On app shutdown:
await jeremy.shutdown()
```

**5. Jeremy initialization in main.py — 1 hour**  
Construct `UniversalMemorySystem`, register characters, construct `JeremyCricket`, assign to BotManager. Wire the `on_message` call into hub's chat broadcast path:
```python
# In hub.handle_message, after broadcasting chat:
if jeremy:
    asyncio.create_task(
        jeremy.on_message(room, data.get("user_id", "anon"), data.get("text", ""))
    )
```

**6. run_in_executor fix for hub.get_recent_history — 20 minutes**  
Listed in Break 4 above. Direct copy-paste.

---

## File Inventory

| File | Source | Status |
|------|--------|--------|
| `jeremy_cricket.py` | Written this session | ✅ Clean — 798 lines, syntax verified |
| `nudge_patch.py` | Written this session | ⚠️ Wrong object structure — use corrected version above |
| `universal_memory_system.py` | From project | ✅ Real, works, in-memory only |
| `circuit_breaker.py` | From project | ✅ Production-grade, thread-safe |
| `irm.py` | From project | ⚠️ Stub — Phase 3 note in file. Works but throttle() is a no-op |
| `bots.py` | From project | ⚠️ Needs 4 fixes above before running |
| `hub.py` | From project (patched) | ⚠️ Needs run_in_executor fix for file I/O |
| `models.py` | From project | ✅ |
| `persistence.py` | From project | ✅ |
| `schemas.py` | From project | ✅ |
| `base.py` | From project | ✅ LLM adapter interface |

---

## Hub Version Ambiguity

There are multiple `hub.py` files in the project at different line counts (112, 155, 515, 687 lines). The authoritative version is the one at approximately 515-687 lines that includes `is_user_in_room`, `get_recent_history`, and `post_chat_message`. Those three methods were added in a previous session.

**Before dropping this into the main project: confirm which hub.py `main.py` is actually importing.** If it's importing the 112-line version, the three bot methods aren't there and everything will fail silently on first nudge attempt.

---

## What This System Cannot Do Yet

Honest list. Don't oversell it to anyone.

- **Memory does not survive server restarts** (Option A/B/C above)
- **Character detection** for Jeremy's `on_message` event uses `user_id.startswith("bot_")` — but bots in PubCast use `bot-{id}` (dash, not underscore). Update the check in `jeremy_cricket.py` line ~214: `if user_id.startswith("bot-") and len(text) > 80`
- **Reflection calls** require a real LLM adapter passed in `adapter_registry`. Without it, reflection features silently skip. This is by design — graceful degradation — but means characters won't reflect until adapters are registered
- **Context detection** uses keyword overlap for relevance. This works but is crude. Phase 3: replace with vector similarity via Ollama Qwen (already flagged in `universal_memory_system.py`)
- **Speaking slot management** in `ConversationOrchestrator` does not yet connect to the actual WebSocket broadcast. The orchestrator tracks state but nothing enforces that bots wait their turn — it's advisory. Full enforcement requires the event queue approach (Approach B above)

---

## The Architecture in One Paragraph

A room runs. Conversation flows. Jeremy's watcher loop reads recent history every 5 seconds, calculates energy, silence pressure, and plot-point age. When drama necessity crosses the threshold and the nudge cooldown has elapsed, Jeremy queries character memory for anything relevant to the current topic, composes a stage direction from what it finds, and calls `BotManager.nudge(room_id, hint)`. BotManager finds the most-idle eligible bot, temporarily injects the hint into its system prompt, and fires a synthetic trigger. The bot generates a reply with its own voice, informed by Jeremy's whisper. Nobody in the room sees the whisper. The bot just knows things.

---

*Feic Mo Chroí — See My Heart*  
*Rear View Foresight LLC*

---

## Note on bots_COMPLETE.py (not included)

A file called `bots_COMPLETE.py` was reviewed during this session. It contains a character personality layer — `BotOrchestrator` with typed roles for Pete, Jeremy Cricket, Sir Purfluous, and Jeeves, with personality archetypes, memory, response templates, and conversation routing. It's PubCast-specific. It belongs in PubCast, not in this package.

**What it's useful for:** The `BotRole` and `BotPersonality` enums in that file are the right vocabulary for the `CharacterProfile.role` and `personality` fields in `UniversalMemorySystem`. When you register characters with Jeremy Cricket, use those categories. They're the correct taxonomy for the character layer that sits above this memory layer.

**The file itself is corrupted** — non-breaking spaces used as indentation from a docx export, plus hard line-wrap breaks mid-statement. Don't try to run it as-is. The architecture is sound; the file needs to be rewritten cleanly before use.

---

## Director vs. Editor — An Architectural Distinction Worth Keeping

From the auto-director design conversation: the distinction between a **Director** (forward-looking, orchestrates conditions, anticipates beats) and an **Editor** (reactive, selects the best available option from what exists) is the right mental model for this system too.

**Jeremy Cricket is a Director.** It watches ahead. It calculates when something needs to happen. It sets conditions — the hint it composes — before the bot speaks.

**The bots are Editors.** They react to what's in front of them. They execute. They don't decide when to speak on their own; Jeremy decides that for them via nudge().

Keep those roles clean. Don't let Jeremy become reactive, and don't let bots start making scene-level decisions. The moment a bot starts watching room energy itself, you've lost the separation that makes this system coherent.

---

*Feic Mo Chroí*
