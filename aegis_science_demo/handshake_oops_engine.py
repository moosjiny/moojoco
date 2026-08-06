#!/usr/bin/env python3
"""
ROOPS (Robot Object-Oriented Programming System - OOPS)
Python High-Performance Sub-Object Modular Architecture for Humanoid Robot Hands
Author: Aegis (Google DeepMind Science / ROOPS Infrastructure Hub)
Dual C++ & Python High-Performance Engine Implementation
"""

import math
import time
import json

class Vector3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

class EulerRotation:
    def __init__(self, rx=0.0, ry=0.0, rz=0.0):
        self.rx = rx
        self.ry = ry
        self.rz = rz

class TcpFrameAxes:
    def __init__(self, length=3.5):
        self.axis_length = length

class CollisionShield:
    def __init__(self, hex_color="0x34d399", opacity=0.7):
        self.color_hex = hex_color
        self.opacity = opacity

    def set_color(self, hex_color):
        self.color_hex = hex_color

class FingerJointLink:
    def __init__(self, name, x, z, length, radius, max_angle):
        self.name = name
        self.x = x
        self.z = z
        self.length = length
        self.radius = radius
        self.max_angle = max_angle
        self.current_curl_angle = 0.0
        self.shield = CollisionShield("0x34d399", 0.7)

    def set_curl_angle(self, angle):
        self.current_curl_angle = min(angle, self.max_angle)

class PalmBase:
    def __init__(self, width=3.6, height=1.2, depth=2.4):
        self.width = width
        self.height = height
        self.depth = depth
        self.shield = CollisionShield("0x34d399", 0.6)

class RobotHandObject:
    def __init__(self, name, is_facing_rotated=False):
        self.name = name
        self.is_facing_rotated = is_facing_rotated
        self.palm = PalmBase(3.6, 1.2, 2.4)
        self.tcp_axes = TcpFrameAxes(3.5)
        
        self.internal_state = {
            "handName": name,
            "px": 0.25 if is_facing_rotated else -0.25,
            "py": 3.0,
            "pz": 4.0 if is_facing_rotated else -4.0,
            "rx": 0.0,
            "ry": math.pi if is_facing_rotated else 0.0,
            "rz": 0.0,
            "lastUpdated": int(time.time() * 1000)
        }

        self.fingers = [
            FingerJointLink("thumb", -1.6, 1.0, 2.2, 0.35, 1.10),
            FingerJointLink("index", -0.8, 1.4, 2.8, 0.32, 1.22),
            FingerJointLink("middle", 0.0, 1.5, 3.0, 0.32, 1.25),
            FingerJointLink("ring", 0.8, 1.4, 2.7, 0.32, 1.20),
            FingerJointLink("pinky", 1.6, 1.2, 2.2, 0.30, 1.15)
        ]

    def set_position(self, x, y, z):
        self.internal_state["px"] = x
        self.internal_state["py"] = y
        self.internal_state["pz"] = z

    def set_rotation(self, rx, ry, rz):
        self.internal_state["rx"] = rx
        self.internal_state["ry"] = ry
        self.internal_state["rz"] = rz

    def set_finger_curl(self, curl_amount):
        for f in self.fingers:
            f.set_curl_angle(curl_amount)

    def set_all_shield_colors(self, hex_color):
        self.palm.shield.set_color(hex_color)
        for f in self.fingers:
            f.shield.set_color(hex_color)

    def export_to_external_json(self, filepath):
        with open(filepath, "w") as f:
            json.dump(self.internal_state, f, indent=2)
        print(f"[ROOPS OOPS Python] Exported {self.name} state to {filepath}")

    def print_telemetry(self):
        st = self.internal_state
        print(f"[{self.name}] Pos: ({st['px']:.2f}, {st['py']:.2f}, {st['pz']:.2f}) | "
              f"Rot: ({st['rx']*180/math.pi:.1f}deg, {st['ry']*180/math.pi:.1f}deg, {st['rz']*180/math.pi:.1f}deg) | "
              f"Shield: {self.palm.shield.color_hex}")

def main():
    print("=========================================================")
    print("  ROOPS OOPS (Object-Oriented Python) Humanoid Hand Engine  ")
    print("=========================================================")

    handA = RobotHandObject("Hand A", False)
    handB = RobotHandObject("Hand B", True)

    handA.print_telemetry()
    handB.print_telemetry()

    # Simulate Sequential Trajectory
    for step in range(6):
        slider_val = step * 0.05
        approach_ratio = min(slider_val / 0.185, 1.0)
        clasp_ratio = max((slider_val - 0.185) / 0.115, 0.0)

        base_z = (1.0 - approach_ratio) * 3.5 + 1.35
        base_curl = approach_ratio * 0.35 + clasp_ratio * 0.90

        handA.set_position(-0.25, 3.0, -base_z)
        handB.set_position(0.25, 3.0, base_z)

        handA.set_finger_curl(base_curl)
        handB.set_finger_curl(base_curl)

        if approach_ratio >= 1.0:
            handA.set_all_shield_colors("0x34d399")
            handB.set_all_shield_colors("0x34d399")
        else:
            handA.set_all_shield_colors("0x38bdf8")
            handB.set_all_shield_colors("0xf97316")

        print(f"\n--- Step {step} (Slider: {slider_val:.2f}m) ---")
        handA.print_telemetry()
        handB.print_telemetry()

    handA.export_to_external_json("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handA_py.json")
    handB.export_to_external_json("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handB_py.json")
    print("\n[ROOPS Python Engine Execution Completed Successfully 🟢]")

if __name__ == "__main__":
    main()
