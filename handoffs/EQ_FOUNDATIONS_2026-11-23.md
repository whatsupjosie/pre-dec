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

- The face rule: "Faces count for performance and avatar reaction. Unless we are actually looking at somebody in a live camera, seeing their actual living face, then faces don't count. Unless it's an avatar impersonating a human, in which case that is an intentional performance mimicking us as naturally as they are able in the most unnatural way."

## What is built

1. modules/eq_observation/ (new, stdlib only), SHADOW mode: it observes, records and scores, and changes no reply, move or judgment.
   - features.py: measurements and their witness groups (one vote per group, because features with a shared cause are not independent): message_shape, emphasis, motor, voice, face, situation, report. Axes are behaviour, not feelings: contraction, activation, disruption. Keyboard, voice and face need the person's consent flag; simulated, negative or non-finite values are refused and written down. Plain capitals (OK, TV, PDF) are not shouting. Likely typos use no dictionary: a lower-case word the person has never used, one keystroke from a word they use often; capitalised words (names, sentence starts) are never judged. Per-feature spread floors stop one exclamation mark from counting as extreme.
   - baseline.py: per-person baselines. Nothing is claimed before 8 samples; after 200 the baseline becomes a moving average and follows the person. A message is read before it joins the baseline.
   - reliability.py: trust per witness group per person, starting at 0.5, moving 0.05 only on an approved calibration account. A disagreement alone changes nothing (tested). The in-the-moment report has its own trust record; "partly" is kept but moves nothing.
   - agreement.py: the agreement map and the report gap ("says fine" with two or more independent groups differing, or "says not fine" with all steady). Never announced; never discounts the report by itself.
   - readers.py: InnerStateReader (personal baselines, "never tell them how they feel") and PerceptionReader (absolute values, because an audience does not know anyone's usual) for replies and for displays (stage, avatars, voice). Perception does not flag "if you feel like it", "how do you feel", "Just checking in", "Go for it"; it does flag a stated or hedged feeling claim, scripted lines, two or more directives.
   - Face rule: for the inner reading a face counts only with origin "live_camera" (a person's own living face) and consent; an avatar, rendered or recorded face is reported as "performance" and never used there. features.performance_face and PerceptionReader.perceive_display(origin=...) take any face, an avatar's included, for performance and avatar reaction. situation_reading.py's camera line is unchanged in behaviour (a camera's emotion label still never moves its estimate) and its comment now states the rule.
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

- tests/test_eq_observation.py, tests/test_eq_broker_and_presence.py, tests/test_eq_disambiguation_fixes.py: 85 passed (142 with test_situation_reading.py, which has 2 skips). Deliberate breaks each caught: the face rule removed, the consent check removed, plain capitals removed, one-account guard removed, a safety question put back into crisis_response, one witness allowed to make a gap; and the old disambiguation engine fails 10 of 17.
- Related existing files, 19 in one run (215 passed) and 9 in another (159 passed). Failing the same way on the starting commit 2541c09, so not caused here and not diagnosed: test_main_route_authorization_parity.py (3), test_internal_routes_guarded.py (12 errors), test_pubpartner_connections.py (2).
- Not run: the full suite; browser tests for PubPartner screens (none were changed).

## Not done, and why (each needs Josie's choice)

- The calibration screen (static/pubpartner_calibration_ui.js) does not yet show the "observation" note or offer the approved-account answer. The routes are there.
- situation_reading.py is still imported by nothing; it needs a model to fill its reading form each turn. Until it is wired, the live layer has no report and no situation, so report gaps cannot fire live.
- No client sends keyboard, voice or face measurements yet, and no consent screen exists.
- The dial numbers.
- Where acting is used first: Alex's replies, the avatars, or the stage.

## Related, other branch

claude/studio-wire-avatars-2026-11-23 (pushed): show clocks on control_room, stage, stage_3d, stage_panoramic. tests/test_show_clocks_browser.py RAN in real Chromium against the real host: 9 passed; breaking the frame arithmetic failed 4. The labels IN and LEFT are the builder's words, not Josie's.

## Design decided in conversation after the face rule (2026-11-23, late). NOT BUILT. Next AI: build these, in this order.

Josie's words, verbatim (she uses speech-to-text; obvious dictation slips are hers to correct, not ours to fix):
- On avatars run by AI characters: "everything that they do in a body is performance, and it's performance to impersonate us as accurately as possible, to try to be passable the way we are. So I think they will be putting out an honest performance to try to accurately portray the emotion that they want to portray. And the emotion that sometimes they'll want to portray is the one that they're generally pulled towards, which is about as close to saying they had a feeling as we can get. Granted, yes, they can still be sycophantic and placating, giving you what you want to see, which is a danger."
- Earlier: "with an avatar, we're likely to be able to more honestly infer what they're feeling, so long as we can determine how more or less how often they tend to be honest."
- On mirroring: "people laugh a whole lot more at a live performance than they would at the same jokes performed at home with just maybe them and a friend. ... laughter's, as they say, is contagious because we mirror each other. It's a natural social dynamic."
- "No feelings are 100%. Pure joy is very rare. Happens, but it's rare." / "Unbridled fear is much more common. Still rare, but exponentially more common."
- "it's much easier to fall into despair and feel like this is the end and this is the worst you know when we're not even f****** close but we buy into our own pain"
- On dictation: "I use speak-to-text a lot. Speak-to-text fucks up a lot. We need some kind of general translation guide to help aid with the understanding when things don't quite make sense ... we're never going to catch the ones that are a yes or no question and someone says do and the speak-to-text puts down don't."

What the builder proposed and Josie did not reject (she asked "What would you like to tweak?" and then raised dictation; she has NOT said go on any item; confirm before building):

1. Baselines per input mode, not just per person: phone typing, laptop typing, dictated. The client reports the mode; compare like with like. Dictated text: the typo witness is off; a dictation slip never counts as a typo or as emotional evidence.
2. Dictation repair, never altering words: a "probably meant" note beside the original; the Verbatim Vault keeps the exact text; Alex quotes the original. Sources, most to least reliable: the person's own past corrections ("I meant don't" stores the pair per person), the dictation engine's alternative words if the client passes them, sound-alike plus context.
3. The uncatchable flips (do/don't, can/can't, keep/delete, yes/no): when one small word flips something that matters and cannot be undone, Alex says that one word back before acting ("Just to be sure: don't send it?"). Low stakes: take the likely reading and accept correction without fuss. NOTE: this is a confirmation on actions, not a safety-check question; Josie's rule against "are you safe" questions still stands.
4. Silence is not lying: a witness that stays steady while something was going on should NOT lose trust (reliability.apply_verdict currently marks it wrong; change: departed and nothing going on = wrong; departed and something = right; steady and nothing = right; steady and something = no change).
5. Calibration answer as conversation: the interviewer asks open questions, proposes a short summary (may be a blend: "mostly tiredness, a little worry"), the person approves or corrects; the approved summary drives trust. Replaces the three fixed answers as the main path (keep them as the stored outcome).
6. Room context as an input (one-on-one, small group, live audience) for the perception reader and portrayals: mirroring and big feelings are normal in a live room.
7. A third reader, character PORTRAYAL (AI characters in avatar bodies), kept apart from inner state and perception. Each character starts neutral and earns an honesty record. Mirroring is expected and never counted against it. Sycophancy signs: its own pull never appears (never holds a feeling the person does not share), folding (drops a feeling or position under pushback with nothing new said), inflation relative to the room. Portrayals are blends, never 100% of one feeling; per-feeling ceilings in dials.py as proposals: pure joy very rare; unbridled fear and despair rare but far more plausible. Ceilings apply to character portrayals and situation events ONLY, never to reading a person's typing or face (the person layer keeps no feeling labels).
8. Despair: never treat its intensity as implausible or average it away; do not take its sense of scale ("worst ever") as a measurement; calibration's later account is the reference. Reply checker rule: don't argue with it ("it's not that bad" is a brush-off) and don't amplify it; stay steady and take it seriously.

Read before building 7: modules/performance/avatar_adapter.py and modules/affect_choreo_bridge.py (not yet read), to record the real portrayal and check whether an expression can be driven to 100% of one feeling.

Still open with Josie: where acting is used first (Alex's replies, the avatars, or the stage); the dial numbers; calibration screen wiring; situation_reading wiring.

## Builder's own proposals (Claude, 2026-11-23). Josie: "pitch your ideas. This is about AI collaboration. I'm not here to be your queen." These are pitches, not her decisions; she said add them. Discuss with her before building.

A. Honesty is not one number per person: keep trust per person per topic and per state (calm vs cornered), so being guarded about one subject does not cost trust everywhere. Extends her point that people are poor reporters in the moment.
B. Test AI characters instead of guessing: replay the same scene offline with the other person's mood varied (pleased, annoyed, neutral). An honest pull stays put; a placating one swings to match. Cleaner sycophancy measure than live inference; no runtime cost.
C. Despair, privately grounded: the system may know this person's own history (the last times it "felt like the end", it eased within days). Alex never says it in the moment (that would be arguing with the feeling); it only grounds her steadiness. Fair to look back on together later in calibration.
D. Dictation flips, two cheap catches before the one-word check: (1) consistency with the person's own stated plan in the conversation; a flip with no stated reason gets the check, a consistent one does not; (2) if the client keeps a few seconds of audio, re-hear the suspicious word first.
