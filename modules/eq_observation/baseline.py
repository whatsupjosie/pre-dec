"""Per-person baselines: "different from usual" means different from THIS person's usual.

Welford's running mean and variance until the dial's memory is reached, then an
exponential moving average with the same effective memory, so the baseline
follows a person who changes. A feature with too few samples is "warming up"
and yields no deviation at all: everybody starts neutral.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from .dials import ObservationDials
from .features import spread_floor


@dataclass
class FeatureBaseline:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0  # sum of squared differences (Welford); variance = m2 / (n - 1)

    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    def deviation(self, value: float, dials: ObservationDials, feature: str = "") -> Optional[float]:
        """Standard deviations from usual, clipped; None while warming up."""
        if self.n < dials.baseline_min_samples:
            return None
        sd = math.sqrt(max(self.variance(), 0.0))
        # A floor on spread (features.spread_floor): a person who always writes exactly
        # five words has not earned an enormous deviation for writing six.
        z = (value - self.mean) / max(sd, spread_floor(feature, self.mean), 1e-9)
        return max(-dials.z_clip, min(dials.z_clip, z))

    def update(self, value: float, dials: ObservationDials) -> None:
        if not math.isfinite(value):
            return
        if self.n < dials.baseline_memory:
            self.n += 1
            delta = value - self.mean
            self.mean += delta / self.n
            self.m2 += delta * (value - self.mean)
            return
        # Moving average with the same effective memory; m2 is kept as n-1 times variance.
        alpha = 2.0 / (dials.baseline_memory + 1.0)
        var = self.variance()
        delta = value - self.mean
        self.mean += alpha * delta
        var = (1.0 - alpha) * (var + alpha * delta * delta)
        self.m2 = var * (self.n - 1)

    def to_dict(self) -> Dict[str, float]:
        return {"n": self.n, "mean": self.mean, "m2": self.m2}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FeatureBaseline":
        try:
            n, mean, m2 = int(data["n"]), float(data["mean"]), float(data["m2"])
        except (KeyError, TypeError, ValueError):
            return cls()
        if n < 0 or not (math.isfinite(mean) and math.isfinite(m2)) or m2 < 0:
            return cls()
        return cls(n=n, mean=mean, m2=m2)


@dataclass
class PersonBaseline:
    features: Dict[str, FeatureBaseline] = field(default_factory=dict)

    def deviations(self, values: Mapping[str, float], dials: ObservationDials) -> Dict[str, Optional[float]]:
        return {name: self.features.get(name, FeatureBaseline()).deviation(v, dials, name) for name, v in values.items()}

    def update(self, values: Mapping[str, float], dials: ObservationDials) -> None:
        for name, v in values.items():
            self.features.setdefault(name, FeatureBaseline()).update(float(v), dials)

    def maturity(self, dials: ObservationDials) -> float:
        """0 to 1: how much of the text baseline has enough samples."""
        core = ("word_count", "sentence_words", "caps_ratio", "exclaim_rate")
        got = [min(1.0, self.features.get(n, FeatureBaseline()).n / dials.baseline_min_samples) for n in core]
        return sum(got) / len(got)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self.features.items()}

    @classmethod
    def from_dict(cls, data: Any) -> "PersonBaseline":
        if not isinstance(data, Mapping):
            return cls()
        return cls(features={str(k): FeatureBaseline.from_dict(v) for k, v in data.items() if isinstance(v, Mapping)})
