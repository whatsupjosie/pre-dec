/**
 * PubCast Behavior + Mocap Motion Pipeline (JavaScript)
 * UI-free runtime bridge for expanded animations, emotional cueing, mocap frames,
 * suppression, and procedural command output.
 */
const expanded = require('./animation_presets_expanded.js');
const engine = require('./behavior_animation_engine.js');

const BehaviorIntent = engine.BehaviorIntent || {
  IDLE: 'idle', LISTENING: 'listening', SPEAKING: 'speaking', THINKING: 'thinking',
  SKEPTICAL: 'skeptical', CONFIDENT: 'confident', RELAXED: 'relaxed', ENTHUSIASTIC: 'enthusiastic',
  GREETING: 'greeting', DIRECTING_ATTENTION: 'directing_attention'
};

const EmotionLabel = {
  NEUTRAL: 'neutral', WARM: 'warm', CURIOUS: 'curious', CONFIDENT: 'confident', THINKING: 'thinking',
  SKEPTICAL: 'skeptical', NERVOUS: 'nervous', RELAXED: 'relaxed', ENTHUSIASTIC: 'enthusiastic',
  GUARDED: 'guarded', FOCUSED: 'focused', RELIEVED: 'relieved'
};

const EMOTION_TO_INTENT = {
  neutral: BehaviorIntent.IDLE, warm: BehaviorIntent.RELAXED, curious: BehaviorIntent.LISTENING,
  confident: BehaviorIntent.CONFIDENT, thinking: BehaviorIntent.THINKING, skeptical: BehaviorIntent.SKEPTICAL,
  nervous: BehaviorIntent.THINKING, relaxed: BehaviorIntent.RELAXED, enthusiastic: BehaviorIntent.ENTHUSIASTIC,
  guarded: BehaviorIntent.SKEPTICAL, focused: BehaviorIntent.THINKING, relieved: BehaviorIntent.RELAXED,
};
const EMOTION_OVERLAY_ANIMS = {
  warm: 'warm_host_idle', curious: 'curious_idle', confident: 'confident_stance', thinking: 'thoughtful_idle',
  skeptical: 'skeptical_expression', nervous: 'nervous_idle', relaxed: 'relaxed_idle', enthusiastic: 'enthusiasm_bounce',
  guarded: 'guarded_idle', focused: 'focused_operator_idle', relieved: 'triumphant_recover'
};
const TEXT_CUE_MAP = [
  [['thank','welcome','glad','happy','great to see'], EmotionLabel.WARM, 0.55],
  [['hmm','interesting','what if','why','how'], EmotionLabel.CURIOUS, 0.45],
  [['exactly','absolutely','clearly',"here's the point"], EmotionLabel.CONFIDENT, 0.60],
  [['maybe','i think','let me think','consider'], EmotionLabel.THINKING, 0.55],
  [['no','but','however',"i don't buy",'skeptical'], EmotionLabel.SKEPTICAL, 0.60],
  [['sorry','uh','um','not sure','worried'], EmotionLabel.NERVOUS, 0.50],
  [['we did it','nice','perfect','finally'], EmotionLabel.RELIEVED, 0.65],
  [['wow','amazing','huge','yes!'], EmotionLabel.ENTHUSIASTIC, 0.70],
  [['focus','check','route','debug','preflight'], EmotionLabel.FOCUSED, 0.55],
];

class AvatarMotionProfile {
  constructor(opts={}) {
    this.avatarId = opts.avatarId || opts.avatar_id || 'avatar';
    this.expressiveness = opts.expressiveness ?? 0.55;
    this.fidgetRate = opts.fidgetRate ?? 0.35;
    this.nodRate = opts.nodRate ?? 0.50;
    this.gestureRate = opts.gestureRate ?? 0.45;
    this.stillnessPreference = opts.stillnessPreference ?? 0.35;
    this.politeness = opts.politeness ?? 0.65;
    this.cameraAwareness = opts.cameraAwareness ?? 0.50;
    this.preferredHand = opts.preferredHand || 'right';
    this.emotionalInertia = opts.emotionalInertia ?? 0.70;
    this.randomSeed = opts.randomSeed;
  }
  applyToState(state) {
    state.stillnessBias = Math.max(0, Math.min(1, this.stillnessPreference));
    state.energyLevel = Math.max(0, Math.min(1, 0.30 + this.expressiveness * 0.45));
    state.socialConfidence = Math.max(0, Math.min(1, 0.35 + this.gestureRate * 0.45));
  }
}

class EmotionCueMapper {
  cueFromText(text, nowMs, ttlMs=2500) {
    const lowered = String(text || '').toLowerCase();
    let best = { label: EmotionLabel.NEUTRAL, intensity: 0, source: 'text', confidence: 1, expiresAtMs: nowMs + ttlMs };
    for (const [needles, label, intensity] of TEXT_CUE_MAP) {
      if (needles.some(n => lowered.includes(n)) && intensity > best.intensity) {
        best = { label, intensity, source: 'text', confidence: 0.75, expiresAtMs: nowMs + ttlMs };
      }
    }
    if (String(text).includes('?') && best.intensity < 0.5) best = { label: EmotionLabel.CURIOUS, intensity: 0.45, source: 'punctuation', confidence: 0.65, expiresAtMs: nowMs + ttlMs };
    if (String(text).includes('!') && best.label === EmotionLabel.NEUTRAL) best = { label: EmotionLabel.ENTHUSIASTIC, intensity: 0.45, source: 'punctuation', confidence: 0.55, expiresAtMs: nowMs + ttlMs };
    return best;
  }
  apply(state, cue, profile, nowMs) {
    if (!cue || cue.label === EmotionLabel.NEUTRAL || (cue.expiresAtMs && nowMs >= cue.expiresAtMs)) return state.intent;
    const amount = Math.max(0, Math.min(1, cue.intensity * cue.confidence));
    const inertia = Math.max(0, Math.min(0.95, profile.emotionalInertia));
    const w = 1 - inertia;
    if ([EmotionLabel.ENTHUSIASTIC, EmotionLabel.CONFIDENT, EmotionLabel.RELIEVED].includes(cue.label)) {
      state.energyLevel = state.energyLevel * inertia + (0.75 + 0.20 * amount) * w;
      state.socialConfidence = state.socialConfidence * inertia + (0.70 + 0.20 * amount) * w;
      state.engagement = Math.max(state.engagement, 0.65 + 0.2 * amount);
    } else if ([EmotionLabel.SKEPTICAL, EmotionLabel.GUARDED].includes(cue.label)) {
      state.engagement = state.engagement * inertia + (0.35 + 0.15 * amount) * w;
      state.dominance = Math.max(state.dominance, 0.45 + 0.25 * amount);
      state.stillnessBias = Math.max(state.stillnessBias, 0.45);
    } else if ([EmotionLabel.THINKING, EmotionLabel.FOCUSED, EmotionLabel.CURIOUS].includes(cue.label)) {
      state.engagement = Math.max(state.engagement, 0.60);
      state.energyLevel = state.energyLevel * inertia + (0.45 + 0.15 * amount) * w;
      state.stillnessBias = Math.max(state.stillnessBias, 0.40);
    } else if (cue.label === EmotionLabel.NERVOUS) {
      state.interruptionPressure = Math.max(state.interruptionPressure, 0.45 + 0.30 * amount);
      state.socialConfidence = Math.min(state.socialConfidence, 0.45);
    }
    return EMOTION_TO_INTENT[cue.label] || state.intent;
  }
}

class MocapAdapter {
  constructor(confidenceThreshold=0.55) { this.confidenceThreshold = confidenceThreshold; }
  angle(a,b) { return Math.atan2(b.y-a.y, b.x-a.x) * 180 / Math.PI; }
  dist(a,b) { return Math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + ((a.z||0)-(b.z||0))**2); }
  inferBehaviorFromMocap(frame) {
    if (!frame || (frame.bodyConfidence ?? frame.body_confidence ?? 0) < this.confidenceThreshold) return [];
    const conf = frame.bodyConfidence ?? frame.body_confidence ?? 1;
    const ts = frame.timestampMs ?? frame.timestamp_ms ?? Date.now();
    const j = frame.joints || {};
    const cues = [];
    const nose = j.nose || j.head, neck = j.neck || j.chest;
    const ls = j.left_shoulder, rs = j.right_shoulder;
    const lw = j.left_wrist, rw = j.right_wrist;
    if (nose && neck && neck.y - nose.y < -0.05) cues.push({label:EmotionLabel.THINKING, intensity:.35, source:'mocap_head', confidence:conf, expiresAtMs:ts+900});
    if (ls && rs && nose) {
      const width = Math.max(0.001, this.dist(ls, rs));
      const lean = (nose.x - ((ls.x + rs.x)/2)) / width;
      if (Math.abs(lean) > .22) cues.push({label:EmotionLabel.CURIOUS, intensity:Math.min(.65, Math.abs(lean)), source:'mocap_lean', confidence:conf, expiresAtMs:ts+1200});
    }
    if (nose && [lw,rw].some(w => w && (w.confidence ?? 1) > .55 && w.y > nose.y - .05)) cues.push({label:EmotionLabel.ENTHUSIASTIC, intensity:.45, source:'mocap_hand_raise', confidence: frame.handsConfidence ?? frame.hands_confidence ?? conf, expiresAtMs: ts+1000});
    return cues;
  }
  buildPoseCommand(avatarId, frame) {
    const conf = frame ? (frame.bodyConfidence ?? frame.body_confidence ?? 0) : 0;
    if (!frame || conf < this.confidenceThreshold) return null;
    const ts = frame.timestampMs ?? frame.timestamp_ms ?? Date.now();
    const j = frame.joints || {};
    const pose = { timestamp_ms: ts, source: frame.source || 'mocap', bones: {} };
    if (j.left_shoulder && j.right_shoulder) pose.bones.spine = { rotation: [0,0, Math.max(-12, Math.min(12, this.angle(j.left_shoulder, j.right_shoulder)))] };
    if (j.nose && j.neck) pose.bones.head = { rotation: [Math.max(-18, Math.min(18, (j.nose.x-j.neck.x)*30)), Math.max(-15, Math.min(15, -(j.nose.y-j.neck.y)*20)), 0] };
    for (const side of ['left','right']) {
      const sh = j[`${side}_shoulder`], el = j[`${side}_elbow`], wr = j[`${side}_wrist`];
      if (sh && el) pose.bones[`arm_${side}`] = { rotation: [0,0,this.angle(sh,el)] };
      if (el && wr) pose.bones[`forearm_${side}`] = { rotation: [0,0,this.angle(el,wr)] };
    }
    return { avatarId, kind:'mocap_pose', layer:'MOCAP_BASE', weight:Math.max(0, Math.min(1, conf)), durationMs:120, blendInMs:50, blendOutMs:80, priority:70, source:frame.source || 'mocap', reason:'live mocap pose retarget proxy', pose };
  }
}

class BehaviorMotionPipeline {
  constructor(profile=new AvatarMotionProfile(), opts={}) {
    this.profile = profile;
    this.mapper = new EmotionCueMapper();
    this.mocap = new MocapAdapter();
    this.state = new engine.BehaviorState(profile.avatarId);
    profile.applyToState(this.state);
    this.selector = new engine.BehaviorAnimationSelector({ library: expanded.ANIMATION_LIBRARY, getAnimationsForContext: expanded.getAnimationsForContext });
    this.activeCues = [];
    this.lastTickMs = null;
  }
  pushEmotion(cue) { this.activeCues.push(cue); }
  pushText(text, nowMs=Date.now()) { const cue = this.mapper.cueFromText(text, nowMs); this.pushEmotion(cue); return cue; }
  chooseIntent(explicitIntent, nowMs) {
    if (explicitIntent) return explicitIntent;
    this.activeCues = this.activeCues.filter(c => !c.expiresAtMs || nowMs < c.expiresAtMs);
    if (!this.activeCues.length) return this.state.intent;
    const strongest = this.activeCues.slice().sort((a,b)=>(b.intensity*b.confidence)-(a.intensity*a.confidence))[0];
    return this.mapper.apply(this.state, strongest, this.profile, nowMs);
  }
  overlayCommand(cue, nowMs) {
    if (!cue || (cue.expiresAtMs && nowMs >= cue.expiresAtMs)) return null;
    const animId = EMOTION_OVERLAY_ANIMS[cue.label];
    const preset = expanded.getAnimation(animId);
    if (!preset) return null;
    return { avatarId:this.profile.avatarId, kind:'overlay', layer:'EMOTION_OVERLAY', animationId:animId, weight:Math.max(.1, Math.min(.65, cue.intensity*cue.confidence*this.profile.expressiveness)), durationMs:preset.durationMs, blendInMs:120, blendOutMs:160, priority:20, source:cue.source, reason:`emotion overlay for ${cue.label}`, metadata:{emotion:cue.label, intensity:cue.intensity} };
  }
  tick({nowMs=Date.now(), elapsedMs=null, explicitIntent=null, transcriptText=null, mocapFrame=null, isSeated=null}={}) {
    if (elapsedMs === null) elapsedMs = this.lastTickMs === null ? 0 : Math.max(0, nowMs-this.lastTickMs);
    this.lastTickMs = nowMs;
    if (isSeated !== null) this.state.isSeated = !!isSeated;
    if (transcriptText) this.pushText(transcriptText, nowMs);
    for (const cue of this.mocap.inferBehaviorFromMocap(mocapFrame)) this.pushEmotion(cue);
    const intent = this.chooseIntent(explicitIntent, nowMs);
    this.state.updateIntent ? this.state.updateIntent(intent) : this.state.intent = intent;
    const commands = [];
    const mocapCmd = this.mocap.buildPoseCommand(this.profile.avatarId, mocapFrame);
    if (mocapCmd) { commands.push(mocapCmd); this.state.stillnessBias = Math.max(this.state.stillnessBias, .5); }
    const live = this.activeCues.filter(c => !c.expiresAtMs || nowMs < c.expiresAtMs);
    const strongest = live.length ? live.slice().sort((a,b)=>(b.intensity*b.confidence)-(a.intensity*a.confidence))[0] : null;
    const overlay = this.overlayCommand(strongest, nowMs);
    if (overlay) commands.push(overlay);
    const decision = this.selector.tick(this.state, elapsedMs, intent, nowMs);
    const overlayAnimId = overlay ? overlay.animationId : null;
    if (decision && decision.animationId && !decision.suppressed && decision.animationId === overlayAnimId) {
      commands.push({ avatarId:this.profile.avatarId, kind:'hold', layer:'STILLNESS', durationMs:250, weight:1, priority:5, source:'overlay_dedupe', reason:'procedural candidate already active as emotional overlay', metadata:{candidate:decision.animationId, intent} });
    } else if (decision && decision.animationId && !decision.suppressed) {
      const preset = expanded.getAnimation(decision.animationId);
      commands.push({ avatarId:this.profile.avatarId, kind:'procedural_animation', layer:decision.layerName || String(decision.layer), animationId:decision.animationId, weight:Math.min(1, .35+this.profile.expressiveness*.65), durationMs:preset ? preset.durationMs : 800, blendInMs:120, blendOutMs:160, priority:50, source:'behavior_selector', reason:decision.reason, metadata:{alternatives:decision.alternatives, score:decision.score, intent} });
    } else if (decision && decision.suppressed) {
      commands.push({ avatarId:this.profile.avatarId, kind:'hold', layer:'STILLNESS', durationMs:250, weight:1, priority:5, source:'suppression_gate', reason:decision.reason, metadata:{candidate:decision.animationId, intent} });
    }
    return { avatarId:this.profile.avatarId, commands, stateSnapshot:{ avatar_id:this.profile.avatarId, intent:this.state.intent, is_seated:this.state.isSeated, energy_level:this.state.energyLevel, social_confidence:this.state.socialConfidence, engagement:this.state.engagement, stillness_bias:this.state.stillnessBias, active_cues:live.map(c=>c.label), last_animation_id:this.state.lastAnimationId }, decision, warnings: commands.length ? [] : ['No motion command emitted; keep previous pose.'] };
  }
}

function makeTestMocapFrame(ts=1000) {
  return { timestampMs:ts, source:'test_webcam_proxy', bodyConfidence:.82, handsConfidence:.66, joints:{ nose:{x:.51,y:.82,confidence:.9}, neck:{x:.50,y:.70,confidence:.9}, left_shoulder:{x:.38,y:.66,confidence:.9}, right_shoulder:{x:.62,y:.66,confidence:.9}, left_elbow:{x:.34,y:.52,confidence:.8}, right_elbow:{x:.66,y:.52,confidence:.8}, left_wrist:{x:.32,y:.42,confidence:.75}, right_wrist:{x:.69,y:.86,confidence:.75} } };
}

module.exports = { EmotionLabel, AvatarMotionProfile, EmotionCueMapper, MocapAdapter, BehaviorMotionPipeline, makeTestMocapFrame, EMOTION_OVERLAY_ANIMS, EMOTION_TO_INTENT };
