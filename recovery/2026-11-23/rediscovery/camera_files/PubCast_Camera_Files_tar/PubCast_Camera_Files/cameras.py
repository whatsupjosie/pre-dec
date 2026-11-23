from __future__ import annotations

import time
import json
import uuid
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

class CameraTransport(str, Enum):
    """Detailed camera transport mechanisms"""
    RTMP = "rtmp"
    NDI = "ndi"
    SRT = "srt"
    LOCAL_FILE = "file"
    VOXEL_ENGINE = "voxel_engine"
    UNREAL_ENGINE = "unreal_engine"

class CameraStatus(str, Enum):
    """Detailed camera connection status"""
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    ERROR = "error"

@dataclass
class CameraMetrics:
    """Capture detailed camera performance metrics"""
    latency_ms: float = 0.0
    frame_rate: float = 0.0
    resolution: str = ""
    signal_strength: float = 0.0  # 0-100%
    last_connection: float = field(default_factory=time.time)
    connection_attempts: int = 0
    total_uptime_seconds: float = 0.0

@dataclass
class VoxelCameraConfig:
    """Specialized configuration for Voxel Engine cameras"""
    input_slot: int = 1
    render_mode: str = "default"
    projection_type: str = "perspective"
    fov: float = 90.0  # Field of View
    near_clip: float = 0.1
    far_clip: float = 1000.0

@dataclass
class CameraSource:
    """Enhanced camera source with detailed tracking and Voxel Engine support"""
    source_id: str
    name: str
    location: str
    description: str
    transport: CameraTransport
    endpoint: str
    input_slot: int = 1
    tags: List[str] = field(default_factory=list)
    status: CameraStatus = CameraStatus.OFFLINE
    metrics: CameraMetrics = field(default_factory=CameraMetrics)
    config: Dict[str, Any] = field(default_factory=dict)
    voxel_config: VoxelCameraConfig = field(default_factory=VoxelCameraConfig)

class AdvancedCameraManager:
    def sources(self) -> List[CameraSource]:
        """List all registered camera sources"""
        return list(self._sources.values())

    def list_cameras(self) -> List[CameraSource]:
        """Alias for sources"""
        return self.sources()
    """Comprehensive camera management with advanced tracking and Voxel Engine integration"""
    def __init__(self, persistence_file: str = "/mnt/project/data/camera_sources.json"):
        self._sources: Dict[str, CameraSource] = {}
        self._persistence_file = persistence_file
        
        # Ensure directory exists
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
        except Exception:
            pass
        
        # Ensure file exists
        if not os.path.exists(self._persistence_file):
            with open(self._persistence_file, 'w') as f:
                json.dump([], f)
        
        # Load sources
        self._load_sources()

    def _load_sources(self):
        """Load camera sources from persistent storage"""
        try:
            with open(self._persistence_file, 'r') as f:
                source_data = f.read()
                # If file is empty, initialize with default sources
                if not source_data.strip():
                    source_data = '[]'
                sources = json.loads(source_data)

                for source in sources:
                    # Backward compatibility and default values
                    metrics_data = source.get('metrics', {})
                    voxel_config_data = source.get('voxel_config', {})
                    
                    self._sources[source['source_id']] = CameraSource(
                        source_id=source['source_id'],
                        name=source['name'],
                        location=source['location'],
                        description=source['description'],
                        transport=source['transport'],
                        endpoint=source['endpoint'],
                        input_slot=source.get('input_slot', 1),
                        tags=source.get('tags', []),
                        status=source.get('status', CameraStatus.OFFLINE),
                        metrics=CameraMetrics(
                            latency_ms=metrics_data.get('latency_ms', 0.0),
                            frame_rate=metrics_data.get('frame_rate', 0.0),
                            resolution=metrics_data.get('resolution', ''),
                            signal_strength=metrics_data.get('signal_strength', 0.0),
                            last_connection=metrics_data.get('last_connection', time.time()),
                            connection_attempts=metrics_data.get('connection_attempts', 0),
                            total_uptime_seconds=metrics_data.get('total_uptime_seconds', 0.0)
                        ),
                        voxel_config=VoxelCameraConfig(
                            input_slot=voxel_config_data.get('input_slot', 1),
                            render_mode=voxel_config_data.get('render_mode', 'default'),
                            projection_type=voxel_config_data.get('projection_type', 'perspective'),
                            fov=voxel_config_data.get('fov', 90.0),
                            near_clip=voxel_config_data.get('near_clip', 0.1),
                            far_clip=voxel_config_data.get('far_clip', 1000.0)
                        ),
                        config=source.get('config', {})
                    )

        except json.JSONDecodeError:
            # If file is corrupted, reset to default
            pass

        # If no sources, add default sources
        if not self._sources:
            # Default single engine camera
            self.register(
                CameraSource(
                    source_id="single_engine_cam",
                    name="Voxel Engine Single Camera",
                    description="Primary 3D world camera",
                    location="voxel_space",
                    transport=CameraTransport.VOXEL_ENGINE,
                    endpoint="rtmp://localhost/live/single_engine",
                    input_slot=1,
                    status=CameraStatus.OFFLINE
                )
            )

    def _save_sources(self):
        """Save camera sources to persistent storage"""
        with open(self._persistence_file, 'w') as f:
            json.dump([
                {
                    "source_id": source.source_id,
                    "name": source.name,
                    "location": source.location,
                    "description": source.description,
                    "transport": source.transport,
                    "endpoint": source.endpoint,
                    "input_slot": source.input_slot,
                    "tags": source.tags,
                    "status": source.status,
                    "metrics": {
                        "latency_ms": source.metrics.latency_ms,
                        "frame_rate": source.metrics.frame_rate,
                        "resolution": source.metrics.resolution,
                        "signal_strength": source.metrics.signal_strength,
                        "last_connection": source.metrics.last_connection,
                        "connection_attempts": source.metrics.connection_attempts,
                        "total_uptime_seconds": source.metrics.total_uptime_seconds
                    },
                    "voxel_config": {
                        "input_slot": source.voxel_config.input_slot,
                        "render_mode": source.voxel_config.render_mode,
                        "projection_type": source.voxel_config.projection_type,
                        "fov": source.voxel_config.fov,
                        "near_clip": source.voxel_config.near_clip,
                        "far_clip": source.voxel_config.far_clip
                    },
                    "config": source.config
                } 
                for source in self._sources.values()
            ], f, indent=2)

    # Additional methods for Voxel Engine integration
    def create_voxel_camera(self, name: str = "Voxel Camera", endpoint: str = "rtmp://localhost/live/single_engine"):
        """Create a specialized Voxel Engine camera"""
        camera = CameraSource(
            source_id=f"voxel_cam_{uuid.uuid4().hex[:8]}",
            name=name,
            location="voxel_space",
            description="Voxel Engine generated camera",
            transport=CameraTransport.VOXEL_ENGINE,
            endpoint=endpoint,
            input_slot=1,
            voxel_config=VoxelCameraConfig(
                input_slot=1,
                render_mode="full_3d",
                projection_type="perspective",
                fov=90.0
            )
        )
        self.register(camera)
        return camera

def create_advanced_camera_manager() -> AdvancedCameraManager:
    """Factory method to create a camera manager with default sources"""
    return AdvancedCameraManager()

    def list_cameras(self) -> List[CameraSource]:
        """List all registered camera sources"""
        return list(self._sources.values())
