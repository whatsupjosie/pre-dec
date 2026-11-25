# PubCast Avatar Motion Runtime Integration

This package connects the behavior animation/mocap pipeline to the actual PubCast app surface.

## What this adds

- `modules/avatar_behavior_runtime.py` — multi-avatar runtime manager.
- `/api/avatar-motion/status` — profile/runtime status.
- `/api/avatar-motion/profiles` — list/update avatar behavior profiles.
- `/api/avatar-motion/tick` — one system-level behavior tick.
- `/api/avatar-motion/frame` — mocap frame ingestion, replacing the old raw broadcast-only endpoint behavior.
- `/api/avatar-motion/{avatar_id}/emotion` — manual emotional cue injection.
- WebSocket event: `avatar_motion_commands`.
- `static/avatar_motion_runtime.js` — browser receiver + tiny client API.
- `static/avatar_motion_debug_probe.js` — optional dev-only visual/log probe.

## Event shape

```json
{
  "type": "avatar_motion_commands",
  "payload": {
    "avatar_id": "manny",
    "room": "studio",
    "commands": [
      {"kind": "mocap_pose", "layer": "MOCAP_BASE", "pose": {}},
      {"kind": "overlay", "layer": "EMOTION_OVERLAY", "animation_id": "thoughtful_idle"},
      {"kind": "procedural_animation", "layer": "HEAD", "animation_id": "nod_slow"}
    ],
    "state": {},
    "decision": {},
    "warnings": [],
    "source": "avatar_behavior_runtime"
  }
}
```

## Install

Copy these into your repo:

```text
modules/animation_presets_complete.py
modules/animation_presets_expanded.py
modules/behavior_animation_engine.py
modules/behavior_motion_pipeline.py
modules/avatar_behavior_runtime.py
static/animation_presets_complete.js
static/animation_presets_expanded.js
static/behavior_animation_engine.js
static/behavior_motion_pipeline.js
static/avatar_motion_runtime.js
```

Then apply `main_avatar_motion_patch.py.diff` or manually paste the endpoint block into `main.py` after the existing `/api/motion/frame` endpoint.

Add this script include near the bottom of `static/control.html` and any stage page that should receive avatar motion:

```html
<script src="/static/avatar_motion_runtime.js"></script>
```

Optional dev probe only:

```html
<script src="/static/avatar_motion_debug_probe.js"></script>
```

## Example calls

```bash
curl -X POST http://localhost:8000/api/avatar-motion/tick \
  -H "Content-Type: application/json" \
  -d '{"avatar_id":"manny","text":"Hmm, that is interesting. What if we try it seated?","is_seated":true}'
```

```bash
curl -X POST http://localhost:8000/api/avatar-motion/sheila/emotion \
  -H "Content-Type: application/json" \
  -d '{"label":"confident","intensity":0.8}'
```

## Why this matters

The old `/api/motion/frame` only rebroadcast a raw mocap payload. The new runtime translates mocap + text + emotional cues + avatar profile tendencies into layered commands: mocap base, emotional overlay, procedural behavior, or stillness hold.

That means a renderer or GLB performer receives one coherent command bundle instead of disconnected animation guesses.
