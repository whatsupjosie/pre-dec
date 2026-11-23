"""Base station contract for operational PubCast stations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..event_bus import EventBus


class BaseStation(ABC):
    """Base class for all operational stations."""

    def __init__(self, station_id: str, station_type: str, event_bus: EventBus):
        self.station_id = station_id
        self.station_type = station_type
        self.event_bus = event_bus
        self.active_performer: Optional[str] = None
        self.local_state: Dict[str, Any] = {}

    @abstractmethod
    def on_activated(self, performer_id: str) -> bool:
        """Called when performer activates this station. Return success."""

    @abstractmethod
    def on_deactivated(self, performer_id: str):
        """Called when performer leaves this station."""

    @abstractmethod
    def on_interaction(self, performer_id: str, interaction_data: dict) -> dict:
        """Handle performer interaction. Return response data."""

    @abstractmethod
    def get_state(self) -> dict:
        """Get current operational state for sync/replication."""

    def emit_event(self, event_type: str, data: dict):
        """Emit station-related event through bus.

        Every station event carries which station sent it and what kind it is,
        so a listener on a shared event type such as camera:focused can tell two
        cameras apart. Keys in ``data`` win if a caller sets them explicitly.
        """

        payload = {"station_id": self.station_id, "station_type": self.station_type, **(data or {})}
        self.event_bus.emit(event_type, payload, source=self.station_id)

