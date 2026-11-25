# Bubble Stack — Traceability & Reconciliation
### Layer 6 of the dossier: Development Conversation vs. Choreography Implementation

**Scope note:** No `bubble_stack.py`, PIKPC engine, or `/api/bubble-stack` files were among the four uploaded — only the choreography/mocap subsystem (`choreography.py`, `choreography_runtime.py`, `choreography_controller.py`, `crowd_choreography.js`). So this reconciliation compares the *conceptual genesis* (3D object tracking → physics inference → predictive blocking) against that one subsystem, not the full Bubble Stack codebase. Treat this as a partial reconciliation until the actual `/api/bubble-stack` and PIKPC files are added.

---

## 1. What the code actually is

| File | Role |
|---|---|
| `choreography.py` | Full/"hardened" system: canonical UE5 joint skeleton (`StandardSkeleton`), pose dataclasses, quaternion-slerp step interpolation, `ChoreographyManager` (save/load/list), `MotionCaptureProcessor` (MediaPipe/ARKit → skeleton) |
| `choreography_runtime.py` | Leaner earlier/parallel version of `Choreography`/`ChoreographyStep` — Euler-only rotation, no skeleton hierarchy, no mocap ingestion. Imported by the controller. |
| `choreography_controller.py` | Live server runtime: `ChoreoController` broadcasts frames over a hub at a tick rate, `MotionConstraints` clamps speed/turn-rate/bounds, `cue_action()` fires canned semantic actions (fall, trip, sit, etc.) |
| `crowd_choreography.js` | Deterministic seeded crowd sim — waypoint walking, frame compilation for instant seek, 3-state animation (idle/walk/run) from displacement magnitude |

In one line: **this is an authoring/playback/broadcast layer for keyframed and captured skeletal motion.** It moves avatars and records what they did.

---

## 2. Where it matches the Bubble Stack concept

- **Position + rotation as first-class tracked state** — `SkeletonJoint`/`SkeletonPose` carry position, quaternion rotation, and scale per joint, matching the doc's "where is it / where is it oriented" bullets.
- **Real capture ingestion** — `MotionCaptureProcessor.mediapipe_to_skeleton()` and `.arkit_to_skeleton()` turn actual sensor landmarks into skeleton frames. This is the doc's "actor: position/rotation/joint state" line, genuinely implemented, not aspirational.
- **A frame-by-frame record stream** — `Choreography.record_frame()` and the controller's `choreo_frame` broadcast are structurally the same shape as the doc's "Frame 10482" capture example: an id, a position, a rotation, a skeleton, at a timestamp.
- **Determinism as a design value** — `crowd_choreography.js`'s seeded LCG exists so a take can be replayed identically, which lines up with the doc's "structured physical performance record that can be replayed."

That's the real overlap. Everything below it is a gap.

---

## 3. What's missing — organized by the doc's three use cases

### A. The performance-capture stream (Frame 10482 example)
The doc's frame spec included velocity, acceleration, angular velocity, contact point, collision normal, relative velocity, estimated impulse, and environment (surface/friction/gravity). The actual `record_frame()`/`choreo_frame` payload has **only** position, rotation, and skeleton. Velocity and acceleration are never computed or stored as data — `ChoreoController._apply_constraints()` computes a per-frame delta internally just to clamp it, then throws it away. There's no persisted derivative of any kind.

### B. Virtual objects with no physical existence (the digital tin cup)
There is no object model anywhere in these four files — no mass, dimensions, shape, collision geometry, material, center of mass, moment of inertia, friction, or restitution for *anything*, avatar or prop. `DEFAULT_ACTIONS` has entries like `hold_coffee` and `film_camera`, but those are just labeled animation clips with a fixed duration — there's no way to define a prop that doesn't physically exist, infer its release kinematics from a captured hand motion, or timestep it through a collision. The entire release → flight → impact → bounce chain from the tin-cup example has no analogue in the code.

### C. Predictive blocking (the monster backhand)
Same gap, different angle: no impulse/impact calculation exists, so nothing here can answer "given this strike, where does the hero land." `fall` and `trip` in `DEFAULT_ACTIONS` are the closest conceptual anchor — but they're pre-authored canned clips selected by name and scaled by an `intensity` multiplier (0.1–3.0) that only affects playback duration, not a simulated outcome of mass, velocity, and contact angle. There's no way to generate a stage mark from a creature's stated strength.

### D. Interaction/reaction/fallout chain generally
The doc's core diagram — `position → velocity → trajectory → collision → interaction → reaction → fallout` — has **no implementation at all**. No two tracked entities in this code are ever checked against each other for proximity, contact, or collision. The crowd system's 100 avatars walk their waypoints completely independently; nothing in `crowd_choreography.js` is aware that another avatar exists.

### E. The "bubbles" themselves
No bounded spatial/tracking regions exist. There's no concept of an object entering a region, being picked up by tracking, and later leaving it — just a flat list of avatars each running its own step queue.

---

## 4. A quiet divergence worth flagging

`MotionConstraints` in the controller is the one place that *gestures* at physics — it limits horizontal/vertical speed, turn rate, and posture angle. But it's a **kinematic clamp**, not a **dynamics simulation**: it enforces "don't move faster than X" as a hard ceiling rather than deriving motion from mass, force, and impulse. It's a plausibility filter on authored/captured motion, not the inference engine the doc describes. Worth naming explicitly in the dossier so it isn't mistaken for a partial physics implementation later.

---

## 5. Bottom line for the dossier

This subsystem is **downstream of where Bubble Stack starts, and upstream of where it's supposed to go.** It's a solid, real implementation of *capturing and replaying skeletal motion* — the "Actor:" block in the doc's Frame 10482 example. It has no code for object physical identity, interaction/collision, impulse-based prediction, or virtual (non-physically-present) props — i.e., none of the three things the development conversation was actually most excited about (the tin cup, the monster backhand, and the interaction/fallout chain).

If/when the real `bubble_stack.py` / PIKPC files are added to this dossier, the natural seam is `Choreography.record_frame()` and `ChoreoController._runner()` — those are the two places a velocity/acceleration/interaction layer would slot in without disturbing the existing playback code.
