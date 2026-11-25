# Motion Capture Integration for PubCast AI v7.0

**Real-Time Mocap-Driven Avatar Animation**

---

## Overview

The Motion Capture Integration System allows PubCast AI to receive live mocap data and apply it to neon avatars in real-time.

### Features

✅ **Multiple Stream Sources**
- UDP streaming (low-latency local)
- WebSocket streaming (remote/web-based)
- File playback

✅ **Auto-Recording Trigger**
- Studio Control automatically starts recording when mocap movement detected
- Integrated with 5-second preflight countdown

✅ **Real-Time Avatar Animation**
- Maps mocap joints to avatar skeleton
- Supports custom skeleton mappings
- 60-240 fps support

✅ **Performance Monitoring**
- FPS tracking
- Latency measurement
- Frame buffer management

---

## Quick Start

### 1. Start PubCast AI with Mocap Support

```python
# In main.py
from modules.mocap_integration import MocapStreamManager

# Initialize mocap manager
mocap_manager = MocapStreamManager(
    hub=hub,
    pete=pete_enhanced,
    config={
        "auto_start_recording": True,  # Auto-trigger Studio Control
        "max_buffer_size": 60           # Keep last 60 frames
    }
)

# Set active avatar to receive mocap data
mocap_manager.set_active_avatar("neon_yellow_a")  # Lumen

# Start receiving mocap stream
await mocap_manager.start_stream("udp://localhost:9001")
```

### 2. Send Mocap Data

#### Option A: Use the Simulator (for testing)

```bash
# Simulate walking animation
python scripts/mocap_simulator.py --mode walk --fps 60

# Simulate dancing
python scripts/mocap_simulator.py --mode dance --fps 120

# Run for 30 seconds
python scripts/mocap_simulator.py --mode walk --duration 30
```

#### Option B: Send Real Mocap Data

```python
import socket
import json
import time

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Send frame
frame = {
    "ts": int(time.time() * 1000),
    "rigId": "my-rig-01",
    "joints": {
        "hips": {"x": 0.0, "y": 0.0, "z": 0.0},
        "spine": {"x": 0.0, "y": 0.2, "z": 0.0},
        "left_knee": {"x": 0.15, "y": -0.4, "z": 0.0},
        "right_knee": {"x": -0.15, "y": -0.4, "z": 0.0}
    }
}

data = json.dumps(frame).encode('utf-8')
sock.sendto(data, ("localhost", 9001))
```

### 3. Watch It Work

- **Studio Control Room** - Opens automatically: `http://localhost:8000/studio`
- Mocap movement triggers 5-second countdown
- Avatar animates in real-time
- Recording starts automatically at T-0

---

## Mocap Frame Format

### Standard Frame Structure

```json
{
  "ts": 1700000000000,          // Timestamp (milliseconds since epoch)
  "rigId": "rig-01",            // Rig identifier
  "frameNumber": 1234,          // Optional frame number
  "fps": 60.0,                  // Optional FPS
  "quality": "medium",          // Optional quality level
  "joints": {
    "hips": {
      "x": 0.0, "y": 0.0, "z": 0.0,           // Position
      "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0,  // Optional rotation (quaternion)
      "confidence": 1.0                        // Optional confidence (0.0-1.0)
    },
    "spine": {"x": 0.0, "y": 0.2, "z": 0.0},
    "chest": {"x": 0.0, "y": 0.4, "z": 0.0},
    // ... more joints
  }
}
```

### Supported Joint Names

**Core:**
- `hips`, `spine`, `chest`, `neck`, `head`

**Left Arm:**
- `left_shoulder`, `left_elbow`, `left_wrist`, `left_hand`

**Right Arm:**
- `right_shoulder`, `right_elbow`, `right_wrist`, `right_hand`

**Left Leg:**
- `left_hip`, `left_knee`, `left_ankle`, `left_foot`

**Right Leg:**
- `right_hip`, `right_knee`, `right_ankle`, `right_foot`

---

## Integration with Studio Control

### Auto-Recording Mode

When mocap stream starts and movement is detected:

```
1. Mocap movement detected
   └─► Studio Control: run_preflight_sequence()
       
2. 5-Second Countdown
   T-5: Countdown starts
   T-4: Gate Check + Scene Validation
   T-3: Countdown continues
   T-2: Ghost Mic Detection + Asset Preloading
   T-1: Final check
   T-0: GO LIVE
        ├─► Recording starts
        ├─► Mocap data applied to avatar
        └─► Rendered in Rust engine @ 60fps
```

### Manual Mode

Disable auto-recording if you want manual control:

```python
mocap_manager = MocapStreamManager(
    hub=hub,
    pete=pete_enhanced,
    config={
        "auto_start_recording": False  # Manual control
    }
)
```

---

## Skeleton Mapping

### Default Mapping

Mocap joints automatically map to avatar bones:

```python
AVATAR_SKELETON_MAPPING = {
    # Mocap joint → Avatar bone
    "hips": "root",
    "spine": "spine1",
    "chest": "spine2",
    "neck": "neck",
    "head": "head",
    "left_shoulder": "l_shoulder",
    "left_elbow": "l_elbow",
    "left_wrist": "l_wrist",
    "right_shoulder": "r_shoulder",
    "right_elbow": "r_elbow",
    "right_wrist": "r_wrist",
    "left_knee": "l_knee",
    "right_knee": "r_knee"
}
```

### Custom Mapping

Update mapping for custom avatar skeletons:

```python
# Add custom mappings
mocap_manager.update_skeleton_mapping({
    "left_fingers": "l_hand_fingers",
    "right_fingers": "r_hand_fingers",
    "left_thumb": "l_thumb",
    "right_thumb": "r_thumb"
})
```

---

## Streaming Protocols

### UDP Streaming (Recommended for Local)

**Pros:**
- Ultra-low latency
- No connection overhead
- Simple protocol

**Cons:**
- Local network only
- No reliability guarantees

**Usage:**
```python
await mocap_manager.start_stream("udp://localhost:9001")
```

### WebSocket Streaming

**Pros:**
- Works over internet
- Reliable delivery
- Firewall-friendly

**Cons:**
- Higher latency
- Connection overhead

**Usage:**
```python
await mocap_manager.start_stream("ws://remote-server.com:8080/mocap")
# or secure:
await mocap_manager.start_stream("wss://remote-server.com/mocap")
```

---

## Performance Tuning

### FPS and Latency

```python
# High FPS (120-240 fps)
# Use for: precise movements, dancing, sports
await mocap_manager.start_stream("udp://localhost:9001")

# Standard FPS (60 fps)
# Use for: normal animation, conversation
# Already optimal for most use cases

# Low FPS (30 fps)
# Use for: bandwidth-limited scenarios
# Reduce data sent from mocap source
```

### Buffer Management

```python
mocap_manager = MocapStreamManager(
    hub=hub,
    pete=pete_enhanced,
    config={
        "max_buffer_size": 120  # Keep 2 seconds at 60fps
    }
)

# Get buffered frames for playback
recent_frames = mocap_manager.get_frame_buffer(max_frames=60)
```

### Quality Levels

```json
{
  "quality": "low",      // 30 fps, basic joints
  "quality": "medium",   // 60 fps, full skeleton (default)
  "quality": "high",     // 120 fps, full skeleton + fingers
  "quality": "ultra"     // 240 fps, full body + facial
}
```

---

## API Reference

### MocapStreamManager

#### Initialization

```python
mocap_manager = MocapStreamManager(
    hub: Hub,
    pete: Optional[PeteEnhanced] = None,
    config: Optional[Dict[str, Any]] = None
)
```

**Config Options:**
- `auto_start_recording`: bool (default: True)
- `max_buffer_size`: int (default: 60)

#### Methods

**start_stream(source_url: str) → bool**
```python
# Start receiving mocap stream
success = await mocap_manager.start_stream("udp://localhost:9001")
```

**stop_stream() → None**
```python
# Stop mocap stream
await mocap_manager.stop_stream()
```

**set_active_avatar(avatar_id: str) → None**
```python
# Set which avatar receives mocap data
mocap_manager.set_active_avatar("neon_yellow_a")
```

**update_skeleton_mapping(mapping: Dict[str, str]) → None**
```python
# Update joint → bone mapping
mocap_manager.update_skeleton_mapping({
    "custom_joint": "custom_bone"
})
```

**get_status() → Dict**
```python
# Get complete status
status = mocap_manager.get_status()
# Returns:
# {
#     "status": "streaming",
#     "rig_id": "rig-01",
#     "active_avatar": "neon_yellow_a",
#     "recording_started": True,
#     "metrics": {
#         "frames_received": 1234,
#         "avg_fps": 60.2,
#         "avg_latency_ms": 5.3,
#         "buffer_size": 60
#     }
# }
```

**get_latest_frame() → Optional[MocapFrame]**
```python
# Get most recent frame
frame = mocap_manager.get_latest_frame()
```

**get_frame_buffer(max_frames: int = 60) → List[MocapFrame]**
```python
# Get recent frames
frames = mocap_manager.get_frame_buffer(max_frames=120)
```

---

## Testing and Debugging

### Test with Simulator

```bash
# Test basic connectivity
python scripts/mocap_simulator.py --mode idle --fps 30 --duration 5

# Test walking animation
python scripts/mocap_simulator.py --mode walk --fps 60

# Test high FPS
python scripts/mocap_simulator.py --mode dance --fps 120

# Send to custom target
python scripts/mocap_simulator.py --target udp://192.168.1.100:9001
```

### Check Status via API

```bash
# Get mocap status
curl http://localhost:8000/api/mocap/status

# Response:
# {
#   "status": "streaming",
#   "rig_id": "sim-rig-01",
#   "metrics": {
#     "fps": 60.1,
#     "latency_ms": 4.2
#   }
# }
```

### Monitor in Studio Control Room

Open `http://localhost:8000/studio` and look for:
- Mocap FPS indicator
- Latency metric
- Recording auto-trigger

---

## Advanced Usage

### Custom Mocap Source Integration

```python
# Integrate with your mocap system
import your_mocap_sdk

async def stream_from_custom_system():
    """Stream from custom mocap system"""
    
    # Initialize your mocap system
    mocap_device = your_mocap_sdk.connect()
    
    # Create sender
    sender = MocapSender("udp://localhost:9001", rig_id="my-device")
    sender.connect()
    
    # Stream frames
    while True:
        # Get frame from your system
        frame_data = mocap_device.get_frame()
        
        # Convert to PubCast format
        joints = {
            "hips": {"x": frame_data.hips.x, "y": frame_data.hips.y, "z": frame_data.hips.z},
            # ... map all joints
        }
        
        # Send
        sender.send_frame(joints, frame_data.frame_number)
        
        await asyncio.sleep(1/60)  # 60 fps
```

### Record and Replay

```python
# Record mocap session
frames_buffer = []

async def record_session(duration_seconds=10):
    """Record mocap frames"""
    start_time = time.time()
    
    while (time.time() - start_time) < duration_seconds:
        frame = mocap_manager.get_latest_frame()
        if frame:
            frames_buffer.append(frame.to_dict())
        await asyncio.sleep(1/60)
    
    # Save to file
    with open("recording.json", "w") as f:
        json.dump(frames_buffer, f)

# Replay
async def replay_session():
    """Replay recorded session"""
    with open("recording.json", "r") as f:
        frames = json.load(f)
    
    sender = MocapSender("udp://localhost:9001")
    sender.connect()
    
    for i, frame_data in enumerate(frames):
        sender.send_frame(frame_data["joints"], i)
        await asyncio.sleep(1/60)
```

---

## Troubleshooting

### No Frames Received

**Check:**
1. Is PubCast AI listening on correct port?
   ```python
   # Should see in logs:
   # 📡 UDP mocap receiver listening on 127.0.0.1:9001
   ```

2. Is mocap source sending to correct port?
   ```bash
   python scripts/mocap_simulator.py --target udp://localhost:9001
   ```

3. Check firewall isn't blocking UDP port 9001

### High Latency

**Solutions:**
- Use UDP instead of WebSocket
- Reduce FPS on mocap source
- Check network congestion
- Ensure Pete Enhanced is running

### Dropped Frames

**Check metrics:**
```python
status = mocap_manager.get_status()
print(f"Dropped: {status['metrics']['frames_dropped']}")
```

**Solutions:**
- Increase buffer size
- Reduce FPS
- Check system CPU usage

### Avatar Not Animating

**Check:**
1. Is active avatar set?
   ```python
   mocap_manager.set_active_avatar("neon_yellow_a")
   ```

2. Are joints mapped correctly?
   ```python
   # Print mapping
   print(mocap_manager._skeleton_mapping)
   ```

3. Is Rust engine running?
   ```bash
   # Check Pete status
   curl http://localhost:8000/api/status
   ```

---

## Production Deployment

### Recommended Settings

```python
# Production config
mocap_manager = MocapStreamManager(
    hub=hub,
    pete=pete_enhanced,
    config={
        "auto_start_recording": True,
        "max_buffer_size": 120,  # 2 seconds at 60fps
    }
)

# Set quality based on bandwidth
# For local: 120 fps (high quality)
# For remote: 60 fps (medium quality)
# For bandwidth-limited: 30 fps (low quality)
```

### Security Considerations

- **UDP:** No encryption - use only on trusted local network
- **WebSocket:** Use WSS (WebSocket Secure) for remote streaming
- **Firewall:** Restrict port 9001 to trusted sources

---

## Credits

**Motion Capture Integration for PubCast AI v7.0**

Enables real-time mocap-driven avatar animation with automatic Studio Control integration.

**"Your movements, their story."** 🎭

---

*Feic Mo Chroí (See My Heart) - Technology serving human storytelling.*
