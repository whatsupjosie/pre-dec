/**
 * PubCast GLB Motion Consumer
 * ---------------------------
 * The missing visible link: consumes avatar_motion_commands events and applies
 * mocap/procedural/overlay/hold commands to loaded Three.js GLB avatar skeletons.
 *
 * This file intentionally creates no menu UI. Stage/avatar code registers Manny,
 * Sheila, or any future GLB after loading. The consumer listens to the existing
 * PubcastAvatarMotionRuntime bridge and browser CustomEvents.
 *
 * Expected command event shape:
 *   window.dispatchEvent(new CustomEvent("pubcast:avatar-motion-commands", {
 *     detail: { avatar_id, commands: [{kind, layer, animation_id, pose, weight...}] }
 *   }))
 */
(function () {
  const DEFAULT_BONE_ALIASES = {
    hips: ["hips", "pelvis", "mixamorigHips", "Armature/Hips"],
    spine: ["spine", "spine_01", "mixamorigSpine", "Spine"],
    chest: ["chest", "spine_02", "upper_chest", "mixamorigSpine1"],
    neck: ["neck", "mixamorigNeck", "Neck"],
    head: ["head", "mixamorigHead", "Head"],
    shoulder_left: ["shoulder_left", "left_shoulder", "mixamorigLeftShoulder", "LeftShoulder"],
    arm_left: ["arm_left", "left_upper_arm", "upper_arm_left", "mixamorigLeftArm", "LeftArm"],
    forearm_left: ["forearm_left", "left_forearm", "lower_arm_left", "mixamorigLeftForeArm", "LeftForeArm"],
    hand_left: ["hand_left", "left_hand", "mixamorigLeftHand", "LeftHand"],
    shoulder_right: ["shoulder_right", "right_shoulder", "mixamorigRightShoulder", "RightShoulder"],
    arm_right: ["arm_right", "right_upper_arm", "upper_arm_right", "mixamorigRightArm", "RightArm"],
    forearm_right: ["forearm_right", "right_forearm", "lower_arm_right", "mixamorigRightForeArm", "RightForeArm"],
    hand_right: ["hand_right", "right_hand", "mixamorigRightHand", "RightHand"],
    leg_left: ["leg_left", "left_upper_leg", "thigh_left", "mixamorigLeftUpLeg", "LeftUpLeg"],
    leg_right: ["leg_right", "right_upper_leg", "thigh_right", "mixamorigRightUpLeg", "RightUpLeg"],
  };

  const DEG2RAD = Math.PI / 180;

  class SpringValue {
    constructor(value = 0) {
      this.value = value;
      this.target = value;
      this.velocity = 0;
    }
    step(dt, stiffness = 28, damping = 9) {
      const delta = this.target - this.value;
      this.velocity += delta * stiffness * dt;
      this.velocity *= Math.exp(-damping * dt);
      this.value += this.velocity * dt;
      if (Math.abs(delta) < 0.00001 && Math.abs(this.velocity) < 0.00001) {
        this.value = this.target;
        this.velocity = 0;
      }
      return this.value;
    }
  }

  function normalizeName(name) {
    return String(name || "")
      .replace(/^.*\//, "")
      .replace(/[^a-zA-Z0-9]/g, "")
      .toLowerCase();
  }

  function findObject(root, predicate) {
    if (!root) return null;
    if (predicate(root)) return root;
    let found = null;
    root.traverse && root.traverse((obj) => {
      if (!found && predicate(obj)) found = obj;
    });
    return found;
  }

  function isBone(obj) {
    return obj && (obj.isBone || obj.type === "Bone" || /bone/i.test(obj.type || ""));
  }

  function collectBones(root) {
    const out = [];
    if (!root) return out;
    root.traverse && root.traverse((obj) => { if (isBone(obj)) out.push(obj); });
    return out;
  }

  function eulerToRadians(rotation) {
    const r = Array.isArray(rotation) ? rotation : [0, 0, 0];
    // Pipeline emits [yaw, pitch, roll]. Three.js Euler order is usually XYZ;
    // we map conservatively as X=pitch, Y=yaw, Z=roll.
    return {
      x: Number(r[1] || 0) * DEG2RAD,
      y: Number(r[0] || 0) * DEG2RAD,
      z: Number(r[2] || 0) * DEG2RAD,
    };
  }

  function safeSlerpQuaternion(bone, targetEuler, alpha) {
    if (!bone) return;
    if (bone.quaternion && typeof THREE !== "undefined" && THREE.Quaternion && THREE.Euler) {
      const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(targetEuler.x, targetEuler.y, targetEuler.z, "XYZ"));
      bone.quaternion.slerp(q, Math.max(0, Math.min(1, alpha)));
      return;
    }
    // Fallback for tests or non-Three hosts.
    bone.rotation = bone.rotation || { x: 0, y: 0, z: 0 };
    bone.rotation.x += (targetEuler.x - bone.rotation.x) * alpha;
    bone.rotation.y += (targetEuler.y - bone.rotation.y) * alpha;
    bone.rotation.z += (targetEuler.z - bone.rotation.z) * alpha;
  }

  class AvatarSkeletonBinding {
    constructor(avatarId, root, options = {}) {
      this.avatarId = avatarId;
      this.root = root;
      this.options = options;
      this.aliases = Object.assign({}, DEFAULT_BONE_ALIASES, options.boneAliases || {});
      this.bones = {};
      this.baseRotations = new Map();
      this.activeTargets = new Map();
      this.lastCommandAt = 0;
      this.lastApplied = null;
      this.enabled = true;
      this.motionScale = Number(options.motionScale ?? 1.0);
      this.overlayScale = Number(options.overlayScale ?? 0.45);
      this.proceduralScale = Number(options.proceduralScale ?? 0.55);
      this.mapBones();
      this.captureBasePose();
    }

    mapBones() {
      const all = collectBones(this.root);
      const byNorm = new Map();
      for (const bone of all) byNorm.set(normalizeName(bone.name), bone);
      for (const [canonical, aliases] of Object.entries(this.aliases)) {
        let found = null;
        for (const alias of aliases) {
          found = byNorm.get(normalizeName(alias));
          if (found) break;
        }
        if (!found) {
          found = findObject(this.root, (obj) => isBone(obj) && normalizeName(obj.name).includes(normalizeName(canonical)));
        }
        if (found) this.bones[canonical] = found;
      }
      return this.bones;
    }

    captureBasePose() {
      for (const bone of Object.values(this.bones)) {
        if (!bone) continue;
        this.baseRotations.set(bone, bone.quaternion && bone.quaternion.clone ? bone.quaternion.clone() : null);
      }
    }

    getBone(canonical) {
      return this.bones[canonical] || null;
    }

    applyCommand(command, now = performance.now()) {
      if (!this.enabled || !command) return false;
      this.lastCommandAt = now;
      this.lastApplied = command;
      if (command.kind === "mocap_pose" && command.pose && command.pose.bones) {
        this.applyPose(command.pose, command.weight ?? 1, command.blend_in_ms ?? 50, "mocap");
        return true;
      }
      if (command.kind === "overlay" || command.kind === "procedural_animation") {
        this.applySemanticAnimation(command, now);
        return true;
      }
      if (command.kind === "hold") {
        // Hold means decay gently toward the current pose, not snap to idle.
        return true;
      }
      return false;
    }

    applyPose(pose, weight = 1, blendMs = 80, source = "pose") {
      const alpha = Math.max(0.02, Math.min(1, weight)) * (this.motionScale || 1);
      for (const [canonical, transform] of Object.entries(pose.bones || {})) {
        const bone = this.getBone(canonical);
        if (!bone || !transform.rotation) continue;
        const e = eulerToRadians(transform.rotation);
        safeSlerpQuaternion(bone, e, Math.min(1, alpha));
        this.activeTargets.set(canonical, { rotation: e, weight, source, expiresAt: performance.now() + Math.max(120, blendMs * 4) });
      }
    }

    applySemanticAnimation(command, now = performance.now()) {
      const id = command.animation_id || "";
      const weight = Math.max(0, Math.min(1, command.weight ?? 0.35));
      const scale = command.kind === "overlay" ? this.overlayScale : this.proceduralScale;
      const w = weight * scale;
      const duration = Math.max(300, command.duration_ms || 800);
      const targets = semanticTargetsForAnimation(id, w);
      for (const [canonical, rot] of Object.entries(targets)) {
        const bone = this.getBone(canonical);
        if (!bone) continue;
        const e = eulerToRadians(rot);
        safeSlerpQuaternion(bone, e, Math.max(0.04, Math.min(0.55, w)));
        this.activeTargets.set(canonical, { rotation: e, weight: w, source: id, expiresAt: now + duration });
      }
    }

    tick(dt = 1 / 60, now = performance.now()) {
      if (!this.enabled) return;
      for (const [canonical, target] of Array.from(this.activeTargets.entries())) {
        if (target.expiresAt < now) {
          this.activeTargets.delete(canonical);
          continue;
        }
        const bone = this.getBone(canonical);
        if (!bone || !target.rotation) continue;
        safeSlerpQuaternion(bone, target.rotation, Math.min(0.25, Math.max(0.02, dt * 5)));
      }
    }

    debugStatus() {
      return {
        avatarId: this.avatarId,
        enabled: this.enabled,
        mappedBones: Object.keys(this.bones).sort(),
        activeTargets: Array.from(this.activeTargets.keys()).sort(),
        lastCommandAt: this.lastCommandAt,
        lastAnimation: this.lastApplied && this.lastApplied.animation_id,
      };
    }
  }

  function semanticTargetsForAnimation(id, weight = 0.5) {
    // These are deliberately small pose accents. Full choreography should come
    // from GLB clips later; this bridge makes behavior visible today.
    const w = Math.max(0, Math.min(1, weight));
    const r = (yaw = 0, pitch = 0, roll = 0) => [yaw * w, pitch * w, roll * w];
    if (/nod/.test(id)) return { head: r(0, 8, 0), neck: r(0, 3, 0) };
    if (/head_shake/.test(id)) return { head: r(9, 0, 0), neck: r(3, 0, 0) };
    if (/tilt.*left|curious/.test(id)) return { head: r(-2, 0, -8), neck: r(-1, 0, -3), spine: r(0, 0, -2) };
    if (/tilt.*right/.test(id)) return { head: r(2, 0, 8), neck: r(1, 0, 3), spine: r(0, 0, 2) };
    if (/lean_forward|engaged/.test(id)) return { spine: r(0, 7, 0), chest: r(0, 5, 0), head: r(0, -2, 0) };
    if (/lean_back|skeptical|guarded/.test(id)) return { spine: r(0, -5, 0), chest: r(0, -3, 0), head: r(4, 0, -2) };
    if (/presentation|open_palm/.test(id)) return { arm_left: r(0, 0, 20), forearm_left: r(0, 0, 18), arm_right: r(0, 0, -20), forearm_right: r(0, 0, -18), chest: r(0, 2, 0) };
    if (/point/.test(id)) return { arm_right: r(0, 0, -32), forearm_right: r(0, 0, -12), chest: r(5, 0, 0) };
    if (/wave/.test(id)) return { arm_right: r(0, 0, -48), forearm_right: r(0, 0, -18), hand_right: r(0, 0, 22) };
    if (/chin|thinking|focused/.test(id)) return { arm_left: r(0, 0, 30), forearm_left: r(0, 0, 28), head: r(0, 4, 0) };
    if (/hips|confident/.test(id)) return { chest: r(0, 4, 0), spine: r(0, 2, 0), arm_left: r(0, 0, -12), arm_right: r(0, 0, 12) };
    if (/cross/.test(id)) return { arm_left: r(0, 0, 34), arm_right: r(0, 0, -34), chest: r(0, -2, 0) };
    if (/shrug/.test(id)) return { shoulder_left: r(0, 0, -8), shoulder_right: r(0, 0, 8), head: r(0, 2, 0) };
    if (/enthusiasm|bounce|triumphant/.test(id)) return { spine: r(0, 6, 0), chest: r(0, 8, 0), head: r(0, -4, 0) };
    if (/relaxed|warm/.test(id)) return { spine: r(0, -2, 0), chest: r(0, -1, 0), head: r(0, 1, 0) };
    if (/nervous|fidget|adjust|glance|touch/.test(id)) return { head: r(-2, 3, -2), hand_left: r(0, 0, 10), hand_right: r(0, 0, -10) };
    return { spine: r(0, 1, 0), head: r(0, 1, 0) };
  }

  const registry = new Map();
  let raf = null;
  let lastTs = 0;

  function registerAvatar(avatarId, root, options = {}) {
    const binding = new AvatarSkeletonBinding(avatarId, root, options);
    registry.set(avatarId, binding);
    ensureLoop();
    return binding;
  }

  function unregisterAvatar(avatarId) {
    registry.delete(avatarId);
  }

  function consumePayload(payload) {
    if (!payload || !payload.avatar_id) return false;
    const binding = registry.get(payload.avatar_id) || registry.get(String(payload.avatar_id).toLowerCase());
    if (!binding) return false;
    const commands = Array.isArray(payload.commands) ? payload.commands.slice() : [];
    commands.sort((a, b) => Number(a.priority || 0) - Number(b.priority || 0));
    let applied = false;
    for (const command of commands) applied = binding.applyCommand(command) || applied;
    return applied;
  }

  function onMotionEvent(e) {
    consumePayload(e.detail || e);
  }

  function ensureLoop() {
    if (raf || typeof requestAnimationFrame === "undefined") return;
    const step = (ts) => {
      const dt = lastTs ? Math.min(0.05, Math.max(0.001, (ts - lastTs) / 1000)) : 1 / 60;
      lastTs = ts;
      for (const binding of registry.values()) binding.tick(dt, ts);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }

  function stopLoopIfEmpty() {
    if (registry.size === 0 && raf && typeof cancelAnimationFrame !== "undefined") {
      cancelAnimationFrame(raf);
      raf = null;
    }
  }

  window.addEventListener("pubcast:avatar-motion-commands", onMotionEvent);

  if (window.PubcastAvatarMotionRuntime && window.PubcastAvatarMotionRuntime.onCommands) {
    window.PubcastAvatarMotionRuntime.onCommands(consumePayload);
  }

  window.PubcastGLBMotionConsumer = {
    registerAvatar,
    unregisterAvatar,
    consumePayload,
    bindings: registry,
    DEFAULT_BONE_ALIASES,
    semanticTargetsForAnimation,
    AvatarSkeletonBinding,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = window.PubcastGLBMotionConsumer;
  }
})();
