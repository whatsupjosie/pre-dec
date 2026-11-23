const assert = require('assert');
const presets = require('../modules/animation_presets_complete.js');
const {
  BehaviorIntent,
  BehaviorState,
  BehaviorAnimationSelector,
  AnimationSuppressionGate,
} = require('../modules/behavior_animation_engine.js');

function main() {
  const selector = new BehaviorAnimationSelector({
    library: presets.ANIMATION_LIBRARY,
    getAnimationsForContext: presets.getAnimationsForContext,
    random: () => 0.42,
  });

  const state = new BehaviorState('js-demo', { isSeated: true, intent: BehaviorIntent.THINKING });
  const decision = selector.decide(state, 10000);
  assert(decision.animationId, 'expected an animation decision');

  const gate = new AnimationSuppressionGate({ minimumGapMs: 0, repeatGapMs: 3000 });
  const nod = presets.getAnimation('nod_slow');
  gate.notePlayed(nod, state, 20000);
  const [suppressed, reason] = gate.shouldSuppress(nod, state, 21000);
  assert.strictEqual(suppressed, true);
  assert(reason.includes('repeat'));

  console.log('JS behavior animation tests passed');
}

main();
