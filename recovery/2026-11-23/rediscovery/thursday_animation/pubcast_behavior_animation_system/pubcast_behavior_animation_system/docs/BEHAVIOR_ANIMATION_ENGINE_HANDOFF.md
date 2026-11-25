# PubCast Behavior Animation Engine Handoff

## What this adds

This package turns the uploaded animation preset library into a behavioral animation system.

The presets remain the vocabulary. The new engine decides when and how those vocabulary tokens should appear, using:

- `BehaviorState` — per-avatar social/physical state
- `BehaviorIntent` — semantic intent like listening, speaking, skeptical, thinking
- `AnimationSuppressionGate` — prevents twitchy over-animation and repeated gestures
- `AnimationConflictResolver` — assigns animations to body layers and blocks conflicts
- `BehaviorAnimationSelector` — scores context-appropriate candidates and emits one decision

## New files

```text
modules/behavior_animation_engine.py
modules/behavior_animation_engine.js
tests/test_behavior_animation_engine.py
tests/test_behavior_animation_engine_js.js
docs/BEHAVIOR_ANIMATION_ENGINE_HANDOFF.md
```

The original uploaded preset files are included too:

```text
modules/animation_presets_complete.py
modules/animation_presets_complete.js
docs/ANIMATION_EXPANSION_GUIDE.md
```

## Integration pattern

### Python

```python
from behavior_animation_engine import (
    BehaviorState,
    BehaviorIntent,
    build_default_selector,
)

selector = build_default_selector(seed=7)
state = BehaviorState(
    avatar_id="manny",
    is_seated=True,
    engagement=0.72,
    energy_level=0.52,
)

decision = selector.tick(
    state,
    elapsed_ms=1100,
    intent=BehaviorIntent.LISTENING,
    now_ms=current_time_ms,
)

if decision.should_play():
    avatar_runtime.play_animation(decision.animation_id, layer=decision.layer.name)
```

### JavaScript

```javascript
const presets = require('./animation_presets_complete.js');
const {
  BehaviorState,
  BehaviorIntent,
  BehaviorAnimationSelector,
} = require('./behavior_animation_engine.js');

const selector = new BehaviorAnimationSelector({
  library: presets.ANIMATION_LIBRARY,
  getAnimationsForContext: presets.getAnimationsForContext,
});

const state = new BehaviorState('sheila', {
  isSeated: true,
  engagement: 0.7,
  energyLevel: 0.55,
});

const decision = selector.tick(state, 1100, BehaviorIntent.THINKING, Date.now());
if (!decision.suppressed && decision.animationId) {
  avatarRuntime.playAnimation(decision.animationId, { layer: decision.layerName });
}
```

## Why this is better than random choice

The expansion guide uses context sets like `get_animations_for_context("listening")`, which is good. But the next layer needs more than a random pick.

This engine adds:

1. **Memory** — recent animation and tag history affect future choices.
2. **Cooldowns** — exact repeats and gesture spam are suppressed.
3. **Stillness** — held poses are intentional; not every pause gets a fidget.
4. **Layering** — head, torso, hands, fidgets, and emotional overlays do not blindly fight.
5. **Social behavior** — listeners avoid stealing focus with large gestures unless their state supports it.

## Runtime philosophy

Do not treat these as canned emotes.

Treat them as body-language vocabulary tokens selected by the avatar's social state.

A listener is not simply idle. A listener has engagement, attention, fatigue, stillness bias, social confidence, rhythm memory, and recent gesture history.

That is how PubCast starts feeling alive rather than animated.

## Test commands

From the package root:

```bash
python -m compileall modules tests
python -m pytest tests/test_behavior_animation_engine.py -v
node --check modules/behavior_animation_engine.js
node --check modules/animation_presets_complete.js
node tests/test_behavior_animation_engine_js.js
```

## Known next steps

1. Wire `AnimationDecision` into the actual avatar runtime's `play_animation` call.
2. Expand `BONE_GROUPS` with the authoritative Manny/Sheila skeleton bone names.
3. Add gaze/eye-contact state once the runtime exposes gaze controls.
4. Add transcript-aware gesture hooks: punctuation, emphasis words, interruption, and turn-taking.
5. Add two-avatar reciprocity: if Avatar A leans in, Avatar B subtly rebalances.
6. Add camera-aware suppression so closeups reduce body motion and favor face/head gestures.
