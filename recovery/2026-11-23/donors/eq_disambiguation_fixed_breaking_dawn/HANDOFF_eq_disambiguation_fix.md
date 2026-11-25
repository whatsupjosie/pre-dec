# Handoff — eq_disambiguation_engine.py emotion-detection fixes

## What changed (single file: `eq_disambiguation_engine.py`)

1. **Added named-emotion output.** `DisambiguationResult` now has:
   - `primary_emotion: str` (e.g. "pride", "grief", "fear", "anger", "neutral")
   - `secondary_emotions: List[str]`
   - `emotion_scores: Dict[str, float]`
   New methods `_detect_emotions()` and `_rank_emotions()` score message text
   against an expanded `ContextPatterns.emotional_markers` dict (grew from 7
   sparse emotions to 16, with weighted multi-word phrase matching). Previously
   this dictionary existed but was never referenced anywhere in the pipeline —
   the engine inferred *context* but never actually named what the user felt.

2. **Fixed neutral-text intensity bug.** `_estimate_intensity()` defaulted
   unmatched text to `0.5` ("moderate") — so "Hi there" scored as emotionally
   loaded as "I'm frustrated." Now defaults to `0.05`. Also removed `"give up"`
   from the crisis-tier regex (false-positives on things like "I give up
   trying to parallel park"). Intensity now also takes a floor from
   `emotion_scores` so strong named-emotion evidence isn't ignored just
   because the older keyword bucket didn't happen to catch the phrasing.

3. **Fixed hit/goal context collision.** `"I hit my goal for the quarter"`
   was tagged both `ACHIEVEMENT` and `VIOLENCE` (only `"shot"` had an
   achievement-phrasing exclusion; `"hit"` didn't), which silently attached
   `"avoid victim-blaming language"` as a sensitive area to good news. Added
   the same exclusion pattern for `"hit"` that `"shot"` already had.

## Verified

Ran the file's own `__main__` demo (unchanged, all 8 cases still produce
sensible output) plus a manual spot-check of 7 new messages covering neutral,
pride, guilt, loneliness, achievement/violence collision, and gratitude —
see conversation for output. No test suite exists for this file specifically
(`test_eq_transitions.py` covers `eq_adaptor.py`, not this file).

## Not done / next steps if you continue this

- `_identify_actor()` still has a real ambiguity gap: "She told me she loves
  him" matches "me" first and returns SELF, when the emotion is actually
  about someone else's situation. Not touched — fixing it properly needs
  clause-level parsing, not a quick regex change.
- `emotion_scores` is exposed but `eq_card_selector.py` / `eq_integration_layer.py`
  were not opened or modified — they don't yet consume `primary_emotion`.
  If you want the response-selection layer to actually use the new emotion
  label (not just context/intensity), that's the next task.
- No new emotion-detection unit tests were added. Recommend a
  `test_eq_disambiguation.py` mirroring `test_eq_transitions.py`'s structure
  if this becomes a maintained module.
