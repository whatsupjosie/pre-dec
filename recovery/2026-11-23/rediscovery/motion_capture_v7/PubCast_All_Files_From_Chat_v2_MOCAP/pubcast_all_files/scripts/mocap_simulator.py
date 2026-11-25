#!/usr/bin/env python3
"""
MOCAP TEST SIMULATOR
====================
Simulates motion capture data for testing PubCast AI mocap integration

Can be used to:
- Test mocap streaming without actual mocap hardware
- Simulate walking, dancing, gestures
- Load and replay recorded mocap sequences
- Benchmark mocap pipeline performance

Usage:
    # Simulate basic movement
    python mocap_simulator.py --mode walk --fps 60
    
    # Replay from file
    python mocap_simulator.py --replay recording.json --fps 120
    
    # Send to PubCast AI
    python mocap_simulator.py --mode dance --target udp://localhost:9001
"""

import asyncio
import json
import math
import time
import socket
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SKELETON TEMPLATES
# ─────────────────────────────────────────────

def get_rest_pose() -> Dict[str, Dict[str, float]]:
    """T-pose rest position"""
    return {
        "hips": {"x": 0.0, "y": 0.0, "z": 0.0},
        "spine": {"x": 0.0, "y": 0.2, "z": 0.0},
        "chest": {"x": 0.0, "y": 0.4, "z": 0.0},
        "neck": {"x": 0.0, "y": 0.6, "z": 0.0},
        "head": {"x": 0.0, "y": 0.75, "z": 0.0},
        
        # Left arm
        "left_shoulder": {"x": 0.15, "y": 0.5, "z": 0.0},
        "left_elbow": {"x": 0.4, "y": 0.5, "z": 0.0},
        "left_wrist": {"x": 0.65, "y": 0.5, "z": 0.0},
        "left_hand": {"x": 0.75, "y": 0.5, "z": 0.0},
        
        # Right arm
        "right_shoulder": {"x": -0.15, "y": 0.5, "z": 0.0},
        "right_elbow": {"x": -0.4, "y": 0.5, "z": 0.0},
        "right_wrist": {"x": -0.65, "y": 0.5, "z": 0.0},
        "right_hand": {"x": -0.75, "y": 0.5, "z": 0.0},
        
        # Left leg
        "left_hip": {"x": 0.1, "y": 0.0, "z": 0.0},
        "left_knee": {"x": 0.1, "y": -0.4, "z": 0.0},
        "left_ankle": {"x": 0.1, "y": -0.8, "z": 0.0},
        "left_foot": {"x": 0.1, "y": -0.9, "z": 0.05},
        
        # Right leg
        "right_hip": {"x": -0.1, "y": 0.0, "z": 0.0},
        "right_knee": {"x": -0.1, "y": -0.4, "z": 0.0},
        "right_ankle": {"x": -0.1, "y": -0.8, "z": 0.0},
        "right_foot": {"x": -0.1, "y": -0.9, "z": 0.05},
    }


# ─────────────────────────────────────────────
# ANIMATION GENERATORS
# ─────────────────────────────────────────────

def generate_walk_cycle(frame_number: int, fps: float = 60.0) -> Dict[str, Dict[str, float]]:
    """Generate walking animation"""
    pose = get_rest_pose()
    
    # Walking cycle parameters
    cycle_time = 1.0  # 1 second per step
    t = (frame_number / fps) % cycle_time
    phase = (t / cycle_time) * 2 * math.pi
    
    # Hip sway
    pose["hips"]["x"] = math.sin(phase * 2) * 0.02
    pose["hips"]["y"] = 0.05 + abs(math.sin(phase * 2)) * 0.03
    
    # Legs (alternating)
    left_phase = phase
    right_phase = phase + math.pi
    
    # Left leg
    pose["left_knee"]["z"] = -abs(math.sin(left_phase)) * 0.3
    pose["left_knee"]["y"] = -0.4 + abs(math.sin(left_phase)) * 0.1
    pose["left_ankle"]["z"] = -abs(math.sin(left_phase)) * 0.4
    
    # Right leg
    pose["right_knee"]["z"] = -abs(math.sin(right_phase)) * 0.3
    pose["right_knee"]["y"] = -0.4 + abs(math.sin(right_phase)) * 0.1
    pose["right_ankle"]["z"] = -abs(math.sin(right_phase)) * 0.4
    
    # Arms (counter-swing)
    pose["left_shoulder"]["z"] = math.sin(right_phase) * 0.15
    pose["right_shoulder"]["z"] = math.sin(left_phase) * 0.15
    
    return pose


def generate_dance_move(frame_number: int, fps: float = 60.0) -> Dict[str, Dict[str, float]]:
    """Generate dancing animation"""
    pose = get_rest_pose()
    
    t = frame_number / fps
    
    # Body sway
    pose["hips"]["x"] = math.sin(t * 2) * 0.1
    pose["spine"]["x"] = math.sin(t * 2 + 0.5) * 0.15
    pose["chest"]["x"] = math.sin(t * 2 + 1.0) * 0.2
    
    # Arms raised and waving
    arm_wave = math.sin(t * 3) * 0.3
    pose["left_shoulder"]["y"] = 0.7
    pose["left_elbow"]["y"] = 0.7 + arm_wave
    pose["right_shoulder"]["y"] = 0.7
    pose["right_elbow"]["y"] = 0.7 - arm_wave
    
    # Slight knee bend
    pose["left_knee"]["y"] = -0.4 + abs(math.sin(t * 4)) * 0.05
    pose["right_knee"]["y"] = -0.4 + abs(math.sin(t * 4 + math.pi)) * 0.05
    
    return pose


def generate_idle(frame_number: int, fps: float = 60.0) -> Dict[str, Dict[str, float]]:
    """Generate subtle idle breathing animation"""
    pose = get_rest_pose()
    
    t = frame_number / fps
    breath = math.sin(t * 0.5) * 0.02  # Slow breathing
    
    pose["chest"]["y"] = 0.4 + breath
    pose["chest"]["z"] = breath * 0.5
    
    return pose


# ─────────────────────────────────────────────
# MOCAP SENDER
# ─────────────────────────────────────────────

class MocapSender:
    """Sends mocap frames to PubCast AI"""
    
    def __init__(self, target_url: str, rig_id: str = "sim-rig-01"):
        self.target_url = target_url
        self.rig_id = rig_id
        self.socket: Optional[socket.socket] = None
        
        # Parse target
        if target_url.startswith("udp://"):
            parts = target_url.replace("udp://", "").split(":")
            self.protocol = "udp"
            self.host = parts[0]
            self.port = int(parts[1]) if len(parts) > 1 else 9001
        else:
            raise ValueError(f"Unsupported target URL: {target_url}")
    
    def connect(self):
        """Connect to target"""
        if self.protocol == "udp":
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logger.info(f"📡 Connected to UDP target: {self.host}:{self.port}")
    
    def send_frame(self, joints: Dict[str, Dict[str, float]], frame_number: int):
        """Send a mocap frame"""
        frame = {
            "ts": int(time.time() * 1000),
            "rigId": self.rig_id,
            "joints": joints,
            "frameNumber": frame_number
        }
        
        # Serialize to JSON
        data = json.dumps(frame).encode('utf-8')
        
        # Send
        if self.protocol == "udp":
            self.socket.sendto(data, (self.host, self.port))
    
    def close(self):
        """Close connection"""
        if self.socket:
            self.socket.close()


# ─────────────────────────────────────────────
# SIMULATOR
# ─────────────────────────────────────────────

class MocapSimulator:
    """Simulates mocap data stream"""
    
    def __init__(
        self,
        mode: str = "idle",
        fps: float = 60.0,
        target_url: Optional[str] = None,
        rig_id: str = "sim-rig-01"
    ):
        self.mode = mode
        self.fps = fps
        self.target_url = target_url
        self.rig_id = rig_id
        
        # Animation generator
        self.generators = {
            "idle": generate_idle,
            "walk": generate_walk_cycle,
            "dance": generate_dance_move
        }
        
        if mode not in self.generators:
            raise ValueError(f"Unknown mode: {mode}. Available: {list(self.generators.keys())}")
        
        self.generator = self.generators[mode]
        
        # Sender
        self.sender: Optional[MocapSender] = None
        if target_url:
            self.sender = MocapSender(target_url, rig_id)
    
    async def run(self, duration_seconds: Optional[float] = None):
        """Run simulation"""
        if self.sender:
            self.sender.connect()
        
        frame_number = 0
        frame_duration = 1.0 / self.fps
        start_time = time.time()
        
        logger.info(f"🎭 Starting mocap simulation: {self.mode} @ {self.fps} fps")
        
        try:
            while True:
                frame_start = time.time()
                
                # Generate frame
                joints = self.generator(frame_number, self.fps)
                
                # Send frame
                if self.sender:
                    self.sender.send_frame(joints, frame_number)
                else:
                    # Just print
                    print(f"Frame {frame_number}: {len(joints)} joints")
                
                frame_number += 1
                
                # Check duration
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    break
                
                # Sleep to maintain FPS
                elapsed = time.time() - frame_start
                sleep_time = max(0, frame_duration - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
        
        finally:
            if self.sender:
                self.sender.close()
            
            logger.info(f"🎭 Simulation complete: {frame_number} frames sent")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PubCast AI Mocap Simulator")
    parser.add_argument("--mode", choices=["idle", "walk", "dance"], default="walk",
                       help="Animation mode")
    parser.add_argument("--fps", type=float, default=60.0,
                       help="Frames per second")
    parser.add_argument("--target", type=str, default="udp://localhost:9001",
                       help="Target URL (e.g., udp://localhost:9001)")
    parser.add_argument("--rig-id", type=str, default="sim-rig-01",
                       help="Rig identifier")
    parser.add_argument("--duration", type=float, default=None,
                       help="Duration in seconds (default: run until Ctrl+C)")
    
    args = parser.parse_args()
    
    # Create simulator
    simulator = MocapSimulator(
        mode=args.mode,
        fps=args.fps,
        target_url=args.target,
        rig_id=args.rig_id
    )
    
    # Run
    asyncio.run(simulator.run(duration_seconds=args.duration))


if __name__ == "__main__":
    main()
