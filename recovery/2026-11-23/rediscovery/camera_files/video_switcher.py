"""
VIDEO SWITCHER — The Vision Mixer for PubCast

"Camera 1 is hot. Ready 2. Take 2."

Responsibility:
    - Manage video inputs (Cameras, Voxel Engine, Remote Feeds)
    - Route the active Program feed
    - Handle Recording logic
    - Integrate with Camera Manager
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from pathlib import Path
import asyncio

if TYPE_CHECKING:
    from .camera_manager import CameraManager

logger = logging.getLogger("switcher")


class SwitcherState(Enum):
    IDLE = "idle"
    PREVIEW = "preview"
    LIVE = "live"
    RECORDING = "recording"
    ERROR = "error"


class TransitionType(Enum):
    CUT = "cut"
    FADE = "fade"
    WIPE = "wipe"
    DISSOLVE = "dissolve"


@dataclass
class VideoInput:
    """Represents a video input to the switcher"""
    id: int
    source_id: str
    name: str
    source_url: str
    type: str  # "voxel_cam", "rtmp", "ndi", "virtual"
    active: bool = False
    preview: bool = False
    recording: bool = False
    audio_enabled: bool = True
    video_enabled: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecordingSession:
    """Represents an active recording session"""
    session_id: str
    filename: str
    sources: List[str]  # List of source IDs being recorded
    start_time: float
    end_time: Optional[float] = None
    format: str = "mp4"
    quality: str = "high"
    audio_enabled: bool = True
    status: str = "recording"  # recording, stopped, error
    file_size_bytes: int = 0
    duration_seconds: float = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


class VideoSwitcher:
    """Professional video switcher with recording capabilities"""
    
    def __init__(self, camera_manager: 'CameraManager', bridge = None):
        self.camera_manager = camera_manager
        self.bridge = bridge  # VoxelBridge for 3D engine integration
        
        # Switcher state
        self.inputs: Dict[int, VideoInput] = {}
        self.program_row = 0        # Which input is LIVE
        self.preview_row = 0        # Which input is PREVIEW  
        self.state = SwitcherState.IDLE
        self.transition_type = TransitionType.CUT
        self.transition_duration_ms = 1000
        
        # Recording state
        self.recording_sessions: Dict[str, RecordingSession] = {}
        self.recording_directory = Path("recordings")
        self.recording_directory.mkdir(exist_ok=True)
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_enabled = False
        
        # Initialize with camera sources
        self._sync_with_camera_manager()
    
    # ═══════════════════════════════════════════════════════════════
    # INITIALIZATION & SYNC
    # ═══════════════════════════════════════════════════════════════
    
    def _sync_with_camera_manager(self):
        """Synchronize inputs with camera manager sources"""
        logger.info("Syncing switcher inputs with camera manager")
        
        # Clear existing inputs
        self.inputs.clear()
        
        # Add all camera sources as inputs
        for i, (source_id, source) in enumerate(self.camera_manager.sources.items()):
            self.register_input(
                input_id=i + 1,
                source_id=source_id,
                name=source.name,
                source_url=source.endpoint,
                input_type=source.transport.value
            )
    
    def register_input(self, input_id: int, source_id: str, name: str, 
                      source_url: str, input_type: str) -> bool:
        """Register a video input"""
        try:
            self.inputs[input_id] = VideoInput(
                id=input_id,
                source_id=source_id,
                name=name,
                source_url=source_url,
                type=input_type,
                active=True
            )
            
            logger.info(f"SWITCHER: Input {input_id} ({name}) registered")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register input {input_id}: {e}")
            return False
    
    def unregister_input(self, input_id: int) -> bool:
        """Unregister a video input"""
        try:
            if input_id in self.inputs:
                input_obj = self.inputs.pop(input_id)
                logger.info(f"SWITCHER: Input {input_id} ({input_obj.name}) unregistered")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to unregister input {input_id}: {e}")
            return False
    
    def register_voxel_camera(self, cam_id: int, name: str = "Voxel Cam") -> bool:
        """Hook up the Voxel Engine's internal camera as an input"""
        try:
            # The Voxel Engine streams its render to a shared texture or local RTMP
            source_url = f"shm://voxel_render_target_{cam_id}"
            
            return self.register_input(
                input_id=cam_id,
                source_id=f"voxel_{cam_id}",
                name=name,
                source_url=source_url,
                input_type="voxel_cam"
            )
            
        except Exception as e:
            logger.error(f"Failed to register voxel camera {cam_id}: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # SWITCHING OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    def cut_to_input(self, input_id: int) -> bool:
        """Cut (immediate switch) to input"""
        try:
            if input_id not in self.inputs:
                logger.error(f"Input {input_id} not found")
                return False
            
            # Clear previous program
            if self.program_row in self.inputs:
                self.inputs[self.program_row].active = False
            
            # Set new program
            self.program_row = input_id
            self.inputs[input_id].active = True
            self.state = SwitcherState.LIVE
            
            # Send command to bridge if available
            if self.bridge:
                self._send_bridge_command("CUT_TO", {"input_id": input_id})
            
            logger.info(f"SWITCHER: Cut to input {input_id} ({self.inputs[input_id].name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cut to input {input_id}: {e}")
            return False
    
    def set_preview(self, input_id: int) -> bool:
        """Set preview input"""
        try:
            if input_id not in self.inputs:
                logger.error(f"Input {input_id} not found")
                return False
            
            # Clear previous preview
            if self.preview_row in self.inputs:
                self.inputs[self.preview_row].preview = False
            
            # Set new preview
            self.preview_row = input_id
            self.inputs[input_id].preview = True
            
            # Send command to bridge
            if self.bridge:
                self._send_bridge_command("SET_PREVIEW", {"input_id": input_id})
            
            logger.info(f"SWITCHER: Preview set to input {input_id} ({self.inputs[input_id].name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set preview {input_id}: {e}")
            return False
    
    def transition(self, transition_type: TransitionType = None, 
                  duration_ms: int = None) -> bool:
        """Execute transition from preview to program"""
        try:
            if self.preview_row not in self.inputs:
                logger.error("No preview input set")
                return False
            
            # Use provided values or defaults
            trans_type = transition_type or self.transition_type
            duration = duration_ms or self.transition_duration_ms
            
            # Execute transition based on type
            if trans_type == TransitionType.CUT:
                return self.cut_to_input(self.preview_row)
            else:
                return self._execute_transition(self.preview_row, trans_type, duration)
                
        except Exception as e:
            logger.error(f"Failed to execute transition: {e}")
            return False
    
    def _execute_transition(self, target_input: int, transition_type: TransitionType, 
                           duration_ms: int) -> bool:
        """Execute a timed transition"""
        try:
            # Send transition command to bridge
            if self.bridge:
                self._send_bridge_command("TRANSITION", {
                    "from_input": self.program_row,
                    "to_input": target_input,
                    "type": transition_type.value,
                    "duration_ms": duration_ms
                })
            
            # Update switcher state
            if self.program_row in self.inputs:
                self.inputs[self.program_row].active = False
            
            self.program_row = target_input
            self.inputs[target_input].active = True
            
            logger.info(f"SWITCHER: {transition_type.value.title()} transition to input {target_input}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute {transition_type.value} transition: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # RECORDING OPERATIONS  
    # ═══════════════════════════════════════════════════════════════
    
    def start_recording(self, sources: List[str] = None, filename: str = None, 
                       quality: str = "high", format: str = "mp4") -> Optional[str]:
        """Start recording session"""
        try:
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Use program feed if no sources specified
            if not sources:
                if self.program_row in self.inputs:
                    sources = [self.inputs[self.program_row].source_id]
                else:
                    logger.error("No sources specified and no program input active")
                    return None
            
            # Generate filename if not provided
            if not filename:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"recording_{timestamp}.{format}"
            
            # Create recording session
            session = RecordingSession(
                session_id=session_id,
                filename=filename,
                sources=sources,
                start_time=time.time(),
                format=format,
                quality=quality
            )
            
            self.recording_sessions[session_id] = session
            self.state = SwitcherState.RECORDING
            
            # Mark inputs as recording
            for input_obj in self.inputs.values():
                if input_obj.source_id in sources:
                    input_obj.recording = True
            
            # Send recording command to bridge
            if self.bridge:
                self._send_bridge_command("START_RECORDING", {
                    "session_id": session_id,
                    "filename": filename,
                    "sources": sources,
                    "quality": quality,
                    "format": format
                })
            
            logger.info(f"SWITCHER: Recording started - {filename} (session: {session_id})")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.state = SwitcherState.ERROR
            return None
    
    def stop_recording(self, session_id: str) -> bool:
        """Stop recording session"""
        try:
            if session_id not in self.recording_sessions:
                logger.error(f"Recording session {session_id} not found")
                return False
            
            session = self.recording_sessions[session_id]
            session.end_time = time.time()
            session.duration_seconds = session.end_time - session.start_time
            session.status = "stopped"
            
            # Clear recording flags
            for input_obj in self.inputs.values():
                if input_obj.source_id in session.sources:
                    input_obj.recording = False
            
            # Update switcher state
            active_recordings = [s for s in self.recording_sessions.values() 
                               if s.status == "recording"]
            if not active_recordings:
                self.state = SwitcherState.LIVE if self.program_row > 0 else SwitcherState.IDLE
            
            # Send stop command to bridge
            if self.bridge:
                self._send_bridge_command("STOP_RECORDING", {"session_id": session_id})
            
            logger.info(f"SWITCHER: Recording stopped - {session.filename} ({session.duration_seconds:.1f}s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop recording {session_id}: {e}")
            return False
    
    def stop_all_recordings(self) -> int:
        """Stop all active recordings"""
        stopped_count = 0
        active_sessions = [s.session_id for s in self.recording_sessions.values() 
                          if s.status == "recording"]
        
        for session_id in active_sessions:
            if self.stop_recording(session_id):
                stopped_count += 1
        
        return stopped_count
    
    def get_recording_status(self, session_id: str) -> Optional[dict]:
        """Get recording session status"""
        if session_id in self.recording_sessions:
            session = self.recording_sessions[session_id]
            
            # Update duration for active recordings
            if session.status == "recording":
                session.duration_seconds = time.time() - session.start_time
            
            return session.to_dict()
        
        return None
    
    def get_all_recordings(self) -> List[dict]:
        """Get all recording sessions"""
        sessions = []
        for session in self.recording_sessions.values():
            # Update duration for active recordings
            if session.status == "recording":
                session.duration_seconds = time.time() - session.start_time
            sessions.append(session.to_dict())
        
        return sessions
    
    # ═══════════════════════════════════════════════════════════════
    # BRIDGE COMMUNICATION
    # ═══════════════════════════════════════════════════════════════
    
    def _send_bridge_command(self, command: str, data: dict = None):
        """Send command to VoxelBridge"""
        try:
            if not self.bridge:
                logger.debug(f"No bridge available for command: {command}")
                return
            
            # Bridge command format
            cmd_data = {
                "command": command,
                "timestamp": time.time(),
                "data": data or {}
            }
            
            # Send to bridge (implementation depends on bridge interface)
            if hasattr(self.bridge, 'send_command'):
                self.bridge.send_command(cmd_data)
            else:
                logger.debug(f"Bridge command would be sent: {cmd_data}")
                
        except Exception as e:
            logger.error(f"Failed to send bridge command {command}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # STATUS & MONITORING
    # ═══════════════════════════════════════════════════════════════
    
    async def start_monitoring(self):
        """Start switcher monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Switcher monitoring already running")
            return
        
        self.monitoring_enabled = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Switcher monitoring started")
    
    async def stop_monitoring(self):
        """Stop switcher monitoring"""
        self.monitoring_enabled = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Switcher monitoring stopped")
    
    async def _monitoring_loop(self):
        """Monitor switcher and input health"""
        try:
            while self.monitoring_enabled:
                await self._update_input_health()
                await self._update_recording_stats()
                await asyncio.sleep(1.0)  # Monitor every second
                
        except asyncio.CancelledError:
            logger.info("Switcher monitoring cancelled")
        except Exception as e:
            logger.error(f"Switcher monitoring error: {e}")
    
    async def _update_input_health(self):
        """Update health status of inputs"""
        for input_obj in self.inputs.values():
            # Check if camera source is online
            camera_status = self.camera_manager.get_status(input_obj.source_id)
            if camera_status:
                # Update input based on camera health
                if not camera_status.online and input_obj.active:
                    logger.warning(f"Active input {input_obj.id} ({input_obj.name}) went offline")
    
    async def _update_recording_stats(self):
        """Update recording session statistics"""
        for session in self.recording_sessions.values():
            if session.status == "recording":
                # Update duration
                session.duration_seconds = time.time() - session.start_time
                
                # Update file size if possible
                try:
                    file_path = self.recording_directory / session.filename
                    if file_path.exists():
                        session.file_size_bytes = file_path.stat().st_size
                except:
                    pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive switcher status"""
        active_recordings = [s for s in self.recording_sessions.values() 
                           if s.status == "recording"]
        
        return {
            "state": self.state.value,
            "program_input": self.program_row,
            "preview_input": self.preview_row,
            "total_inputs": len(self.inputs),
            "active_inputs": sum(1 for inp in self.inputs.values() if inp.active),
            "recording_sessions": len(active_recordings),
            "transition_type": self.transition_type.value,
            "transition_duration_ms": self.transition_duration_ms,
            "bridge_connected": self.bridge is not None,
            "monitoring_enabled": self.monitoring_enabled
        }
    
    def get_inputs(self) -> List[dict]:
        """Get all inputs"""
        return [inp.to_dict() for inp in self.inputs.values()]
    
    def get_client_data(self) -> Dict[str, Any]:
        """Get data for client consumption"""
        return {
            "inputs": self.get_inputs(),
            "status": self.get_status(),
            "recordings": self.get_all_recordings(),
            "program_input": self.program_row,
            "preview_input": self.preview_row,
            "state": self.state.value
        }
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def set_transition_type(self, transition_type: TransitionType):
        """Set default transition type"""
        self.transition_type = transition_type
        logger.info(f"SWITCHER: Default transition set to {transition_type.value}")
    
    def set_transition_duration(self, duration_ms: int):
        """Set default transition duration"""
        self.transition_duration_ms = max(100, min(5000, duration_ms))
        logger.info(f"SWITCHER: Default transition duration set to {duration_ms}ms")
    
    def enable_audio(self, input_id: int, enabled: bool = True) -> bool:
        """Enable/disable audio for input"""
        if input_id in self.inputs:
            self.inputs[input_id].audio_enabled = enabled
            logger.info(f"SWITCHER: Audio {'enabled' if enabled else 'disabled'} for input {input_id}")
            return True
        return False
    
    def enable_video(self, input_id: int, enabled: bool = True) -> bool:
        """Enable/disable video for input"""
        if input_id in self.inputs:
            self.inputs[input_id].video_enabled = enabled
            logger.info(f"SWITCHER: Video {'enabled' if enabled else 'disabled'} for input {input_id}")
            return True
        return False


if __name__ == "__main__":
    # Quick test
    import asyncio
    from camera_manager import create_default_cameras
    
    async def test_switcher():
        # Create camera manager
        camera_manager = create_default_cameras()
        
        # Create switcher
        switcher = VideoSwitcher(camera_manager)
        
        print(f"Switcher created with {len(switcher.inputs)} inputs")
        print("Status:", switcher.get_status())
        
        # Test switching
        if len(switcher.inputs) > 1:
            input_ids = list(switcher.inputs.keys())
            switcher.cut_to_input(input_ids[0])
            switcher.set_preview(input_ids[1])
            
            # Start recording
            session_id = switcher.start_recording()
            if session_id:
                print(f"Recording started: {session_id}")
                
                # Wait a bit
                await asyncio.sleep(2)
                
                # Stop recording
                switcher.stop_recording(session_id)
                print("Recording stopped")
        
        print("Final status:", switcher.get_status())
    
    asyncio.run(test_switcher())
