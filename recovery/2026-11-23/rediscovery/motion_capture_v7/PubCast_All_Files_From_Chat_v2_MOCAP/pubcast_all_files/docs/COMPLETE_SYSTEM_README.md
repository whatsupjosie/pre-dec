# PubCast AI — Complete Studio System

**Professional Production Control + 3D Environment Management**

---

## What's This?

This is the **complete production studio infrastructure** for your PubCast AI virtual production platform. It consists of two integrated systems:

### 1. Studio Control Room (The "Iron Core")
Professional broadcast control with:
- **5-Second Preflight Countdown** with hardware audit
- **Audio Matrix** monitoring (5 channels)
- **Emergency Save** system (Dead Man's Switch)
- **Local-first logic** - works even offline

### 2. Voxel Asset System
Complete 3D environment management with:
- **91-asset library** (furniture, structures, props, vehicles, outdoor)
- **Visual Scene Builder** for composition
- **Automatic preflight validation** for scenes
- **Integration with Studio Control** countdown

Both systems work together seamlessly during your 5-second preflight countdown.

---

## What's Included

```
PubCast_Complete_Studio_System_v1.zip (54KB)
│
├── Studio Control Room Files:
│   ├── studio_control.py                  # Python backend
│   ├── studio_websocket.py                # WebSocket handler
│   ├── studio_control_room.html           # Control interface
│   ├── setup_studio_control.py            # Setup script
│   ├── STUDIO_CONTROL_INTEGRATION.md      # Studio guide
│   └── QUICK_REFERENCE.md                 # Quick reference card
│
├── Voxel Asset System Files:
│   ├── voxel_asset_manager.py             # Asset manager
│   ├── voxel_studio_integration.py        # Integration layer
│   ├── voxel_scene_builder.html           # Scene builder UI
│   ├── voxel_asset_library.json           # Asset catalog (91 items)
│   └── VOXEL_SYSTEM_README.md             # Voxel guide
│
└── README.md                               # This file
```

---

## Quick Start (5 Minutes)

### 1. Extract Files

```bash
unzip PubCast_Complete_Studio_System_v1.zip
```

### 2. Run Setup Script

```bash
python setup_studio_control.py
```

This will:
- Check Python dependencies
- Verify your PubCast AI structure
- Organize files into proper locations
- Show you the FastAPI integration code

### 3. Add to Your FastAPI App

Copy the generated code to your `main.py`:

```python
from modules.studio_control import StudioControl
from modules.studio_websocket import create_studio_websocket_endpoint
from modules.voxel_asset_manager import VoxelAssetManager
from modules.voxel_studio_integration import VoxelStudioIntegration

# Initialize Studio Control
studio_control = StudioControl(hub, pete_enhanced, Path("./data"))
studio_ws_handler = create_studio_websocket_endpoint(studio_control)

# Initialize Voxel System
voxel_manager = VoxelAssetManager(
    library_path=Path("./data/voxel_asset_library.json"),
    pete=pete_enhanced
)

# Create integration
voxel_integration = VoxelStudioIntegration(
    asset_manager=voxel_manager,
    studio_control=studio_control,
    pete=pete_enhanced
)

# Register preflight hooks
await voxel_integration.register_preflight_hooks()

# WebSocket endpoint
@app.websocket("/ws/studio")
async def websocket_studio(websocket: WebSocket):
    await studio_ws_handler.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await studio_ws_handler.handle_message(websocket, data)
    except WebSocketDisconnect:
        await studio_ws_handler.disconnect(websocket)

# Serve interfaces
@app.get("/studio")
async def get_studio_control_room():
    with open("./static/studio_control_room.html") as f:
        return HTMLResponse(content=f.read())

@app.get("/scene-builder")
async def get_scene_builder():
    with open("./static/voxel_scene_builder.html") as f:
        return HTMLResponse(content=f.read())
```

### 4. Test It

```bash
# Start your server
python main.py

# Studio Control Room
http://localhost:8000/studio

# Scene Builder
http://localhost:8000/scene-builder

# Press SPACE to start countdown
# Press ESC for emergency save
```

---

## How The Systems Work Together

```
┌─────────────────────────────────────────────────────────┐
│              STUDIO CONTROL ROOM                         │
│              (Browser Interface)                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │Audio     │  │Countdown │  │Preflight Checks    │    │
│  │Matrix    │  │T-5...T-1 │  │✓ Gate Check        │    │
│  │5 Channels│  │          │  │✓ Scene Validation  │    │
│  └──────────┘  └──────────┘  └────────────────────┘    │
└──────────────────┬──────────────────────────────────────┘
                   │ WebSocket
                   ▼
┌─────────────────────────────────────────────────────────┐
│            STUDIO CONTROL BACKEND                        │
│         (studio_control.py)                              │
│                                                          │
│  • Audio Matrix Monitoring                              │
│  • 5-Second Preflight Countdown                         │
│  • Emergency Save (Dead Man's Switch)                   │
│  • Preflight Check Coordination                         │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌─────────────────┐   ┌──────────────────────────────────┐
│VOXEL INTEGRATION│   │    SCENE BUILDER                  │
│                 │   │    (Browser Interface)            │
│ T-4: Validate   │   │                                   │
│      Scene      │◄──┤  ┌────────┐  ┌──────────────┐    │
│                 │   │  │Asset   │  │Scene         │    │
│ T-2: Preload    │   │  │Library │  │Viewport      │    │
│      Assets     │   │  │91 Items│  │              │    │
│                 │   │  └────────┘  └──────────────┘    │
└────────┬────────┘   └──────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│         VOXEL ASSET MANAGER                              │
│      (voxel_asset_manager.py)                            │
│                                                          │
│  • Asset Catalog (91 items)                             │
│  • Scene Composition                                    │
│  • Preflight Validation                                 │
│  • Pete Enhanced Integration                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              PETE ENHANCED                               │
│          (Your existing system)                          │
│                                                          │
│  • Twin Engine Orchestration                            │
│  • Rust Voxel Engine Communication                      │
│  • WebRTC Streaming                                     │
│  • Hardware Monitoring                                  │
└─────────────────────────────────────────────────────────┘
```

---

## The 5-Second Preflight Countdown (Integrated)

When you press **START COUNTDOWN** in Studio Control Room:

**T-5:** Countdown starts
- Audio matrix activates
- Pete speaks "T minus 5"

**T-4:** Gate Check + Scene Validation
- Verifies hardware matches scene
- Validates scene composition
- Checks instance count (max 1000)
- Verifies memory usage (max 512MB)

**T-3:** Countdown continues
- Pete speaks "T minus 3"

**T-2:** Ghost Mic Detection + Asset Preloading
- Scans for unexpected audio inputs
- Preloads all required 3D assets
- Synchronizes with Rust engine
- Verifies textures/models ready

**T-1:** Final check
- Pete speaks "T minus 1"

**T-0:** GO LIVE
- Recording starts
- Dead Man's Switch activates (auto-save every 60s)
- Scene syncs to Rust engine
- Audio matrix monitors in real-time

---

## Complete Workflow Example

### 1. Build Your Scene

```bash
# Open Scene Builder
http://localhost:8000/scene-builder
```

- Browse 91 assets (furniture, props, structures, vehicles)
- Click assets to add to scene
- Configure lighting, fog, camera
- Save scene as JSON

### 2. Load Scene in Python

```python
# Load your custom scene
scene = voxel_manager.load_scene_from_file(
    Path("./scenes/my_scene.json")
)

# Or use preset
scene = voxel_manager.create_preset_scene_detective_office()

# Set as active
voxel_manager.set_active_scene(scene.scene_id)
```

### 3. Start Production

```bash
# Open Studio Control Room
http://localhost:8000/studio

# Press SPACE or click "START COUNTDOWN"
```

**The system automatically:**
- T-4: Validates your scene
- T-2: Preloads all assets
- T-0: Syncs to Rust engine
- Records with audio monitoring
- Auto-saves every 60 seconds

### 4. Emergency Protection

```bash
# If something goes wrong:
# Press ESC or click "EMERGENCY SAVE"
```

**The system immediately:**
- Flushes all audio/video buffers to disk
- Saves complete scene state
- Creates timestamped recovery folder
- Preserves your work

---

## Key Features

### Studio Control Room

✅ **5-Second Preflight** - Mandatory pre-recording checks with AI voice cues
✅ **Audio Matrix** - Real-time 5-channel monitoring (10 Hz updates)
✅ **Emergency Save** - Dead Man's Switch (auto-save every 60s)
✅ **Isolation Mode** - Instant dialogue-only monitoring
✅ **Local-First** - Core safety works even if AI/network is offline
✅ **WebSocket Sync** - Real-time browser ↔ Python updates

### Voxel Asset System

✅ **91-Asset Library** - Curated 3D assets (furniture, structures, props, vehicles, outdoor)
✅ **Visual Scene Builder** - Browser-based composition tool
✅ **Preflight Integration** - Automatic scene validation during countdown
✅ **Preset Scenes** - Ready-to-use environments (Detective Office, Living Room)
✅ **Performance Limits** - Enforced safe limits (1000 instances, 512MB memory)
✅ **Pete Integration** - Direct sync with Rust voxel engine

---

## Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| **SPACE** | Start countdown | Studio Control (IDLE) |
| **ESC** | Emergency save | Studio Control (LIVE) |

---

## Documentation

### Comprehensive Guides

- **STUDIO_CONTROL_INTEGRATION.md** (22KB) - Complete Studio Control Room guide
  - Architecture diagrams
  - Integration steps
  - WebSocket protocol
  - Customization examples
  - Troubleshooting
  - Production checklist

- **VOXEL_SYSTEM_README.md** (19KB) - Complete Voxel Asset System guide
  - Asset library structure
  - Scene composition API
  - Preflight integration
  - Performance limits
  - Extension points
  - Best practices

- **QUICK_REFERENCE.md** (5KB) - One-page desk reference
  - File overview
  - Setup steps
  - Key features
  - Common customizations

---

## Configuration

### Studio Control

```python
StudioControl(hub, pete, data_dir, config={
    "dead_man_switch_interval": 60.0,  # Auto-save interval (seconds)
    "audio_update_interval": 0.1,      # Monitor rate (10 Hz)
    "enable_voice_cues": True,         # AI countdown voices
    "countdown_voice": "pete",         # Which AI voice
})
```

### Voxel Asset Manager

```python
VoxelAssetManager(library_path, pete, config={
    "max_instances": 1000,       # Max instances per scene
    "max_memory_mb": 512,        # Max memory usage
    "enable_lod": True,          # Level of Detail
    "culling_distance": 50.0,    # Culling distance
})
```

---

## System Requirements

- Python 3.8+
- FastAPI + uvicorn
- websockets
- pydantic
- asyncio (built-in)

**Already included in PubCast AI** - no new dependencies!

---

## Production Checklist

Before going live:

### Studio Control Room
- [ ] Test preflight countdown 10+ times
- [ ] Verify audio meters update in real-time
- [ ] Test emergency save creates recovery folders
- [ ] Confirm Dead Man's Switch auto-saves every 60s
- [ ] Verify WebSocket reconnects after network drop
- [ ] Test keyboard shortcuts (SPACE, ESC)
- [ ] Monitor Python logs during live session

### Voxel System
- [ ] Validate all scenes pass preflight
- [ ] Confirm instance counts < 1000
- [ ] Verify memory usage < 512MB
- [ ] Test asset preloading completes before T-0
- [ ] Confirm scenes sync to Rust engine
- [ ] Verify camera positions work
- [ ] Test preset scenes (Detective Office, Living Room)

---

## Troubleshooting

### Common Issues

**WebSocket Won't Connect**
1. Check FastAPI is running: `http://localhost:8000/docs`
2. Verify `/ws/studio` endpoint exists
3. Check firewall settings
4. Try `ws://` instead of `wss://` for local dev

**Scene Validation Fails**
1. Check instance count < 1000
2. Verify all assets exist in library
3. Reduce memory usage (< 512MB)
4. Check asset IDs match exactly

**Assets Won't Load**
1. Verify `voxel_asset_library.json` in `data/`
2. Check asset IDs match library
3. Rebuild catalog with setup script
4. Check Python logs for errors

---

## Customization Examples

### Add Custom Preflight Check

```python
# In studio_control.py
async def run_preflight_sequence(self):
    # ... existing countdown ...
    
    if i == 3:  # Run at T-3
        await self._check_custom_system()

async def _check_custom_system(self):
    # Your custom validation
    system_ok = await self.check_something()
    
    check = PreflightCheck(
        "custom_check",
        "Custom System Check",
        passed=system_ok,
        message="System ready" if system_ok else "System error"
    )
    
    self._preflight_checks.append(check)
    await self._broadcast_check_result(check)
```

### Add Custom Assets

```python
# In voxel_asset_library.json
{
  "props": [
    "phone", "lamp", "glass", "cake", "horse", "potty",
    "your_custom_prop"  // Add here
  ]
}

# Rebuild catalog
voxel_manager._build_asset_catalog()
```

### Create Custom Scene

```python
scene = voxel_manager.create_scene(
    "my_custom_scene",
    "My Custom Scene",
    "Description here"
)

# Add your assets
scene.add_instance(SceneAssetInstance(
    instance_id="custom_1",
    asset_id="furniture_standard_couch",
    position=[0, 0, 0]
))

# Configure environment
scene.ambient_light = 0.4
scene.camera_position = [5, 2, 5]

# Save
voxel_manager.save_scene_to_file(
    scene.scene_id,
    Path("./scenes/my_custom_scene.json")
)
```

---

## Philosophy: "Feic Mo Chroí" (See My Heart)

Both systems embody the core PubCast AI philosophy: **technology serving human storytelling**.

Professional creators need tools they can trust:

**Studio Control Room** ensures:
- Your audio is being monitored
- Your hardware is verified
- Your recording is being saved
- If something goes wrong, your work is protected

**Voxel Asset System** ensures:
- Your environment is ready
- Your assets are loaded
- Your scene is validated
- Your vision comes to life

**"Local-First, Cloud-Enhanced"** - Critical production control never depends on network connectivity or cloud services.

---

## Next Steps

1. ✅ Run `python setup_studio_control.py`
2. ✅ Integrate with your FastAPI app
3. ✅ Test Studio Control Room (`/studio`)
4. ✅ Build a scene in Scene Builder (`/scene-builder`)
5. ✅ Run a full preflight countdown
6. ✅ Read the comprehensive guides

---

## Support

For issues, questions, or customization help:

1. Check **STUDIO_CONTROL_INTEGRATION.md** for Studio Control troubleshooting
2. Check **VOXEL_SYSTEM_README.md** for Voxel System troubleshooting
3. Review Python logs: `tail -f data/agent_run_log.txt`
4. Check browser console for JavaScript errors
5. Verify WebSocket connection status in Network tab

---

## Credits

**PubCast AI — Complete Studio System**

Designed for creators who need professional-grade production control with broadcast-quality 3D environments.

**"Build your world. Make it safe. Tell your story."** 🎛️🎨

---

*The Iron Core is ready. The scene is set. Let's make magic.*
