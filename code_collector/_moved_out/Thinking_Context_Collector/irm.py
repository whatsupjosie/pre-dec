"""
irm.py — Intelligent Resource Monitor
Reads CPU/RAM health and exposes a throttle actuator.
Phase 3: real hardware-level throttling via C++ twin engine.

Rear View Foresight LLC — Feic Mo Chroí
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


class HealthStatus(str, Enum):
    HEALTHY  = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN  = "unknown"


@dataclass
class HealthReport:
    status:      HealthStatus = HealthStatus.UNKNOWN
    cpu_percent: float        = 0.0
    ram_percent: float        = 0.0
    timestamp:   float        = field(default_factory=time.time)

    def to_dict(self):
        return {
            "status":      self.status.value,
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "timestamp":   self.timestamp,
        }


class IRMSensor:
    def sample(self) -> HealthReport:
        if not _PSUTIL:
            return HealthReport(status=HealthStatus.UNKNOWN)
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
        except Exception:
            return HealthReport(status=HealthStatus.UNKNOWN)
        if cpu > 90 or ram > 90:
            status = HealthStatus.CRITICAL
        elif cpu > 70 or ram > 75:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        return HealthReport(status=status, cpu_percent=cpu, ram_percent=ram)


class IRMActuator:
    def throttle(self, percent: float) -> None:
        pass  # Phase 3: real throttling

    def boost_priority(self) -> None:
        pass


class IRMController:
    def __init__(self) -> None:
        self.sensor   = IRMSensor()
        self.actuator = IRMActuator()
        self._last: Optional[HealthReport] = None

    def check(self) -> HealthReport:
        report = self.sensor.sample()
        self._last = report
        if report.status == HealthStatus.CRITICAL:
            self.actuator.throttle(50.0)
        return report

    @property
    def last_report(self) -> Optional[HealthReport]:
        return self._last
