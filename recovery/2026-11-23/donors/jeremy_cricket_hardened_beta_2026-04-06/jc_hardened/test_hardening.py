"""
test_hardening.py — Jeremy Cricket Adaptive Awareness Suite
Phase 2: Stress tests, logic validation, error handling verification.
Run with: pytest test_hardening.py -v
"""

import asyncio
import os
import time
from pathlib import Path

import pytest
import yaml

# ─── Fixtures ─────────────────────────────────────────────────────────────────

CONFIG_PATH = "config.yaml"

@pytest.fixture
def config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path

@pytest.fixture
def engine():
    from character_engine import CharacterEngine
    return CharacterEngine(CONFIG_PATH)

@pytest.fixture
async def memory(tmp_dir):
    from memory_processor import MemoryProcessor
    mp = MemoryProcessor("test_char", tmp_dir, CONFIG_PATH)
    await mp.init()
    yield mp
    await mp.close()

@pytest.fixture
async def governor(tmp_dir):
    from safety_governor import SafetyGovernor
    gov = SafetyGovernor(tmp_dir / "project", CONFIG_PATH)
    yield gov

@pytest.fixture
async def vault(tmp_dir):
    from sanctuary_vault import SanctuaryVault
    os.environ["SANCTUARY_KEY"] = ""  # Force ephemeral key
    sv = SanctuaryVault(tmp_dir, CONFIG_PATH)
    await sv.init()
    yield sv
    await sv.close()

# ─── Character Engine Tests ───────────────────────────────────────────────────

class TestCharacterEngine:

    def test_default_mode_is_ambient(self, engine):
        from character_engine import Mode
        assert engine.current_mode == Mode.AMBIENT

    @pytest.mark.asyncio
    async def test_high_signals_escalate_to_mandate(self, engine):
        from character_engine import Mode, VarianceSignal
        # Send 3 consecutive high signals (mandate threshold)
        for _ in range(3):
            await engine.ingest_signal(VarianceSignal(
                timestamp=time.time(),
                complexity_score=0.95,
                emotional_velocity=0.90,
            ))
        assert engine.current_mode == Mode.TOTAL_CARE_MANDATE

    @pytest.mark.asyncio
    async def test_handshake_cannot_be_instant_bypassed(self, engine):
        from character_engine import Mode, VarianceSignal
        # Escalate to mandate
        for _ in range(3):
            await engine.ingest_signal(VarianceSignal(
                timestamp=time.time(), complexity_score=0.95, emotional_velocity=0.90
            ))
        assert engine.current_mode == Mode.TOTAL_CARE_MANDATE

        # Try to do all 3 handshakes at once (rapid fire) — window is 60s so they
        # will all count, but we verify the state only steps DOWN one level at a time
        result = await engine.submit_stability_handshake()
        assert result == False  # Need 3 total

        result2 = await engine.submit_stability_handshake()
        assert result2 == False  # Need 3 total

        result3 = await engine.submit_stability_handshake()
        assert result3 == True  # 3rd confirms
        # Mode should have stepped down one level, not jumped to AMBIENT
        assert engine.current_mode != Mode.AMBIENT  # Still elevated

    @pytest.mark.asyncio
    async def test_tone_apply_reframes_in_care_mode(self, engine):
        from character_engine import Mode, VarianceSignal
        for _ in range(3):
            await engine.ingest_signal(VarianceSignal(
                timestamp=time.time(), complexity_score=0.95, emotional_velocity=0.90
            ))
        result = engine.apply_tone("There was a critical error in the database failure")
        assert "critical error" not in result
        assert "database failure" not in result

    def test_tone_ambient_no_reframe(self, engine):
        result = engine.apply_tone("There was a critical error")
        assert "critical error" in result  # No reframe in AMBIENT

    @pytest.mark.asyncio
    async def test_low_signals_step_down(self, engine):
        from character_engine import Mode, VarianceSignal
        # Escalate
        for _ in range(2):
            await engine.ingest_signal(VarianceSignal(
                timestamp=time.time(), complexity_score=0.70, emotional_velocity=0.60
            ))
        assert engine.current_mode != Mode.AMBIENT

        # Send 5 low signals to cool down
        for _ in range(5):
            await engine.ingest_signal(VarianceSignal(
                timestamp=time.time(), complexity_score=0.10, emotional_velocity=0.05
            ))
        # Should have stepped down
        assert engine.current_mode.value in ["AMBIENT", "ATTENTIVE"]

    def test_mode_change_hook_fires(self, engine):
        from character_engine import Mode, VarianceSignal
        fired = []
        engine.register_mode_change_hook(lambda old, new: fired.append((old, new)))

        async def run():
            for _ in range(3):
                await engine.ingest_signal(VarianceSignal(
                    timestamp=time.time(), complexity_score=0.95, emotional_velocity=0.90
                ))
        asyncio.get_event_loop().run_until_complete(run())
        assert len(fired) > 0

# ─── Memory Processor Tests ───────────────────────────────────────────────────

class TestMemoryProcessor:

    @pytest.mark.asyncio
    async def test_remember_and_recall(self, memory):
        from memory_processor import Chapter, StoryMemory
        m = StoryMemory(
            id=None, character_id="test_char", chapter=Chapter.SUPPORT,
            headline="First breakthrough", narrative="We solved the hard problem together.",
            lesson="Patience unlocks everything.", importance=8,
            emotional_tag="breakthrough", created_at=time.time(), accessed_at=time.time()
        )
        await memory.remember(m)
        # Force flush
        async with memory._lock:
            await memory._flush_buffer()

        results = await memory.recall("breakthrough", mode="AMBIENT")
        assert len(results) >= 1
        assert results[0].headline == "First breakthrough"

    @pytest.mark.asyncio
    async def test_chapter_gating_in_care_mode(self, memory):
        from memory_processor import Chapter, StoryMemory
        # Store a COMPLEX_LOGISTICS memory
        m = StoryMemory(
            id=None, character_id="test_char", chapter=Chapter.COMPLEX_LOGISTICS,
            headline="Server migration plan", narrative="Complex deployment steps.",
            lesson="Do it in order.", importance=9, emotional_tag="technical",
            created_at=time.time(), accessed_at=time.time()
        )
        await memory.remember(m)
        async with memory._lock:
            await memory._flush_buffer()

        # Should NOT appear in CARE mode
        results = await memory.recall("migration", mode="CARE")
        titles = [r.headline for r in results]
        assert "Server migration plan" not in titles

        # SHOULD appear in AMBIENT mode
        results = await memory.recall("migration", mode="AMBIENT")
        titles = [r.headline for r in results]
        assert "Server migration plan" in titles

    @pytest.mark.asyncio
    async def test_eviction_keeps_db_bounded(self, memory):
        from memory_processor import Chapter, StoryMemory
        # Lower the limit for testing speed
        memory._max_memories = 20
        memory._eviction_target = 15
        memory._batch_size = 5

        for i in range(30):
            m = StoryMemory(
                id=None, character_id="test_char", chapter=Chapter.GROWTH,
                headline=f"Memory {i}", narrative=f"Story {i}",
                lesson="", importance=(i % 10) + 1, emotional_tag="test",
                created_at=time.time(), accessed_at=time.time()
            )
            await memory.remember(m)

        count = await memory.count()
        assert count <= 20, f"Eviction failed: {count} memories in DB"

    @pytest.mark.asyncio
    async def test_recall_returns_empty_on_timeout(self, memory):
        memory._recall_timeout = 0.000001  # Impossibly short
        results = await memory.recall("anything")
        assert results == []

# ─── Safety Governor Tests ────────────────────────────────────────────────────

class TestSafetyGovernor:

    @pytest.mark.asyncio
    async def test_engage_lock_blocks_writes(self, governor, tmp_dir):
        project_dir = tmp_dir / "project"
        project_dir.mkdir()
        test_file = project_dir / "main.py"
        test_file.write_text("# code")

        await governor.engage_lock()
        assert governor.is_locked
        assert not governor.can_write(test_file)

    @pytest.mark.asyncio
    async def test_handshake_bypass_prevention(self, governor):
        from safety_governor import LockState
        await governor.engage_lock()

        # One and two — should not unlock
        r1 = await governor.submit_handshake()
        r2 = await governor.submit_handshake()
        assert r1 == False
        assert r2 == False
        assert governor.lock_state != LockState.UNLOCKED

    @pytest.mark.asyncio
    async def test_three_handshakes_unlock(self, governor):
        from safety_governor import LockState
        await governor.engage_lock()
        await governor.submit_handshake()
        await governor.submit_handshake()
        r = await governor.submit_handshake()
        assert r == True
        assert governor.lock_state == LockState.UNLOCKED

    @pytest.mark.asyncio
    async def test_mode_change_hook_triggers_lock(self, governor):
        await governor.on_mode_change("CARE", "TOTAL_CARE_MANDATE")
        assert governor.is_locked

    @pytest.mark.asyncio
    async def test_non_sensitive_files_writeable_during_lock(self, governor, tmp_dir):
        await governor.engage_lock()
        txt_file = tmp_dir / "notes.txt"
        assert governor.can_write(txt_file)  # .txt not in locked extensions

# ─── Sanctuary Vault Tests ────────────────────────────────────────────────────

class TestSanctuaryVault:

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, vault):
        entry_id = await vault.store(
            "private_moment_01",
            {"note": "User shared something vulnerable.", "context": "grief"},
            emotional_context="vulnerable"
        )
        assert entry_id is not None

        entry = await vault.retrieve("private_moment_01")
        assert entry is not None
        assert entry.payload["note"] == "User shared something vulnerable."

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_returns_none(self, vault):
        result = await vault.retrieve("does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_works(self, vault):
        await vault.store("to_delete", {"data": "sensitive"})
        count = await vault.delete("to_delete")
        assert count >= 1
        result = await vault.retrieve("to_delete")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_labels_never_exposes_payload(self, vault):
        await vault.store("label_a", {"secret": "very private"})
        await vault.store("label_b", {"secret": "also private"})
        labels = await vault.list_labels()
        assert "label_a" in labels
        assert "label_b" in labels
        # Verify labels are strings, not dicts
        for l in labels:
            assert isinstance(l, str)

    @pytest.mark.asyncio
    async def test_audit_log_has_no_payload(self, vault):
        await vault.store("audited_entry", {"private": "content"})
        await vault.retrieve("audited_entry")
        log = await vault.get_audit_log()
        # Verify no payload content in audit
        for entry in log:
            assert "private" not in str(entry.get("event", ""))
            assert "content" not in str(entry)

    @pytest.mark.asyncio
    async def test_vault_isolated_from_memory_imports(self):
        """Verify sanctuary_vault.py does not import memory_processor or character_engine."""
        import ast, inspect
        import sanctuary_vault
        src = inspect.getsource(sanctuary_vault)
        tree = ast.parse(src)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        assert "memory_processor" not in imports, "Vault imports memory_processor — isolation broken"
        assert "character_engine" not in imports, "Vault imports character_engine — isolation broken"
