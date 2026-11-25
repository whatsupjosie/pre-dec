# PubCast GLB Motion Consumer Handoff

**Purpose:** make the behavior/mocap pipeline visible on Manny/Sheila GLB skeletons.

This bundle adds the final runtime bridge:

```text
mocap frame / emotion / intent
  -> AvatarBehaviorRuntime
  -> avatar_motion_commands event
  -> PubcastAvatarMotionRuntime browser bridge
  -> PubcastGLBMotionConsumer
  -> Manny/Sheila Three.js GLB bones
```

## Files

- `static/avatar_glb_motion_consumer.js`
  - Browser-side command consumer.
  - Registers loaded GLB avatar roots.
  - Maps common Mixamo/GLB bone names to canonical PubCast bones.
  - Applies `mocap_pose`, `overlay`, `procedural_animation`, and `hold` commands.
  - Creates **no menus** and no UI.

- `modules/glb_motion_retargeter.py`
  - Server/tooling helper for canonical GLB bone command normalization.
  - Clamps unsafe rotations.
  - Drops unknown bones.

- `tests/test_glb_motion_retargeter.py`
- `tests/test_avatar_glb_motion_consumer_node.js`

## Install

Copy:

```bash
copy static\avatar_glb_motion_consumer.js YOUR_REPO\static\avatar_glb_motion_consumer.js
copy modules\glb_motion_retargeter.py YOUR_REPO\modules\glb_motion_retargeter.py
```

Add this script after `avatar_motion_runtime.js` on the stage/control page that loads Manny/Sheila:

```html
<script src="/static/avatar_glb_motion_consumer.js"></script>
```

## Register Manny/Sheila after GLB load

Wherever the real GLB loader finishes loading Manny or Sheila:

```javascript
// after GLTFLoader loads Manny.glb
window.PubcastGLBMotionConsumer.registerAvatar("manny", gltf.scene, {
  motionScale: 1.0,
  overlayScale: 0.45,
  proceduralScale: 0.55,
});

// after GLTFLoader loads Sheila.glb
window.PubcastGLBMotionConsumer.registerAvatar("sheila", gltf.scene, {
  motionScale: 1.0,
});
```

Then existing runtime events should start moving mapped bones.

## Smoke test in browser console

```javascript
PubcastGLBMotionConsumer.consumePayload({
  avatar_id: "manny",
  commands: [{
    kind: "mocap_pose",
    layer: "MOCAP_BASE",
    weight: 1,
    priority: 70,
    pose: { bones: { head: { rotation: [10, 5, 0] }, spine: { rotation: [0, 4, 0] } } }
  }]
});
```

Manny's head/spine should move subtly. If not, check:

```javascript
PubcastGLBMotionConsumer.bindings.get("manny").debugStatus()
```

If `mappedBones` is sparse, pass custom `boneAliases` in `registerAvatar`.

## Important design choice

This is not final high-end animation. It is the visible live bridge. It deliberately applies small conservative rotations so the system comes alive without breaking rigs. Later, high-quality GLB animation clips can replace the semantic fallback poses while preserving the same command event contract.
