"""
main_integration.py
════════════════════
Integration snippet for main.py — shows the correct construction order,
memory restore/serialize, Jeremy wiring, and room lifecycle hooks.

This is NOT a standalone file. Paste the relevant sections into your
existing main.py, adapting to your actual Hub/BotManager init flow.

Rear View Foresight LLC — Feic Mo Chroí
"""

import asyncio
import logging
import signal

from universal_memory_system import (
    CharacterProfile,
    MemoryEntry,
    MemoryType,
    UniversalMemorySystem,
)
from jeremy_cricket import JeremyCricket, JeremyConfig, create_jeremy_cricket

logger = logging.getLogger(__name__)

MEMORY_SNAPSHOT_PATH = "data/memory_snapshot.json"


# ── 1. Construction order ─────────────────────────────────────────────────────
#
# CRITICAL: Build in this exact order to avoid None reference errors.
# Jeremy needs bot_manager, bot_manager needs jeremy — but only after both exist.

async def build_jeremy(hub, bot_manager) -> JeremyCricket:
    """
    Construct UniversalMemorySystem, restore any persisted memory,
    register characters, then create JeremyCricket.
    """

    # 1a. Memory system
    memory = UniversalMemorySystem()

    # 1b. Restore from last snapshot (Option A persistence)
    restored = memory.restore(MEMORY_SNAPSHOT_PATH)
    if restored:
        logger.info("Restored %d memory entries from snapshot.", restored)

    # 1c. Register characters.
    #     If already in snapshot, register_character is safe to call again —
    #     it won't overwrite existing banks, just upserts the profile.
    memory.register_character(CharacterProfile(
        character_id = "bot-pete",
        name         = "Pete",
        role         = "host",
        personality  = {"style": "warm", "tendency": "storytelling"},
        backstory    = "Pete has been hosting PubCast since the beginning.",
    ))
    memory.register_character(CharacterProfile(
        character_id = "bot-purfluous",
        name         = "Sir Purfluous",
        role         = "commentator",
        personality  = {"style": "dry", "tendency": "observation"},
        backstory    = "Sir Purfluous notices what others miss.",
    ))
    # Add more characters here as needed.

    # 1d. Optional: adapter_registry maps character_id → LLM adapter
    #     Omit or leave empty if you don't have adapters wired yet —
    #     reflection features will skip gracefully.
    adapter_registry = {}  # e.g. {"bot-pete": your_pete_adapter}

    # 1e. Create Jeremy (Approach A: direct references)
    jeremy = await create_jeremy_cricket(
        memory_system    = memory,
        bot_manager      = bot_manager,   # BotManager must exist before this call
        hub              = hub,
        adapter_registry = adapter_registry,
        config           = JeremyConfig(
            poll_interval      = 5.0,
            silence_threshold  = 45.0,
            min_nudge_interval = 90.0,
            drama_threshold    = 0.65,
        ),
    )

    # 1f. Assign back to BotManager so it can call jeremy.on_message() etc.
    bot_manager.jeremy_cricket = jeremy

    return jeremy


# ── 2. Room lifecycle ─────────────────────────────────────────────────────────
#
# Call these wherever your Hub/BotManager creates and tears down rooms.

async def on_room_created(jeremy: JeremyCricket, room_id: str) -> None:
    """Call when a new room opens."""
    await jeremy.watch_room(room_id)
    logger.info("Jeremy now watching room: %s", room_id)


async def on_room_closed(jeremy: JeremyCricket, room_id: str) -> None:
    """Call when a room closes."""
    await jeremy.release_room(room_id)
    logger.info("Jeremy released room: %s", room_id)


# ── 3. Message wiring ─────────────────────────────────────────────────────────
#
# In hub.py, find the place where you broadcast a chat message to all clients.
# After broadcasting, add:
#
#     if hasattr(self, '_jeremy') and self._jeremy:
#         asyncio.create_task(
#             self._jeremy.on_message(room, data.get("user_id", "anon"), data.get("text", ""))
#         )
#
# Or pass jeremy into hub at construction and call directly.
# Either way — fire-and-forget with create_task so hub never blocks on Jeremy.


# ── 4. Shutdown — serialize memory before exit ────────────────────────────────

async def shutdown(jeremy: JeremyCricket) -> None:
    """
    Graceful shutdown: stop Jeremy's watcher loops, serialize memory.
    Hook this into your app's shutdown/signal handler.
    """
    logger.info("Shutting down Jeremy Cricket...")
    await jeremy.shutdown()

    logger.info("Serializing memory snapshot...")
    jeremy.memory.serialize(MEMORY_SNAPSHOT_PATH)
    logger.info("Memory saved. Goodbye.")


# ── 5. Putting it together (example) ─────────────────────────────────────────

async def main():
    # Your existing Hub and BotManager construction goes here.
    # hub = Hub(...)
    # bm  = BotManager(data_dir, hub)   ← jeremy_cricket=None initially

    # Build Jeremy and wire it up
    # jeremy = await build_jeremy(hub, bm)

    # Watch any rooms that already exist at startup
    # for room_id in hub.active_rooms():
    #     await on_room_created(jeremy, room_id)

    # Register shutdown handler
    # loop = asyncio.get_event_loop()
    # loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(jeremy)))
    # loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(shutdown(jeremy)))

    # ... rest of your startup ...
    pass


# ── 6. bots.py changes checklist ─────────────────────────────────────────────
#
# Break 1 — import line (line 12 of bots.py):
#   OLD: from jeremy_cricket import get_jeremy_cricket, JeremyCricketOrchestrator
#   NEW: from jeremy_cricket import JeremyCricket, create_jeremy_cricket, JeremyConfig
#
# Break 2 — replace these calls in BotManager:
#
#   jeremy.start_background_orchestration()
#     → Remove entirely. Jeremy starts its own watcher loops via watch_room().
#
#   jeremy.store_character_memory(char_id, content, context, importance, tags)
#     → Replace with:
#        from universal_memory_system import MemoryEntry, MemoryType
#        jeremy.memory.get_or_create_bank(char_id).add(MemoryEntry(
#            content=content, importance=importance, tags=tags
#        ))
#
#   jeremy.register_character_personality(char_id, name, core_traits, ...)
#     → Replace with:
#        from universal_memory_system import CharacterProfile
#        jeremy.memory.register_character(CharacterProfile(
#            character_id=char_id, name=name, personality={"core_traits": core_traits}
#        ))
#
#   jeremy.get_memory_suggestions(bot_id, room_id, history)
#     → Remove entirely. Jeremy now whispers proactively via nudge().
#       There is no on-demand per-reply suggestions call anymore.
#
# Break 3 — replace nudge() with the version in nudge_corrected.py
#
# Break 4 — replace get_recent_history() with the version in hub_patch.py
#
# ─────────────────────────────────────────────────────────────────────────────
