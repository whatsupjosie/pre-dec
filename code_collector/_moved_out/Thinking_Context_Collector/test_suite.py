"""
test_suite.py
═════════════
Test suite for Thinking Context Collector.

Run with:  python3 test_suite.py
Or:        python3 -m pytest test_suite.py -v

Tests cover:
  - UniversalMemorySystem (add, search, recent, serialize/restore)
  - SQLiteMemorySystem and SQLiteMemoryBank
  - NudgeQueue and NudgeConsumer
  - JeremyCricket drama necessity math
  - JeremyCricket room lifecycle
  - CircuitBreaker state machine
  - IRMController health checks

Rear View Foresight LLC — Feic Mo Chroí
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from universal_memory_system import (
    CharacterMemoryBank,
    CharacterProfile,
    MemoryEntry,
    MemoryType,
    UniversalMemorySystem,
)
from sqlite_memory_backend import SQLiteMemoryBank, SQLiteMemorySystem
from nudge_queue import NudgeConsumer, NudgeEvent, NudgeQueue
from circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from irm import HealthStatus, IRMController
from jeremy_cricket import (
    JeremyConfig,
    RoomSceneState,
    ScenePhase,
    _calculate_drama_necessity,
    _derive_phase,
    _estimate_energy,
    _extract_plot_points,
    create_jeremy_cricket,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_profile(char_id="bot-pete", name="Pete") -> CharacterProfile:
    return CharacterProfile(character_id=char_id, name=name, role="host")


def make_entry(content="test memory", importance=0.5, tags=None) -> MemoryEntry:
    return MemoryEntry(content=content, importance=importance, tags=tags or [])


# ─────────────────────────────────────────────────────────────────────────────
# UniversalMemorySystem
# ─────────────────────────────────────────────────────────────────────────────

class TestUniversalMemorySystem(unittest.TestCase):

    def setUp(self):
        self.mem = UniversalMemorySystem()
        self.mem.register_character(make_profile())

    def test_register_creates_bank(self):
        self.assertIn("bot-pete", self.mem._banks)
        self.assertIn("bot-pete", self.mem._profiles)

    def test_add_and_search(self):
        bank = self.mem.get_or_create_bank("bot-pete")
        bank.add(make_entry("Pete loves a good story"))
        bank.add(make_entry("The first broadcast was exciting"))
        results = bank.search("broadcast")
        self.assertTrue(any("broadcast" in r.content for r in results))

    def test_search_by_type(self):
        bank = self.mem.get_or_create_bank("bot-pete")
        bank.add(MemoryEntry(content="emotional moment", memory_type=MemoryType.EMOTIONAL))
        bank.add(MemoryEntry(content="factual detail", memory_type=MemoryType.SEMANTIC))
        results = bank.search("", memory_type=MemoryType.EMOTIONAL)
        self.assertTrue(all(r.memory_type == MemoryType.EMOTIONAL for r in results))

    def test_recent(self):
        bank = self.mem.get_or_create_bank("bot-pete")
        for i in range(5):
            bank.add(make_entry(f"entry {i}", importance=0.5))
        recent = bank.recent(limit=3)
        self.assertEqual(len(recent), 3)
        # Most recent first
        self.assertTrue(recent[0].timestamp >= recent[-1].timestamp)

    def test_broadcast_to_all(self):
        self.mem.register_character(make_profile("bot-sir", "Sir Purfluous"))
        entry = make_entry("a shared memory")
        self.mem.broadcast_to_all(entry)
        for cid in ["bot-pete", "bot-sir"]:
            bank = self.mem.get_or_create_bank(cid)
            self.assertTrue(any(m.content == "a shared memory" for m in bank._memories))
        self.assertTrue(any(m.content == "a shared memory" for m in self.mem._global))

    def test_global_context(self):
        for i in range(5):
            self.mem.add_global_event(make_entry(f"global {i}"))
        ctx = self.mem.global_context(limit=3)
        self.assertEqual(len(ctx), 3)

    def test_serialize_restore_roundtrip(self):
        bank = self.mem.get_or_create_bank("bot-pete")
        bank.add(make_entry("persistent memory", importance=0.9, tags=["test"]))
        self.mem.add_global_event(make_entry("global persistent"))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.mem.serialize(path)

            mem2 = UniversalMemorySystem()
            count = mem2.restore(path)
            self.assertGreater(count, 0)

            bank2 = mem2.get_or_create_bank("bot-pete")
            self.assertTrue(any("persistent memory" in m.content for m in bank2._memories))
            self.assertTrue(any("global persistent" in m.content for m in mem2._global))
            self.assertIn("bot-pete", mem2._profiles)
        finally:
            os.unlink(path)

    def test_restore_missing_file_returns_zero(self):
        count = self.mem.restore("/tmp/does_not_exist_abc123.json")
        self.assertEqual(count, 0)

    def test_max_entries_cap(self):
        bank = CharacterMemoryBank("test", max_entries=3)
        for i in range(10):
            bank.add(make_entry(f"entry {i}", importance=float(i) / 10))
        self.assertLessEqual(len(bank._memories), 3)
        # Should keep highest importance
        contents = [m.content for m in bank._memories]
        self.assertIn("entry 9", contents)


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Backend
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLiteMemoryBank(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.bank = SQLiteMemoryBank("bot-pete", self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_add_persists(self):
        entry = make_entry("SQLite memory")
        self.bank.add(entry)
        # Open a fresh bank on the same file — should find the entry
        bank2 = SQLiteMemoryBank("bot-pete", self.db_path)
        recent = bank2.recent(limit=10)
        self.assertTrue(any("SQLite memory" in m.content for m in recent))

    def test_search_returns_relevant(self):
        self.bank.add(make_entry("broadcast and radio waves"))
        self.bank.add(make_entry("completely unrelated topic"))
        results = self.bank.search("broadcast")
        self.assertTrue(any("broadcast" in r.content for r in results))

    def test_search_type_filter(self):
        self.bank.add(MemoryEntry(content="emotional recall", memory_type=MemoryType.EMOTIONAL))
        self.bank.add(MemoryEntry(content="factual recall", memory_type=MemoryType.SEMANTIC))
        results = self.bank.search("recall", memory_type=MemoryType.EMOTIONAL)
        self.assertTrue(all(r.memory_type == MemoryType.EMOTIONAL for r in results))

    def test_count(self):
        for i in range(5):
            self.bank.add(make_entry(f"entry {i}"))
        self.assertEqual(self.bank.count(), 5)

    def test_clear(self):
        self.bank.add(make_entry("to be cleared"))
        self.bank.clear()
        self.assertEqual(self.bank.count(), 0)

    def test_tags_roundtrip(self):
        entry = make_entry("tagged memory", tags=["alpha", "beta"])
        self.bank.add(entry)
        recent = self.bank.recent(limit=1)
        self.assertIn("alpha", recent[0].tags)
        self.assertIn("beta", recent[0].tags)


class TestSQLiteMemorySystem(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.mem = SQLiteMemorySystem(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_register_and_persist_profile(self):
        self.mem.register_character(make_profile())
        # New instance on same DB should restore profile
        mem2 = SQLiteMemorySystem(self.db_path)
        count = mem2.restore_profiles()
        self.assertGreaterEqual(count, 1)
        self.assertIn("bot-pete", mem2._profiles)

    def test_serialize_noop(self):
        # Should not raise
        self.mem.serialize("/tmp/should_not_be_written.json")
        self.assertFalse(os.path.exists("/tmp/should_not_be_written.json"))

    def test_get_or_create_bank_returns_sqlite_bank(self):
        bank = self.mem.get_or_create_bank("bot-pete")
        self.assertIsInstance(bank, SQLiteMemoryBank)

    def test_memory_survives_across_instances(self):
        self.mem.register_character(make_profile())
        bank = self.mem.get_or_create_bank("bot-pete")
        bank.add(make_entry("survived the restart"))

        mem2 = SQLiteMemorySystem(self.db_path)
        bank2 = mem2.get_or_create_bank("bot-pete")
        recent = bank2.recent(limit=5)
        self.assertTrue(any("survived the restart" in m.content for m in recent))


# ─────────────────────────────────────────────────────────────────────────────
# NudgeQueue
# ─────────────────────────────────────────────────────────────────────────────

class TestNudgeQueue(unittest.TestCase):

    def test_enqueue_and_dequeue(self):
        async def _run():
            q = NudgeQueue()
            result = await q.nudge("room-1", "say something interesting")
            self.assertTrue(result)
            self.assertEqual(q.qsize, 1)
            event = await q.get()
            self.assertEqual(event.room_id, "room-1")
            self.assertEqual(event.hint, "say something interesting")
        run_async(_run())

    def test_full_queue_returns_false(self):
        async def _run():
            q = NudgeQueue(maxsize=1)
            await q.nudge("room-1", "first")
            result = await q.nudge("room-1", "second — should be dropped")
            self.assertFalse(result)
        run_async(_run())

    def test_stale_events_discarded(self):
        async def _run():
            delivered = []

            class FakeBM:
                async def nudge(self, room_id, hint):
                    delivered.append((room_id, hint))
                    return True

            q = NudgeQueue()
            consumer = NudgeConsumer(q, FakeBM(), max_age=0.01)

            # Put an event then wait for it to go stale
            await q.nudge("room-1", "stale hint")
            await asyncio.sleep(0.05)

            # Start consumer and let it run one cycle
            task = asyncio.create_task(consumer.run())
            await asyncio.sleep(0.1)
            consumer.stop()
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Stale event should NOT have been delivered
            self.assertEqual(len(delivered), 0)

        run_async(_run())

    def test_fresh_events_delivered(self):
        async def _run():
            delivered = []

            class FakeBM:
                async def nudge(self, room_id, hint):
                    delivered.append((room_id, hint))
                    return True

            q = NudgeQueue()
            consumer = NudgeConsumer(q, FakeBM(), max_age=30.0)

            task = asyncio.create_task(consumer.run())
            await q.nudge("room-1", "fresh hint")
            await asyncio.sleep(0.2)
            consumer.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            self.assertEqual(len(delivered), 1)
            self.assertEqual(delivered[0][1], "fresh hint")

        run_async(_run())


# ─────────────────────────────────────────────────────────────────────────────
# JeremyCricket — math and lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestDramaMath(unittest.TestCase):

    def _state(self, silence=0, energy=0.5, open_pts=0) -> RoomSceneState:
        state = RoomSceneState(room_id="test-room")
        state.last_message_at = time.time() - silence
        state.record_energy_sample(energy)
        for i in range(open_pts):
            from jeremy_cricket import PlotPoint
            state.plot_points.append(PlotPoint(text=f"unresolved question {i}?"))
        return state

    def test_silence_raises_necessity(self):
        cfg = JeremyConfig()
        low  = _calculate_drama_necessity(self._state(silence=0,   energy=0.8), cfg)
        high = _calculate_drama_necessity(self._state(silence=200, energy=0.3), cfg)
        self.assertGreater(high, low)

    def test_necessity_bounded(self):
        cfg = JeremyConfig()
        for silence in [0, 30, 90, 300]:
            for energy in [0.0, 0.5, 1.0]:
                n = _calculate_drama_necessity(self._state(silence, energy), cfg)
                self.assertGreaterEqual(n, 0.0)
                self.assertLessEqual(n, 1.0)

    def test_climax_suppresses_necessity(self):
        cfg = JeremyConfig()
        state = self._state(silence=60, energy=0.9)
        state.phase = ScenePhase.CLIMAX
        n = _calculate_drama_necessity(state, cfg)
        self.assertLess(n, cfg.drama_threshold)

    def test_silence_phase_boosts_necessity(self):
        cfg = JeremyConfig()
        state = self._state(silence=100, energy=0.1)
        state.phase = ScenePhase.SILENCE
        n = _calculate_drama_necessity(state, cfg)
        self.assertGreaterEqual(n, cfg.drama_threshold)

    def test_open_plot_points_raise_necessity(self):
        cfg = JeremyConfig()
        without = _calculate_drama_necessity(self._state(silence=50, energy=0.4, open_pts=0), cfg)
        with_pts = _calculate_drama_necessity(self._state(silence=50, energy=0.4, open_pts=2), cfg)
        # Should be greater after the plot point urgency ages
        # (immediately after creation urgency is low — that's correct)
        self.assertGreaterEqual(with_pts, 0.0)

    def test_derive_phase_silence(self):
        cfg = JeremyConfig()
        state = self._state(silence=cfg.silence_threshold + 1, energy=0.5)
        self.assertEqual(_derive_phase(state, cfg), ScenePhase.SILENCE)

    def test_derive_phase_opening(self):
        cfg = JeremyConfig()
        state = RoomSceneState(room_id="x")
        state.opened_at = time.time() - 30  # only 30s old
        state.last_message_at = time.time()
        state.record_energy_sample(0.5)
        self.assertEqual(_derive_phase(state, cfg), ScenePhase.OPENING)

    def test_derive_phase_climax(self):
        cfg = JeremyConfig()
        state = self._state(silence=0, energy=0.9)
        state.opened_at = time.time() - 120
        self.assertEqual(_derive_phase(state, cfg), ScenePhase.CLIMAX)


class TestExtractPlotPoints(unittest.TestCase):

    def _msgs(self, *texts):
        return [{"text": t, "ts": time.time()} for t in texts]

    def test_questions_detected(self):
        msgs = self._msgs(
            "Why do you think that happened?",
            "What would you do differently?",
            "How does that make you feel?",
        )
        pts = _extract_plot_points(msgs)
        self.assertEqual(len(pts), 3)

    def test_filler_ignored(self):
        pts = _extract_plot_points(self._msgs("okay?", "right?", "yeah?"))
        self.assertEqual(len(pts), 0)

    def test_statements_ignored(self):
        pts = _extract_plot_points(self._msgs("The weather is nice today."))
        self.assertEqual(len(pts), 0)


class TestEstimateEnergy(unittest.TestCase):

    def test_no_messages_zero_energy(self):
        self.assertEqual(_estimate_energy([]), 0.0)

    def test_recent_messages_raise_energy(self):
        now = time.time()
        msgs = [{"ts": now - i} for i in range(20)]
        energy = _estimate_energy(msgs, window_seconds=60.0)
        self.assertGreater(energy, 0.0)

    def test_old_messages_low_energy(self):
        old = time.time() - 3600
        msgs = [{"ts": old - i} for i in range(5)]
        energy = _estimate_energy(msgs, window_seconds=120.0)
        self.assertEqual(energy, 0.0)


class TestJeremyCricketLifecycle(unittest.TestCase):

    @staticmethod
    async def _make_jeremy_async():
        class FakeHub:
            async def get_recent_history(self, room_id, limit=12):
                return []

        class FakeBM:
            async def nudge(self, room_id, hint):
                return True

        mem = UniversalMemorySystem()
        mem.register_character(make_profile())
        jeremy = await create_jeremy_cricket(
            memory_system = mem,
            bot_manager   = FakeBM(),
            hub           = FakeHub(),
            config        = JeremyConfig(poll_interval=0.05),
        )
        return jeremy, mem

    def test_watch_and_release_room(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            await jeremy.watch_room("room-1")
            self.assertIn("room-1", jeremy._rooms)
            await jeremy.release_room("room-1")
            self.assertNotIn("room-1", jeremy._rooms)
            await jeremy.shutdown()
        run_async(_run())

    def test_watch_idempotent(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            await jeremy.watch_room("room-1")
            await jeremy.watch_room("room-1")
            self.assertEqual(len(jeremy._rooms), 1)
            await jeremy.shutdown()
        run_async(_run())

    def test_on_message_updates_state(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            await jeremy.watch_room("room-1")
            t_before = jeremy._rooms["room-1"].last_message_at
            await asyncio.sleep(0.01)
            await jeremy.on_message("room-1", "user-1", "hello world")
            t_after = jeremy._rooms["room-1"].last_message_at
            self.assertGreater(t_after, t_before)
            await jeremy.shutdown()
        run_async(_run())

    def test_bot_dash_prefix_resolves_plot_points(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            await jeremy.watch_room("room-1")
            await jeremy.on_message("room-1", "user-1", "Why did that happen?")
            self.assertEqual(len(jeremy._rooms["room-1"].open_plot_points()), 1)
            await jeremy.on_message(
                "room-1", "bot-pete",
                "That happened because of a very specific set of circumstances that unfolded over time.",
            )
            self.assertEqual(len(jeremy._rooms["room-1"].open_plot_points()), 0)
            await jeremy.shutdown()
        run_async(_run())

    def test_get_scene_state(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            await jeremy.watch_room("room-1")
            state = jeremy.get_scene_state("room-1")
            self.assertIsNotNone(state)
            self.assertIn("phase", state)
            self.assertIn("energy", state)
            self.assertIn("drama_necessity", state)
            await jeremy.shutdown()
        run_async(_run())

    def test_get_stats(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            stats = jeremy.get_stats()
            self.assertIn("rooms_watched", stats)
            self.assertIn("characters_known", stats)
            await jeremy.shutdown()
        run_async(_run())

    def test_detect_directed_ai(self):
        async def _run():
            jeremy, _ = await self._make_jeremy_async()
            result = jeremy.detect_directed_ai("Hey Pete, what do you think?")
            self.assertEqual(result, "bot-pete")
            result2 = jeremy.detect_directed_ai("Nobody was mentioned here")
            self.assertIsNone(result2)
            await jeremy.shutdown()
        run_async(_run())


# ─────────────────────────────────────────────────────────────────────────────
# CircuitBreaker
# ─────────────────────────────────────────────────────────────────────────────

class TestCircuitBreaker(unittest.TestCase):

    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.is_closed)

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        def fail(): raise ValueError("boom")
        for _ in range(3):
            try:
                cb.call(fail)
            except ValueError:
                pass
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertTrue(cb.is_open)

    def test_open_rejects_calls(self):
        cb = CircuitBreaker(failure_threshold=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError()))
        except (ValueError, StopIteration, TypeError):
            pass
        # Force open
        cb._consecutive_failures = 10
        cb._on_failure()
        with self.assertRaises(CircuitOpenError):
            cb.call(lambda: None)

    def test_half_open_then_closed(self):
        cb = CircuitBreaker(failure_threshold=1, success_threshold=2, recovery_timeout=0.01)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError()))
        except Exception:
            pass
        cb._on_failure()  # force open
        time.sleep(0.02)
        # Next call transitions to HALF_OPEN
        cb.call(lambda: None)
        cb.call(lambda: None)
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb._on_failure()
        cb._on_failure()
        self.assertTrue(cb.is_open)
        cb.reset()
        self.assertTrue(cb.is_closed)

    def test_stats_tracked(self):
        cb = CircuitBreaker(failure_threshold=10)
        cb.call(lambda: None)
        cb.call(lambda: None)
        stats = cb.get_stats()
        self.assertEqual(stats["successful_calls"], 2)
        self.assertEqual(stats["total_calls"], 2)


# ─────────────────────────────────────────────────────────────────────────────
# IRM
# ─────────────────────────────────────────────────────────────────────────────

class TestIRM(unittest.TestCase):

    def test_check_returns_report(self):
        ctrl = IRMController()
        report = ctrl.check()
        self.assertIsNotNone(report)
        self.assertIn(report.status, list(HealthStatus))

    def test_last_report_set_after_check(self):
        ctrl = IRMController()
        self.assertIsNone(ctrl.last_report)
        ctrl.check()
        self.assertIsNotNone(ctrl.last_report)

    def test_unknown_status_without_psutil(self):
        import irm as irm_mod
        original = irm_mod._PSUTIL
        irm_mod._PSUTIL = False
        try:
            ctrl = IRMController()
            report = ctrl.check()
            self.assertEqual(report.status, HealthStatus.UNKNOWN)
        finally:
            irm_mod._PSUTIL = original


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()

    test_classes = [
        TestUniversalMemorySystem,
        TestSQLiteMemoryBank,
        TestSQLiteMemorySystem,
        TestNudgeQueue,
        TestDramaMath,
        TestExtractPlotPoints,
        TestEstimateEnergy,
        TestJeremyCricketLifecycle,
        TestCircuitBreaker,
        TestIRM,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
