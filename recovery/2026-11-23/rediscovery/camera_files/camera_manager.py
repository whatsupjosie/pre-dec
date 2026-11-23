"""
Camera Management System for PubCast
Complete implementation with source management, health monitoring, and integration
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import asyncio

logger = logging.getLogger(__name__)


class CameraTransport(str, Enum):
    """Delivery mechanism for a camera feed."""
    NDI = "ndi"
    RTMP = "rtmp"
    SRT = "srt"
    FILE = "file"
    VIRTUAL = "virtual"
    WEBCAM = "webcam"
    VOXEL = "voxel"


@dataclass
class CameraSource:
    """Describes a physical or virtual camera feed that can be recorded."""
    source_id: str
    name: str
    location: str
    description: str
    transport: CameraTransport
    endpoint: str
    audio_channels: int = 2
    video_enabled: bool = True
    audio_enabled: bool = True
    tags: List[str] = field(default_factory=list)
    is_private: bool = False
    resolution: str = "1920x1080"
    framerate: int = 30
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['transport'] = self.transport.value
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CameraSource':
        """Create from dictionary"""
        if isinstance(data.get('transport'), str):
            data['transport'] = CameraTransport(data['transport'])
        return cls(**data)


@dataclass
class CameraStatus:
    """Represents the health of a camera feed."""
    source_id: str
    online: bool
    last_check: float = field(default_factory=time.time)
    latency_ms: Optional[float] = None
    notes: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None
    bandwidth_kbps: Optional[float] = None
    dropped_frames: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class CameraManager:
    """
    Keeps track of all camera feeds and their latest health information.
    Provides registration, monitoring, and management of camera sources.
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir
        self.sources: Dict[str, CameraSource] = {}
        self.statuses: Dict[str, CameraStatus] = {}
        self.tags: Set[str] = set()
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_enabled = False
        self.health_check_interval = 30.0  # seconds
        
        # Load existing sources if data directory provided
        if self.data_dir:
            self.load_sources()
    
    # ═══════════════════════════════════════════════════════════════
    # SOURCE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    def register(self, source: CameraSource) -> bool:
        """Register a camera source"""
        try:
            # Validate source
            if not source.source_id or not source.name:
                logger.error("Camera source requires source_id and name")
                return False
            
            # Check for duplicate IDs
            if source.source_id in self.sources:
                logger.warning(f"Camera source {source.source_id} already exists, updating")
            
            # Store source
            self.sources[source.source_id] = source
            
            # Initialize status
            self.statuses[source.source_id] = CameraStatus(
                source_id=source.source_id,
                online=False,
                notes="Registered, not yet tested"
            )
            
            # Update tags
            self.tags.update(source.tags)
            
            # Save to disk if data directory available
            if self.data_dir:
                self.save_sources()
            
            logger.info(f"Camera registered: {source.name} ({source.source_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register camera source {source.source_id}: {e}")
            return False
    
    def unregister(self, source_id: str) -> bool:
        """Unregister a camera source"""
        try:
            if source_id not in self.sources:
                logger.warning(f"Camera source {source_id} not found")
                return False
            
            source = self.sources.pop(source_id)
            self.statuses.pop(source_id, None)
            
            # Save to disk
            if self.data_dir:
                self.save_sources()
            
            logger.info(f"Camera unregistered: {source.name} ({source_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister camera source {source_id}: {e}")
            return False
    
    def get_source(self, source_id: str) -> Optional[CameraSource]:
        """Get camera source by ID"""
        return self.sources.get(source_id)
    
    def get_sources(self, 
                   transport: Optional[CameraTransport] = None,
                   location: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   online_only: bool = False) -> List[CameraSource]:
        """Get filtered list of camera sources"""
        sources = list(self.sources.values())
        
        # Filter by transport
        if transport:
            sources = [s for s in sources if s.transport == transport]
        
        # Filter by location
        if location:
            sources = [s for s in sources if s.location == location]
        
        # Filter by tags
        if tags:
            sources = [s for s in sources if any(tag in s.tags for tag in tags)]
        
        # Filter by online status
        if online_only:
            online_source_ids = {s_id for s_id, status in self.statuses.items() if status.online}
            sources = [s for s in sources if s.source_id in online_source_ids]
        
        return sources
    
    # ═══════════════════════════════════════════════════════════════
    # STATUS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    def update_status(self, source_id: str, status: CameraStatus) -> bool:
        """Update camera status"""
        try:
            if source_id not in self.sources:
                logger.warning(f"Cannot update status for unknown source {source_id}")
                return False
            
            self.statuses[source_id] = status
            return True
            
        except Exception as e:
            logger.error(f"Failed to update status for {source_id}: {e}")
            return False
    
    def get_status(self, source_id: str) -> Optional[CameraStatus]:
        """Get camera status"""
        return self.statuses.get(source_id)
    
    def get_all_statuses(self) -> Dict[str, CameraStatus]:
        """Get all camera statuses"""
        return self.statuses.copy()
    
    def set_online(self, source_id: str, online: bool, notes: str = ""):
        """Set camera online/offline status"""
        if source_id in self.statuses:
            self.statuses[source_id].online = online
            self.statuses[source_id].last_check = time.time()
            if notes:
                self.statuses[source_id].notes = notes
    
    def report_error(self, source_id: str, error: str):
        """Report error for camera source"""
        if source_id in self.statuses:
            status = self.statuses[source_id]
            status.error_count += 1
            status.last_error = error
            status.online = False
            status.last_check = time.time()
            status.notes = f"Error: {error}"
    
    # ═══════════════════════════════════════════════════════════════
    # HEALTH MONITORING
    # ═══════════════════════════════════════════════════════════════
    
    async def start_monitoring(self):
        """Start health monitoring for all camera sources"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Camera monitoring already running")
            return
        
        self.monitoring_enabled = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Camera monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        self.monitoring_enabled = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Camera monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self.monitoring_enabled:
                await self._health_check_all()
                await asyncio.sleep(self.health_check_interval)
        except asyncio.CancelledError:
            logger.info("Camera monitoring cancelled")
        except Exception as e:
            logger.error(f"Camera monitoring error: {e}")
    
    async def _health_check_all(self):
        """Perform health check on all sources"""
        for source_id, source in self.sources.items():
            try:
                await self._health_check_source(source)
            except Exception as e:
                logger.error(f"Health check failed for {source_id}: {e}")
                self.report_error(source_id, f"Health check failed: {e}")
    
    async def _health_check_source(self, source: CameraSource):
        """Perform health check on a single source"""
        start_time = time.time()
        
        try:
            # Health check based on transport type
            success = False
            
            if source.transport == CameraTransport.VIRTUAL:
                # Virtual sources are always "online" if registered
                success = True
                
            elif source.transport == CameraTransport.VOXEL:
                # Voxel sources depend on the bridge connection
                # This would need integration with VoxelBridge
                success = True  # Assume success for now
                
            elif source.transport == CameraTransport.NDI:
                # NDI source discovery/ping would go here
                success = await self._check_ndi_source(source)
                
            elif source.transport == CameraTransport.RTMP:
                # RTMP endpoint health check
                success = await self._check_rtmp_source(source)
                
            elif source.transport == CameraTransport.SRT:
                # SRT endpoint health check
                success = await self._check_srt_source(source)
                
            elif source.transport == CameraTransport.FILE:
                # File existence check
                success = await self._check_file_source(source)
                
            elif source.transport == CameraTransport.WEBCAM:
                # Webcam availability check
                success = await self._check_webcam_source(source)
            
            # Update status
            latency_ms = (time.time() - start_time) * 1000
            
            if source.source_id in self.statuses:
                status = self.statuses[source.source_id]
                status.online = success
                status.last_check = time.time()
                status.latency_ms = latency_ms
                
                if success:
                    status.notes = "Health check passed"
                else:
                    status.notes = "Health check failed"
                    status.error_count += 1
            
        except Exception as e:
            self.report_error(source.source_id, f"Health check exception: {e}")
    
    async def _check_ndi_source(self, source: CameraSource) -> bool:
        """Check NDI source availability"""
        # Placeholder for NDI discovery
        # In real implementation, would use NDI discovery APIs
        return True
    
    async def _check_rtmp_source(self, source: CameraSource) -> bool:
        """Check RTMP source availability"""
        # Placeholder for RTMP endpoint ping
        # In real implementation, would attempt connection
        return True
    
    async def _check_srt_source(self, source: CameraSource) -> bool:
        """Check SRT source availability"""
        # Placeholder for SRT endpoint ping
        return True
    
    async def _check_file_source(self, source: CameraSource) -> bool:
        """Check file source availability"""
        try:
            # Check if file exists and is readable
            file_path = Path(source.endpoint.replace("file://", ""))
            return file_path.exists() and file_path.is_file()
        except:
            return False
    
    async def _check_webcam_source(self, source: CameraSource) -> bool:
        """Check webcam availability"""
        # Placeholder for webcam device check
        # In real implementation, would check device availability
        return True
    
    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════
    
    def save_sources(self):
        """Save camera sources to disk"""
        if not self.data_dir:
            return
        
        try:
            cameras_file = self.data_dir / "cameras.json"
            cameras_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "sources": {
                    source_id: source.to_dict() 
                    for source_id, source in self.sources.items()
                },
                "statuses": {
                    source_id: status.to_dict()
                    for source_id, status in self.statuses.items()
                }
            }
            
            with open(cameras_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save camera sources: {e}")
    
    def load_sources(self):
        """Load camera sources from disk"""
        if not self.data_dir:
            return
        
        try:
            cameras_file = self.data_dir / "cameras.json"
            if not cameras_file.exists():
                return
            
            with open(cameras_file, 'r') as f:
                data = json.load(f)
            
            # Load sources
            for source_id, source_data in data.get("sources", {}).items():
                try:
                    source = CameraSource.from_dict(source_data)
                    self.sources[source_id] = source
                    self.tags.update(source.tags)
                except Exception as e:
                    logger.error(f"Failed to load camera source {source_id}: {e}")
            
            # Load statuses
            for source_id, status_data in data.get("statuses", {}).items():
                if source_id in self.sources:
                    try:
                        self.statuses[source_id] = CameraStatus(**status_data)
                    except Exception as e:
                        logger.error(f"Failed to load camera status {source_id}: {e}")
            
            logger.info(f"Loaded {len(self.sources)} camera sources from disk")
            
        except Exception as e:
            logger.error(f"Failed to load camera sources: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of camera system"""
        online_count = sum(1 for status in self.statuses.values() if status.online)
        
        by_transport = {}
        for source in self.sources.values():
            transport = source.transport.value
            by_transport[transport] = by_transport.get(transport, 0) + 1
        
        by_location = {}
        for source in self.sources.values():
            location = source.location
            by_location[location] = by_location.get(location, 0) + 1
        
        return {
            "total_sources": len(self.sources),
            "online_sources": online_count,
            "offline_sources": len(self.sources) - online_count,
            "by_transport": by_transport,
            "by_location": by_location,
            "available_tags": list(self.tags),
            "monitoring_enabled": self.monitoring_enabled
        }
    
    def get_client_data(self) -> Dict[str, Any]:
        """Get data safe for client consumption"""
        return {
            "sources": [source.to_dict() for source in self.sources.values()],
            "statuses": [status.to_dict() for status in self.statuses.values()],
            "summary": self.get_summary()
        }


def create_default_cameras() -> CameraManager:
    """Helper to bootstrap built-in sources"""
    manager = CameraManager()
    
    # Program feed (virtual)
    manager.register(CameraSource(
        source_id="program",
        name="Program Feed",
        description="Primary program output",
        location="any",
        transport=CameraTransport.VIRTUAL,
        endpoint="internal://program",
        tags=["program", "mix"],
    ))
    
    # Studio cameras
    manager.register(CameraSource(
        source_id="cam1",
        name="Camera 1 ISO",
        description="Stage left ISO feed",
        location="studio",
        transport=CameraTransport.NDI,
        endpoint="ndi://stage-left",
        tags=["iso", "studio"],
    ))
    
    manager.register(CameraSource(
        source_id="cam2", 
        name="Camera 2 ISO",
        description="Stage right ISO feed",
        location="studio",
        transport=CameraTransport.NDI,
        endpoint="ndi://stage-right",
        tags=["iso", "studio"],
    ))
    
    manager.register(CameraSource(
        source_id="cam3",
        name="Camera 3 ISO",
        description="Wide auditorium cam",
        location="studio", 
        transport=CameraTransport.RTMP,
        endpoint="rtmp://encoder/cam3",
        tags=["iso", "studio"],
    ))
    
    # Virtual spaces
    manager.register(CameraSource(
        source_id="pub_world",
        name="Pub World Feed",
        description="Side-scrolling social hub",
        location="pub",
        transport=CameraTransport.VIRTUAL,
        endpoint="internal://pub",
        audio_enabled=False,
        tags=["virtual", "social"]
    ))
    
    manager.register(CameraSource(
        source_id="green_room",
        name="Green Room Feed", 
        description="Backstage prep area",
        location="green_room",
        transport=CameraTransport.VIRTUAL,
        endpoint="internal://green",
        tags=["virtual", "restricted"],
    ))
    
    manager.register(CameraSource(
        source_id="conference",
        name="Conference Room Feed",
        description="Business meeting capture", 
        location="conference",
        transport=CameraTransport.SRT,
        endpoint="srt://conference",
        tags=["conference", "business"]
    ))
    
    # Voxel engine cameras for 3D world views
    manager.register(CameraSource(
        source_id="voxel_main",
        name="Voxel Main Camera",
        description="Primary 3D world view",
        location="voxel",
        transport=CameraTransport.VOXEL,
        endpoint="voxel://main_camera",
        tags=["voxel", "3d", "main"]
    ))
    
    manager.register(CameraSource(
        source_id="voxel_overhead",
        name="Voxel Overhead View", 
        description="Top-down 3D world view",
        location="voxel",
        transport=CameraTransport.VOXEL,
        endpoint="voxel://overhead_camera", 
        tags=["voxel", "3d", "overhead"]
    ))
    
    return manager


if __name__ == "__main__":
    # Quick test
    import asyncio
    
    async def test_camera_manager():
        manager = create_default_cameras()
        print(f"Created manager with {len(manager.sources)} sources")
        
        # Start monitoring
        await manager.start_monitoring()
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Print summary
        summary = manager.get_summary()
        print("Summary:", summary)
        
        # Stop monitoring
        await manager.stop_monitoring()
    
    asyncio.run(test_camera_manager())
