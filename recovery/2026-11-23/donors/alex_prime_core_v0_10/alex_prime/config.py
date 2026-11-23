from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectorConfig:
    recent_turn_window: int = 16
    sycophancy_window: int = 10
    escalation_window: int = 10
    role_drift_window: int = 12
    escalation_hit_threshold: int = 3
    context_token_warning_threshold: int = 8_000
    context_token_critical_threshold: int = 20_000
    long_session_goal_refresh_turns: int = 30
