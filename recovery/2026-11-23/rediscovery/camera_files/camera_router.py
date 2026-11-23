"""
Camera Router for PubCast API
Handles camera management and video switching operations
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import logging

from .camera_manager import CameraManager, CameraSource, CameraStatus, CameraTransport
from .video_switcher import VideoSwitcher, TransitionType, RecordingSession

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# ═══════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class CameraSourceRequest(BaseModel):
    name: str = Field(..., description="Camera display name")
    location: str = Field(..., description="Physical or logical location")
    description: str = Field("", description="Camera description")
    transport: CameraTransport = Field(..., description="Transport protocol")
    endpoint: str = Field(..., description="Connection endpoint")
    audio_channels: int = Field(2, description="Number of audio channels")
    video_enabled: bool = Field(True, description="Video enabled")
    audio_enabled: bool = Field(True, description="Audio enabled")
    tags: List[str] = Field(default_factory=list, description="Camera tags")
    is_private: bool = Field(False, description="Private camera flag")
    resolution: str = Field("1920x1080", description="Video resolution")
    framerate: int = Field(30, description="Video framerate")


class CameraSourceResponse(BaseModel):
    source_id: str
    name: str
    location: str
    description: str
    transport: str
    endpoint: str
    audio_channels: int
    video_enabled: bool
    audio_enabled: bool
    tags: List[str]
    is_private: bool
    resolution: str
    framerate: int
    created_at: float


class CameraStatusResponse(BaseModel):
    source_id: str
    online: bool
    last_check: float
    latency_ms: Optional[float]
    notes: Optional[str]
    error_count: int
    last_error: Optional[str]
    bandwidth_kbps: Optional[float]
    dropped_frames: int


class SwitcherInputResponse(BaseModel):
    id: int
    source_id: str
    name: str
    source_url: str
    type: str
    active: bool
    preview: bool
    recording: bool
    audio_enabled: bool
    video_enabled: bool


class SwitcherStatusResponse(BaseModel):
    state: str
    program_input: int
    preview_input: int
    total_inputs: int
    active_inputs: int
    recording_sessions: int
    transition_type: str
    transition_duration_ms: int
    bridge_connected: bool
    monitoring_enabled: bool


class RecordingRequest(BaseModel):
    sources: Optional[List[str]] = Field(None, description="Source IDs to record")
    filename: Optional[str] = Field(None, description="Recording filename") 
    quality: str = Field("high", description="Recording quality")
    format: str = Field("mp4", description="Recording format")


class RecordingResponse(BaseModel):
    session_id: str
    filename: str
    sources: List[str]
    start_time: float
    end_time: Optional[float]
    format: str
    quality: str
    audio_enabled: bool
    status: str
    file_size_bytes: int
    duration_seconds: float


class TransitionRequest(BaseModel):
    input_id: Optional[int] = Field(None, description="Target input ID")
    transition_type: Optional[TransitionType] = Field(None, description="Transition type")
    duration_ms: Optional[int] = Field(None, description="Transition duration")


# ═══════════════════════════════════════════════════════════════
# DEPENDENCY INJECTION
# ═══════════════════════════════════════════════════════════════

# These will be injected by the main application
camera_manager: Optional[CameraManager] = None
video_switcher: Optional[VideoSwitcher] = None


def get_camera_manager() -> CameraManager:
    """Get camera manager dependency"""
    if camera_manager is None:
        raise HTTPException(status_code=503, detail="Camera manager not initialized")
    return camera_manager


def get_video_switcher() -> VideoSwitcher:
    """Get video switcher dependency"""
    if video_switcher is None:
        raise HTTPException(status_code=503, detail="Video switcher not initialized")
    return video_switcher


def init_camera_systems(cm: CameraManager, vs: VideoSwitcher):
    """Initialize camera systems (called by main app)"""
    global camera_manager, video_switcher
    camera_manager = cm
    video_switcher = vs


# ═══════════════════════════════════════════════════════════════
# CAMERA MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=Dict[str, Any])
async def list_cameras(
    transport: Optional[CameraTransport] = None,
    location: Optional[str] = None,
    online_only: bool = False,
    cm: CameraManager = Depends(get_camera_manager)
):
    """List all camera sources with optional filtering"""
    try:
        sources = cm.get_sources(
            transport=transport,
            location=location, 
            online_only=online_only
        )
        
        return {
            "sources": [
                CameraSourceResponse(**source.to_dict()).dict()
                for source in sources
            ],
            "total": len(sources),
            "summary": cm.get_summary()
        }
        
    except Exception as e:
        logger.error(f"Failed to list cameras: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict[str, str])
async def create_camera(
    camera_data: CameraSourceRequest,
    cm: CameraManager = Depends(get_camera_manager),
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Create a new camera source"""
    try:
        # Generate unique source ID
        source_id = f"cam_{int(time.time())}"
        
        # Create camera source
        source = CameraSource(
            source_id=source_id,
            **camera_data.dict()
        )
        
        # Register with camera manager
        if not cm.register(source):
            raise HTTPException(status_code=400, detail="Failed to register camera")
        
        # Sync with switcher
        vs._sync_with_camera_manager()
        
        return {
            "source_id": source_id,
            "message": f"Camera '{camera_data.name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create camera: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{source_id}", response_model=CameraSourceResponse)
async def get_camera(
    source_id: str,
    cm: CameraManager = Depends(get_camera_manager)
):
    """Get camera source by ID"""
    try:
        source = cm.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail=f"Camera {source_id} not found")
        
        return CameraSourceResponse(**source.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get camera {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{source_id}")
async def delete_camera(
    source_id: str,
    cm: CameraManager = Depends(get_camera_manager),
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Delete camera source"""
    try:
        if not cm.unregister(source_id):
            raise HTTPException(status_code=404, detail=f"Camera {source_id} not found")
        
        # Sync with switcher
        vs._sync_with_camera_manager()
        
        return {"message": f"Camera {source_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete camera {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{source_id}/status", response_model=CameraStatusResponse)
async def get_camera_status(
    source_id: str,
    cm: CameraManager = Depends(get_camera_manager)
):
    """Get camera status"""
    try:
        status = cm.get_status(source_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Camera {source_id} not found")
        
        return CameraStatusResponse(**status.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get camera status {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/all", response_model=List[CameraStatusResponse])
async def get_all_camera_statuses(
    cm: CameraManager = Depends(get_camera_manager)
):
    """Get all camera statuses"""
    try:
        statuses = cm.get_all_statuses()
        return [
            CameraStatusResponse(**status.to_dict())
            for status in statuses.values()
        ]
        
    except Exception as e:
        logger.error(f"Failed to get camera statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/start")
async def start_camera_monitoring(
    background_tasks: BackgroundTasks,
    cm: CameraManager = Depends(get_camera_manager)
):
    """Start camera health monitoring"""
    try:
        background_tasks.add_task(cm.start_monitoring)
        return {"message": "Camera monitoring started"}
        
    except Exception as e:
        logger.error(f"Failed to start camera monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_camera_monitoring(
    background_tasks: BackgroundTasks,
    cm: CameraManager = Depends(get_camera_manager)
):
    """Stop camera health monitoring"""
    try:
        background_tasks.add_task(cm.stop_monitoring)
        return {"message": "Camera monitoring stopped"}
        
    except Exception as e:
        logger.error(f"Failed to stop camera monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# VIDEO SWITCHER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/switcher/status", response_model=SwitcherStatusResponse)
async def get_switcher_status(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Get video switcher status"""
    try:
        status = vs.get_status()
        return SwitcherStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Failed to get switcher status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/switcher/inputs", response_model=List[SwitcherInputResponse])
async def get_switcher_inputs(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Get all switcher inputs"""
    try:
        inputs = vs.get_inputs()
        return [SwitcherInputResponse(**inp) for inp in inputs]
        
    except Exception as e:
        logger.error(f"Failed to get switcher inputs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switcher/cut/{input_id}")
async def cut_to_input(
    input_id: int,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Cut to input immediately"""
    try:
        if not vs.cut_to_input(input_id):
            raise HTTPException(status_code=400, detail=f"Failed to cut to input {input_id}")
        
        return {"message": f"Cut to input {input_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cut to input {input_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switcher/preview/{input_id}")
async def set_preview_input(
    input_id: int,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Set preview input"""
    try:
        if not vs.set_preview(input_id):
            raise HTTPException(status_code=400, detail=f"Failed to set preview {input_id}")
        
        return {"message": f"Preview set to input {input_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set preview {input_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switcher/transition")
async def execute_transition(
    request: TransitionRequest,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Execute transition"""
    try:
        # If input_id provided, set as preview first
        if request.input_id is not None:
            vs.set_preview(request.input_id)
        
        # Execute transition
        if not vs.transition(request.transition_type, request.duration_ms):
            raise HTTPException(status_code=400, detail="Failed to execute transition")
        
        return {"message": "Transition executed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute transition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# RECORDING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/recording/start", response_model=Dict[str, str])
async def start_recording(
    request: RecordingRequest,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Start recording session"""
    try:
        session_id = vs.start_recording(
            sources=request.sources,
            filename=request.filename,
            quality=request.quality,
            format=request.format
        )
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Failed to start recording")
        
        return {
            "session_id": session_id,
            "message": "Recording started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recording/stop/{session_id}")
async def stop_recording(
    session_id: str,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Stop recording session"""
    try:
        if not vs.stop_recording(session_id):
            raise HTTPException(status_code=404, detail=f"Recording session {session_id} not found")
        
        return {"message": f"Recording {session_id} stopped"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop recording {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recording/stop-all")
async def stop_all_recordings(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Stop all active recordings"""
    try:
        stopped_count = vs.stop_all_recordings()
        return {"message": f"Stopped {stopped_count} recordings"}
        
    except Exception as e:
        logger.error(f"Failed to stop all recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recording/{session_id}", response_model=RecordingResponse)
async def get_recording_status(
    session_id: str,
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Get recording session status"""
    try:
        status = vs.get_recording_status(session_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Recording session {session_id} not found")
        
        return RecordingResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recording status {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recording", response_model=List[RecordingResponse])
async def list_recordings(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """List all recording sessions"""
    try:
        recordings = vs.get_all_recordings()
        return [RecordingResponse(**rec) for rec in recordings]
        
    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/data", response_model=Dict[str, Any])
async def get_camera_data(
    cm: CameraManager = Depends(get_camera_manager),
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Get complete camera and switcher data for client"""
    try:
        return {
            "cameras": cm.get_client_data(),
            "switcher": vs.get_client_data(),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to get camera data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_systems(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Synchronize switcher with camera manager"""
    try:
        vs._sync_with_camera_manager()
        return {"message": "Systems synchronized"}
        
    except Exception as e:
        logger.error(f"Failed to sync systems: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_switcher(
    vs: VideoSwitcher = Depends(get_video_switcher)
):
    """Reset switcher to idle state"""
    try:
        # Stop all recordings
        vs.stop_all_recordings()
        
        # Clear program/preview
        vs.state = vs.state.IDLE
        vs.program_row = 0
        vs.preview_row = 0
        
        # Reset all inputs
        for inp in vs.inputs.values():
            inp.active = False
            inp.preview = False
            inp.recording = False
        
        return {"message": "Switcher reset to idle state"}
        
    except Exception as e:
        logger.error(f"Failed to reset switcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import time at the top
import time
