# Studio Control Room - Integration Guide

**Production-Grade Live Control for PubCast AI**

---

## Overview

The **Studio Control Room** is the "Iron Core" production control layer for PubCast AI. It provides broadcast-quality live production management with:

- **Audio Matrix Monitoring** (5 channels: Mic Inputs, Dialogue, Studio Feed, System Audio, Room Noise)
- **5-Second Preflight Countdown** with hardware audit (Gate Check, Ghost Mic detection)
- **Emergency Save Protocols** (Dead Man's Switch)
- **Local-First Logic** - Core safety features work even offline
- **Real-Time WebSocket Integration** with Pete Enhanced orchestration

### Philosophy: "Local-First, Cloud-Enhanced"

Critical production control **NEVER** requires cloud AI. All core safety features (emergency save, audio monitoring, preflight checks) work independently. Pete Enhanced provides orchestration and intelligence, but the Iron Core operates autonomously.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  STUDIO CONTROL ROOM                         │
│                  (Browser Interface)                         │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐   │
│  │Audio Matrix│  │ Countdown  │  │ Preflight Checks    │   │
│  │5 Channels  │  │ Display    │  │ Gate/Ghost Detection│   │
│  └────────────┘  └────────────┘  └─────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket (Real-time)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              STUDIO CONTROL BACKEND                          │
│                (studio_control.py)                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • StudioControl: Core production logic                │  │
│  │ • AudioMatrix: 5-channel monitoring                   │  │
│  │ • PreflightSequence: 5-second countdown + audits      │  │
│  │ • EmergencySave: Dead Man's Switch                    │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               PETE ENHANCED ORCHESTRATOR                     │
│             (pete_enhanced.py)                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • Twin Engine Management (Python + Rust)              │  │
│  │ • WebRTC Streaming Coordination                       │  │
│  │ • AI Voice Cues (TTS integration)                     │  │
│  │ • System Health Monitoring                            │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌───────────────┐            ┌─────────────────┐
│  VOXEL ENGINE │            │  AUDIO PIPELINE │
│  (Rust/C++)   │            │  Recording/Mix  │
│  60fps Render │            │  Multi-track    │
└───────────────┘            └─────────────────┘
```

---

## Installation

### 1. File Placement

Place the Studio Control Room files in your PubCast AI project structure:

```
your-pubcast-project/
├── modules/
│   ├── studio_control.py        # Backend logic
│   └── studio_websocket.py      # WebSocket handler
├── pete_enhanced.py              # Your existing Pete Enhanced
├── static/
│   └── studio_control_room.html # Control interface
└── main.py or hub.py             # Your FastAPI app
```

### 2. Python Dependencies

No new dependencies required! The Studio Control Room uses:
- `asyncio` (built-in)
- `fastapi` + `websockets` (already in PubCast AI)
- `pydantic` (already in PubCast AI)

### 3. Integration with FastAPI

Add the WebSocket endpoint to your FastAPI app:

```python
# In your main.py or hub.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pathlib import Path

from modules.studio_control import StudioControl
from modules.studio_websocket import create_studio_websocket_endpoint
from pete_enhanced import PeteEnhanced

app = FastAPI()

# Initialize Studio Control (after Pete is initialized)
studio_control = StudioControl(
    hub=hub,
    pete=pete_enhanced,
    data_dir=Path("./data"),
    config={
        "dead_man_switch_interval": 60.0,  # Auto-save every 60s
        "audio_update_interval": 0.1,       # 10 Hz monitoring
    }
)

# Create WebSocket handler
studio_ws_handler = create_studio_websocket_endpoint(studio_control)

# WebSocket endpoint
@app.websocket("/ws/studio")
async def websocket_studio(websocket: WebSocket):
    """WebSocket endpoint for Studio Control Room"""
    await studio_ws_handler.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await studio_ws_handler.handle_message(websocket, data)
    except WebSocketDisconnect:
        await studio_ws_handler.disconnect(websocket)

# Serve the Studio Control Room interface
@app.get("/studio", response_class=HTMLResponse)
async def get_studio_control_room():
    """Serve the Studio Control Room HTML interface"""
    html_path = Path("./static/studio_control_room.html")
    with open(html_path) as f:
        return HTMLResponse(content=f.read())
```

### 4. Pete Enhanced Integration

Update your Pete Enhanced to handle Studio Control commands:

```python
# In pete_enhanced.py

class PeteEnhanced(BasePete):
    def __init__(self, hub, bridge, motion_system, data_dir, config=None):
        super().__init__(hub, bridge, motion_system, data_dir, config)
        
        # Register Studio Control reference
        self.studio_control = None  # Will be set after initialization
    
    async def speak_voice_cue(self, text: str, voice: str = "pete"):
        """
        Trigger AI voice announcement for Studio Control
        
        This is called during the 5-second countdown:
        - T-minus 5, 4, 3, 2, 1
        - Preflight warnings/confirmations
        """
        logger.info(f"🎭 Pete: Speaking '{text}'")
        
        # TODO: Integrate with your TTS system
        # await self.tts_engine.speak(text, voice_profile=voice)
        
        # For now, just log it
        pass
```

Then in your initialization code:

```python
# After creating both objects
pete_enhanced = PeteEnhanced(hub, bridge, motion_system, data_dir)
studio_control = StudioControl(hub, pete_enhanced, data_dir)

# Link them together
pete_enhanced.studio_control = studio_control
```

---

## Features & Workflows

### 1. The 5-Second Preflight Countdown

**What it does:**
- Runs mandatory hardware checks before every recording session
- Provides AI voice countdown cues through Pete
- Detects ghost microphones and configuration issues
- Gives production team time to verify everything is ready

**Workflow:**

1. User clicks **"START COUNTDOWN"** (or presses SPACE)
2. System enters PREFLIGHT state
3. Countdown begins: T-minus 5, 4, 3, 2, 1
4. **At T-4:** Gate Check (camera/buffer verification)
5. **At T-2:** Ghost Mic Detection (audio input audit)
6. System automatically transitions to LIVE state
7. Recording begins with Dead Man's Switch active

**Python Hook Points:**

```python
# In studio_control.py

async def _check_the_gate(self) -> None:
    """
    T-4: Gate Check - Camera/Buffer Verification
    
    TODO: Integrate with Pete's hardware monitoring:
    - Query actual USB/XLR device list
    - Compare to scene requirements
    - Flag unexpected devices
    """
    # Your integration code here
    detected_devices = await self.pete.get_connected_audio_devices()
    required_devices = await self.pete.get_scene_requirements()
    
    if len(detected_devices) > len(required_devices):
        self._ghost_mics = list(set(detected_devices) - set(required_devices))
        logger.warning(f"👻 Ghost devices: {self._ghost_mics}")

async def _trigger_voice_cue(self, text: str) -> None:
    """
    Trigger AI voice through Pete
    
    TODO: Integrate with your TTS system
    """
    await self.pete.speak_voice_cue(text, voice="pete")
```

### 2. Audio Matrix (5 Channels)

**The 5 Key Categories:**

1. **Microphone Inputs** - Physical USB/XLR microphones
2. **Dialogue Track** - Processed/cleaned speech audio
3. **Studio Feed** - SFX, music, background audio
4. **System Audio** - Desktop/app sounds
5. **Room Noise** - Ambient monitoring channel

**Real-Time Monitoring:**
- 10 Hz signal level updates
- Visual meters with color-coded status (OK, WARNING, CRITICAL)
- Peak tracking with timestamps
- Individual mute/unmute controls

**Python Hook Points:**

```python
# Update audio levels from your recording pipeline
await studio_control.update_audio_channel(
    channel_id="mic_inputs",
    signal_db=-25.5,  # Current dB level
    active=True
)

# Get current audio matrix state
audio_state = studio_control.audio_matrix.to_dict()
```

### 3. Emergency Save - The "Dead Man's Switch"

**What it does:**
- Provides instant crash protection for recordings
- Automatically saves every 60 seconds during LIVE state
- Manual trigger via button or ESC key
- Flushes all buffers immediately to disk

**Workflow:**

1. **During LIVE:** Auto-saves every 60s in background
2. **On Emergency:** Immediately flushes all buffers
3. Creates timestamped recovery folder with:
   - Audio matrix state (`audio_matrix.json`)
   - Preflight check history (`preflight_checks.json`)
   - Recovery manifest (`recovery_manifest.json`)
   - All recording buffers (via Pete integration)

**Python Hook Points:**

```python
# In your recording pipeline, implement buffer flush
class PeteEnhanced(BasePete):
    async def emergency_flush_buffers(self, save_path: Path) -> None:
        """
        Emergency buffer flush for Studio Control
        
        Called when Dead Man's Switch triggers.
        Must save ALL in-flight data immediately.
        """
        logger.critical("🚨 Flushing all recording buffers!")
        
        # Save audio tracks
        for track_id, buffer in self.audio_tracks.items():
            track_file = save_path / f"audio_{track_id}.wav"
            buffer.flush_to_file(track_file)
        
        # Save video/voxel frames
        if self.voxel_integration:
            await self.voxel_integration.emergency_save(save_path)
        
        logger.info(f"✅ Emergency save complete: {save_path}")
```

### 4. Isolation Mode (Dialogue Only)

**What it does:**
- Instantly mutes everything except dialogue track
- Perfect for emergency audio cleanup
- One-button restoration of full mix

**Use Cases:**
- Background noise contamination during recording
- Unexpected system sounds
- Testing dialogue clarity
- Quick audio troubleshooting

**Controls:**
- **"ISOLATION MODE"** button - Mute all but dialogue
- **"UNMUTE ALL"** button - Restore full mix
- Individual channel toggles for fine control

---

## Keyboard Shortcuts

| Key | Action | State Required |
|-----|--------|----------------|
| **SPACE** | Start Countdown | IDLE |
| **ESC** | Emergency Save | LIVE |

---

## WebSocket Message Protocol

### Client → Server (Commands)

```json
{
  "command": "start_preflight"
}
```

```json
{
  "command": "toggle_channel",
  "channel_id": "mic_inputs",
  "active": false
}
```

```json
{
  "command": "emergency_save",
  "reason": "Manual trigger"
}
```

### Server → Client (Updates)

**State Change:**
```json
{
  "type": "state_update",
  "state": "LIVE",
  "timestamp": "2026-03-09T12:34:56.789"
}
```

**Audio Update:**
```json
{
  "type": "audio_update",
  "audio_matrix": {
    "mic_inputs": {
      "name": "Microphone Inputs",
      "active": true,
      "signal_db": -25.5,
      "status": "OK",
      "last_peak_db": -18.2
    },
    ...
  },
  "timestamp": "2026-03-09T12:34:56.789"
}
```

**Countdown:**
```json
{
  "type": "countdown",
  "seconds": 3,
  "timestamp": "2026-03-09T12:34:56.789"
}
```

**Preflight Check:**
```json
{
  "type": "preflight_check",
  "check": {
    "check_id": "gate_check",
    "name": "Gate Check",
    "passed": true,
    "message": "All inputs verified",
    "timestamp": 1709990096.789
  },
  "timestamp": "2026-03-09T12:34:56.789"
}
```

---

## Configuration Options

### StudioControl Configuration

```python
studio_control = StudioControl(
    hub=hub,
    pete=pete_enhanced,
    data_dir=Path("./data"),
    config={
        # Dead Man's Switch interval (seconds)
        "dead_man_switch_interval": 60.0,
        
        # Audio monitoring update rate (seconds)
        "audio_update_interval": 0.1,  # 10 Hz
        
        # Emergency save directory
        "emergency_save_dir": Path("./data/emergency_saves"),
        
        # Preflight timeout (seconds)
        "preflight_timeout": 30.0,
        
        # Enable AI voice cues
        "enable_voice_cues": True,
        
        # Pete voice profile for countdown
        "countdown_voice": "pete",
    }
)
```

---

## Testing

### Standalone Testing (No Backend)

The Studio Control Room HTML interface has built-in local fallback logic. You can test it without the Python backend:

1. Open `studio_control_room.html` directly in browser
2. Interface will use simulated audio and local countdown
3. All UI features work (buttons, meters, countdown)
4. WebSocket will attempt to connect but gracefully fall back

### With Backend

1. Start your PubCast AI server: `python main.py`
2. Navigate to `http://localhost:8000/studio`
3. Check browser console for WebSocket connection status
4. Test preflight sequence with SPACE key
5. Monitor Python logs for command execution

### Test Checklist

- [ ] WebSocket connects successfully
- [ ] START COUNTDOWN triggers 5-second sequence
- [ ] Gate Check runs at T-4
- [ ] Ghost Mic Detection runs at T-2
- [ ] State transitions: IDLE → PREFLIGHT → LIVE
- [ ] Audio meters update in real-time
- [ ] ISOLATION MODE mutes non-dialogue channels
- [ ] STOP RECORDING returns to IDLE
- [ ] EMERGENCY SAVE triggers and creates recovery folder
- [ ] ESC key triggers emergency save during LIVE

---

## Customization

### Adding Custom Preflight Checks

```python
# In studio_control.py

async def run_preflight_sequence(self):
    # ... existing countdown logic ...
    
    # Add your custom check
    if i == 3:
        await self._check_custom_hardware()

async def _check_custom_hardware(self) -> None:
    """Custom hardware verification"""
    # Your custom check logic
    camera_ready = await self.pete.verify_camera_system()
    
    check = PreflightCheck(
        "camera_check",
        "Camera System Verification",
        passed=camera_ready,
        message="Camera system ready" if camera_ready else "Camera system error"
    )
    
    self._preflight_checks.append(check)
    await self._broadcast_check_result(check)
```

### Adding More Audio Channels

```python
# In studio_control.py - AudioMatrix class

@dataclass
class AudioMatrix:
    # Existing channels...
    
    # Add new channel
    guest_feed: AudioChannel = field(default_factory=lambda: AudioChannel(
        "guest_feed", "Guest Feed (Remote)", active=False, signal_db=-60.0
    ))
    
    def get_all_channels(self) -> List[AudioChannel]:
        return [
            self.mic_inputs,
            self.dialogue,
            self.studio_feed,
            self.system_audio,
            self.room_noise,
            self.guest_feed,  # Include new channel
        ]
```

Then update the HTML to display the new channel:

```javascript
// In studio_control_room.html - StudioEngine.audioMatrix

audioMatrix: {
    mic_inputs:   { ... },
    dialogue:     { ... },
    studio_feed:  { ... },
    system_audio: { ... },
    room_noise:   { ... },
    guest_feed:   { name: 'Guest Feed (Remote)', active: false, signal_db: -60, status: 'OK' }  // New
}
```

---

## Troubleshooting

### WebSocket Won't Connect

**Problem:** Browser console shows WebSocket connection errors

**Solutions:**
1. Verify FastAPI is running: `http://localhost:8000/docs`
2. Check WebSocket endpoint exists: `/ws/studio`
3. Ensure `studio_websocket.py` is imported in `main.py`
4. Check firewall isn't blocking WebSocket connections
5. Try `ws://` instead of `wss://` for local development

### Preflight Checks Not Running

**Problem:** Countdown starts but checks don't appear

**Solutions:**
1. Check Python logs for errors during preflight
2. Verify `_check_the_gate()` and `_check_ghost_mics()` are being called
3. Ensure WebSocket messages are being broadcast
4. Check browser console for received messages
5. Verify `renderPreflightChecks()` is executing

### Audio Meters Not Updating

**Problem:** Audio meters show no signal

**Solutions:**
1. Verify `update_audio_channel()` is being called from your recording pipeline
2. Check audio update interval (default 0.1s = 10 Hz)
3. Ensure WebSocket is connected and receiving `audio_update` messages
4. Check browser console for JavaScript errors
5. Verify `renderAudioMatrix()` is executing

### Emergency Save Fails

**Problem:** Emergency save triggers but files aren't created

**Solutions:**
1. Check `emergency_save_dir` exists and is writable
2. Verify Pete's `emergency_flush_buffers()` is implemented
3. Check Python logs for file write errors
4. Ensure sufficient disk space
5. Verify JSON serialization of audio matrix state

---

## Production Deployment Checklist

- [ ] Test preflight sequence 10+ times without errors
- [ ] Verify all audio channels update in real-time
- [ ] Test emergency save under load (simulated crash)
- [ ] Confirm Dead Man's Switch auto-saves during recording
- [ ] Verify WebSocket reconnection after network interruption
- [ ] Test keyboard shortcuts (SPACE, ESC)
- [ ] Monitor Python logs during live session
- [ ] Verify recovery from emergency save files
- [ ] Test isolation mode during actual recording
- [ ] Confirm ghost mic detection with extra devices connected
- [ ] Load test with multiple WebSocket clients
- [ ] Verify audio latency <100ms end-to-end

---

## Next Steps

### Immediate Integration

1. **Add to Existing Launcher**
   - Add "Studio Control Room" tab to your `pubcast_launcher.html`
   - Or serve as standalone page at `/studio`

2. **Connect to Audio Pipeline**
   - Hook `update_audio_channel()` to your actual recording system
   - Implement real audio level monitoring

3. **Integrate with Pete's TTS**
   - Connect `_trigger_voice_cue()` to Pete's voice system
   - Add countdown voice clips

### Future Enhancements

- **Video Preview Feed** - Add camera preview during preflight
- **Multi-Track Recording** - Expand from 5 to N audio channels
- **Remote Monitoring** - Allow observers to watch countdown
- **Recording Templates** - Pre-configured preflight sequences per show type
- **AI-Assisted Mixing** - Pete suggests audio level adjustments
- **Cloud Backup** - Automatic upload of emergency saves to S3/GCS
- **Analytics Dashboard** - Track preflight success rates over time

---

## Credits

**Studio Control Room** - The "Iron Core" production control system for PubCast AI

Designed with the philosophy: **"Local-First, Cloud-Enhanced"**

Critical production safety never depends on network connectivity or cloud services. The Iron Core runs autonomously, with Pete Enhanced providing intelligent orchestration when available.

**"Feic Mo Chroí"** (See My Heart) - Technology serving human storytelling.

---

## Support

For issues, questions, or feature requests:
1. Check Python logs: `tail -f data/agent_run_log.txt`
2. Check browser console for JavaScript errors
3. Verify WebSocket connection status
4. Review this integration guide for troubleshooting steps

---

**🎛️ The Iron Core is ready. Let's make magic.**
