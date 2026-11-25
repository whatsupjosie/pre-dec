# 🎭 PubCast AI v7.0 — The Complete System

**The Unified Virtual Production Platform**

---

## What's This?

This is **PubCast AI v7.0** - the complete unified system that integrates everything:

✅ **Studio Control Room** (NEW) - Production control with 5-second preflight countdown  
✅ **Voxel Asset System** (NEW) - 3D environment management with 91 curated assets  
✅ **Pete Enhanced v7** (NEW) - Master orchestrator coordinating all systems  
✅ **Avatar System** - Neon avatars (Lumen, Azure, Nova)  
✅ **Ollama Integration** - Free local AI for bots and agents  
✅ **FastAPI Hub** - Real-time WebSocket infrastructure  
✅ **Autonomous Agent** - Overnight code improvement  

**Package Size:** 78KB  
**Version:** 7.0  
**Release Date:** March 2026  

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Extract the zip
unzip PubCast_AI_v7_Complete.zip
cd pubcast-ai-v7

# 2. Run setup script
python setup_pubcast_v7.py

# 3. Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 4. Start Ollama (separate terminal)
ollama serve
ollama pull gemma4:4b

# 5. Start PubCast AI
python main.py

# 6. Open in browser
http://localhost:8000/studio          # Studio Control Room
http://localhost:8000/scene-builder   # Scene Builder
http://localhost:8000/                # Main Launcher
```

---

## 📦 What's Included

### Core Application Files

| File | Description | Location |
|------|-------------|----------|
| **main_v7.py** | Main application entry point | Rename to `main.py` |
| **pete_enhanced_v7.py** | Pete Enhanced orchestrator | Rename to `pete_enhanced.py` |
| **requirements_v7.txt** | Python dependencies | Rename to `requirements.txt` |
| **.env_example_v7** | Configuration template | Rename to `.env.example` |
| **setup_pubcast_v7.py** | Automated setup script | Run first |

### Studio Control Room (NEW)

| File | Description |
|------|-------------|
| **studio_control.py** | Backend logic → `modules/` |
| **studio_websocket.py** | WebSocket handler → `modules/` |
| **studio_control_room.html** | Control interface → `static/` |

**Features:**
- 5-second preflight countdown with hardware audit
- Audio matrix monitoring (5 channels, 10 Hz)
- Emergency save system (Dead Man's Switch)
- Isolation mode (dialogue-only monitoring)
- Keyboard shortcuts (SPACE, ESC)

### Voxel Asset System (NEW)

| File | Description |
|------|-------------|
| **voxel_asset_manager.py** | Asset manager → `modules/` |
| **voxel_studio_integration.py** | Studio integration → `modules/` |
| **voxel_scene_builder.html** | Scene builder UI → `static/` |
| **voxel_asset_library.json** | 91-asset catalog → `data/` |

**Asset Library:**
- Furniture: 16 items (couch, chair, desk, bookshelf...)
- Home Structure: 14 items (wall, window, door, stairs...)
- Rooms: 9 prefabs (living room, bedroom, kitchen...)
- Outdoor: 10 items (tree, fence, fountain, gazebo...)
- Vehicles: 6 items (car, truck, sports car...)
- Props: 6 items (lamp, phone, glass...)

### Documentation

| File | Description |
|------|-------------|
| **ARCHITECTURE_V7.md** | Complete system architecture (18KB) |
| **DEPLOYMENT_GUIDE_V7.md** | Step-by-step deployment guide (15KB) |
| **STUDIO_CONTROL_INTEGRATION.md** | Studio Control detailed guide (22KB) |
| **VOXEL_SYSTEM_README.md** | Voxel System detailed guide (19KB) |
| **QUICK_REFERENCE.md** | One-page quick reference (5KB) |
| **COMPLETE_SYSTEM_README.md** | Overview of unified system (11KB) |

---

## 🎯 The Integration Story

### Before v7: Fragmented Systems

You had separate pieces:
- Studio Control Room JavaScript (from coding partner)
- Pete Enhanced (twin engine orchestrator)
- Voxel asset library JSON
- Avatar system
- Launcher HTML

### After v7: Unified Platform

Everything works together:

**The 5-Second Countdown (Integrated):**
```
T-5: Countdown starts, audio matrix activates
T-4: Gate Check + Scene Validation (voxel system)
T-3: Countdown continues
T-2: Ghost Mic Detection + Asset Preloading (voxel system)
T-1: Final check
T-0: GO LIVE (scene syncs to Rust engine, recording starts)
```

**The Flow:**
```
User clicks START → Studio Control → Pete Enhanced → Twin Engine
                           ↓              ↓
                    Voxel System    Avatar System
                    (91 assets)     (3 avatars)
                           ↓              ↓
                    Rust Rendering @ 60fps
                           ↓
                    WebRTC Stream to Browser
```

---

## 🏗️ Project Structure

After setup, your project will look like this:

```
pubcast-ai-v7/
├── main.py                           # FastAPI application
├── pete_enhanced.py                  # Master orchestrator
├── requirements.txt                  # Dependencies
├── .env                              # Your configuration
├── .env.example                      # Config template
│
├── modules/                          # Backend modules
│   ├── studio_control.py
│   ├── studio_websocket.py
│   ├── voxel_asset_manager.py
│   ├── voxel_studio_integration.py
│   ├── avatar_system.py
│   ├── avatar_assets.py
│   ├── ollama_adapter.py
│   ├── bots.py
│   ├── hub.py
│   └── recording.py
│
├── static/                           # Frontend
│   ├── studio_control_room.html
│   ├── voxel_scene_builder.html
│   └── pubcast_launcher.html
│
├── data/                             # Persistent data
│   ├── voxel_asset_library.json      # 91 assets
│   ├── avatars/                      # Avatar state
│   ├── scenes/                       # Scene files
│   └── emergency_saves/              # Emergency recovery
│
├── scripts/                          # Helper scripts
│   └── setup_pubcast_v7.py
│
├── logs/                             # Log files
│   └── pubcast.log
│
└── docs/                             # Documentation
    ├── ARCHITECTURE_V7.md
    ├── DEPLOYMENT_GUIDE_V7.md
    ├── STUDIO_CONTROL_INTEGRATION.md
    ├── VOXEL_SYSTEM_README.md
    └── QUICK_REFERENCE.md
```

---

## ⚙️ System Requirements

**Required:**
- Python 3.8 or higher
- Ollama (for local AI)
- 4GB RAM minimum
- 1GB disk space

**Optional (for full functionality):**
- Rust voxel engine (for 60fps rendering)
- Node.js 16+ (for any JS/TS components)

**Tested On:**
- Ubuntu 22.04 LTS
- macOS 12+
- Windows 10/11

---

## 🎬 Example Workflow

### 1. Build Your Scene

Open Scene Builder: `http://localhost:8000/scene-builder`
- Browse 91 assets by category
- Click assets to add to scene
- Configure lighting (ambient, directional, fog)
- Set camera position
- Save scene as JSON

### 2. Start Production

Open Studio Control Room: `http://localhost:8000/studio`
- Press **SPACE** (or click START COUNTDOWN)
- Watch 5-second countdown
- System automatically:
  - Validates scene (T-4)
  - Preloads assets (T-2)
  - Syncs to Rust engine (T-0)
  - Starts recording with audio monitoring
  - Auto-saves every 60 seconds

### 3. Emergency Protection

If something goes wrong:
- Press **ESC**
- System immediately flushes all buffers
- Creates timestamped recovery folder
- Saves complete state for recovery

---

## 🔑 Key Features

### Studio Control Room
✅ **5-Second Preflight** - Mandatory hardware verification  
✅ **Audio Matrix** - Real-time 5-channel monitoring  
✅ **Emergency Save** - Dead Man's Switch (auto-save every 60s)  
✅ **Isolation Mode** - Instant dialogue-only monitoring  
✅ **Local-First** - Core features work offline  
✅ **Keyboard Shortcuts** - SPACE/ESC for quick actions  

### Voxel Asset System
✅ **91-Asset Library** - Curated 3D assets  
✅ **Visual Scene Builder** - Browser-based composition  
✅ **Preflight Integration** - Automatic validation during countdown  
✅ **Preset Scenes** - Detective Office, Living Room ready to use  
✅ **Performance Limits** - Enforced safe limits (1000 instances, 512MB)  
✅ **Pete Integration** - Direct sync with Rust engine  

### Pete Enhanced
✅ **Twin Engine Management** - Coordinates Python + Rust  
✅ **Studio Control Integration** - Executes preflight, manages state  
✅ **Health Monitoring** - Continuous performance tracking  
✅ **Emergency Protocols** - Auto-recovery, emergency saves  
✅ **Avatar Coordination** - Manages neon avatar animations  
✅ **WebRTC Streaming** - 60fps video to browsers  

---

## 📚 Documentation Overview

### Start Here
1. **This README** - Overview and quick start
2. **DEPLOYMENT_GUIDE_V7.md** - Complete deployment walkthrough
3. **setup_pubcast_v7.py** - Run this script first

### Deep Dives
4. **ARCHITECTURE_V7.md** - System architecture and design
5. **STUDIO_CONTROL_INTEGRATION.md** - Studio Control detailed guide
6. **VOXEL_SYSTEM_README.md** - Voxel System detailed guide

### Reference
7. **QUICK_REFERENCE.md** - One-page desk reference

---

## 🛠️ Configuration Quick Reference

**Minimum .env configuration:**
```env
HOST=0.0.0.0
PORT=8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:4b
DATA_DIR=./data
```

**Full configuration:** See `.env.example`

---

## 🐛 Troubleshooting

### Server won't start
```bash
# Check Python version
python --version  # Must be 3.8+

# Activate venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Ollama not found
```bash
# Start Ollama
ollama serve

# Pull model
ollama pull gemma4:4b

# Verify
curl http://localhost:11434/api/tags
```

### WebSocket won't connect
- Check FastAPI is running: `http://localhost:8000/docs`
- Verify `/ws/studio` endpoint exists
- Try `ws://` instead of `wss://` for local dev

**See DEPLOYMENT_GUIDE_V7.md for complete troubleshooting guide.**

---

## 🔄 Migration from Previous Versions

**From v6/alpha:**
1. Extract v7 package to new directory
2. Copy your existing `data/` directory
3. Copy your existing `.env` (update with new variables)
4. Run `python setup_pubcast_v7.py`
5. Test with `python main.py`

**From Studio Control Room v1 + Voxel System v1:**
- v7 includes and integrates both systems
- No migration needed - everything is unified

---

## 📖 Philosophy

**"Feic Mo Chroí" (See My Heart)**

Technology serving human storytelling.

**"Local-First, Cloud-Enhanced"**

Critical production control never depends on network or cloud services.  
The "Iron Core" operates autonomously.  
Pete Enhanced provides orchestration when available.

**If everything else fails, the Iron Core protects your production.**

---

## 🎯 Next Steps

1. **Extract and Setup** - Run `python setup_pubcast_v7.py`
2. **Read Deployment Guide** - DEPLOYMENT_GUIDE_V7.md
3. **Test Studio Control** - Press SPACE, watch countdown
4. **Build a Scene** - Use Scene Builder, add some furniture
5. **Explore Documentation** - ARCHITECTURE_V7.md for deep dive

---

## 🎭 Credits

**PubCast AI v7.0** - The complete unified virtual production platform

**Integrated Systems:**
- Studio Control Room - The "Iron Core" production control
- Voxel Asset System - 3D environment management (91 assets)
- Pete Enhanced - Master orchestrator (twin engine coordinator)
- Avatar System - Neon avatars with personality
- Ollama Integration - Free local AI

**Built with love for creators who need professional-grade tools.**

---

**The complete system is ready. Build your world. Make it safe. Tell your story.** 🎛️🎨🎭
