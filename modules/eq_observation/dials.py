"""Owner dials for the shared EQ observation layer.

Every number here is a decision that belongs to the owner. The values are the
builder's starting proposals from the EQ integration plan (2026-11-23) and are
PENDING her answer. They live in one frozen object so a change is one edit and
can be reviewed, never scattered through the code.

Owner principles these dials encode, in her words:
  - "everybody starts neutral, because we don't know anything about them yet."
  - "none of these things are especially reliable alone. That's why we look at
    them all in aggregate."
  - "if the data is gathered and it continually runs in conflict, then you do
    have to slowly discount more and more what they're reporting. But that
    remains to be seen until the verdict is in."
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationDials:
    # Baselines. Until a feature has this many samples for a person it is
    # "warming up" and contributes nothing: no deviation is claimed.
    baseline_min_samples: int = 8
    # After this many samples the baseline becomes a moving average, so it
    # follows the person as they change instead of freezing on their first week.
    baseline_memory: int = 200
    # Deviations are clipped so one wild value cannot dominate.
    z_clip: float = 4.0
    # How far from their usual (in standard deviations) counts as "different".
    deviation_threshold: float = 1.0

    # Reliability. Every witness, for every person, starts here and moves only
    # when an approved calibration verdict says it was right or wrong.
    neutral_reliability: float = 0.5
    reliability_learning_rate: float = 0.05
    reliability_floor: float = 0.1
    reliability_ceiling: float = 0.9

    # A report is only in conflict with the rest when at least this many
    # independent witness groups (never report-derived) agree against it.
    report_conflict_min_groups: int = 2
    # Fewer mature groups than this: the aggregate is not reported at all.
    aggregate_min_groups: int = 2

    # Bands for display. No decimals leave the layer for display.
    band_noticed: float = 0.35
    band_strong: float = 0.60

    # Calibration moments offered per interview (matches the calibration
    # store's target of three main questions).
    calibration_moments: int = 3

    # Personal vocabulary used to spot likely typos without a dictionary.
    vocabulary_limit: int = 4000
    vocabulary_min_count: int = 3

    # Readings kept per person for calibration and scoring (numbers and ids only).
    readings_kept: int = 200
    verdicts_kept: int = 500

    # Perception reader, first proposals. The perception scorecard, scored against
    # what observers actually reported, is what should set these.
    reply_orders_min_directives: int = 2       # this many directives in one reply may read as orders
    reply_overwhelming_ratio: float = 6.0      # reply this many times longer than a short message
    reply_overwhelming_max_user_words: int = 12
    reply_curt_min_user_words: int = 60        # a long message answered in
    reply_curt_max_words: int = 8              # this few words may read as curt
    display_intense_caps: float = 0.3
    display_intense_exclaims: float = 1.0
    display_brief_words: int = 3
    display_rushed_typos: float = 0.15
    display_fast_speech_rate: float = 3.5      # words per second
    display_flat_expressivity: float = 0.15
    display_disengaged_gaze: float = 0.6


DEFAULT_DIALS = ObservationDials()
