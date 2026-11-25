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

