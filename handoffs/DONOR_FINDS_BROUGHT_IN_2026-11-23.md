# Donor finds brought into pre-dec - 2026-11-23

Branch: claude/bring-in-donor-finds-2026-11-23 (main untouched).
Written by Claude at Josie's request ("Bring them all into pre dec").

## Reason
While planning the PubPartner connector, Claude searched Josie's other repositories for memory, EQ and continuity work that pre-dec does not have. She asked for the finds to be brought in. This change only ADDS files. Nothing in the running application was edited, imported or wired. No existing file was overwritten or moved.

## Where everything is
All paths are under recovery/2026-11-23/. MANIFEST_SHA256.json lists every file (175) with its SHA-256, size and the exact source repository, commit, zip and nested zip it came from. All 175 hashes were re-checked after writing: zero mismatches. Files are byte-identical to the zip members they came from. Cache files (__pycache__, .pyc, .pytest_cache) were not copied and the test runs below did not create any.

1. donors/alex_prime_core_v0_10 (83 files)
   Source: repo 6.0-, commit bb20a0c, alex_prime_core_handoff_package.zip.
   What it is: persistent memory with a review-first promotion gate, an append-only hash-chained memory log, a continuity layer (golden sample, drift detection, reawakening, companion promise ledger, limited-recovery labelling), and an identity filter (an outside model may answer as a knowledge engine but may not impersonate Alex; generic-assistant and sentience-claim rejection; approved-memory retrieval). It also holds the uploaded source-locked files it wraps, docs, examples, and its own owned-failure ledger.
2. donors/peq_v0_1_backbreaker_hardened (43 files) and donors/peq_v0_1_hardened_two_passes (30 files)
   Source: repo The-Prime, commit ecf01ba, PEQ_v0.1_backbreaker_hardened.zip and PEQ_v0.1_hardened_two_passes.zip.
   What it is: PEQ, a probabilistic EQ layer that separates "what state is most probable" from "what response is appropriate", with evidence domains, a confidence cap of 98.5 percent, truth-testing of suspected lies or sarcasm, a non-diagnostic clinical-pattern evidence registry, and provenance-aware evidence retrieval. The backbreaker copy has more tests than the two-passes copy and appears to be the later one (it adds a claim layer and scientific-bridge hardening). That is Claude's reading of the file contents, not something either zip states.
3. donors/jeremy_cricket_hardened_beta_2026-04-06 (12 files)
   Source: repo DREAMS, commit 2f2fe57, dreams_repo_import_package_2026-04-06.zip, jeremy_cricket_separate_bundle, JEREMY_CRICKET_HARDENED_BETA (1).zip plus the Jcrkdocs2.zip docs.
   What it is: the Jeremy Cricket Adaptive Awareness Suite: four care modes (AMBIENT, ATTENTIVE, CARE, TOTAL_CARE_MANDATE) that gate which memory chapters are visible, a safety governor (preservation lock and autopilot), an encrypted sanctuary vault, input scorer, memory processor, config and tests. Per the September 21 notes in Pubcast-Reach, older "Jeremy Cricket" work is Jeremy's own work, not the newer personal Cricket.
4. donors/eq_disambiguation_fixed_breaking_dawn (3 files)
   Source: repo Pubcaast-Breaking-Dawn, commit 302e348, files (71).zip.
   What it is: a newer eq_disambiguation_engine.py (35,224 bytes) than pre-dec's companion_support copy (29,912 bytes), with its handoff note. DIFF_vs_pre-dec_companion_support.diff shows every difference. The pre-dec file was NOT replaced.
5. design_docs (5 files)
   Source: The-Prime (commit ecf01ba) and its alex_core_adaptive_companion.zip: the cartridge architecture audit, the memory verification pass, the collaborative-mode handoff, sketch and prototype.

## Not brought in, and why
- Breaking Dawn memory_api.py: it imports pubcast_memory_hardened, which is not in that repository, so it cannot run; it also has a placeholder secret key and allows all origins.
- Iteration Wallet continuity code (runtime_continuity.py and the continuous-agent files): a separate product; Josie's notes say its place is still being weighed.
- The private repositories October and Pub-Experiment: not readable here.
- Anything in repositories not searched by name-and-keyword. The comparison was by filename and keyword, so it will miss things pre-dec holds under other names.

## Tested (run locally in the sandbox, Python 3.13; no GitHub Actions)
- alex_prime_core_v0_10: 58 passed, run from its pre-dec location. Its README says 55; the actual count is 58.
- peq_v0_1_hardened_two_passes: 48 passed.
- peq_v0_1_backbreaker_hardened: 85 passed (run from its peq_claim_work folder).
- jeremy_cricket_hardened_beta_2026-04-06: 20 passed, 2 failed (with pytest-asyncio installed in the sandbox).
  Failure 1: TestCharacterEngine.test_low_signals_step_down, assertion that the mode is not AMBIENT but it is. A genuine assertion failure, not diagnosed.
  Failure 2: TestCharacterEngine.test_mode_change_hook_fires, "There is no current event loop", which looks like a Python 3.13 test-harness issue. Not diagnosed.
  Without pytest-asyncio it is 3 passed, 5 failed, 14 errors; the async fixtures need that plugin. pre-dec's pytest.ini already sets asyncio_mode = auto.
- eq_disambiguation_fixed_breaking_dawn: its own demo runs. No test suite exists for it (its handoff says so).

## Untested
- None of this is wired into main.py, run_reach.py or any route. Nothing here has been run inside the real application, on Windows or PowerShell 5, or against a real model.
- The full pre-dec suite was NOT run. These directories are outside pytest.ini's testpaths (tests), so the normal suite does not collect them and cannot be affected by them.
- The sanctuary vault's encryption path was not exercised separately.

## Things Josie should know before anything is wired
1. The fixed EQ engine drops "give up" from the crisis-tier pattern. Its own demo scores "I broke my leg" at intensity 0.05 with "Low emotional intensity". The fix lowers false alarms but may also under-read real distress. Both effects need her decision and a test set before it replaces pre-dec's copy.
2. The Alex Prime identity filter admits in its own comments that it is regex matching with a negation heuristic and can be defeated by a determined rewrite. It is a first line, not a guarantee.
3. Alex Prime's doctrine file describes personal Alex and "PubCast AlexT" as one Prime in two contexts. That sits beside, and has not been reconciled with, the System Alex versus personal Alex split in the Cricket design notes.
4. Alex Prime's persistent memory (review-first, consent-gated) and pre-dec's CricketKeeper and PubPartner memory are separate stores. Nothing here merges them. The collaborative handoff already warns about competing memory authorities.

## Next step (proposed, not started)
Build the PubPartner connector on top of the Alex Prime identity filter and memory gate through a thin adapter, and add the mailbox and doorbell. Port code out of recovery/ into active modules only with her approval, with tests, one piece at a time.
