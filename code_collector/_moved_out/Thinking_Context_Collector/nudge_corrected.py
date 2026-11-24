"""
nudge_corrected.py
══════════════════
Drop-in replacement for the nudge() method in BotManager (bots.py).

The version in nudge_patch.py was written against a hypothetical bot structure.
This version matches the real BotSession objects used in PubCast.

HOW TO USE:
  1. Copy the `nudge()` method below into your BotManager class in bots.py.
  2. Add `import asyncio` at the top of bots.py if not already present.
  3. In _generate_and_send(), find the early-exit guard for empty text and
     add the nudge bypass (see the NOTE below the method).

Rear View Foresight LLC — Feic Mo Chroí
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


# ── Paste this method into BotManager ────────────────────────────────────────

class _BotManagerStub:
    """Stub wrapper — extract nudge() and paste into your real BotManager."""

    async def nudge(self, room_id: str, hint: str) -> bool:
        """
        Jeremy Cricket's activation lever.

        Finds the most-idle eligible bot in the given room, temporarily
        injects `hint` as a stage direction into its system prompt, then
        fires a synthetic trigger payload through _generate_and_send().

        The bot generates its reply with its own voice — it simply finds
        itself with richer context. Nobody in the room sees the hint.

        Returns True if a bot was successfully nudged, False otherwise.
        """
        # 1. Snapshot current sessions without holding the lock during delivery
        async with self._lock:
            sessions = list(self._sessions.values())

        # 2. Find eligible sessions for this room
        eligible = [
            s for s in sessions
            if room_id in s.config.enabled_rooms
            and not s.busy
        ]
        if not eligible:
            logger.debug("nudge(%s): no eligible sessions in room", room_id)
            return False

        # 3. Prefer the most-idle session (spoke least recently)
        target = min(eligible, key=lambda s: s.last_reply_at)

        # 4. Temporarily inject the hint into the system prompt
        original_prompt = target.config.system_prompt or ""
        target.config.system_prompt = (
            f"{original_prompt}\n\n"
            f"[STAGE DIRECTION — for your eyes only]\n"
            f"{hint}\n"
            f"[END STAGE DIRECTION]"
        )

        # 5. Build synthetic trigger payload
        payload = {
            "room":    room_id,
            "user_id": "__jeremy__",
            "text":    "",
            "nudge":   True,
            "ts":      asyncio.get_event_loop().time(),
        }

        try:
            target.busy = True
            asyncio.create_task(self._generate_and_send(target, payload))
            logger.info(
                "nudge(%s): fired to '%s' | hint=%r",
                room_id, target.config.bot_id, hint[:80],
            )
            return True

        except Exception as exc:
            logger.error("nudge(%s): failed to fire task: %s", room_id, exc)
            target.busy = False
            return False

        finally:
            # Restore system prompt after a brief delay so the spawned task
            # captures the enriched version before we reset it.
            # _generate_and_send handles setting busy=False in its own finally.
            async def _restore():
                await asyncio.sleep(0.15)
                target.config.system_prompt = original_prompt
            asyncio.create_task(_restore())


# ── Patch for _generate_and_send ─────────────────────────────────────────────
#
# In bots.py, find _generate_and_send(). It likely has an early-exit guard
# that looks like:
#
#     if not text:
#         return
#
# Replace it with:
#
#     if not text and not payload.get("nudge"):
#         return
#
# This lets nudge payloads through even though their text field is empty.
# Without this, the synthetic trigger will be silently dropped and the bot
# will never speak.
#
# ─────────────────────────────────────────────────────────────────────────────
