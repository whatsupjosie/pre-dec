# PubCast AI — Unified System Architecture v7.0

**"Feic Mo Chroí" (See My Heart) — Technology Serving Human Storytelling**

---

## System Overview

PubCast AI is a professional virtual production platform combining:
- **Studio Control Room** - Broadcast-quality production control with preflight validation
- **Voxel Asset System** - Complete 3D environment management (91 assets)
- **Pete Enhanced** - Twin-engine orchestrator (Python + Rust) with WebRTC streaming
- **Avatar System** - Neon avatars with real-time animation (Lumen, Azure, Nova)
- **Ollama Integration** - Local AI for bots and agents (free-tier solution)
- **FastAPI Hub** - Real-time WebSocket communication infrastructure
- **Autonomous Agent** - Overnight maintenance and code improvement system

---

## Architecture Layers

```
┌────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │Studio Control│  │Scene Builder │  │PubCast Launcher      │     │
│  │Room (HTML)   │  │(HTML)        │  │(HTML)                │     │
│  └──────────────┘  └──────────────┘  └──────────────────────┘     │
└───────────────────────────┬────────────────────────────────────────┘
                            │ WebSocket / HTTP
┌───────────────────────────▼────────────────────────────────────────┐
│                      FASTAPI HUB LAYER                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • WebSocket Manager (real-time communication)               │  │
│  │  • Studio Control WebSocket (/ws/studio)                     │  │
│  │  • Scene Builder API                                         │  │
│  │  • Avatar System API                                         │  │
│  │  • Bot Chat API                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────┬────────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────────┐
│                    PETE ENHANCED ORCHESTRATOR                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  COORDINATION LAYER                                          │  │
│  │  • Studio Control Integration                                │  │
│  │  • Voxel Scene Management                                    │  │
│  │  • Avatar Animation Coordination                             │  │
│  │  • Twin Engine Health Monitoring                             │  │
│  │  • Emergency Protocols                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │Studio Control  │  │Voxel Asset      │  │Avatar System     │   │
│  │- Audio Matrix  │  │- 91 Assets      │  │- Neon Avatars    │   │
│  │- Preflight     │  │- Scene Composer │  │- Animations      │   │
│  │- Emergency Save│  │- Validation     │  │- Voice Profiles  │   │
│  └────────────────┘  └─────────────────┘  └──────────────────┘   │
└───────────────────────────┬────────────────────────────────────────┘
                            │
        ┌───────────────────┴──────────────────┐
        ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  PYTHON ENGINE      │              │  RUST VOXEL ENGINE  │
│  • FastAPI Server   │◄─ Bridge ───►│  • 60fps Rendering  │
│  • Recording        │              │  • GPU Acceleration │
│  • Audio Mix        │              │  • Scene Rendering  │
│  • Bot Intelligence │              │  • Physics          │
│  • Ollama Interface │              └─────────┬───────────┘
└─────────────────────┘                        │
                                               │ WebRTC
                                               ▼
                                      ┌─────────────────────┐
                                      │ BROWSER DISPLAY     │
                                      │ • 60fps Stream      │
                                      │ • Real-time Avatar  │
                                      │ • Interactive View  │
                                      └─────────────────────┘
```

---

## Core Systems

### 1. Studio Control Room (The "Iron Core")

**Purpose:** Production-grade live control with safety protocols

**Components:**
- **Audio Matrix** - 5-channel monitoring (Mic Inputs, Dialogue, Studio Feed, System Audio, Room Noise)
- **5-Second Preflight Countdown** - Hardware verification before recording
  - T-5: Start countdown
  - T-4: Gate Check + Scene Validation
  - T-3: Countdown
  - T-2: Ghost Mic Detection + Asset Preloading
  - T-1: Final check
  - T-0: GO LIVE
- **Emergency Save System** - Dead Man's Switch (auto-save every 60s)
- **Isolation Mode** - Instant dialogue-only audio monitoring

**Key Files:**
- `modules/studio_control.py` - Backend logic
- `modules/studio_websocket.py` - WebSocket handler
- `static/studio_control_room.html` - Control interface

**Philosophy:** Local-first logic. Core safety features work even if AI/network fails.

---

### 2. Voxel Asset System

**Purpose:** Complete 3D environment management for virtual production

**Asset Library:** 91 curated assets
- Furniture: 16 items (standard + fancy)
- Home Structure: 14 items (walls, windows, doors, etc.)
- Rooms: 9 prefabs (living room, bedroom, kitchen, etc.)
- Outdoor: 10 items (trees, fences, fountains, etc.)
- Vehicles: 6 items (cars, trucks, sports cars)
- Props: 6 items (lamp, phone, glass, etc.)

**Components:**
- **VoxelAssetManager** - Asset catalog and scene composition
- **Scene Builder** - Visual composition tool (HTML interface)
- **Voxel Studio Integration** - Hooks into Studio Control preflight
- **Pete Integration** - Syncs scenes to Rust voxel engine

**Preflight Integration:**
- **T-4:** Scene validation (instance count, memory usage, missing assets)
- **T-2:** Asset preloading (all 3D models loaded before recording)

**Key Files:**
- `modules/voxel_asset_manager.py` - Asset manager
- `modules/voxel_studio_integration.py` - Studio Control integration
- `static/voxel_scene_builder.html` - Scene builder UI
- `data/voxel_asset_library.json` - Asset catalog

---

### 3. Pete Enhanced (The Orchestrator)

**Purpose:** Coordinates entire twin-engine system with production intelligence

**Responsibilities:**
- **Twin Engine Management** - Coordinates Python backend + Rust voxel engine
- **Studio Control Integration** - Executes preflight checks, manages state transitions
- **Voxel Scene Coordination** - Loads scenes, syncs to Rust engine
- **Avatar Animation** - Coordinates neon avatar movements and expressions
- **WebRTC Streaming** - Manages 60fps video stream to browsers
- **System Health Monitoring** - Tracks performance, triggers optimizations
- **Emergency Protocols** - Handles crashes, auto-recovery, emergency saves

**Performance Tiers:**
- **PERFECT** - <16ms total latency, all systems optimal
- **EXCELLENT** - <33ms total latency, all systems healthy
- **GOOD** - <50ms total latency, minor issues
- **DEGRADED** - <100ms total latency, performance issues
- **CRITICAL** - >100ms latency, major issues
- **EMERGENCY** - System failure imminent, emergency protocols active

**Key Files:**
- `pete_enhanced.py` - Enhanced orchestrator
- `modules/pete_core.py` - Base Pete functionality

**Integration Points:**
```python
class PeteEnhanced:
    # Studio Control
    async def execute_preflight_sequence()
    async def on_studio_live()
    async def on_studio_emergency()
    
    # Voxel System
    async def load_voxel_scene(scene_data)
    async def validate_scene()
    async def preload_scene_assets()
    
    # Avatar System
    async def animate_avatar(avatar_id, animation)
    async def update_avatar_expression(mood)
    
    # Twin Engine
    async def monitor_rust_engine()
    async def sync_bridge_commands()
    async def stream_webrtc_frames()
```

---

### 4. Avatar System

**Purpose:** Neon avatar management with personality and animation

**Avatars:**
- **Lumen** - Radiant neon-yellow host (bright, happy, classic smile)
- **Azure** - Cool neon-blue (mellow, playful wink)
- **Nova** - Neon pink (warm, expressive, ponytail)

**Features:**
- Real-time skeletal animation
- Voice profile matching
- Mood system (happy, mischief, warm, neutral)
- Accessories (hats, glasses, earrings)
- Features (lashes, hair variations)
- Halo animation (clockwise/counter-clockwise)

**Key Files:**
- `modules/avatar_system.py` - Avatar state management
- `modules/avatar_assets.py` - Asset loading and manifests

---

### 5. Ollama Integration (Free-Tier AI)

**Purpose:** Local AI for bots and agents without paid APIs

**Supported Models:**
- gemma4:4b (preferred)
- mistral
- llama3
- phi3

**Use Cases:**
- **Bot Intelligence** - AI-powered chat bots in stream
- **Agent System** - Autonomous code improvement overnight
- **Voice Cues** - Generate countdown announcements
- **Scene Analysis** - Smart asset recommendations

**Key Files:**
- `modules/ollama_adapter.py` - Async Ollama interface
- `modules/bots.py` - Bot personality system

**Configuration:**
```env
BOT_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:4b
OLLAMA_TIMEOUT=60
```

---

### 6. FastAPI Hub

**Purpose:** Real-time communication infrastructure

**Endpoints:**
- `/ws/studio` - Studio Control Room WebSocket
- `/ws/chat` - Bot chat WebSocket
- `/ws/scene` - Scene Builder updates
- `/api/avatars` - Avatar API
- `/api/scenes` - Scene management API
- `/studio` - Studio Control Room interface
- `/scene-builder` - Scene Builder interface
- `/` - Main PubCast launcher

**Key Files:**
- `main.py` - FastAPI application
- `modules/hub.py` - WebSocket hub manager

---

### 7. Autonomous Agent System

**Purpose:** Overnight code improvement and maintenance

**Capabilities:**
- File organization and cleanup
- Dependency analysis
- Gap identification
- Code improvements
- Ollama-powered analysis
- Safe backup-before-modify

**Key Files:**
- `scripts/pubcast_agent.py` - Autonomous agent
- `scripts/pubcast_organizer.py` - File organizer

---

## Data Flow Examples

### Recording Session Start

```
1. User clicks "START COUNTDOWN" in Studio Control Room
   └─► WebSocket → studio_websocket.py
       └─► StudioControl.run_preflight_sequence()
           ├─► T-5: Countdown starts
           ├─► T-4: Pete.validate_scene() + Gate Check
           │   └─► VoxelAssetManager.validate_scene_for_preflight()
           ├─► T-3: Countdown continues
           ├─► T-2: Pete.preload_assets() + Ghost Mic Detection
           │   └─► VoxelAssetManager.preload_scene_assets()
           │       └─► Pete.sync_scene_to_rust_engine()
           ├─► T-1: Final check
           └─► T-0: GO LIVE
               ├─► Studio transitions to LIVE state
               ├─► Dead Man's Switch activates
               ├─► Audio matrix monitors in real-time
               ├─► Rust engine renders scene at 60fps
               └─► WebRTC streams to browser
```

### Emergency Save

```
1. User presses ESC or system detects failure
   └─► StudioControl.trigger_emergency_save()
       ├─► Immediately flush all buffers
       ├─► Save audio matrix state
       ├─► Save preflight check history
       ├─► Pete.emergency_flush_buffers()
       │   ├─► Save all audio tracks to disk
       │   ├─► Save voxel scene state
       │   └─► Save avatar positions/states
       ├─► Create timestamped recovery folder
       └─► Generate recovery manifest
```

### Scene Composition

```
1. User builds scene in Scene Builder
   ├─► Click asset → add to scene
   ├─► Configure lighting/camera
   └─► Save scene JSON

2. Scene loaded in Python
   └─► VoxelAssetManager.load_scene_from_file()
       └─► scene.required_assets = [asset1, asset2, ...]

3. Preflight validates scene (T-4)
   └─► Check instance count < 1000
   └─► Check memory < 512MB
   └─► Verify all assets exist

4. Assets preload (T-2)
   └─► VoxelAssetManager.preload_scene_assets()
       └─► Pete.sync_scene_to_rust_engine()
           └─► Rust engine loads voxels
           └─► Ready for 60fps rendering

5. Recording starts (T-0)
   └─► Scene renders in real-time
   └─► WebRTC streams to browser
```

---

## Configuration

### Environment Variables

```env
# Server
HOST=0.0.0.0
PORT=8000

# Ollama (Local AI)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:4b
BOT_PROVIDER=ollama

# Pete Enhanced
RUST_ENGINE_HOST=localhost
RUST_ENGINE_PORT=9000
WEBRTC_STREAM_URL=ws://localhost:8001/stream

# Studio Control
DEAD_MAN_SWITCH_INTERVAL=60.0
AUDIO_UPDATE_INTERVAL=0.1
ENABLE_VOICE_CUES=true
COUNTDOWN_VOICE=pete

# Voxel System
MAX_SCENE_INSTANCES=1000
MAX_SCENE_MEMORY_MB=512
VOXEL_LIBRARY_PATH=./data/voxel_asset_library.json

# Avatar System
DEFAULT_AVATAR=neon_yellow_a
AVATAR_DATA_DIR=./data/avatars

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/pubcast.log
```

---

## Project Structure

```
pubcast-ai/
├── main.py                              # FastAPI application entry point
├── pete_enhanced.py                     # Pete Enhanced orchestrator
├── requirements.txt                     # Python dependencies
├── .env                                 # Environment configuration
│
├── modules/                             # Core backend modules
│   ├── hub.py                           # WebSocket hub manager
│   ├── studio_control.py                # Studio Control Room backend
│   ├── studio_websocket.py              # Studio Control WebSocket
│   ├── voxel_asset_manager.py           # Voxel asset management
│   ├── voxel_studio_integration.py      # Voxel + Studio integration
│   ├── avatar_system.py                 # Avatar management
│   ├── avatar_assets.py                 # Avatar asset loading
│   ├── ollama_adapter.py                # Ollama AI interface
│   ├── bots.py                          # Bot personality system
│   ├── recording.py                     # Audio/video recording
│   └── bridge.py                        # Rust engine bridge
│
├── static/                              # Frontend assets
│   ├── studio_control_room.html         # Studio Control interface
│   ├── voxel_scene_builder.html         # Scene Builder interface
│   ├── pubcast_launcher.html            # Main launcher
│   ├── css/                             # Stylesheets
│   ├── js/                              # JavaScript
│   └── assets/                          # Images, fonts
│
├── data/                                # Persistent data
│   ├── voxel_asset_library.json         # 91-asset catalog
│   ├── avatars/                         # Avatar state files
│   ├── scenes/                          # Scene JSON files
│   ├── emergency_saves/                 # Emergency recovery data
│   └── users.db                         # User database
│
├── scripts/                             # Helper scripts
│   ├── pubcast_agent.py                 # Autonomous agent
│   ├── pubcast_organizer.py             # File organizer
│   └── setup_studio_control.py          # Setup script
│
├── logs/                                # Log files
│   └── pubcast.log
│
├── docs/                                # Documentation
│   ├── ARCHITECTURE.md                  # This file
│   ├── STUDIO_CONTROL_INTEGRATION.md    # Studio Control guide
│   ├── VOXEL_SYSTEM_README.md           # Voxel System guide
│   └── QUICK_REFERENCE.md               # Quick reference
│
└── tests/                               # Test suite
    ├── test_studio_control.py
    ├── test_voxel_system.py
    └── test_pete_enhanced.py
```

---

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| **Total Pipeline Latency** | <33ms | <100ms |
| **Rust Engine FPS** | 60fps | >30fps |
| **WebRTC Stream FPS** | 60fps | >30fps |
| **Audio Monitoring Rate** | 10 Hz | 5 Hz |
| **Preflight Countdown** | 5.0s | N/A |
| **Emergency Save Time** | <2s | <5s |
| **Scene Validation Time** | <1s | <3s |
| **Asset Preload Time** | <3s | <5s |

---

## Safety Protocols

### Emergency Save Triggers
- Manual (ESC key or button)
- Automatic (Dead Man's Switch every 60s)
- System crash detected
- Memory limit exceeded
- Latency critical threshold
- Rust engine disconnected

### Recovery Procedures
1. Emergency save creates timestamped folder
2. All buffers flushed to disk immediately
3. Complete system state preserved
4. Recovery manifest generated
5. User can resume from last checkpoint

### Failsafe Modes
- **Studio Control** - Local-first, works offline
- **Pete Enhanced** - Continues with limited functionality if subsystems fail
- **Voxel System** - Scenes cached locally
- **Audio Matrix** - Continues monitoring even if recording fails

---

## Deployment

### Prerequisites
- Python 3.8+
- Node.js 16+ (for Rust engine bridge)
- Ollama installed and running
- Rust voxel engine compiled

### Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/pubcast-ai.git
cd pubcast-ai

# 2. Install Python dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Run setup script
python scripts/setup_studio_control.py

# 5. Start Ollama
ollama serve

# 6. Start Rust voxel engine (in separate terminal)
cd rust-voxel-engine
cargo run --release

# 7. Start PubCast AI
python main.py
```

### Access Points
- **Main Launcher:** http://localhost:8000
- **Studio Control Room:** http://localhost:8000/studio
- **Scene Builder:** http://localhost:8000/scene-builder
- **API Docs:** http://localhost:8000/docs

---

## Future Enhancements

### Phase 1 (Current)
- ✅ Studio Control Room with preflight
- ✅ Voxel Asset System with 91 assets
- ✅ Pete Enhanced orchestration
- ✅ Avatar system with 3 neon avatars
- ✅ Ollama integration for free-tier AI
- ✅ Emergency save protocols

### Phase 2 (Next)
- [ ] Multi-camera support
- [ ] Advanced avatar expressions (Detective Humphrey)
- [ ] Scene animation system (camera paths)
- [ ] Cloud backup integration
- [ ] Analytics dashboard
- [ ] Mobile app for remote monitoring

### Phase 3 (Future)
- [ ] Multi-user collaboration
- [ ] Cloud rendering fallback
- [ ] AI-assisted scene composition
- [ ] Advanced physics simulation
- [ ] VR headset support
- [ ] Professional OBS integration

---

## Credits

**PubCast AI v7.0** - The unified virtual production platform

**Systems:**
- Studio Control Room - The "Iron Core"
- Voxel Asset System - 3D environment management
- Pete Enhanced - Twin-engine orchestrator
- Avatar System - Neon avatars with personality
- Ollama Integration - Free-tier local AI

**Philosophy:** "Feic Mo Chroí" (See My Heart) - Technology serving human storytelling

**Architecture:** Local-first, cloud-enhanced. Critical systems never depend on network or cloud services.

---

*The complete system is ready. Build your world. Make it safe. Tell your story.* 🎛️🎨🎭
