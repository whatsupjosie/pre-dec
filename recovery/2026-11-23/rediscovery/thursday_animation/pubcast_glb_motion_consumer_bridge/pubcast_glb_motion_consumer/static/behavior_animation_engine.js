/**
 * PubCast Behavior Animation Engine (JavaScript)
 * ---------------------------------------------
 * Browser/Node companion to behavior_animation_engine.py.
 * Turns conversational intent into layered, suppression-aware animation choices.
 */

const BodyLayer = Object.freeze({
  BASE_POSTURE: 10,
  EMOTION_OVERLAY: 20,
  TORSO: 30,
  HEAD: 40,
  GAZE: 45,
  HANDS: 50,
  FIDGET: 55,
  SPEECH_GESTURE: 60,
  SCRIPTED: 80,
  SAFETY_OVERRIDE: 100,
});

const BehaviorIntent = Object.freeze({
  IDLE: "idle",
  LISTENING: "listening",
  SPEAKING: "speaking",
  THINKING: "thinking",
  SKEPTICAL: "skeptical",
  CONFIDENT: "confident",
  RELAXED: "relaxed",
  ENTHUSIASTIC: "enthusiastic",
  GREETING: "greeting",
  DIRECTING_ATTENTION: "directing_attention",
});

const LayerNames = Object.fromEntries(Object.entries(BodyLayer).map(([k, v]) => [v, k]));

const ANIMATION_LAYER_HINTS = Object.freeze({
  confident_stance: BodyLayer.EMOTION_OVERLAY,
  thoughtful_idle: BodyLayer.EMOTION_OVERLAY,
  skeptical_expression: BodyLayer.EMOTION_OVERLAY,
  enthusiasm_bounce: BodyLayer.EMOTION_OVERLAY,
  relaxed_idle: BodyLayer.EMOTION_OVERLAY,
  nod_slow: BodyLayer.HEAD,
  nod_emphatic: BodyLayer.HEAD,
  head_shake: BodyLayer.HEAD,
  head_tilt_left: BodyLayer.HEAD,
  head_tilt_right: BodyLayer.HEAD,
  lean_forward: BodyLayer.TORSO,
  lean_back: BodyLayer.TORSO,
  weight_shift_left: BodyLayer.TORSO,
  weight_shift_right: BodyLayer.TORSO,
  open_palm_presentation: BodyLayer.SPEECH_GESTURE,
  pointing_gesture: BodyLayer.SPEECH_GESTURE,
  hand_wave: BodyLayer.SPEECH_GESTURE,
  shoulder_shrug: BodyLayer.SPEECH_GESTURE,
  hand_to_chin: BodyLayer.HANDS,
  hands_on_hips: BodyLayer.HANDS,
  hands_cross_chest: BodyLayer.HANDS,
  hands_together_chest: BodyLayer.HANDS,
  adjust_collar: BodyLayer.FIDGET,
  smooth_hair: BodyLayer.FIDGET,
  clasp_hands_relax: BodyLayer.FIDGET,
  finger_tap: BodyLayer.FIDGET,
  glance_down: BodyLayer.HEAD,
  touch_face: BodyLayer.FIDGET,
  adjust_seat: BodyLayer.FIDGET,
});

const INTENT_TAG_WEIGHTS = Object.freeze({
  listening: { listening: 2.0, agreement: 1.2, engagement: 1.1, natural: 0.7 },
  speaking: { gesture: 2.0, presentation: 1.6, emphasis: 1.4, direction: 1.0 },
  thinking: { thinking: 2.0, pondering: 1.7, fidget: 0.8, thoughtful: 1.4 },
  skeptical: { skepticism: 2.2, disagreement: 1.6, defensive: 1.1 },
  confident: { confident: 2.0, assertive: 1.3, presentation: 0.8 },
  relaxed: { relaxed: 2.0, calm: 1.0, natural: 0.8 },
  enthusiastic: { enthusiastic: 2.0, gesture: 1.1, friendly: 0.8 },
  greeting: { greeting: 3.0, friendly: 2.0 },
  directing_attention: { direction: 3.0, reference: 1.5, emphasis: 1.0 },
  idle: { natural: 1.0, presence: 0.8, relaxed: 0.7 },
});

const INTENT_ANIMATION_BONUSES = Object.freeze({
  skeptical: { head_shake: 1.5, lean_back: 1.0, skeptical_expression: 1.3, hands_cross_chest: 0.9 },
  thinking: { hand_to_chin: 1.4, glance_down: 1.1, thoughtful_idle: 1.5, touch_face: 0.6 },
  confident: { confident_stance: 1.6, hands_on_hips: 1.2, open_palm_presentation: 0.6 },
  relaxed: { relaxed_idle: 1.6, clasp_hands_relax: 0.8, lean_back: 0.5 },
  enthusiastic: { enthusiasm_bounce: 1.5, open_palm_presentation: 1.1, nod_emphatic: 0.8 },
  greeting: { hand_wave: 4.0 },
  directing_attention: { pointing_gesture: 3.0, open_palm_presentation: 1.2 },
});

function clamp01(v) { return Math.max(0, Math.min(1, Number(v) || 0)); }

class BehaviorState {
  constructor(avatarId, options = {}) {
    this.avatarId = avatarId;
    this.isSeated = !!options.isSeated;
    this.intent = options.intent || BehaviorIntent.IDLE;
    this.energyLevel = clamp01(options.energyLevel ?? 0.45);
    this.socialConfidence = clamp01(options.socialConfidence ?? 0.5);
    this.attentionFocus = options.attentionFocus || null;
    this.engagement = clamp01(options.engagement ?? 0.5);
    this.dominance = clamp01(options.dominance ?? 0.35);
    this.interruptionPressure = clamp01(options.interruptionPressure ?? 0);
    this.fatigue = clamp01(options.fatigue ?? 0.1);
    this.stillnessBias = clamp01(options.stillnessBias ?? 0.35);
    this.lastAnimationId = null;
    this.lastAnimationAtMs = -10000;
    this.cooldowns = {};
    this.activeLayers = {};
    this.recentTags = [];
    this.heldPoseUntilMs = 0;
  }

  updateIntent(intent) { this.intent = intent || this.intent; }

  decay(elapsedMs) {
    const factor = Math.min(1, Math.max(0, elapsedMs) / 10000);
    this.interruptionPressure *= (1 - 0.5 * factor);
    this.fatigue = clamp01(this.fatigue + 0.015 * factor);
    this.energyLevel = clamp01(this.energyLevel - 0.01 * factor + this.engagement * 0.005 * factor);
  }
}

class AnimationConflictResolver {
  constructor(layerHints = {}) { this.layerHints = { ...ANIMATION_LAYER_HINTS, ...layerHints }; }

  inferLayer(preset) {
    if (!preset) return BodyLayer.TORSO;
    const id = preset.animationId || preset.animation_id;
    if (this.layerHints[id]) return this.layerHints[id];
    const tags = new Set(preset.tags || []);
    const category = preset.category || "";
    if (tags.has("fidget") || category === "fidget") return BodyLayer.FIDGET;
    if (tags.has("gesture") || category === "gesture") return BodyLayer.SPEECH_GESTURE;
    if (tags.has("listening")) return BodyLayer.HEAD;
    if (category === "emotional") return BodyLayer.EMOTION_OVERLAY;
    return BodyLayer.TORSO;
  }

  affectedBones(preset) {
    return new Set((preset.frames || []).map(f => f.boneId || f.bone_id).filter(Boolean));
  }

  conflicts(preset, state, nowMs) {
    const newLayer = this.inferLayer(preset);
    const newBones = this.affectedBones(preset);
    for (const [layerKey, active] of Object.entries(state.activeLayers)) {
      if (active.untilMs <= nowMs) { delete state.activeLayers[layerKey]; continue; }
      const activeBones = new Set(active.bones || []);
      const boneOverlap = [...newBones].some(b => activeBones.has(b));
      const sameLayer = Number(layerKey) === newLayer;
      if (active.locked && (boneOverlap || sameLayer)) return [true, `blocked by locked ${active.animationId}`];
      if (boneOverlap && newLayer < Number(layerKey)) return [true, `bone conflict with ${active.animationId}`];
      if (sameLayer && (preset.animationId || preset.animation_id) !== active.animationId) return [true, `layer occupied by ${active.animationId}`];
    }
    return [false, "no conflict"];
  }

  activate(preset, state, nowMs, locked = false) {
    const layer = this.inferLayer(preset);
    const duration = preset.durationMs || preset.duration_ms || 800;
    state.activeLayers[layer] = {
      animationId: preset.animationId || preset.animation_id,
      layer,
      startedAtMs: nowMs,
      untilMs: nowMs + Math.max(100, duration),
      bones: [...this.affectedBones(preset)],
      locked: locked || !!(preset.isBlocking || preset.is_blocking),
    };
    return state.activeLayers[layer];
  }
}

class AnimationSuppressionGate {
  constructor({ minimumGapMs = 450, repeatGapMs = 2400 } = {}) {
    this.minimumGapMs = minimumGapMs;
    this.repeatGapMs = repeatGapMs;
  }

  shouldSuppress(preset, state, nowMs) {
    const id = preset.animationId || preset.animation_id;
    if (nowMs < state.heldPoseUntilMs) return [true, "pose hold is intentionally suppressing new motion"];
    if (nowMs - state.lastAnimationAtMs < this.minimumGapMs) return [true, "minimum animation gap not met"];
    if (id === state.lastAnimationId && nowMs - state.lastAnimationAtMs < this.repeatGapMs) return [true, "exact repeat suppressed"];
    if (nowMs < (state.cooldowns[id] || -1)) return [true, `${id} is cooling down`];
    const tags = new Set(preset.tags || []);
    const isFidget = tags.has("fidget") || preset.category === "fidget";
    const isBigGesture = tags.has("gesture") || tags.has("presentation") || tags.has("direction");
    if (state.intent === BehaviorIntent.LISTENING && isBigGesture && state.energyLevel < 0.75) return [true, "listener should not steal focus"];
    if (state.fatigue > 0.78 && isFidget) return [true, "fatigue prefers stillness"];
    if (state.stillnessBias > 0.65 && isFidget && state.energyLevel < 0.55) return [true, "stillness bias suppresses fidget"];
    return [false, "allowed"];
  }

  notePlayed(preset, state, nowMs) {
    const id = preset.animationId || preset.animation_id;
    const duration = preset.durationMs || preset.duration_ms || 800;
    const tags = preset.tags || [];
    state.lastAnimationId = id;
    state.lastAnimationAtMs = nowMs;
    state.recentTags = [...state.recentTags, ...tags].slice(-12);
    let cooldown = Math.max(900, Math.floor(duration * 1.35));
    if (id.startsWith("nod")) cooldown = Math.max(cooldown, 1400);
    if (tags.includes("gesture") || tags.includes("presentation")) cooldown = Math.max(cooldown, 1800);
    if (tags.includes("fidget")) cooldown = Math.max(cooldown, 2600);
    state.cooldowns[id] = nowMs + cooldown;
    if (tags.includes("gesture") || tags.includes("emphasis")) state.heldPoseUntilMs = Math.max(state.heldPoseUntilMs, nowMs + Math.min(900, duration));
  }
}

class BehaviorAnimationSelector {
  constructor({ library, getAnimationsForContext, random = Math.random, resolver, suppression } = {}) {
    this.library = library || {};
    this.getAnimationsForContext = getAnimationsForContext || (() => ({}));
    this.random = random;
    this.resolver = resolver || new AnimationConflictResolver();
    this.suppression = suppression || new AnimationSuppressionGate();
  }

  contextCandidates(state) {
    const contextMap = {
      idle: ["standing"], listening: ["listening"], speaking: ["speaking"], thinking: ["thinking"],
      skeptical: ["listening", "thinking"], confident: ["speaking", "standing"], relaxed: ["standing", "seated"],
      enthusiastic: ["speaking"], greeting: ["speaking"], directing_attention: ["speaking"],
    };
    const contexts = [...(contextMap[state.intent] || [])];
    if (state.isSeated) contexts.unshift("seated");
    const candidates = {};
    for (const ctx of contexts) Object.assign(candidates, this.getAnimationsForContext(ctx) || {});
    for (const id of Object.keys(INTENT_ANIMATION_BONUSES[state.intent] || {})) if (this.library[id]) candidates[id] = this.library[id];
    return Object.keys(candidates).length ? candidates : this.library;
  }

  score(preset, state, nowMs) {
    const id = preset.animationId || preset.animation_id;
    const tags = new Set(preset.tags || []);
    let score = 0.1;
    for (const [tag, weight] of Object.entries(INTENT_TAG_WEIGHTS[state.intent] || {})) if (tags.has(tag)) score += weight;
    score += (INTENT_ANIMATION_BONUSES[state.intent] || {})[id] || 0;
    if (state.isSeated && tags.has("seated")) score += 1.1;
    if (!state.isSeated && tags.has("seated")) score -= 1.8;
    if (tags.has("engagement") || tags.has("listening")) score += 0.8 * state.engagement;
    if (tags.has("confident") || tags.has("assertive")) score += 0.8 * state.socialConfidence + 0.4 * state.dominance;
    if (tags.has("fidget")) score += 0.9 * state.interruptionPressure + 0.3 * state.energyLevel - 0.9 * state.stillnessBias;
    if (tags.has("gesture") || tags.has("presentation") || tags.has("emphasis")) score += 0.8 * state.energyLevel + 0.4 * state.socialConfidence;
    if (tags.has("skepticism") || tags.has("disagreement")) score += 0.7 * (1 - state.engagement) + 0.5 * state.dominance;
    if (id === state.lastAnimationId) score -= 4.0;
    const overlap = [...tags].filter(t => state.recentTags.slice(-5).includes(t)).length;
    score -= Math.min(1.5, overlap * 0.25);
    if (nowMs < (state.cooldowns[id] || -1)) score -= 5.0;
    score += (this.random() * 0.24) - 0.12;
    return score;
  }

  decide(state, nowMs = Date.now()) {
    const candidates = this.contextCandidates(state);
    const scored = [];
    for (const [id, preset] of Object.entries(candidates)) {
      const [conflict] = this.resolver.conflicts(preset, state, nowMs);
      if (conflict) continue;
      const score = this.score(preset, state, nowMs);
      if (score > 0) scored.push([id, score, preset]);
    }
    scored.sort((a, b) => b[1] - a[1]);
    if (!scored.length) return { animationId: null, suppressed: true, reason: "no viable animation candidates", alternatives: [] };
    const [id, score, preset] = scored[0];
    const layer = this.resolver.inferLayer(preset);
    const [suppressed, reason] = this.suppression.shouldSuppress(preset, state, nowMs);
    const alternatives = scored.slice(0, 5).map(([aid, s]) => [aid, Number(s.toFixed(3))]);
    if (suppressed) return { animationId: id, layer, layerName: LayerNames[layer], suppressed, reason, score, alternatives };
    this.resolver.activate(preset, state, nowMs);
    this.suppression.notePlayed(preset, state, nowMs);
    return { animationId: id, layer, layerName: LayerNames[layer], suppressed: false, reason: "selected from behavior state", score, alternatives };
  }

  tick(state, elapsedMs, intent, nowMs = Date.now()) {
    if (intent) state.updateIntent(intent);
    state.decay(elapsedMs || 0);
    return this.decide(state, nowMs);
  }
}

if (typeof module !== "undefined") {
  module.exports = { BodyLayer, BehaviorIntent, BehaviorState, AnimationConflictResolver, AnimationSuppressionGate, BehaviorAnimationSelector };
}
if (typeof window !== "undefined") {
  window.PubcastBehaviorAnimation = { BodyLayer, BehaviorIntent, BehaviorState, AnimationConflictResolver, AnimationSuppressionGate, BehaviorAnimationSelector };
}
