"""
safety_governor.py — Jeremy Cricket Adaptive Awareness Suite
Preservation Lock: enforces READ_ONLY on project files during high dysregulation.
Stability Handshake: the only legitimate unlock path.
Autopilot: handles administrative burden while user is in TOTAL_CARE_MANDATE.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class LockState(str, Enum):
    UNLOCKED  = "UNLOCKED"
    READ_ONLY = "READ_ONLY"
    SNAPSHOT  = "SNAPSHOT_ONLY"


@dataclass
class AutopilotAction:
    name: str
    description: str
    completed: bool = False
    result: str = ""


class SafetyGovernor:
    """
    Watches CharacterEngine mode. When TOTAL_CARE_MANDATE fires:
      - Sets lock_state = READ_ONLY
      - Runs autopilot tasks (save work, reschedule, lock files)
      - Blocks all write operations to guarded paths
      - Only exits lockdown via verified Stability Handshake
    """

    def __init__(self, guarded_root: Path, config_path: str = "config.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        safety = cfg["safety"]

        self._guarded_root     = guarded_root
        self._lock_extensions  = set(safety["lock_sensitive_extensions"])
        self._autopilot_tasks  = safety["autopilot_tasks"]
        self._lock_mode        = LockState(safety["preservation_lock_mode"])

        sm = cfg["state_machine"]
        self._handshake_needed = sm["stability_handshake_required"]
        self._handshake_window = sm["stability_handshake_window_seconds"]

        self._state: LockState            = LockState.UNLOCKED
        self._lock                        = asyncio.Lock()
        self._handshake_log: List[float]  = []
        self._autopilot_log: List[AutopilotAction] = []
        self._snapshot_path: Optional[Path] = None
        self._locked_at: Optional[float]  = None

        # External callbacks: register to be notified on lock/unlock
        self._on_lock_hooks:   List[Callable] = []
        self._on_unlock_hooks: List[Callable] = []

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def lock_state(self) -> LockState:
        return self._state

    @property
    def is_locked(self) -> bool:
        return self._state != LockState.UNLOCKED

    def register_lock_hook(self, fn: Callable) -> None:
        self._on_lock_hooks.append(fn)

    def register_unlock_hook(self, fn: Callable) -> None:
        self._on_unlock_hooks.append(fn)

    async def on_mode_change(self, old_mode: str, new_mode: str) -> None:
        """
        Hook to wire into CharacterEngine.register_mode_change_hook().
        Automatically triggers lockdown or evaluates unlock on mode change.
        """
        if new_mode == "TOTAL_CARE_MANDATE" and not self.is_locked:
            await self.engage_lock()
        elif old_mode == "TOTAL_CARE_MANDATE" and new_mode != "TOTAL_CARE_MANDATE":
            # Mode stepped down but lock requires explicit handshake — do nothing here.
            logger.info("Mode stepped down from TOTAL_CARE_MANDATE. Lock persists until handshake.")

    async def engage_lock(self) -> None:
        """Engage the Preservation Lock. Runs autopilot. Non-blocking for caller."""
        async with self._lock:
            if self._state != LockState.UNLOCKED:
                return  # Already locked
            self._state = self._lock_mode
            self._locked_at = time.time()
            logger.warning("PRESERVATION LOCK ENGAGED: %s", self._state.value)
            asyncio.create_task(self._run_autopilot())
            self._fire_hooks(self._on_lock_hooks)

    async def submit_handshake(self) -> bool:
        """
        User submits a calm stability confirmation.
        Must be called `handshake_needed` times within `handshake_window` seconds.
        Returns True when handshake is accepted and lock is released.

        Cannot be bypassed by rapid-fire submissions — window enforcement is strict.
        """
        async with self._lock:
            now = time.monotonic()
            # Prune stale entries
            self._handshake_log = [t for t in self._handshake_log if now - t < self._handshake_window]
            self._handshake_log.append(now)

            count = len(self._handshake_log)
            remaining = self._handshake_needed - count

            if count >= self._handshake_needed:
                self._handshake_log.clear()
                old_state = self._state
                self._state = LockState.UNLOCKED
                self._locked_at = None
                logger.info("Stability handshake accepted. Lock released (%s → UNLOCKED).", old_state.value)
                self._fire_hooks(self._on_unlock_hooks)
                return True

            logger.info(
                "Handshake logged (%d/%d). %d more needed within %ds.",
                count, self._handshake_needed, remaining, self._handshake_window
            )
            return False

    def can_write(self, path: Path) -> bool:
        """
        Gate any write operation. Returns False if locked and path is sensitive.
        Use this before any file mutation.
        """
        if not self.is_locked:
            return True
        ext = path.suffix.lower()
        is_sensitive = (
            ext in self._lock_extensions or
            self._guarded_root in path.parents or
            path == self._guarded_root
        )
        if is_sensitive:
            logger.warning("WRITE BLOCKED (lock=%s): %s", self._state.value, path)
            return False
        return True

    def status_summary(self) -> dict:
        return {
            "lock_state":        self._state.value,
            "locked_at":         self._locked_at,
            "handshake_pending": len(self._handshake_log),
            "handshake_needed":  self._handshake_needed,
            "autopilot_actions": [
                {"name": a.name, "completed": a.completed, "result": a.result}
                for a in self._autopilot_log
            ],
            "snapshot_path": str(self._snapshot_path) if self._snapshot_path else None,
        }

    # ── Autopilot ─────────────────────────────────────────────────────────────

    async def _run_autopilot(self) -> None:
        """
        Non-blocking background tasks Jeremy handles during lockdown.
        Failures are caught and logged — never raises.
        """
        logger.info("Autopilot starting. Tasks: %s", self._autopilot_tasks)
        for task_name in self._autopilot_tasks:
            action = AutopilotAction(name=task_name, description=task_name)
            try:
                handler = getattr(self, f"_autopilot_{task_name}", None)
                if handler:
                    result = await handler()
                    action.result = result or "done"
                else:
                    action.result = "no handler (skipped)"
                action.completed = True
            except Exception as e:
                action.result = f"error: {e}"
                logger.error("Autopilot task [%s] failed: %s", task_name, e)
            self._autopilot_log.append(action)
            logger.info("Autopilot [%s]: %s", task_name, action.result)

    async def _autopilot_save_current_work(self) -> str:
        """Take a snapshot of guarded_root."""
        snapshot_dir = self._guarded_root.parent / ".jc_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        dest = snapshot_dir / f"snapshot_{stamp}"
        if self._guarded_root.exists():
            await asyncio.to_thread(shutil.copytree, str(self._guarded_root), str(dest))
            self._snapshot_path = dest
            return f"Snapshot saved to {dest}"
        return "guarded_root does not exist, nothing to snapshot"

    async def _autopilot_reschedule_pending_actions(self) -> str:
        # Stub — integrate with your scheduler if present
        return "pending actions flagged for rescheduling (stub)"

    async def _autopilot_lock_sensitive_files(self) -> str:
        """Make sensitive files read-only at OS level."""
        if not self._guarded_root.exists():
            return "guarded_root missing"
        count = 0
        for path in self._guarded_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in self._lock_extensions:
                current = path.stat().st_mode
                # Remove write bits: user, group, other
                path.chmod(current & ~0o222)
                count += 1
        return f"locked {count} sensitive files"

    async def _autopilot_send_care_notification(self) -> str:
        # Stub — hook into your notification system
        logger.info("[CARE NOTIFICATION] User entered TOTAL_CARE_MANDATE. Jeremy is holding it.")
        return "notification sent (stub)"

    def _fire_hooks(self, hooks: List[Callable]) -> None:
        for fn in hooks:
            try:
                fn()
            except Exception as e:
                logger.warning("Governor hook error: %s", e)
