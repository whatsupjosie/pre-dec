/**
 * PubCast Expanded Animation Presets (JavaScript)
 * Adds second-wave behavior vocabulary over animation_presets_complete.js.
 */
const base = require('./animation_presets_complete.js');
const { AnimationCategory } = base;

function frame(boneId, frameNumber, durationMs, position=[0,0,0], rotation=[0,0,0], scale=[1,1,1]) {
  return { boneId, frameNumber, durationMs, position, rotation, scale };
}
function preset(animationId, category, displayName, durationMs, frames, opts={}) {
  return {
    animationId,
    category,
    displayName,
    durationMs,
    isLoopable: !!opts.loop,
    isBlocking: !!opts.blocking,
    frames,
    rootMotion: false,
    blendableWith: opts.blendableWith || [],
    tags: opts.tags || [],
    description: opts.description || '',
    characterSpecific: {},
  };
}

const EXPANDED_ANIMATIONS = {
  micro_nod: preset('micro_nod', AnimationCategory.LISTENING, 'Micro Nod', 520, [frame('head',0,0), frame('head',8,170,[0,0,0],[0,1.1,0]), frame('head',16,180), frame('head',24,170,[0,0,0],[0,-0.4,0])], {tags:['listening','agreement','subtle','presence','natural'], description:'Tiny acknowledgment nod.'}),
  delayed_nod: preset('delayed_nod', AnimationCategory.LISTENING, 'Delayed Nod', 1800, [frame('head',0,0), frame('head',18,650), frame('head',28,420,[0,0,0],[0,2.2,0]), frame('head',40,420), frame('head',48,310,[0,0,0],[0,-0.7,0])], {tags:['listening','agreement','thoughtful','delayed','natural'], description:'Agreement after processing.'}),
  double_take_subtle: preset('double_take_subtle', AnimationCategory.LISTENING, 'Subtle Double Take', 900, [frame('head',0,0), frame('head',8,220,[0,0,0],[0,0,4]), frame('head',16,180), frame('head',24,250,[0,0,0],[0,0,-5]), frame('head',32,250)], {tags:['surprise','curiosity','listening','reaction','subtle']}),
  listen_breath_settle: preset('listen_breath_settle', AnimationCategory.LISTENING, 'Listening Breath Settle', 1600, [frame('spine',0,0), frame('chest',0,0), frame('spine',20,800,[0,0,0],[0,0,1.2]), frame('chest',20,800,[0,0.25,0]), frame('spine',40,800), frame('chest',40,800)], {loop:true, tags:['listening','breath','presence','subtle','natural']}),
  attentive_turn_left: preset('attentive_turn_left', AnimationCategory.LISTENING, 'Attentive Turn Left', 760, [frame('head',0,0), frame('spine',0,0), frame('head',16,380,[0,0,0],[-5,0,-2]), frame('spine',16,380,[0,0,0],[-2,0,0]), frame('head',32,380,[0,0,0],[-3,0,-1])], {tags:['listening','attention','turn','left','engagement']}),
  attentive_turn_right: preset('attentive_turn_right', AnimationCategory.LISTENING, 'Attentive Turn Right', 760, [frame('head',0,0), frame('spine',0,0), frame('head',16,380,[0,0,0],[5,0,2]), frame('spine',16,380,[0,0,0],[2,0,0]), frame('head',32,380,[0,0,0],[3,0,1])], {tags:['listening','attention','turn','right','engagement']}),
  soft_disagree: preset('soft_disagree', AnimationCategory.LISTENING, 'Soft Disagreement', 950, [frame('head',0,0), frame('head',10,240,[0,0,0],[0,0,-3.5]), frame('head',20,240,[0,0,0],[0,0,3.5]), frame('head',30,240,[0,0,0],[0,0,-2]), frame('head',38,230)], {tags:['disagreement','skepticism','listening','subtle','natural']}),
  processing_pause: preset('processing_pause', AnimationCategory.LISTENING, 'Processing Pause', 1400, [frame('head',0,0), frame('spine',0,0), frame('head',20,700,[0,0,0],[2.5,0,0]), frame('spine',20,700,[0,0,0],[0,0,-1]), frame('head',40,700), frame('spine',40,700)], {tags:['thinking','listening','processing','stillness','subtle']}),

  small_beat_left: preset('small_beat_left', AnimationCategory.GESTURE, 'Small Beat Left', 520, [frame('hand_left',0,0), frame('arm_left',0,0), frame('hand_left',10,220,[0.6,0.8,0],[0,0,12]), frame('arm_left',10,220,[0,0,0],[0,0,12]), frame('hand_left',24,300), frame('arm_left',24,300)], {tags:['gesture','emphasis','speech','beat','subtle']}),
  small_beat_right: preset('small_beat_right', AnimationCategory.GESTURE, 'Small Beat Right', 520, [frame('hand_right',0,0), frame('arm_right',0,0), frame('hand_right',10,220,[-0.6,0.8,0],[0,0,-12]), frame('arm_right',10,220,[0,0,0],[0,0,-12]), frame('hand_right',24,300), frame('arm_right',24,300)], {tags:['gesture','emphasis','speech','beat','subtle']}),
  count_on_fingers: preset('count_on_fingers', AnimationCategory.GESTURE, 'Count on Fingers', 1500, [frame('hand_right',0,0), frame('arm_right',0,0), frame('hand_right',10,300,[-1.2,1.1,0],[0,0,-20]), frame('hand_right',25,400,[-1.1,1.15,0],[0,0,-10]), frame('hand_right',40,400,[-1.0,1.2,0],[0,0,-4]), frame('hand_right',55,400), frame('arm_right',55,400)], {tags:['gesture','explain','counting','speech','emphasis']}),
  frame_the_idea: preset('frame_the_idea', AnimationCategory.GESTURE, 'Frame the Idea', 1100, [frame('hand_left',0,0), frame('hand_right',0,0), frame('hand_left',20,500,[1.3,1.1,0],[0,0,25]), frame('hand_right',20,500,[-1.3,1.1,0],[0,0,-25]), frame('hand_left',40,600,[1.4,1.1,0],[0,0,20]), frame('hand_right',40,600,[-1.4,1.1,0],[0,0,-20])], {tags:['gesture','presentation','explain','idea','speech']}),
  offer_object_space: preset('offer_object_space', AnimationCategory.GESTURE, 'Offer Object Space', 950, [frame('hand_left',0,0), frame('hand_right',0,0), frame('hand_left',20,460,[0.9,0.6,0.3],[0,0,28]), frame('hand_right',20,460,[-0.9,0.6,0.3],[0,0,-28]), frame('hand_left',38,490,[0.7,0.6,0.3]), frame('hand_right',38,490,[-0.7,0.6,0.3])], {tags:['gesture','presentation','offering','space','speech']}),
  precision_pinch: preset('precision_pinch', AnimationCategory.GESTURE, 'Precision Pinch', 700, [frame('hand_right',0,0), frame('arm_right',0,0), frame('hand_right',16,350,[-1.0,1.1,0],[0,0,-8]), frame('arm_right',16,350,[0,0,0],[0,0,-18]), frame('hand_right',32,350), frame('arm_right',32,350)], {tags:['gesture','precision','small','emphasis','speech']}),
  palms_down_calm: preset('palms_down_calm', AnimationCategory.GESTURE, 'Palms Down Calm', 900, [frame('hand_left',0,0), frame('hand_right',0,0), frame('hand_left',20,450,[0.8,-0.4,0],[0,0,-8]), frame('hand_right',20,450,[-0.8,-0.4,0],[0,0,8]), frame('hand_left',40,450), frame('hand_right',40,450)], {tags:['gesture','calm','deescalate','speech','control']}),
  not_me_gesture: preset('not_me_gesture', AnimationCategory.GESTURE, 'Not Me Gesture', 850, [frame('hand_left',0,0), frame('hand_right',0,0), frame('shoulder_left',0,0), frame('shoulder_right',0,0), frame('hand_left',18,380,[1.1,0.7,0],[0,0,18]), frame('hand_right',18,380,[-1.1,0.7,0],[0,0,-18]), frame('shoulder_left',18,380,[0,0.5,0]), frame('shoulder_right',18,380,[0,0.5,0]), frame('hand_left',36,470), frame('hand_right',36,470)], {tags:['gesture','uncertainty','deflect','humor','speech']}),

  adjust_sleeve_left: preset('adjust_sleeve_left', AnimationCategory.FIDGET, 'Adjust Left Sleeve', 1050, [frame('hand_right',0,0), frame('arm_right',0,0), frame('hand_right',12,350,[0.9,0.2,0],[0,0,-18]), frame('hand_right',24,350,[0.8,0.1,0],[0,0,-12]), frame('hand_right',36,350), frame('arm_right',36,350)], {tags:['fidget','grooming','natural','subtle','hands']}),
  adjust_sleeve_right: preset('adjust_sleeve_right', AnimationCategory.FIDGET, 'Adjust Right Sleeve', 1050, [frame('hand_left',0,0), frame('arm_left',0,0), frame('hand_left',12,350,[-0.9,0.2,0],[0,0,18]), frame('hand_left',24,350,[-0.8,0.1,0],[0,0,12]), frame('hand_left',36,350), frame('arm_left',36,350)], {tags:['fidget','grooming','natural','subtle','hands']}),
  rub_palms_once: preset('rub_palms_once', AnimationCategory.FIDGET, 'Rub Palms Once', 950, [frame('hand_left',0,0), frame('hand_right',0,0), frame('hand_left',12,300,[0.35,-0.2,0]), frame('hand_right',12,300,[-0.35,-0.2,0]), frame('hand_left',24,300,[0.15,-0.2,0]), frame('hand_right',24,300,[-0.15,-0.2,0]), frame('hand_left',36,350), frame('hand_right',36,350)], {tags:['fidget','anticipation','thinking','hands','subtle']}),
  ankle_shift_seated: preset('ankle_shift_seated', AnimationCategory.SEATED, 'Ankle Shift Seated', 800, [frame('foot_left',0,0), frame('foot_right',0,0), frame('pelvis',0,0), frame('foot_left',16,400,[0.2,0,0],[0,0,3]), frame('pelvis',16,400,[0.15,0,0]), frame('foot_left',32,400), frame('pelvis',32,400)], {tags:['seated','fidget','body','subtle','natural']}),
  table_hand_settle: preset('table_hand_settle', AnimationCategory.SEATED, 'Table Hand Settle', 700, [frame('hand_left',0,0), frame('hand_right',0,0), frame('hand_left',14,350,[0.5,-0.8,0.4]), frame('hand_right',14,350,[-0.5,-0.8,0.4]), frame('hand_left',28,350,[0.45,-0.85,0.4]), frame('hand_right',28,350,[-0.45,-0.85,0.4])], {tags:['seated','hands','settle','podcast','natural']}),
  mic_check_lean: preset('mic_check_lean', AnimationCategory.SEATED, 'Mic Check Lean', 850, [frame('spine',0,0), frame('head',0,0), frame('hand_right',0,0), frame('spine',18,420,[1,0,0],[0,0,4]), frame('head',18,420,[0,0,0],[0,1,0]), frame('hand_right',18,420,[-0.5,-0.3,0.6]), frame('spine',34,430), frame('head',34,430), frame('hand_right',34,430)], {tags:['seated','podcast','mic','lean','technical','fidget']}),
  chair_recenter: preset('chair_recenter', AnimationCategory.SEATED, 'Chair Recenter', 1000, [frame('pelvis',0,0), frame('spine',0,0), frame('pelvis',12,300,[0.35,0,0]), frame('spine',12,300,[0,0,0],[0,0,-1.5]), frame('pelvis',24,300,[-0.2,0,0]), frame('spine',24,300,[0,0,0],[0,0,1]), frame('pelvis',40,400), frame('spine',40,400)], {tags:['seated','body','adjust','fidget','natural']}),

  guarded_idle: preset('guarded_idle', AnimationCategory.EMOTIONAL, 'Guarded Idle', 1800, [frame('spine',0,0), frame('shoulder_left',0,0), frame('shoulder_right',0,0), frame('head',0,0), frame('spine',30,900,[0,0,0],[0,0,-1.5]), frame('shoulder_left',30,900,[0,0.25,0]), frame('shoulder_right',30,900,[0,0.25,0]), frame('head',30,900,[0,0,0],[0,-0.5,0]), frame('spine',60,900)], {loop:true, tags:['guarded','defensive','skepticism','emotional','subtle']}),
  curious_idle: preset('curious_idle', AnimationCategory.EMOTIONAL, 'Curious Idle', 1700, [frame('head',0,0), frame('spine',0,0), frame('head',28,850,[0,0,0],[-1.5,0.5,-2.5]), frame('spine',28,850,[0,0,0],[0.8,0,1]), frame('head',56,850), frame('spine',56,850)], {loop:true, tags:['curious','engagement','listening','emotional','presence']}),
  nervous_idle: preset('nervous_idle', AnimationCategory.EMOTIONAL, 'Nervous Idle', 1300, [frame('spine',0,0), frame('hand_left',0,0), frame('hand_right',0,0), frame('spine',16,420,[0,0,0],[0,0,-0.8]), frame('hand_left',16,420,[0.1,-0.2,0]), frame('hand_right',16,420,[-0.1,-0.2,0]), frame('spine',32,420,[0,0,0],[0,0,0.8]), frame('spine',48,460)], {loop:true, tags:['nervous','fidget','emotional','uncertain','subtle']}),
  warm_host_idle: preset('warm_host_idle', AnimationCategory.EMOTIONAL, 'Warm Host Idle', 1900, [frame('spine',0,0), frame('head',0,0), frame('shoulder_left',0,0), frame('shoulder_right',0,0), frame('spine',30,950,[0,0,0],[0,0,1.5]), frame('head',30,950,[0,0,0],[0,1,1]), frame('shoulder_left',30,950,[0,-0.15,0]), frame('shoulder_right',30,950,[0,-0.15,0]), frame('spine',60,950), frame('head',60,950)], {loop:true, tags:['warm','friendly','host','emotional','presence']}),
  focused_operator_idle: preset('focused_operator_idle', AnimationCategory.EMOTIONAL, 'Focused Operator Idle', 1600, [frame('head',0,0), frame('spine',0,0), frame('hand_right',0,0), frame('head',24,800,[0,0,0],[1,0,0]), frame('spine',24,800,[0,0,0],[0,0,2]), frame('hand_right',24,800,[-0.2,-0.4,0.2]), frame('head',48,800), frame('spine',48,800)], {loop:true, tags:['focused','operator','technical','emotional','thinking']}),
  triumphant_recover: preset('triumphant_recover', AnimationCategory.EMOTIONAL, 'Triumphant Recover', 1500, [frame('spine',0,0), frame('head',0,0), frame('hand_left',0,0), frame('hand_right',0,0), frame('spine',18,500,[0,0,0],[0,0,5]), frame('head',18,500,[0,0,0],[0,-2,0]), frame('hand_left',18,500,[0.8,0.6,0]), frame('hand_right',18,500,[-0.8,0.6,0]), frame('spine',48,1000), frame('head',48,1000)], {tags:['relief','success','confidence','emotional','recovery']}),

  look_to_camera: preset('look_to_camera', AnimationCategory.SCRIPTED, 'Look to Camera', 500, [frame('head',0,0), frame('spine',0,0), frame('head',16,350), frame('spine',16,350), frame('head',24,150)], {tags:['camera','attention','scripted','host','focus']}),
  look_to_guest: preset('look_to_guest', AnimationCategory.SCRIPTED, 'Look to Guest', 620, [frame('head',0,0), frame('spine',0,0), frame('head',16,360,[0,0,0],[4,0,1]), frame('spine',16,360,[0,0,0],[1.5,0,0]), frame('head',28,260,[0,0,0],[3,0,0.5])], {tags:['guest','attention','scripted','listening','focus']}),
  invite_response: preset('invite_response', AnimationCategory.INTERACTION, 'Invite Response', 1200, [frame('hand_left',0,0), frame('hand_right',0,0), frame('head',0,0), frame('hand_left',20,520,[0.9,0.7,0],[0,0,20]), frame('hand_right',20,520,[-0.9,0.7,0],[0,0,-20]), frame('head',20,520,[0,0,0],[0,1,0]), frame('hand_left',44,680), frame('hand_right',44,680), frame('head',44,680)], {tags:['interaction','invite','handoff','gesture','friendly']}),
  yield_floor: preset('yield_floor', AnimationCategory.INTERACTION, 'Yield the Floor', 1050, [frame('hand_right',0,0), frame('head',0,0), frame('spine',0,0), frame('hand_right',16,440,[-1.1,0.5,0.2],[0,0,-25]), frame('head',16,440,[0,0,0],[3,0,1]), frame('spine',16,440,[0,0,0],[1.5,0,0]), frame('hand_right',38,610), frame('head',38,610), frame('spine',38,610)], {tags:['interaction','handoff','listening','gesture','floor']}),
  interrupt_start: preset('interrupt_start', AnimationCategory.INTERACTION, 'Interrupt Start', 650, [frame('hand_left',0,0), frame('head',0,0), frame('spine',0,0), frame('hand_left',12,260,[0.7,0.8,0],[0,0,18]), frame('head',12,260,[0,0,0],[-2,0,-1]), frame('spine',12,260,[0,0,0],[0,0,2]), frame('hand_left',26,390,[0.5,0.65,0])], {tags:['interaction','interrupt','speech','attention','gesture']}),
};

const ANIMATION_LIBRARY = { ...base.ANIMATION_LIBRARY, ...EXPANDED_ANIMATIONS };
function getAnimation(id) { return ANIMATION_LIBRARY[id]; }
function getAnimationsByCategory(category) { return Object.fromEntries(Object.entries(ANIMATION_LIBRARY).filter(([,p]) => p.category === category)); }
function getAnimationsByTag(tag) { return Object.fromEntries(Object.entries(ANIMATION_LIBRARY).filter(([,p]) => (p.tags || []).includes(tag))); }
function getLoopableAnimations() { return Object.fromEntries(Object.entries(ANIMATION_LIBRARY).filter(([,p]) => p.isLoopable)); }
function getAnimationsForContext(context) {
  const tagsByContext = {
    seated: ['seated','podcast','fidget','body','hands'],
    standing: ['gesture','listening','presence','host','attention'],
    listening: ['listening','agreement','engagement','attention','processing'],
    speaking: ['gesture','presentation','emphasis','speech','explain','handoff'],
    thinking: ['thinking','contemplative','processing','fidget','focused'],
    camera: ['camera','host','focus'],
    interaction: ['interaction','handoff','invite','floor','interrupt'],
    technical: ['technical','operator','mic','focused'],
  };
  const tags = tagsByContext[context] || [];
  return Object.fromEntries(Object.entries(ANIMATION_LIBRARY).filter(([,p]) => tags.some(t => (p.tags || []).includes(t))));
}
function listAllAnimations() { return Object.fromEntries(Object.entries(ANIMATION_LIBRARY).map(([id,p]) => [id, {...p, frames: p.frames.length}])); }

module.exports = { AnimationCategory, ANIMATION_LIBRARY, EXPANDED_ANIMATIONS, getAnimation, getAnimationsByCategory, getAnimationsByTag, getLoopableAnimations, getAnimationsForContext, listAllAnimations };
