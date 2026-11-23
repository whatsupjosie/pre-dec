# editor_core

The "effective editor" layer for the PubCast collaborative writing engine.
Spelling, grammar/syntax, thesaurus, and rhyme dictionary — all offline,
all deterministic, zero model calls. Plot-hole/continuity checking is the
one pass that calls a model, and it's isolated to a single file so that
boundary stays clean.

Everything in this package is real, installed, and tested — 24/24 tests
pass against actual dictionary data, not mocked lookups. Run it yourself:

```bash
pip install -r requirements.txt --break-system-packages
python -m nltk.downloader wordnet   # one-time, ~10MB, then fully offline
pytest tests/ -v
```

## What's in here

| File | What it does | Model call? | Data source |
|---|---|---|---|
| `spelling.py` | Flags unknown words, ranked suggestions | No | `pyspellchecker` (bundled frequency dict) |
| `grammar.py` | Confusable homophones, doubled words, passive voice, long sentences, punctuation | No | Pure regex/rules, extensible list |
| `thesaurus.py` | Sense-grouped synonyms + antonyms | No | WordNet via `nltk` |
| `rhyme.py` | Perfect / slant / consonance / multi-syllable rhyme classification, stress/meter pattern | No | CMUdict (126k pronunciations) via `cmudict` |
| `plothole.py` | Continuity/contradiction checking against established facts | **Yes** | Any chat function matching `pub_partner_chat.chat_with_pub_partner`'s signature |
| `annotations.py` | Shared `Annotation` data model every pass returns | — | — |
| `engine.py` | Runs spelling+grammar together, optionally logs to `memory_engine` | No | — |
| `editor_router.py` | Routes an on-demand command ("what rhymes with X") to the right tool | No | Same keyword-scoring pattern as `switchblade_router.py` |

## Design decisions worth knowing

**Most of "editor" isn't AI.** Spelling, grammar-rule checks, thesaurus, and
rhyme lookups are solved lookup problems. Routing them through a 2B local
model would be slower, less accurate, and would burn your offline compute
budget on something a dictionary already does perfectly. Only continuity
checking — which requires actually reading and comparing meaning — goes
through a model call, and even then it's constrained to a structured
JSON response validated by Pydantic, not free text.

**The thesaurus is honest about what WordNet gives you.** Earlier
conversation described tone-tagged synonyms ("gritty / poetic / clinical /
archaic"). WordNet doesn't carry that tagging. What it gives instead —
synonyms grouped by *sense* (so "happy" meaning "fortunate" doesn't get
mixed with "happy" meaning "glad") — is implemented and tested. Tone
tagging would need either a hand-curated dataset or a model call per
lookup; flagging that as a real design choice rather than building
something that silently returns wrong-register suggestions.

**Rhyme classification is the real four-way split**, not just "sounds
similar": perfect, slant/assonance, consonance, and multi-syllable
("blink") rhymes, computed from ARPAbet stress-marked phonemes — see
`test_rhyme_classifies_multi_syllable` (`gravity`/`depravity`) for a
concrete example.

## Known gap — not wired to a live model yet

`plothole.py` takes a `chat_caller` argument shaped like
`modules/pub_partner_chat.py:chat_with_pub_partner` and is fully tested
against a stub. It has **not** been run against the real function, because
`modules/pub_partner_chat.py` imports `.ai_providers` and `.ai_runtime`,
and neither of those files has been uploaded to this environment — so
that import chain can't be exercised here. The integration point is real
and tested at the boundary (see `test_continuity_check_flags_contradiction_with_stub_model`
in `tests/test_editor_core.py`); wiring it to the live model just means
passing the real `chat_with_pub_partner` in as `chat_caller` once those
two files are available. Flagging this now so it isn't assumed to be
verified end-to-end when it isn't.

## Not built yet

- Quote dictionary (needs a curated/licensed dataset — a model
  should not be trusted to invent or misattribute quotes)
- Craft-book-derived coaching (King/McKee/Truby/Lamott frameworks) — this
  is prompt-engineering + curated content work, not started
- Genre/trope taxonomies and format transformer (screenplay/stage/sitcom/etc.)
- Long-term style analytics (crutch words, vocabulary growth, passive-voice
  trend over time) — `engine.py` already logs rule-hit counts to
  `memory_engine` per pass, which is the raw data this would aggregate,
  but the aggregation/reporting layer itself doesn't exist yet
