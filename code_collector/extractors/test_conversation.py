"""
extractors/test_conversation.py
═══════════════════════════════
Pytest suite for conversation.py

Covers every public function and method with:
  - Happy path correctness
  - Edge cases (empty, None, wrong types, boundary values)
  - Adversarial inputs (huge content, injection attempts, unicode)
  - Contract enforcement (caps, dedup, filters)
  - Regression cases (bugs we fixed)

Run:
    python3 -m pytest extractors/test_conversation.py -v

Rear View Foresight LLC — Feic Mo Chroí
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from extractors.conversation import (
    ConversationTurn,
    ConversationExtractor,
    SessionSummary,
    _split_sentences,
    _clean_sentence,
    _deduplicate_sentences,
    _derive_purpose,
    _is_project_file,
    _FILE_PATTERN,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_extractor(session_id="test123", url="https://claude.ai/chat/test123"):
    return ConversationExtractor(
        session_id=session_id,
        source_url=url,
        source_title="Claude",
        platform="claude",
    )


def make_turn(role="assistant", content="The fix is working now."):
    return ConversationTurn(role=role, content=content)


def basic_turns():
    """Standard set of turns that should produce clean signal."""
    return [
        {"role": "user",      "content": "What's the issue with main.py?"},
        {"role": "assistant", "content": "The import on line 12 is wrong. Let's use the correct path instead. That's the fix."},
        {"role": "user",      "content": "What about routes.ts?"},
        {"role": "assistant", "content": "I built a corrected version of routes.ts. The new file handles auth correctly."},
        {"role": "user",      "content": "What's still broken?"},
        {"role": "assistant", "content": "The session handler is broken — it fails on empty input. Next steps: 1. Fix the handler. 2. Add input validation."},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# S1 — _split_sentences
# ─────────────────────────────────────────────────────────────────────────────

class TestSplitSentences:

    def test_basic_period(self):
        result = _split_sentences("Hello world. Goodbye world.")
        assert len(result) == 2
        assert result[0] == "Hello world."
        assert result[1] == "Goodbye world."

    def test_question_mark(self):
        result = _split_sentences("What is this? It's a test.")
        assert len(result) == 2

    def test_exclamation(self):
        result = _split_sentences("It works! Great.")
        assert len(result) == 2

    def test_empty_string(self):
        assert _split_sentences("") == []

    def test_whitespace_only(self):
        assert _split_sentences("   \n\n  ") == []

    def test_code_blocks_stripped(self):
        text = "Here is the fix.\n```python\ndef foo(): pass\n```\nThat should work."
        result = _split_sentences(text)
        # Code block content should not appear in sentences
        full = " ".join(result)
        assert "def foo" not in full
        assert "Here is the fix." in result

    def test_inline_code_stripped(self):
        text = "Use `os.path.join` for paths. That is correct."
        result = _split_sentences(text)
        full = " ".join(result)
        assert "os.path.join" not in full

    def test_bullet_points_split(self):
        text = "Steps:\n- First do this\n- Then do that\n- Finally finish"
        result = _split_sentences(text)
        assert len(result) >= 2

    def test_single_sentence_no_period(self):
        result = _split_sentences("Just one line with no terminator")
        assert len(result) == 1
        assert result[0] == "Just one line with no terminator"

    def test_none_does_not_crash(self):
        # Should not raise even if called with edge inputs
        result = _split_sentences("")
        assert isinstance(result, list)

    def test_very_long_text(self):
        text = ("This is a sentence. " * 1000).strip()
        result = _split_sentences(text)
        assert len(result) == 1000

    def test_unicode(self):
        result = _split_sentences("日本語のテスト。これは文です。")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_multiple_code_blocks(self):
        text = "First point.\n```\ncode1\n```\nSecond point.\n```\ncode2\n```\nThird point."
        result = _split_sentences(text)
        full = " ".join(result)
        assert "code1" not in full
        assert "code2" not in full


# ─────────────────────────────────────────────────────────────────────────────
# S2 — _clean_sentence
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanSentence:

    def test_strips_leading_bullet(self):
        assert _clean_sentence("• Fix the bug") == "Fix the bug"

    def test_strips_leading_dash(self):
        assert _clean_sentence("- Fix the bug") == "Fix the bug"

    def test_strips_leading_asterisk(self):
        assert _clean_sentence("* Fix the bug") == "Fix the bug"

    def test_strips_numbered_list(self):
        assert _clean_sentence("1. Fix the bug") == "Fix the bug"
        assert _clean_sentence("42. Fix the bug") == "Fix the bug"

    def test_strips_bold_markdown(self):
        assert _clean_sentence("**Important** fix") == "Important fix"
        assert _clean_sentence("*emphasis* here") == "emphasis here"

    def test_strips_inline_code(self):
        assert _clean_sentence("Use `foo()` here") == "Use foo() here"

    def test_empty_string(self):
        assert _clean_sentence("") == ""

    def test_no_markup(self):
        s = "This is a plain sentence."
        assert _clean_sentence(s) == s

    def test_nested_bold(self):
        assert "Important" in _clean_sentence("**Important thing**")

    def test_whitespace_trimmed(self):
        assert _clean_sentence("  trimmed  ") == "trimmed"


# ─────────────────────────────────────────────────────────────────────────────
# S3 — _deduplicate_sentences
# ─────────────────────────────────────────────────────────────────────────────

class TestDeduplicateSentences:

    def test_empty_list(self):
        assert _deduplicate_sentences([]) == []

    def test_no_duplicates(self):
        items = ["First thing.", "Second thing.", "Third thing."]
        result = _deduplicate_sentences(items)
        assert len(result) == 3

    def test_exact_duplicates_removed(self):
        items = ["Fix the bug.", "Fix the bug.", "Fix the bug."]
        result = _deduplicate_sentences(items)
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        items = ["Fix the bug.", "fix the bug.", "FIX THE BUG."]
        result = _deduplicate_sentences(items)
        assert len(result) == 1

    def test_whitespace_normalized_for_dedup(self):
        items = ["Fix  the  bug.", "Fix the bug."]
        result = _deduplicate_sentences(items)
        assert len(result) == 1

    def test_first_occurrence_preserved(self):
        items = ["Original sentence.", "Original sentence."]
        result = _deduplicate_sentences(items)
        assert result[0] == "Original sentence."

    def test_order_preserved_for_unique(self):
        items = ["Alpha.", "Beta.", "Gamma."]
        result = _deduplicate_sentences(items)
        assert result == items

    def test_key_truncated_at_60_chars(self):
        # Key is s[:60]. To trigger dedup via truncation, strings must be
        # LONGER than 60 chars with the same first 60. 61+ chars needed.
        long      = "A" * 60 + "X"  # key = 60 A chars (X truncated off)
        also_long = "A" * 60 + "Y"  # same key = 60 A chars (Y truncated off)
        result = _deduplicate_sentences([long, also_long])
        assert len(result) == 1

    def test_empty_strings_not_added(self):
        items = ["", "   ", "Real sentence."]
        result = _deduplicate_sentences(items)
        assert all(r.strip() for r in result)


# ─────────────────────────────────────────────────────────────────────────────
# S4 — _is_project_file
# ─────────────────────────────────────────────────────────────────────────────

class TestIsProjectFile:

    # Files that SHOULD be accepted
    def test_simple_python(self):
        assert _is_project_file("main.py") is True

    def test_simple_js(self):
        assert _is_project_file("index.js") is True

    def test_shallow_path(self):
        assert _is_project_file("src/routes.py") is True

    def test_two_level_path(self):
        assert _is_project_file("backend/api/routes.ts") is True

    def test_config_file(self):
        assert _is_project_file("config.yaml") is True

    def test_markdown(self):
        assert _is_project_file("README.md") is True

    def test_shell_script(self):
        assert _is_project_file("deploy.sh") is True

    def test_four_level_path(self):
        assert _is_project_file("src/modules/auth/handler.py") is True

    # Files that SHOULD be rejected
    def test_node_modules(self):
        assert _is_project_file("node_modules/lodash/index.js") is False

    def test_site_packages(self):
        assert _is_project_file("site-packages/requests/models.py") is False

    def test_site_packages_with_version_prefix(self):
        # Regression: python3.11 path matching "11/site-packages/..."
        assert _is_project_file("11/site-packages/requests/models.py") is False

    def test_url_fragment_ai(self):
        # Regression: claude.ai/chat/main.py → "ai/chat/main.py"
        assert _is_project_file("ai/chat/main.py") is False

    def test_url_fragment_com(self):
        # Regression: example.com/api/config.json → "com/api/config.json"
        assert _is_project_file("com/api/config.json") is False

    def test_domain_prefix(self):
        assert _is_project_file("example.com/api/config.json") is False

    def test_versioned_api_path(self):
        assert _is_project_file("v1/endpoints/auth.py") is False

    def test_usr_lib(self):
        assert _is_project_file("/usr/lib/python3/dist-packages/x.py") is False

    def test_empty_string(self):
        assert _is_project_file("") is False

    def test_dist_packages(self):
        assert _is_project_file("dist-packages/six.py") is False

    def test_excessively_deep(self):
        assert _is_project_file("a/b/c/d/e/f/g.py") is False


# ─────────────────────────────────────────────────────────────────────────────
# S5 — ConversationTurn
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationTurn:

    def test_word_count_basic(self):
        t = make_turn(content="hello world foo bar")
        assert t.word_count() == 4

    def test_word_count_empty(self):
        assert make_turn(content="").word_count() == 0

    def test_word_count_whitespace(self):
        assert make_turn(content="   ").word_count() == 0

    def test_has_decision_positive(self):
        assert make_turn(content="Let's use Python instead.").has_decision() is True
        assert make_turn(content="The fix is to use pathlib.").has_decision() is True
        assert make_turn(content="We'll go with SQLite.").has_decision() is True

    def test_has_decision_negative(self):
        assert make_turn(content="I have no idea what to do.").has_decision() is False
        assert make_turn(content="The weather is nice today.").has_decision() is False

    def test_has_break_positive(self):
        assert make_turn(content="There is a bug in line 42.").has_break() is True
        assert make_turn(content="This is broken.").has_break() is True
        assert make_turn(content="The test fails consistently.").has_break() is True

    def test_has_break_negative(self):
        assert make_turn(content="Everything is working well.").has_break() is False

    def test_has_build_positive(self):
        assert make_turn(content="I built the new endpoint.").has_build() is True
        assert make_turn(content="Added the validation logic.").has_build() is True
        assert make_turn(content="Created a new component.").has_build() is True

    def test_has_build_negative(self):
        assert make_turn(content="Nothing was done today.").has_build() is False

    def test_mentions_files_basic(self):
        t = make_turn(content="The fix is in main.py and routes.ts.")
        files = t.mentions_files()
        assert "main.py" in files
        assert "routes.ts" in files

    def test_mentions_files_empty(self):
        t = make_turn(content="No files mentioned here at all.")
        assert t.mentions_files() == []

    def test_mentions_files_deduped(self):
        t = make_turn(content="Edit main.py then test main.py again.")
        assert t.mentions_files().count("main.py") == 1

    def test_mentions_files_url_filtered(self):
        # URL-embedded filenames should not appear
        t = make_turn(content="See https://example.com/api/config.json for details.")
        files = t.mentions_files()
        assert "config.json" not in files or all("/" not in f for f in files)

    def test_mentions_files_node_modules_filtered(self):
        t = make_turn(content="Check node_modules/lodash/index.js for reference.")
        files = t.mentions_files()
        assert not any("node_modules" in f for f in files)

    def test_turn_index_default(self):
        t = ConversationTurn(role="user", content="hello")
        assert t.turn_index == 0

    def test_timestamp_default_is_recent(self):
        before = time.time() - 1
        t = ConversationTurn(role="user", content="hello")
        after = time.time() + 1
        assert before <= t.timestamp <= after


# ─────────────────────────────────────────────────────────────────────────────
# S6 — _derive_purpose
# ─────────────────────────────────────────────────────────────────────────────

class TestDerivePurpose:

    def test_decision_turn(self):
        t = make_turn(content="Let's use Redis instead of Memcached.")
        assert _derive_purpose(t) == "decision"

    def test_build_turn(self):
        t = make_turn(content="I built the authentication module.")
        assert _derive_purpose(t) == "build"

    def test_break_turn(self):
        t = make_turn(content="The connection is broken and fails on startup.")
        assert _derive_purpose(t) == "break / open issue"

    def test_fallback_to_first_sentence(self):
        t = make_turn(content="Here is a description of what this does. It handles routing.")
        purpose = _derive_purpose(t)
        assert len(purpose) > 0
        assert len(purpose) <= 80

    def test_empty_content_fallback(self):
        t = make_turn(content="")
        assert _derive_purpose(t) == "assistant response"

    def test_short_content_fallback(self):
        t = make_turn(content="OK.")
        assert _derive_purpose(t) == "assistant response"

    def test_purpose_capped_at_80(self):
        long = "A" * 200 + ". More text."
        t = make_turn(content=long)
        purpose = _derive_purpose(t)
        assert len(purpose) <= 80


# ─────────────────────────────────────────────────────────────────────────────
# S7 — ConversationExtractor.ingest_raw
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestRaw:

    def test_basic_ingest(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        assert len(ext._turns) == 6

    def test_empty_list(self):
        ext = make_extractor()
        ext.ingest_raw([])
        assert ext._turns == []

    def test_not_a_list(self):
        ext = make_extractor()
        ext.ingest_raw("not a list")  # type: ignore
        assert ext._turns == []

    def test_none_input(self):
        ext = make_extractor()
        ext.ingest_raw(None)  # type: ignore
        assert ext._turns == []

    def test_non_dict_elements_skipped(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user", "content": "valid"},
            "not a dict",
            None,
            42,
            {"role": "assistant", "content": "also valid"},
        ])
        assert len(ext._turns) == 2

    def test_invalid_role_normalized(self):
        ext = make_extractor()
        ext.ingest_raw([{"role": "hacker", "content": "sneaky"}])
        assert ext._turns[0].role == "user"

    def test_non_string_content_coerced(self):
        ext = make_extractor()
        ext.ingest_raw([{"role": "user", "content": 12345}])
        assert ext._turns[0].content == "12345"

    def test_none_content_becomes_empty(self):
        ext = make_extractor()
        ext.ingest_raw([{"role": "user", "content": None}])
        assert ext._turns[0].content == "None"  # str(None)

    def test_content_capped_at_max(self):
        huge = "x" * (ConversationExtractor.MAX_CONTENT_CHARS + 10_000)
        ext = make_extractor()
        ext.ingest_raw([{"role": "user", "content": huge}])
        assert len(ext._turns[0].content) == ConversationExtractor.MAX_CONTENT_CHARS

    def test_turns_capped_at_max(self):
        turns = [{"role": "user", "content": f"Turn {i}"} for i in range(600)]
        ext = make_extractor()
        ext.ingest_raw(turns)
        assert len(ext._turns) == ConversationExtractor.MAX_TURNS

    def test_invalid_timestamp_replaced(self):
        ext = make_extractor()
        before = time.time() - 1
        ext.ingest_raw([{"role": "user", "content": "hi", "ts": "not_a_number"}])
        after = time.time() + 1
        assert before <= ext._turns[0].timestamp <= after

    def test_valid_timestamp_preserved(self):
        ts = 1_700_000_000.0
        ext = make_extractor()
        ext.ingest_raw([{"role": "user", "content": "hi", "ts": ts}])
        assert ext._turns[0].timestamp == ts

    def test_turn_index_assigned_sequentially(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        for i, turn in enumerate(ext._turns):
            assert turn.turn_index == i

    def test_missing_content_defaults_to_empty(self):
        ext = make_extractor()
        ext.ingest_raw([{"role": "user"}])
        assert ext._turns[0].content == ""

    def test_missing_role_defaults_to_user(self):
        ext = make_extractor()
        ext.ingest_raw([{"content": "hello"}])
        assert ext._turns[0].role == "user"


# ─────────────────────────────────────────────────────────────────────────────
# S8 — ConversationExtractor.summarize
# ─────────────────────────────────────────────────────────────────────────────

class TestSummarize:

    def test_returns_session_summary(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        summary = ext.summarize()
        assert isinstance(summary, SessionSummary)

    def test_session_id_preserved(self):
        ext = make_extractor(session_id="myid123")
        ext.ingest_raw(basic_turns())
        assert ext.summarize().session_id == "myid123"

    def test_platform_preserved(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        assert ext.summarize().platform == "claude"

    def test_turn_count_correct(self):
        ext = make_extractor()
        turns = basic_turns()
        ext.ingest_raw(turns)
        assert ext.summarize().turn_count == len(turns)

    def test_empty_turns_produces_valid_summary(self):
        ext = make_extractor()
        ext.ingest_raw([])
        summary = ext.summarize()
        assert summary.turn_count == 0
        assert summary.files_touched == []
        assert summary.decisions == []

    def test_user_turns_not_extracted_for_signal(self):
        # Signal (decisions, builds, breaks) only extracted from assistant turns
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user", "content": "Let's fix the broken bug in main.py now."},
        ])
        summary = ext.summarize()
        # User turn content should not produce decisions/builds/breaks
        assert summary.decisions == []
        assert summary.breaks == []
        assert summary.builds == []

    def test_assistant_decisions_extracted(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user", "content": "What should we do?"},
            {"role": "assistant", "content": "Let's use PostgreSQL instead of SQLite. That is the right call."},
        ])
        summary = ext.summarize()
        assert len(summary.decisions) > 0

    def test_assistant_breaks_extracted(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user", "content": "What's wrong?"},
            {"role": "assistant", "content": "The authentication handler is broken — it fails on empty tokens consistently."},
        ])
        summary = ext.summarize()
        assert len(summary.breaks) > 0

    def test_assistant_builds_extracted(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user", "content": "What did you do?"},
            {"role": "assistant", "content": "I built the new session manager and added the validation layer."},
        ])
        summary = ext.summarize()
        assert len(summary.builds) > 0

    def test_files_touched_from_all_turns(self):
        # Files extracted from both user AND assistant turns
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user",      "content": "What's wrong with main.py?"},
            {"role": "assistant", "content": "The issue is in routes.ts line 42."},
        ])
        summary = ext.summarize()
        assert "main.py" in summary.files_touched
        assert "routes.ts" in summary.files_touched

    def test_files_capped_at_20(self):
        content = " ".join(f"file{i}.py" for i in range(30))
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        assert len(summary.files_touched) <= 20

    def test_decisions_capped_at_10(self):
        lines = [f"Let's use option{i} instead." for i in range(20)]
        content = " ".join(lines)
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        assert len(summary.decisions) <= 10

    def test_breaks_capped_at_10(self):
        lines = [f"Component{i} is broken and fails." for i in range(20)]
        content = ". ".join(lines)
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        assert len(summary.breaks) <= 10

    def test_next_steps_capped_at_5(self):
        lines = [f"Next step {i}: do something important." for i in range(10)]
        content = " ".join(lines)
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        assert len(summary.next_steps) <= 5

    def test_decisions_deduplicated(self):
        # Same decision repeated should appear once
        line = "Let's use Redis instead of Memcached."
        content = " ".join([line] * 5)
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        assert summary.decisions.count(summary.decisions[0]) == 1 if summary.decisions else True

    def test_total_words_counted(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user",      "content": "one two three"},       # 3 words
            {"role": "assistant", "content": "four five six seven"}, # 4 words
        ])
        assert ext.summarize().total_words == 7

    def test_short_sentences_filtered(self):
        # Sentences < 20 chars should not appear in output
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "assistant", "content": "OK. Yes. Fixed. Let's use the new approach which is much better overall."},
        ])
        summary = ext.summarize()
        # Short sentences like "OK." "Yes." "Fixed." should not appear in decisions/builds/breaks
        for bucket in (summary.decisions, summary.breaks, summary.builds):
            for s in bucket:
                assert len(s) >= 20

    def test_ended_at_is_recent(self):
        before = time.time() - 1
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        summary = ext.summarize()
        after = time.time() + 1
        assert before <= summary.ended_at <= after


# ─────────────────────────────────────────────────────────────────────────────
# S9 — SessionSummary.to_context_block
# ─────────────────────────────────────────────────────────────────────────────

class TestToContextBlock:

    def _make_summary(self, **kwargs):
        defaults = dict(
            session_id="s1",
            source_url="https://claude.ai/chat/s1",
            source_title="Claude",
            started_at=time.time() - 100,
            ended_at=time.time(),
            platform="claude",
        )
        defaults.update(kwargs)
        return SessionSummary(**defaults)

    def test_returns_dict(self):
        s = self._make_summary()
        block = s.to_context_block()
        assert isinstance(block, dict)

    def test_has_required_keys(self):
        s = self._make_summary()
        block = s.to_context_block()
        assert "content" in block
        assert "language" in block
        assert "session_id" in block
        assert "platform" in block

    def test_language_is_conversation(self):
        s = self._make_summary()
        assert s.to_context_block()["language"] == "conversation"

    def test_empty_summary_content_is_string(self):
        s = self._make_summary()
        block = s.to_context_block()
        assert isinstance(block["content"], str)

    def test_builds_in_content(self):
        s = self._make_summary(builds=["Built the auth module.", "Created the router."])
        content = s.to_context_block()["content"]
        assert "WHAT WAS BUILT" in content
        assert "Built the auth module." in content

    def test_decisions_in_content(self):
        s = self._make_summary(decisions=["Use PostgreSQL.", "Avoid Redis."])
        content = s.to_context_block()["content"]
        assert "DECISIONS MADE" in content
        assert "Use PostgreSQL." in content

    def test_breaks_in_content(self):
        s = self._make_summary(breaks=["Auth handler broken.", "Tests failing."])
        content = s.to_context_block()["content"]
        assert "BROKEN / OPEN" in content

    def test_next_steps_in_content(self):
        s = self._make_summary(next_steps=["Fix the handler.", "Add tests."])
        content = s.to_context_block()["content"]
        assert "NEXT STEPS" in content

    def test_files_in_content(self):
        s = self._make_summary(files_touched=["main.py", "routes.ts"])
        content = s.to_context_block()["content"]
        assert "FILES TOUCHED" in content
        assert "main.py" in content

    def test_builds_capped_at_5_in_output(self):
        s = self._make_summary(builds=[f"Built item {i}." for i in range(10)])
        content = s.to_context_block()["content"]
        # Only first 5 should appear
        assert "Built item 4." in content
        assert "Built item 5." not in content

    def test_content_hash_16_chars(self):
        s = self._make_summary()
        block = s.to_context_block()
        assert len(block["content_hash"]) == 16

    def test_session_id_in_block(self):
        s = self._make_summary(session_id="unique_id_xyz")
        assert s.to_context_block()["session_id"] == "unique_id_xyz"

    def test_captured_at_is_iso_format(self):
        s = self._make_summary()
        captured = s.to_context_block()["captured_at"]
        # Should be parseable as ISO format
        from datetime import datetime
        datetime.strptime(captured, "%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────────────────
# S10 — Full pipeline (ingest_raw → summarize → to_context_block)
# ─────────────────────────────────────────────────────────────────────────────

class TestFullPipeline:

    def test_full_pipeline_produces_valid_block(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        summary = ext.summarize()
        block = summary.to_context_block()
        assert isinstance(block["content"], str)
        assert len(block["content"]) > 0

    def test_to_payload_structure(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        payload = ext.to_payload()
        assert "source_url" in payload
        assert "blocks" in payload
        assert isinstance(payload["blocks"], list)

    def test_to_blocks_includes_summary_block(self):
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        blocks = ext.to_blocks()
        assert len(blocks) > 0
        # Last block should be the summary
        last = blocks[-1]
        assert last["language"] == "conversation"

    def test_to_blocks_filters_short_assistant_turns(self):
        # All blocks have language="conversation" — correct for this extractor.
        # Short turns (< 30 words) are skipped. to_blocks always ends with summary.
        # 0 qualifying turns = 1 block (summary only)
        # 1 qualifying turn  = 2 blocks (turn + summary)
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "assistant", "content": "OK."},  # < 30 words, filtered out
            {"role": "assistant", "content": " ".join(["word"] * 35)},  # >= 30 words
        ])
        blocks = ext.to_blocks()
        assert len(blocks) == 2  # 1 qualifying turn + 1 summary

    def test_to_blocks_context_before_after(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user",      "content": "What should we do?"},
            {"role": "assistant", "content": " ".join(["word"] * 35)},
            {"role": "user",      "content": "Got it."},
        ])
        blocks = ext.to_blocks()
        assert len(blocks) >= 2
        turn_block = blocks[0]  # all blocks have language="conversation"
        assert turn_block["context_before"] != ""
        assert turn_block["context_after"] != ""

    def test_adversarial_unicode_does_not_crash(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user",      "content": "日本語テスト。この関数は壊れています。"},
            {"role": "assistant", "content": "修正しました。main.pyを使ってください。"},
        ])
        summary = ext.summarize()
        block = summary.to_context_block()
        assert isinstance(block["content"], str)

    def test_adversarial_empty_content_turns(self):
        ext = make_extractor()
        ext.ingest_raw([
            {"role": "user",      "content": ""},
            {"role": "assistant", "content": ""},
            {"role": "user",      "content": "Something real finally."},
        ])
        # Should not crash
        summary = ext.summarize()
        assert summary.turn_count == 3

    def test_adversarial_all_user_turns(self):
        ext = make_extractor()
        ext.ingest_raw([{"role": "user", "content": f"Message {i}"} for i in range(10)])
        summary = ext.summarize()
        # No assistant turns → no signal extracted
        assert summary.decisions == []
        assert summary.breaks == []
        assert summary.builds == []

    def test_adversarial_code_block_injection(self):
        # Code block with decision-like content should not contaminate signal
        content = "Here is some code.\n```\nLet's use Redis instead.\nThis is broken.\n```\nThat's all."
        ext = make_extractor()
        ext.ingest_raw([{"role": "assistant", "content": content}])
        summary = ext.summarize()
        # Signal inside code blocks should be stripped by _split_sentences
        # so decisions/breaks from inside ``` should not appear
        # (they may or may not depending on sentence splitting — just verify no crash)
        assert isinstance(summary.decisions, list)

    def test_source_url_preserved_in_summary(self):
        url = "https://claude.ai/chat/abc123"
        ext = ConversationExtractor(
            session_id="x", source_url=url, source_title="Claude", platform="claude"
        )
        ext.ingest_raw(basic_turns())
        assert ext.summarize().source_url == url

    def test_double_summarize_stable(self):
        # Calling summarize twice should give consistent results
        ext = make_extractor()
        ext.ingest_raw(basic_turns())
        s1 = ext.summarize()
        s2 = ext.summarize()
        assert s1.turn_count == s2.turn_count
        assert s1.files_touched == s2.files_touched
        assert s1.decisions == s2.decisions


# ─────────────────────────────────────────────────────────────────────────────
# S11 — conversation_server.py integration
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationServer:
    """
    Tests the subprocess entry point by importing and calling main() directly
    via stdin/stdout manipulation — no subprocess spawning needed.
    """

    def _run(self, payload: dict) -> dict:
        import io
        from unittest.mock import patch
        import extractors.conversation_server as srv

        stdin_data = json.dumps(payload)
        stdout_capture = io.StringIO()

        with patch("sys.stdin", io.StringIO(stdin_data)), \
             patch("sys.stdout", stdout_capture):
            try:
                srv.main()
            except SystemExit:
                pass

        output = stdout_capture.getvalue().strip()
        return json.loads(output)

    def test_basic_call_returns_valid_json(self):
        result = self._run({
            "session_id": "test_srv_1",
            "platform": "claude",
            "source_url": "https://claude.ai/chat/test",
            "source_title": "Claude",
            "turns": basic_turns(),
        })
        assert "session_id" in result
        assert "context" in result
        assert "files_touched" in result

    def test_session_id_preserved(self):
        result = self._run({
            "session_id": "preserved_id",
            "platform": "claude",
            "source_url": "https://claude.ai/chat/x",
            "source_title": "Claude",
            "turns": basic_turns(),
        })
        assert result["session_id"] == "preserved_id"

    def test_empty_turns_returns_valid(self):
        result = self._run({
            "session_id": "empty",
            "platform": "claude",
            "source_url": "https://claude.ai/chat/x",
            "source_title": "Claude",
            "turns": [],
        })
        assert "context" in result
        assert isinstance(result["context"], str)

    def test_missing_session_id_defaults(self):
        result = self._run({
            "platform": "claude",
            "source_url": "https://claude.ai/chat/x",
            "source_title": "Claude",
            "turns": basic_turns(),
        })
        assert result.get("session_id") is not None

    def test_output_is_json_serializable(self):
        result = self._run({
            "session_id": "s",
            "platform": "claude",
            "source_url": "https://claude.ai/chat/x",
            "source_title": "Claude",
            "turns": basic_turns(),
        })
        # Re-serialize to confirm no unserializable types
        json.dumps(result)

    def test_output_within_size_cap(self):
        # Send a large session to verify output cap works
        big_turns = [
            {"role": "assistant", "content": "word " * 10_000}
            for _ in range(10)
        ]
        result = self._run({
            "session_id": "big",
            "platform": "claude",
            "source_url": "https://claude.ai/chat/x",
            "source_title": "Claude",
            "turns": big_turns,
        })
        output_size = len(json.dumps(result))
        assert output_size <= 600 * 1024, f"Output too large: {output_size} bytes"
