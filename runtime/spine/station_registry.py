"""Authoritative station registry."""

from __future__ import annotations

from typing import Dict, Optional

from .event_bus import EventBus
from .stations.base_station import BaseStation


class StationRegistry:
    """Authoritative registry for all stations."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._stations: Dict[str, BaseStation] = {}

    def register_station(self, station: BaseStation):
        """Register a new station."""

        if station.station_id in self._stations:
            raise ValueError(f"Station already registered: {station.station_id}")
        self._stations[station.station_id] = station
        self.event_bus.emit(
            "station:state_change",
            {"station_id": station.station_id, "registered": True, "station_type": station.station_type},
            source="station_registry",
        )

    def get_station(self, station_id: str) -> Optional[BaseStation]:
        """Retrieve station by ID."""

        return self._stations.get(station_id)

    def activate_station(self, station_id: str, performer_id: str) -> bool:
        """Performer activates station."""

        station = self._require(station_id)
        success = station.on_activated(performer_id)
        if success:
            station.active_performer = performer_id
            self.event_bus.emit(
                "station:activated",
                {"station_id": station_id, "performer_id": performer_id},
                source="station_registry",
            )
        return success

    def deactivate_station(self, station_id: str, performer_id: str):
        """Performer leaves station."""

        station = self._require(station_id)
        station.on_deactivated(performer_id)
        if station.active_performer == performer_id:
            station.active_performer = None
        self.event_bus.emit(
            "station:deactivated",
            {"station_id": station_id, "performer_id": performer_id},
            source="station_registry",
        )

    def broadcast_station_states(self) -> Dict:
        """Get all station states for replication."""

        states = {station_id: station.get_state() for station_id, station in self._stations.items()}
        self.event_bus.emit("station:state_change", {"stations": states}, source="station_registry")
        return states

    def _require(self, station_id: str) -> BaseStation:
        station = self._stations.get(station_id)
        if station is None:
            raise KeyError(f"Unknown station: {station_id}")
        return station

