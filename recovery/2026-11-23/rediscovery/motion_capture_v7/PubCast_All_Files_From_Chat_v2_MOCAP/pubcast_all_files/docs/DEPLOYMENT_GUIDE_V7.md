# PubCast AI v7.0 — Complete Deployment Guide

**The Unified Virtual Production Platform**

---

## Overview

This guide will help you deploy the complete PubCast AI v7.0 system, which integrates:

- ✅ **Studio Control Room** - Production control with preflight validation
- ✅ **Voxel Asset System** - 3D environment management (91 assets)
- ✅ **Pete Enhanced** - Master orchestrator (Twin Engine coordinator)
- ✅ **Avatar System** - Neon avatars (Lumen, Azure, Nova)
- ✅ **Ollama Integration** - Free local AI for bots and agents
- ✅ **FastAPI Hub** - Real-time WebSocket infrastructure
- ✅ **Autonomous Agent** - Overnight code improvement

---

## Prerequisites

### Required Software

1. **Python 3.8+**
   ```bash
   python --version  # Should be 3.8 or higher
   ```

2. **Ollama** (for local AI)
   ```bash
   # Install from https://ollama.ai
   ollama serve  # Start Ollama server
   ollama pull gemma4:4b  # Download model
   ```

3. **Git** (for version control)
   ```bash
   git --version
   ```

### Optional (for full functionality)

4. **Rust Voxel Engine** (for 60fps rendering)
   - Requires Rust compiler
   - See rust-voxel-engine/ directory

5. **Node.js 16+** (if using any JS/TS components)
   ```bash
   node --version
   ```

---

## Installation Steps

### 1. Create Project Structure

```bash
# Create main directory
mkdir pubcast-ai-v7
cd pubcast-ai-v7

# Create subdirectories
mkdir -p modules static data logs scripts docs tests
mkdir -p data/avatars data/scenes data/emergency_saves
```

### 2. Place Core Files

Copy these files to the appropriate locations:

```
pubcast-ai-v7/
├── main_v7.py                        → main.py (root)
├── pete_enhanced_v7.py               → pete_enhanced.py (root)
├── requirements_v7.txt               → requirements.txt (root)
├── .env_example_v7                   → .env.example (root)
│
├── modules/
│   ├── studio_control.py
│   ├── studio_websocket.py
│   ├── voxel_asset_manager.py
│   ├── voxel_studio_integration.py
│   ├── avatar_system.py
│   ├── avatar_assets.py
│   ├── ollama_adapter.py
│   ├── bots.py
│   ├── hub.py
│   ├── recording.py
│   └── bridge.py
│
├── static/
│   ├── studio_control_room.html
│   ├── voxel_scene_builder.html
│   └── pubcast_launcher.html
│
├── data/
│   └── voxel_asset_library.json
│
├── scripts/
│   ├── pubcast_agent.py
│   ├── pubcast_organizer.py
│   └── setup_studio_control.py
│
└── docs/
    ├── ARCHITECTURE_V7.md
    ├── STUDIO_CONTROL_INTEGRATION.md
    ├── VOXEL_SYSTEM_README.md
    └── QUICK_REFERENCE.md
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Minimum required changes in .env:**
```env
# Verify Ollama is configured
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:4b

# Set your data directory
DATA_DIR=./data
```

### 5. Verify Ollama Installation

```bash
# Start Ollama (in separate terminal)
ollama serve

# Pull required model
ollama pull gemma4:4b

# Test Ollama
curl http://localhost:11434/api/tags
```

You should see a list of installed models including `gemma4:4b`.

---

## Starting PubCast AI

### Option 1: Quick Start (Development)

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Start PubCast AI
python main.py
```

You should see:
```
🎭 PubCast AI v7.0 - Startup Complete
═══════════════════════════════════════
🌐 Studio Control Room: http://0.0.0.0:8000/studio
🎨 Scene Builder: http://0.0.0.0:8000/scene-builder
🚀 Main Launcher: http://0.0.0.0:8000/
📚 API Docs: http://0.0.0.0:8000/docs
═══════════════════════════════════════
```

### Option 2: Production Deployment

```bash
# Install production server
pip install gunicorn

# Start with Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Option 3: Background Service (Linux)

Create systemd service file `/etc/systemd/system/pubcast.service`:

```ini
[Unit]
Description=PubCast AI v7.0
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/pubcast-ai-v7
Environment="PATH=/path/to/pubcast-ai-v7/venv/bin"
ExecStart=/path/to/pubcast-ai-v7/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pubcast
sudo systemctl start pubcast
sudo systemctl status pubcast
```

---

## First Run Checklist

After starting PubCast AI, verify everything works:

### 1. Check Main Launcher
- Navigate to: `http://localhost:8000/`
- Should see PubCast launcher interface

### 2. Test Studio Control Room
- Navigate to: `http://localhost:8000/studio`
- Should see:
  - Audio Matrix (5 channels)
  - START COUNTDOWN button
  - Preflight checks section
  - System metrics
- Press **SPACE** key - should start 5-second countdown
- Press **ESC** during countdown - should trigger emergency save

### 3. Test Scene Builder
- Navigate to: `http://localhost:8000/scene-builder`
- Should see:
  - Asset library (91 items)
  - Category tabs (furniture, structures, rooms, etc.)
  - Scene viewport
  - Properties panel
- Click an asset - should add to scene
- Click "Validate for Preflight" - should show validation results

### 4. Check API Endpoints
- Navigate to: `http://localhost:8000/docs`
- Should see FastAPI interactive documentation
- Test endpoints:
  - GET `/api/status` - System status
  - GET `/api/avatars/presets` - Avatar presets
  - GET `/api/scenes` - Scene list
  - GET `/api/assets` - Asset library

### 5. Verify Logs
```bash
# Check main log file
tail -f logs/pubcast.log

# Should see initialization messages
# Look for "✅" success indicators
# No "❌" or "💥" error indicators
```

---

## Testing The Complete Workflow

### Test 1: Complete Recording Session

1. **Build a Scene**
   - Open Scene Builder: `http://localhost:8000/scene-builder`
   - Add some furniture (couch, chair, table)
   - Add a lamp (prop)
   - Configure lighting (ambient = 0.4)
   - Click "Validate for Preflight" - should pass
   - Save scene as "test_scene.json"

2. **Start Recording**
   - Open Studio Control Room: `http://localhost:8000/studio`
   - Press **SPACE** or click "START COUNTDOWN"
   - Watch the countdown:
     - T-5: Countdown starts
     - T-4: **Scene Validation** runs (voxel system)
     - T-3: Countdown continues
     - T-2: **Asset Preloading** runs (voxel system)
     - T-1: Final check
     - T-0: Goes LIVE
   - Verify:
     - Audio meters are updating
     - Recording timer is running
     - System is in LIVE state

3. **Test Emergency Save**
   - Press **ESC** key
   - Should trigger immediate emergency save
   - Check `data/emergency_saves/` for timestamped folder
   - Should contain:
     - `audio_matrix.json`
     - `preflight_checks.json`
     - `recovery_manifest.json`

### Test 2: Keyboard Shortcuts

- **SPACE** (when IDLE) - Start countdown ✅
- **ESC** (when LIVE) - Emergency save ✅

### Test 3: WebSocket Communication

```javascript
// Open browser console on Studio Control page
// Should see WebSocket connection messages
const ws = new WebSocket('ws://localhost:8000/ws/studio');
ws.onmessage = (event) => console.log('Received:', JSON.parse(event.data));
```

---

## Troubleshooting

### Issue: Server Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Verify virtual environment is activated
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt
```

---

### Issue: Ollama Not Found

**Error:** `🎭 Pete: Ollama not available`

**Solution:**
```bash
# Start Ollama server
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags

# Pull model
ollama pull gemma4:4b
```

---

### Issue: WebSocket Won't Connect

**Error:** Browser console shows "WebSocket connection failed"

**Solution:**
1. Check FastAPI is running: `http://localhost:8000/docs`
2. Verify `/ws/studio` endpoint exists
3. Check firewall isn't blocking WebSocket
4. Try `ws://` instead of `wss://` for local development

---

### Issue: Scene Validation Fails

**Error:** "Scene validation failed: Scene too complex"

**Solution:**
- Reduce instance count (max 1000)
- Use room prefabs instead of individual furniture
- Check estimated memory usage (max 512MB)
- Review VOXEL_SYSTEM_README.md for limits

---

### Issue: Audio Meters Not Updating

**Error:** Audio Matrix shows all channels at -60dB

**Solution:**
- This is expected if no actual audio recording is active
- Meters update from recording pipeline
- In demo mode, meters simulate audio
- See studio_control.py `start_audio_simulation()`

---

## Advanced Configuration

### Custom Scenes

Create custom scenes programmatically:

```python
# In Python REPL or script
from pathlib import Path
from modules.voxel_asset_manager import VoxelAssetManager, SceneAssetInstance

# Load manager
voxel_manager = VoxelAssetManager(Path("./data/voxel_asset_library.json"))

# Create scene
scene = voxel_manager.create_scene(
    "my_custom_scene",
    "My Custom Scene",
    "Description here"
)

# Add assets
scene.add_instance(SceneAssetInstance(
    instance_id="desk_1",
    asset_id="furniture_standard_desk",
    position=[0, 0, 0]
))

scene.add_instance(SceneAssetInstance(
    instance_id="chair_1",
    asset_id="furniture_standard_chair",
    position=[0, 0, 1.5]
))

# Configure environment
scene.ambient_light = 0.3
scene.camera_position = [5, 2, 5]

# Save
voxel_manager.save_scene_to_file(
    scene.scene_id,
    Path("./data/scenes/my_custom_scene.json")
)
```

### Custom Preflight Checks

Add custom checks in `studio_control.py`:

```python
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

---

## Performance Optimization

### Monitor System Performance

```bash
# Watch Pete's health status
curl http://localhost:8000/api/status | jq '.pete_status'

# Watch system metrics
watch -n 1 'curl -s http://localhost:8000/api/status | jq ".pete_status.metrics"'
```

### Optimize for Your Hardware

**Low-End Systems:**
```env
# In .env
MAX_SCENE_INSTANCES=500
MAX_SCENE_MEMORY_MB=256
ENABLE_ADAPTIVE_QUALITY=true
AUDIO_UPDATE_INTERVAL=0.2  # 5 Hz instead of 10 Hz
```

**High-End Systems:**
```env
MAX_SCENE_INSTANCES=2000
MAX_SCENE_MEMORY_MB=1024
ENABLE_ADAPTIVE_QUALITY=false
AUDIO_UPDATE_INTERVAL=0.05  # 20 Hz for ultra-smooth
```

---

## Backup and Recovery

### Automatic Emergency Saves

Emergency saves are created in `data/emergency_saves/` with timestamp:
```
emergency_20260309_123456/
├── audio_matrix.json
├── preflight_checks.json
├── recovery_manifest.json
└── [buffers from Pete]
```

### Manual Backup

```bash
# Backup entire data directory
tar -czf pubcast-backup-$(date +%Y%m%d).tar.gz data/

# Backup just scenes
tar -czf scenes-backup-$(date +%Y%m%d).tar.gz data/scenes/

# Backup configuration
cp .env .env.backup-$(date +%Y%m%d)
```

### Recovery from Emergency Save

```bash
# List emergency saves
ls -lth data/emergency_saves/

# Examine recovery manifest
cat data/emergency_saves/emergency_TIMESTAMP/recovery_manifest.json

# Restore scene
cp data/emergency_saves/emergency_TIMESTAMP/scene_*.json data/scenes/
```

---

## Next Steps

### Phase 1: Get Comfortable

1. ✅ Deploy PubCast AI v7
2. ✅ Test Studio Control Room
3. ✅ Build a few scenes
4. ✅ Run complete preflight countdown
5. ✅ Test emergency save

### Phase 2: Customize

1. Create custom scenes for your shows
2. Add custom preflight checks
3. Configure audio matrix for your hardware
4. Customize avatar presets

### Phase 3: Production

1. Set up Rust voxel engine for 60fps rendering
2. Configure WebRTC streaming
3. Set up systemd service for auto-start
4. Configure cloud backups
5. Set up monitoring and alerts

---

## Support and Documentation

### Documentation Files

- **ARCHITECTURE_V7.md** - Complete system architecture
- **STUDIO_CONTROL_INTEGRATION.md** - Studio Control detailed guide
- **VOXEL_SYSTEM_README.md** - Voxel System detailed guide
- **QUICK_REFERENCE.md** - Quick reference card

### Log Files

- **logs/pubcast.log** - Main application log
- Check for "✅" (success) and "❌" (error) markers

### Health Check

```bash
# Quick health check
curl http://localhost:8000/health

# Full system status
curl http://localhost:8000/api/status | jq
```

---

## Credits

**PubCast AI v7.0** - The unified virtual production platform

**Integrated Systems:**
- Studio Control Room - The "Iron Core"
- Voxel Asset System - 3D environment management
- Pete Enhanced - Master orchestrator
- Avatar System - Neon avatars with personality
- Ollama Integration - Free local AI

**Philosophy:** "Feic Mo Chroí" (See My Heart)

Technology serving human storytelling.

---

**🎭 The complete system is ready. Build your world. Make it safe. Tell your story.**
