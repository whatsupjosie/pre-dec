# Studio Control Room - Quick Reference Card

**🎛️ The "Iron Core" Production Control System**

---

## Files Overview

| File | Purpose | Location After Setup |
|------|---------|---------------------|
| `studio_control.py` | Python backend module | `modules/` |
| `studio_websocket.py` | WebSocket handler | `modules/` |
| `studio_control_room.html` | Control interface | `static/` |
| `setup_studio_control.py` | Quick start script | Root (run once) |
| `STUDIO_CONTROL_INTEGRATION.md` | Full guide | Documentation |
| `README.md` | Overview | Documentation |

---

## 30-Second Setup

```bash
# 1. Run setup
python setup_studio_control.py

# 2. Add to your main.py (code will be shown by setup script)

# 3. Restart server
python main.py

# 4. Open browser
http://localhost:8000/studio
```

---

## Keyboard Shortcuts

| Key | Action | When |
|-----|--------|------|
| **SPACE** | Start countdown | IDLE state |
| **ESC** | Emergency save | LIVE state |

---

## The 5-Second Countdown

```
T-5: Countdown starts
T-4: Gate Check (hardware verification)
T-3: (available for custom checks)
T-2: Ghost Mic Detection
T-1: Final check
T-0: LIVE - Recording starts
```

---

## Audio Matrix (5 Channels)

1. **Microphone Inputs** - Physical USB/XLR mics
2. **Dialogue Track** - Processed speech
3. **Studio Feed** - SFX/music/background
4. **System Audio** - Desktop sounds
5. **Room Noise** - Ambient monitoring

---

## Key Features

✅ **5-Second Preflight** - Mandatory pre-recording checks
✅ **Audio Matrix** - Real-time 5-channel monitoring
✅ **Emergency Save** - Dead Man's Switch (auto-save every 60s)
✅ **Isolation Mode** - Instant dialogue-only monitoring
✅ **Local-First** - Works even if AI/network is offline
✅ **WebSocket Sync** - Real-time browser ↔ Python

---

## Emergency Save Locations

When Dead Man's Switch triggers:
```
data/emergency_saves/
└── emergency_20260309_123456/
    ├── audio_matrix.json
    ├── preflight_checks.json
    ├── recovery_manifest.json
    └── [audio/video buffers via Pete]
```

---

## Integration Points with Pete

```python
# Pete Enhanced needs these methods:

async def speak_voice_cue(text: str, voice: str = "pete"):
    """AI countdown voice"""
    pass

async def emergency_flush_buffers(save_path: Path):
    """Save everything NOW"""
    pass

async def get_connected_audio_devices():
    """List hardware for Gate Check"""
    pass
```

---

## WebSocket Commands

```json
// Start countdown
{"command": "start_preflight"}

// Stop recording
{"command": "stop_recording"}

// Emergency save
{"command": "emergency_save", "reason": "Manual"}

// Isolation mode
{"command": "mute_all_but_dialogue"}

// Toggle channel
{"command": "toggle_channel", "channel_id": "mic_inputs", "active": false}
```

---

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| WebSocket won't connect | Check FastAPI running, verify /ws/studio endpoint |
| No countdown | Check Python logs, verify WebSocket connected |
| No audio meters | Call `update_audio_channel()` from recording pipeline |
| Emergency save fails | Check `data/emergency_saves/` exists and is writable |

---

## Configuration Quick Reference

```python
StudioControl(hub, pete, data_dir, config={
    "dead_man_switch_interval": 60.0,  # Auto-save interval
    "audio_update_interval": 0.1,      # Monitor rate (10 Hz)
    "enable_voice_cues": True,         # AI countdown
    "countdown_voice": "pete",         # Which AI voice
})
```

---

## States & Transitions

```
IDLE ──(START)──► PREFLIGHT ──(Auto)──► LIVE ──(STOP)──► IDLE
  │                                        │
  │                                        ▼
  └────────────────────────────────── EMERGENCY
                                           │
                                           ▼
                                         IDLE
```

---

## Production Checklist

Before going live:
- [ ] Test countdown 10+ times
- [ ] Verify audio meters update
- [ ] Test emergency save
- [ ] Confirm auto-save works
- [ ] Check WebSocket reconnects
- [ ] Test keyboard shortcuts
- [ ] Verify ghost mic detection
- [ ] Load test multiple clients

---

## Key Philosophy

**"Local-First, Cloud-Enhanced"**

The Iron Core runs autonomously. Critical safety features **NEVER** depend on:
- Network connectivity
- Cloud services
- AI availability

**If everything else fails, the Iron Core protects your production.**

---

## Documentation Links

- **README.md** - Overview and quick start
- **STUDIO_CONTROL_INTEGRATION.md** - Complete integration guide
- **setup_studio_control.py** - Automated setup script

---

## Common Customizations

### Add Preflight Check
```python
if i == 3:
    await self._check_custom_system()
```

### Add Audio Channel
```python
@dataclass
class AudioMatrix:
    # ... existing ...
    new_channel: AudioChannel = field(...)
```

### Custom Emergency Action
```python
async def trigger_emergency_save(self, reason):
    # ... standard save ...
    await self.custom_emergency_action()
```

---

**🎬 "The show must go on. The Iron Core makes sure it does."**

---

*Feic Mo Chroí (See My Heart) - Technology serving human storytelling.*
