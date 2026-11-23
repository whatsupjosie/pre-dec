"""
example_integration.py
═══════════════════════
Minimal example showing how to wire thinking_context into any FastAPI app.

This is NOT PubCast-specific. Replace the stub adapter methods with
whatever your app uses to read history and trigger your AI agents.

Rear View Foresight LLC — Feic Mo Chroí
"""

import asyncio
from typing import Any, Dict, List

from fastapi import FastAPI, Depends, WebSocket
from thinking_context import mount, CharacterProfile, get_thinking_context, ThinkingContext


# ── 1. Your adapter ───────────────────────────────────────────────────────────
#
# One class. Two methods. That's the entire contract.
# Replace the bodies with your real hub/bot logic.

class MyAppAdapter:
    """
    Replace these two methods with your real implementations.
    The types and return shapes are what matter — not the internals.
    """

    def __init__(self, my_hub, my_bot_pool):
        self._hub  = my_hub
        self._bots = my_bot_pool

    async def get_recent_history(self, room: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Return recent messages from the room as a list of dicts.
        Each dict needs at least: {"user_id": str, "text": str, "ts": float}
        Extra keys are ignored.
        """
        # Example — replace with your real call:
        return await self._hub.recent_messages(room, n=limit)

    async def nudge(self, room_id: str, hint: str) -> bool:
        """
        Inject the hint into your AI agent and trigger a response.
        Return True if an agent was triggered, False if none available.
        """
        # Example — replace with your real call:
        return await self._bots.inject_and_trigger(room_id, hint)


# ── 2. Your app ───────────────────────────────────────────────────────────────

app = FastAPI(title="My App with Thinking Context")

# Your real hub and bot pool would be constructed here
# hub      = MyHub(...)
# bot_pool = MyBotPool(...)
# adapter  = MyAppAdapter(hub, bot_pool)

# For this example, use a stub adapter
class _StubAdapter:
    async def get_recent_history(self, room, limit=12): return []
    async def nudge(self, room_id, hint): return False

adapter = _StubAdapter()

# ── 3. Mount — this is the whole integration ──────────────────────────────────

mount(
    app,
    adapter,
    characters = [
        CharacterProfile(
            character_id = "bot-alice",
            name         = "Alice",
            role         = "host",
            personality  = {"style": "warm", "tendency": "storytelling"},
            backstory     = "Alice has been hosting since the beginning.",
        ),
        CharacterProfile(
            character_id = "bot-bob",
            name         = "Bob",
            role         = "commentator",
            personality  = {"style": "dry", "tendency": "observation"},
        ),
        # Add as many characters as you have bots
    ],
    snapshot_path      = "data/memory_snapshot.json",  # where memory is saved
    silence_threshold  = 45.0,   # seconds quiet before Jeremy considers nudging
    min_nudge_interval = 90.0,   # minimum seconds between nudges per room
    drama_threshold    = 0.65,   # 0–1, how much energy drop triggers a nudge
    startup_rooms      = [],     # rooms to watch immediately — or use watch_room() below
)


# ── 4. Room lifecycle — call watch_room / release_room from your routes ───────

@app.post("/rooms/{room_id}/open")
async def open_room(room_id: str, tc: ThinkingContext = Depends(get_thinking_context)):
    """Example: when a room opens, tell Jeremy to watch it."""
    await tc.watch_room(room_id)
    return {"status": "watching", "room": room_id}


@app.post("/rooms/{room_id}/close")
async def close_room(room_id: str, tc: ThinkingContext = Depends(get_thinking_context)):
    """Example: when a room closes, tell Jeremy to stop watching."""
    await tc.release_room(room_id)
    return {"status": "released", "room": room_id}


# ── 5. Message wiring — feed chat events to Jeremy ────────────────────────────
#
# In your WebSocket handler or wherever you broadcast chat messages,
# add ONE line after you broadcast to clients:
#
#   asyncio.create_task(tc.on_message(room_id, user_id, text))
#
# Example:

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    tc: ThinkingContext = app.state.thinking_context

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            user_id = data.get("user_id", "anon")
            text    = data.get("text", "")

            # ... your normal broadcast to all room clients goes here ...

            # Feed the message to Jeremy (fire and forget — never blocks)
            if text:
                asyncio.create_task(tc.on_message(room_id, user_id, text))

    except Exception:
        pass


# ── 6. Status endpoint (included automatically by mount) ─────────────────────
#
# GET /thinking-context/status
# Returns uptime, active rooms, nudge counts, memory stats.
# Disable with: mount(..., include_router=False)


# ── 7. Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
