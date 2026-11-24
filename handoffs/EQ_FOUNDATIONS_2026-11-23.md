# EQ foundations, 2026-11-23

Branch: claude/eq-foundations-2026-11-23, built on claude/studio-assembly-2026-11-23 (2541c09), because the calibration code lives there. Not merged to main.

Labels: RAN = I ran it and saw the result. READ = I opened and read it. GUESS = my reasoning, not checked. Josie asked for no tests yet: nothing below was run through pytest. "RAN" here means a one-off script with synthetic messages, not the test suite.

## What was built

1. modules/eq_observation/ (new, stdlib only). The shared observation layer from the EQ plan, in SHADOW mode: it observes and records, and changes no reply, no move, no judgment.
   - features.py: witness features and their groups (one vote per group, because features with a shared cause are not independent): message_shape, emphasis, motor, voice, face, situation, report. Axes are behaviour, not feelings: contraction, activation, disruption. Keyboard, voice and face are used only with the person's consent flag; simulated values are refused.
   - Likely typos use no dictionary: a word the person has never used that is one keystroke from a word they use often. Their own spellings stop counting as typos once habitual.
   - baseline.py: per-person baselines. A feature says nothing until it has 8 samples ("everybody starts neutral"); after 200 it becomes a moving average so it follows the person.
   - reliability.py: trust per witness group per person, starting at 0.5, moving 0.05 per approved calibration verdict, never from a disagreement alone. The in-the-moment report has its own trust record; the later calibration account is the reference and is not scored, but every verdict keeps the delay and whether the person was calm.
   - agreement.py: the agreement map (which groups differ from usual, which way, where they split) and the report gap (says fine while two or more independent groups differ; or says not fine while all are steady). The gap is never announced and never discounts the report by itself.
   - readers.py: two readers that are never mixed. InnerStateReader uses personal baselines and is labelled "never tell them how they feel". PerceptionReader uses absolute values (an audience does not know anyone's usual) and predicts how a reply or a display comes across.
   - scorecards.py: separate scorecards: inner against the person's approved later account; perception against what an observer reported.
   - layer.py: ObservationLayer: observe_turn, shadow_view, perceive_reply, calibration_moments (evidence refs in the calibration store's format: session_id, turn_id, source_id), apply_calibration_verdict, record_perception_feedback, summary, forget.
   - dials.py: every number in one place, all PENDING Josie's answer.
   - store.py: one private file per person under data/pubpartner/eq_observation/. Numbers, ids, and the person's vocabulary (word counts for typo spotting). No whole messages; originals stay in the Verbatim Vault.
2. modules/pubpartner_core.py: the layer is built in PubPartnerSpine (eq_observation_enabled=True by default). build_turn_packet observes private-audience message turns and puts the result on the turn under "eq_observation". run_turn adds "eq_perception" for the reply. Neither goes into the prompt (RAN: checked llm_prompt_text). A failure is recorded, never blocks the turn. New optional argument behaviour= on both; the routes do not pass it yet.
3. modules/emotional_orchestrator.py: three fixes ported from the 2026-10-02 empathy zip: NaN and infinite values are refused instead of turned into zero; PEQ and CRE-EQ are forced to clinical-hypothesis at the broker too; one source may hold at most half the buffer. NOT ported: the zip's rule that a self-report always wins. It conflicts with Josie's design (people are poor reporters in the moment; trust is earned per person), so the existing priority order stands.
4. companion_support/conversation_pacing.py and eq_disambiguation_engine.py: referral wording removed (Josie, settled: "unless the person asks, no referring to services. No brushing them off."). crisis_response is now presence only. Josie, 2026-11-23, on safety-check questions: "Don't ask them that. It makes it worse. It always makes it worse." So the acute-moment gate now BLOCKS a hand-off to a service and a safety-check script ("are you safe", "is anyone with you") instead of requiring "988" or "crisis". READ: this text was computed but did not reach a reply on the live path (the advisory forwards only the pacing decision).

## Checked (RAN, one-off scripts)

- Every new and edited file parses and imports; PubPartnerSpine imports.
- Synthetic person, ten ordinary messages then a three-word "fine" message: message_shape departed, the rest steady, calibration moment offered with "messages were shorter than usual; they said they were fine"; an approved verdict moved trust by 0.025; reply perception flagged a scripted line and orders; keyboard values without consent were refused.
- Real spine in a temp folder: build_turn_packet and run_turn (offline provider) both return the shadow keys; nothing in the prompt.

## Not done, and why

- No pytest, browser or full-suite run (Josie: not yet).
- Not wired: situation_reading (still imported by nothing), the calibration interview using calibration_moments and apply_calibration_verdict, routes passing behaviour, EVO and avatars using perceive_display, the reply checker acting on perception. Each needs a placement or behaviour choice.
- situation_reading.py says "The camera never contributes to the estimate. Faces do not map to feelings." Josie's aggregation point (2026-11-23) includes facial tics in the aggregate. The new layer treats face as a low-trust, consent-only witness; situation_reading was not changed. One of them has to give; that is her call.
- Danger behaviour, as Josie set it: stay with them as a friend; no safety-check questions; no service unless they ask, and then give the details. Do not ask her to reword this.
- Defects found earlier and not fixed here: eq_disambiguation "lost my keys" as loss and "give up" as crisis (a fixed 858-line donor is under rediscovery recovery/2026-11-23); conversation_state's 0.7 placeholder (wired stack, not live).

## Next step

Josie's choices: the dial numbers; face in situation_reading; whether the calibration interview should pull moments from this layer; where acting is used first (Alex's replies, the avatars, or the stage).
