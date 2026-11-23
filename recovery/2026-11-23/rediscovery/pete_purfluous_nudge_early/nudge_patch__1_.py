"""
nudge_patch.py
══════════════
Copy the `nudge()` method below into your BotManager class in bots.py.
Placement: after the existing remove_bot() or _handle_message() method,
before the end of the class block.

The stub class here exists only so this file parses cleanly.
Do not import this module — extract the method.
"""

import logging
import time as _time

logger = logging.getLogger(__name__)


class _BotManagerStub:
    """Stub. Replace with your real BotManager class."""

    async def nudge(self, room_id: str, hint: str) -> bool:
        """
        Sir Purfluous's activation lever.

        Finds an idle bot in the room, temporarily enriches its system prompt
        with `hint`, then fires a synthetic trigger so it speaks on its own.
        The bot never sees this as an external command — it simply finds itself
        with richer context and responds accordingly.

        Returns True if a bot was nudged, False if no eligible bot is available.
        """
        # 1. Find eligible bots for this room
        room_bots = [
            bot for bot in self._bots.values()
            if getattr(bot, "room_id", None) == room_id
            and getattr(bot, "enabled", True)
        ]
        if not room_bots:
            logger.debug("nudge(%s): no bots in room", room_id)
            return False

        # 2. Prefer the bot that spoke least recently
        def _last_spoke(bot) -> float:
            return getattr(bot, "_last_spoke_at", 0.0)

        target = min(room_bots, key=_last_spoke)

        # 3. Temporarily inject the hint into the system prompt
        original_system = getattr(target, "system_prompt", "")
        enriched_system = (
            f"{original_system}\n\n"
            f"[STAGE DIRECTION -- visible only to you]\n{hint}\n"
            f"[END STAGE DIRECTION]"
        )
        target.system_prompt = enriched_system

        # 4. Fire a synthetic trigger message
        try:
            synthetic_payload = {
                "room": room_id,
                "user_id": "__purfluous__",
                "text": "",
                "nudge": True,
                "ts": _time.time(),
            }
            await target.on_message(synthetic_payload)
            logger.info(
                "nudge(%s): delivered to bot '%s' | hint=%r",
                room_id,
                getattr(target, "bot_id", "unknown"),
                hint[:80],
            )
            return True

        except Exception as exc:
            logger.error("nudge(%s): bot.on_message raised: %s", room_id, exc)
            return False

        finally:
            # 5. Always restore original system prompt
            target.system_prompt = original_system
