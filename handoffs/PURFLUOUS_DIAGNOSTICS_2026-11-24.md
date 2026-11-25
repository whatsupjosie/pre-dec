# Sir Purfluous offline diagnostics, 2026-11-24

Produced by tools/purfluous_diagnostics.py. No AI model used. Numbers are from this run.

## 1. Soak (20 simulated users x 50 turns)

- replies: 1000
- repeat_within_10: 17
- repeat_rate: 0.017
- fallback_rate: 0.084
- door_line_rate: 0.111
- sancho_per_10_lines: 1.160
- words_median: 23.000
- words_max: 61
- ms_median: 0.839
- ms_p99: 7.008
- errors: 0
- slot leaks: 0

## 2. Fuzz (58 hostile or odd inputs)

- errors: 0
- slot leaks: 0
- slower than 250 ms: 0
- empty replies: 0

## 3. Routing (37/37 = 100%)

- celebrate: 2/2
- chair: 1/1
- craft_tip: 3/3
- everyday: 4/4
- farewell: 2/2
- ghost: 1/1
- greeting: 3/3
- hurt: 4/4
- hurt_or_betrayal: 1/1
- pete_shush: 1/1
- podcast_tip: 2/2
- pubcast_room: 3/3
- refuse_fact: 3/3
- scottish_play: 2/2
- setback: 1/1
- unclothed: 2/2
- unclothed_awards: 1/1
- unclothed_craft: 1/1

Misses (expected, message, what it looked like, reply):


## Full test suite, branch claude/purfluous-more-cards-2026-11-24 (run 2026-11-24, 37 min)

2,885 passed, 13 failed, 17 errors, 10 skipped. None traced to today's work:

- Same on main (checked by running the same tests on origin/main): 10 failures
  (5 in test_2i_claude_functionality_browser, 3 in test_2i_format_matrix
  [m4a, mov, mp4 decode], test_camera_pool_browser, test_clacker_recording_browser)
  and all 17 errors (14 in tests/primp_chromium/test_mirror.py: fixture 'page'
  not found, i.e. the pytest-playwright plugin is not installed here; 3 in
  test_2i_typewriter_event_browser).
- Pass on main, failed in the branch's full run, but pass when run alone on the
  branch: test_alex_routes_bridge::test_alex_routes_message_and_recent_memory
  (also fails on main when run in a group, so it depends on test order there
  too), test_production_notes::test_the_store_closes_every_database_connection_it_opens,
  test_participant_audio_browser::test_renderer_crash_recovers_...
  These are order- or load-dependent. Today's changes touch none of their modules.
  Not proven harmless: a full branch run with those three in isolation order has
  not been done.
