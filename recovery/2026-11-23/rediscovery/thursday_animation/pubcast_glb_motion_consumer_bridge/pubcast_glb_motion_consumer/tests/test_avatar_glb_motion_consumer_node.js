global.window = {
  listeners: {},
  addEventListener(name, fn) { this.listeners[name] = this.listeners[name] || []; this.listeners[name].push(fn); },
  dispatchEvent(evt) { for (const fn of this.listeners[evt.type] || []) fn(evt); },
};
global.performance = { now: () => 1000 };
global.requestAnimationFrame = undefined;
global.CustomEvent = function CustomEvent(type, init) { this.type = type; this.detail = init && init.detail; };

function makeBone(name) {
  return {
    name,
    type: "Bone",
    rotation: { x: 0, y: 0, z: 0 },
    quaternion: null,
  };
}
const bones = ["mixamorigHead", "mixamorigSpine", "mixamorigLeftArm", "mixamorigRightArm"].map(makeBone);
const root = { traverse(fn) { bones.forEach(fn); } };

const consumer = require("../static/avatar_glb_motion_consumer.js");
const binding = consumer.registerAvatar("manny", root);
if (!binding.getBone("head")) throw new Error("head bone was not mapped");

consumer.consumePayload({
  avatar_id: "manny",
  commands: [
    { kind: "mocap_pose", priority: 70, weight: 1, pose: { bones: { head: { rotation: [10, 5, 0] } } } },
    { kind: "overlay", priority: 80, animation_id: "confident_stance", weight: 0.5, duration_ms: 1000 },
  ],
});

if (Math.abs(binding.getBone("head").rotation.y) <= 0) throw new Error("head yaw did not move");
if (!binding.debugStatus().mappedBones.includes("head")) throw new Error("debug status missing head");
console.log("avatar_glb_motion_consumer smoke test passed");
