# EQ foundations, 2026-11-23

Branch: claude/eq-foundations-2026-11-23 (pushed), built on claude/studio-assembly-2026-11-23 at 2541c09, because the calibration code lives there. Not merged to main. Commits: ee7e499 foundations, 474f8d5 crisis presence, 1035c69 hardening and routes, ca4f706 disambiguation fixes, plus this handoff.

Labels: RAN = I ran it and saw the result. READ = I opened and read it. GUESS = my reasoning, not checked.

## Josie's rules this work follows (her words)

- "unless the person asks, no referring to services. No brushing them off. We're here to be their partner, we're here to be their friend, and most of the time that's all they really need."
- On safety-check questions: "Don't ask them that. It makes it worse. It always makes it worse."
- "everybody starts neutral, because we don't know anything about them yet."
- "none of these things are especially reliable alone. That's why we look at them all in aggregate."
- "if the data is gathered and it continually runs in conflict, then you do have to slowly discount more and more what they're reporting. But that remains to be seen until the verdict is in."
- "with acting, whether or not the person is actually feeling something isn't necessarily as important as if we perceive that they are. So there are two purposes, two goals here that aren't necessarily simpatico, and at the same time they're not in opposition either."

## What is built

1. modules/eq_observation/ (new, stdlib only), SHADOW mode: it observes, records and scores, and changes no reply, move or judgment.
   - features.py: measurements and their witness groups (one vote per group, because features with a shared cause are not independent): message_shape, emphasis, motor, voice, face, situation, report. Axes are behaviour, not feelings: contraction, activation, disruption. Keyboard, voice and face need the person's consent flag; simulated, negative or non-finite values are refused and written down. Plain capitals (OK, TV, PDF) are not shouting. Likely typos use no dictionary: a lower-case word the person has never used, one keystroke from a word they use often; capitalised words (names, sentence starts) are never judged. Per-feature spread floors stop one exclamation mark from counting as extreme.
   - baseline.py: per-person baselines. Nothing is claimed before 8 samples; after 200 the baseline becomes a moving average and follows the person. A message is read before it joins the baseline.
   - reliability.py: trust per witness group per person, starting at 0.5, moving 0.05 only on an approved calibration account. A disagreement alone changes nothing (tested). The in-the-moment report has its own trust record; "partly" is kept but moves nothing.
   - agreement.py: the agreement map and the report gap ("says fine" with two or more independent groups differing, or "says not fine" with all steady). Never announced; never discounts the report by itself.
   - readers.py: InnerStateReader (personal baselines, "never tell them how they feel") and PerceptionReader (absolute values, because an audience does not know anyone's usual) for replies and for displays (stage, avatars, voice). Perception does not flag "if you feel like it", "how do you feel", "Just checking in", "Go for it"; it does flag a stated or hedged feeling claim, scripted lines, two or more directives.
   - scorecards.py: inner scored against the person's approved later account; perception scored against what an observer reported. A reading with too few witnesses made no prediction and is not scored.
   - store.py: one private folder per person, data/pubpartner/eq_observation/<slug>-<digest>/: state.json (atomic), readings.jsonl and perception.jsonl (append-only, trimmed to the newest rows, torn lines skipped, damaged state set aside). Holds numbers, ids and the person's word counts; no whole messages (tested). forget() removes the folder.
   - layer.py: ObservationLayer: observe_turn, shadow_view, perceive_reply, calibration_moments, moment_notes, apply_calibration_verdict (one per moment, delay measured from the reading, calm recorded), record_perception_feedback (one per prediction), summary, forget.
   - dials.py: every owner number in one place, all PENDING Josie.
2. modules/pubpartner_core.py: PubPartnerSpine builds the layer (eq_observation_enabled=True). Private message turns get "eq_observation"; live replies get "eq_perception". Shared rooms do not feed a private baseline. Neither is in the prompt. A failure is recorded and never blocks the turn. New optional behaviour= argument.
3. modules/pubpartner_routes.py: owner-scoped routes under /api/pubpartner/eq-observation/: GET summary, GET moments, POST verdicts, POST perception-feedback, POST forget (needs {"confirm": "forget"}). Turns accept "behaviour". The existing /calibration/moments list gains an additive "observation" note on moments the layer flagged.
4. modules/emotional_orchestrator.py: ported from the 2026-10-02 empathy pass: malformed (NaN, infinite, non-numeric) evidence is refused; PEQ and CRE-EQ are clinical at the broker too; one source holds at most half the buffer. NOT ported: "self-report always wins" (conflicts with trust earned per person). tests/test_emotional_orchestrator.py now carries the empathy pass's own tests for the refusal, in place of the old "coerce to a bounded number" test.
5. companion_support/conversation_pacing.py: crisis_response is presence only ("What you're saying matters, and I'm staying right here with you."). During an acute moment the gate BLOCKS a hand-off to a service and a safety-check script ("are you safe", "is anyone with you").
6. companion_support/eq_disambiguation_engine.py (used live by the advisory): from the donor recovery/2026-11-23/donors/eq_disambiguation_fixed_breaking_dawn: neutral text 0.05 (was 0.5); crisis wording explicit only ("give up", "end it", "dying" removed); "hit my goal" is not violence. The donor's named-emotion scoring was NOT ported (no single emotion label). New: "lost my keys" is not a loss. The referral opportunity line is gone.

## Tested (RAN)

- tests/test_eq_observation.py, tests/test_eq_broker_and_presence.py, tests/test_eq_disambiguation_fixes.py: 78 passed. Deliberate breaks each caught: consent check removed, plain capitals removed, one-account guard removed, a safety question put back into crisis_response, one witness allowed to make a gap; and the old disambiguation engine fails 10 of 17.
- Related existing files, 19 in one run (215 passed) and 9 in another (159 passed). Failing the same way on the starting commit 2541c09, so not caused here and not diagnosed: test_main_route_authorization_parity.py (3), test_internal_routes_guarded.py (12 errors), test_pubpartner_connections.py (2).
- Not run: the full suite; browser tests for PubPartner screens (none were changed).

## Not done, and why (each needs Josie's choice)

- The calibration screen (static/pubpartner_calibration_ui.js) does not yet show the "observation" note or offer the approved-account answer. The routes are there.
- situation_reading.py is still imported by nothing; it needs a model to fill its reading form each turn. Until it is wired, the live layer has no report and no situation, so report gaps cannot fire live.
- situation_reading.py says faces never count; Josie's aggregation point includes them. The new layer treats face as a consent-only, low-trust witness. Unchanged; her call.
- No client sends keyboard, voice or face measurements yet, and no consent screen exists.
- The dial numbers.
- Where acting is used first: Alex's replies, the avatars, or the stage.

## Related, other branch

claude/studio-wire-avatars-2026-11-23 (pushed): show clocks on control_room, stage, stage_3d, stage_panoramic. tests/test_show_clocks_browser.py RAN in real Chromium against the real host: 9 passed; breaking the frame arithmetic failed 4. The labels IN and LEFT are the builder's words, not Josie's.
