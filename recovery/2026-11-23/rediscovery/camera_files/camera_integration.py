"""
PubCast Camera System Integration
Complete guide to integrate camera management and video switching into existing PubCast
"""

import logging
from pathlib import Path
from typing import Optional

from .camera_manager import CameraManager, create_default_cameras
from .video_switcher import VideoSwitcher
from .camera_router import router as camera_router, init_camera_systems

logger = logging.getLogger(__name__)


class PubCastCameraIntegration:
    """
    Integration layer for PubCast camera systems
    Handles initialization, coordination, and lifecycle management
    """
    
    def __init__(self, data_dir: Path, bridge=None):
        self.data_dir = data_dir
        self.bridge = bridge
        
        # Core components
        self.camera_manager: Optional[CameraManager] = None
        self.video_switcher: Optional[VideoSwitcher] = None
        
        # State
        self.initialized = False
        self.monitoring_active = False
    
    async def initialize(self):
        """Initialize camera systems"""
        try:
            logger.info("Initializing PubCast camera systems...")
            
            # Create camera manager with data persistence
            self.camera_manager = CameraManager(self.data_dir / "cameras")
            
            # Initialize with default cameras if no existing sources
            if not self.camera_manager.sources:
                logger.info("No existing cameras found, creating defaults")
                default_manager = create_default_cameras()
                for source in default_manager.sources.values():
                    self.camera_manager.register(source)
            
            # Create video switcher
            self.video_switcher = VideoSwitcher(
                camera_manager=self.camera_manager,
                bridge=self.bridge
            )
            
            # Initialize the router dependencies
            init_camera_systems(self.camera_manager, self.video_switcher)
            
            # Start monitoring
            await self.start_monitoring()
            
            self.initialized = True
            logger.info(f"Camera systems initialized with {len(self.camera_manager.sources)} sources")
            
        except Exception as e:
            logger.error(f"Failed to initialize camera systems: {e}")
            raise
    
    async def start_monitoring(self):
        """Start system monitoring"""
        if not self.initialized:
            logger.warning("Cannot start monitoring - system not initialized")
            return
        
        try:
            # Start camera monitoring
            await self.camera_manager.start_monitoring()
            
            # Start switcher monitoring  
            await self.video_switcher.start_monitoring()
            
            self.monitoring_active = True
            logger.info("Camera system monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start camera monitoring: {e}")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        try:
            if self.camera_manager:
                await self.camera_manager.stop_monitoring()
            
            if self.video_switcher:
                await self.video_switcher.stop_monitoring()
            
            self.monitoring_active = False
            logger.info("Camera system monitoring stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop camera monitoring: {e}")
    
    async def shutdown(self):
        """Shutdown camera systems"""
        try:
            logger.info("Shutting down camera systems...")
            
            # Stop all recordings
            if self.video_switcher:
                self.video_switcher.stop_all_recordings()
            
            # Stop monitoring
            await self.stop_monitoring()
            
            # Save current state
            if self.camera_manager:
                self.camera_manager.save_sources()
            
            self.initialized = False
            logger.info("Camera systems shut down")
            
        except Exception as e:
            logger.error(f"Error during camera system shutdown: {e}")
    
    def get_router(self):
        """Get FastAPI router for camera endpoints"""
        return camera_router
    
    def get_status(self):
        """Get overall system status"""
        if not self.initialized:
            return {"initialized": False}
        
        return {
            "initialized": True,
            "monitoring_active": self.monitoring_active,
            "camera_count": len(self.camera_manager.sources) if self.camera_manager else 0,
            "switcher_inputs": len(self.video_switcher.inputs) if self.video_switcher else 0,
            "camera_summary": self.camera_manager.get_summary() if self.camera_manager else {},
            "switcher_status": self.video_switcher.get_status() if self.video_switcher else {}
        }


# ═══════════════════════════════════════════════════════════════
# MAIN APP INTEGRATION EXAMPLE
# ═══════════════════════════════════════════════════════════════

"""
How to integrate into main.py:

```python
from fastapi import FastAPI
from .camera_integration import PubCastCameraIntegration
from pathlib import Path

app = FastAPI()
camera_integration = None

@app.on_event("startup")
async def startup_event():
    global camera_integration
    
    # Initialize camera systems
    data_dir = Path("data")
    camera_integration = PubCastCameraIntegration(data_dir)
    await camera_integration.initialize()
    
    # Include camera router
    app.include_router(camera_integration.get_router())

@app.on_event("shutdown") 
async def shutdown_event():
    if camera_integration:
        await camera_integration.shutdown()

# Health check endpoint
@app.get("/api/cameras/health")
async def camera_health():
    if camera_integration:
        return camera_integration.get_status()
    return {"initialized": False}
```
"""


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET INTEGRATION
# ═══════════════════════════════════════════════════════════════

class CameraWebSocketHandler:
    """
    WebSocket handler for real-time camera updates
    Integrates with existing hub.py WebSocket system
    """
    
    def __init__(self, camera_integration: PubCastCameraIntegration):
        self.integration = camera_integration
        
    async def handle_camera_message(self, websocket, message_data):
        """Handle camera-related WebSocket messages"""
        try:
            message_type = message_data.get("type")
            
            if message_type == "camera_cut":
                # Handle cut to camera
                input_id = message_data.get("input_id")
                if input_id and self.integration.video_switcher:
                    success = self.integration.video_switcher.cut_to_input(input_id)
                    await self._broadcast_switcher_update(success)
                    
            elif message_type == "camera_preview":
                # Handle preview set
                input_id = message_data.get("input_id")
                if input_id and self.integration.video_switcher:
                    success = self.integration.video_switcher.set_preview(input_id)
                    await self._broadcast_switcher_update(success)
                    
            elif message_type == "recording_start":
                # Handle recording start
                if self.integration.video_switcher:
                    session_id = self.integration.video_switcher.start_recording()
                    await self._broadcast_recording_update(session_id)
                    
            elif message_type == "recording_stop":
                # Handle recording stop
                session_id = message_data.get("session_id")
                if session_id and self.integration.video_switcher:
                    success = self.integration.video_switcher.stop_recording(session_id)
                    await self._broadcast_recording_update(success)
                    
            elif message_type == "camera_status_request":
                # Handle status request
                await self._broadcast_full_status()
                
        except Exception as e:
            logger.error(f"Error handling camera WebSocket message: {e}")
    
    async def _broadcast_switcher_update(self, success=True):
        """Broadcast switcher status update"""
        if self.integration.video_switcher:
            status = self.integration.video_switcher.get_client_data()
            # Broadcast to all connected clients
            # Implementation depends on existing WebSocket hub
            pass
    
    async def _broadcast_recording_update(self, data):
        """Broadcast recording status update"""
        # Implementation depends on existing WebSocket hub
        pass
    
    async def _broadcast_full_status(self):
        """Broadcast complete camera system status"""
        status = self.integration.get_status()
        # Implementation depends on existing WebSocket hub
        pass


"""
Integration with existing hub.py:

```python
# In hub.py, add camera handler
from .camera_integration import CameraWebSocketHandler

class Hub:
    def __init__(self, ...):
        # ... existing code ...
        self.camera_handler = None
    
    def set_camera_integration(self, camera_integration):
        self.camera_handler = CameraWebSocketHandler(camera_integration)
    
    async def handle_message(self, websocket: WebSocket, raw_message: str):
        # ... existing message handling ...
        
        # Add camera message handling
        if message.get("category") == "camera" and self.camera_handler:
            await self.camera_handler.handle_camera_message(websocket, message)
            return
        
        # ... rest of existing code ...
```
"""


# ═══════════════════════════════════════════════════════════════
# VOXEL BRIDGE INTEGRATION
# ═══════════════════════════════════════════════════════════════

class CameraBridgeExtension:
    """
    Extension to VoxelBridge for camera operations
    Handles commands from video switcher to 3D engine
    """
    
    def __init__(self, voxel_bridge):
        self.bridge = voxel_bridge
        self.active_cameras = {}
        
    def handle_switcher_command(self, command_data):
        """Handle commands from video switcher"""
        try:
            command = command_data.get("command")
            data = command_data.get("data", {})
            
            if command == "CUT_TO":
                return self._handle_cut_to(data)
            elif command == "SET_PREVIEW":
                return self._handle_set_preview(data)
            elif command == "TRANSITION":
                return self._handle_transition(data)
            elif command == "START_RECORDING":
                return self._handle_start_recording(data)
            elif command == "STOP_RECORDING":
                return self._handle_stop_recording(data)
                
        except Exception as e:
            logger.error(f"Error handling switcher command: {e}")
            return False
    
    def _handle_cut_to(self, data):
        """Handle cut to camera command"""
        input_id = data.get("input_id")
        # Send command to 3D engine via bridge
        # Implementation depends on bridge interface
        logger.info(f"Bridge: Cut to camera {input_id}")
        return True
    
    def _handle_set_preview(self, data):
        """Handle set preview command"""
        input_id = data.get("input_id")
        # Send command to 3D engine via bridge
        logger.info(f"Bridge: Preview set to camera {input_id}")
        return True
    
    def _handle_transition(self, data):
        """Handle transition command"""
        from_input = data.get("from_input")
        to_input = data.get("to_input")
        transition_type = data.get("type")
        duration_ms = data.get("duration_ms")
        
        # Send transition command to 3D engine
        logger.info(f"Bridge: Transition from {from_input} to {to_input} ({transition_type}, {duration_ms}ms)")
        return True
    
    def _handle_start_recording(self, data):
        """Handle start recording command"""
        session_id = data.get("session_id")
        filename = data.get("filename")
        sources = data.get("sources")
        
        # Send recording command to 3D engine
        logger.info(f"Bridge: Start recording {filename} (session: {session_id})")
        return True
    
    def _handle_stop_recording(self, data):
        """Handle stop recording command"""
        session_id = data.get("session_id")
        
        # Send stop recording command to 3D engine
        logger.info(f"Bridge: Stop recording (session: {session_id})")
        return True


"""
Integration with existing bridge:

```python
# In your VoxelBridge class
from .camera_integration import CameraBridgeExtension

class VoxelBridge:
    def __init__(self, ...):
        # ... existing code ...
        self.camera_extension = CameraBridgeExtension(self)
    
    def send_command(self, command_data):
        # Handle camera commands
        if command_data.get("category") == "camera":
            return self.camera_extension.handle_switcher_command(command_data)
        
        # ... existing command handling ...
```
"""


# ═══════════════════════════════════════════════════════════════
# TESTING UTILITIES
# ═══════════════════════════════════════════════════════════════

async def test_camera_integration():
    """Test the camera integration"""
    import tempfile
    import asyncio
    
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir)
        
        # Create integration
        integration = PubCastCameraIntegration(data_dir)
        
        try:
            # Initialize
            await integration.initialize()
            
            # Test camera operations
            if integration.camera_manager:
                sources = integration.camera_manager.get_sources()
                print(f"Found {len(sources)} camera sources")
                
                for source in sources[:3]:  # Test first 3
                    print(f"  - {source.name} ({source.transport.value})")
            
            # Test switcher operations
            if integration.video_switcher and integration.video_switcher.inputs:
                input_ids = list(integration.video_switcher.inputs.keys())
                if len(input_ids) >= 2:
                    # Test cut
                    integration.video_switcher.cut_to_input(input_ids[0])
                    print(f"Cut to input {input_ids[0]}")
                    
                    # Test preview
                    integration.video_switcher.set_preview(input_ids[1])
                    print(f"Preview set to input {input_ids[1]}")
                    
                    # Test recording
                    session_id = integration.video_switcher.start_recording()
                    if session_id:
                        print(f"Recording started: {session_id}")
                        await asyncio.sleep(1)
                        integration.video_switcher.stop_recording(session_id)
                        print("Recording stopped")
            
            # Print status
            status = integration.get_status()
            print("Integration Status:", status)
            
        finally:
            # Cleanup
            await integration.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_camera_integration())
