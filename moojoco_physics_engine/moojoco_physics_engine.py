#!/usr/bin/env python3
"""ROOPS OOPS 엔진 — Moojoco 실물리(mj_step) 버전.

## 배경
`aegis_science_demo/handshake_oops_engine.cpp`(및 .py)는 동일한 클래스 구조
(TcpFrameAxes, CollisionShield, FingerJointLink, PalmBase, RobotHandObject)를
갖지만, 내부적으로는 `approachRatio`/`claspRatio` 선형보간으로 위치·손가락 각도를
직접 대입하는 순기구학(forward kinematics)이다. `CollisionShield`도 색상 hex
문자열만 저장할 뿐 실제 충돌을 감지하지 않는다.

이 버전은 **동일한 클래스 이름과 구조**를 유지하되, 내부 상태를 전부
`urdf/amazinghand_5finger_docking.xml`(실제 질량 0.35kg 손목 + capsule 손가락,
density=600, friction, solref/solimp 접촉 모델)을 구동하는 MuJoCo
`mj_step` 물리 적분 결과로 채운다:

- **질량(mass)**: 하드코딩 값이 아니라 `model.body_mass[bid]`에서 실측
- **힘(force)**: `mj_contactForce`로 매 스텝 실측한 법선 접촉력(N)
- **접촉 반응(contact)**: `data.contact[i].dist`로 실제 지오메트리 침투/접촉 판정.
  `CollisionShield`는 이 실측값이 문턱을 넘을 때만 녹색으로 바뀐다(스크립트 단계
  번호가 아니라 물리 상태가 색을 결정한다)

## 비교 방법
OOPS 엔진과 동일하게 6단계(step 0~5, slider 관용값)의 텔레메트리를 출력해
"목표값을 그대로 찍은 로그"와 "물리 적분을 거쳐 나온 로그"를 나란히 비교할 수
있게 한다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json
import math

import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_DIR = "/home/moos/dev_ws/dual_arms/moojoco_physics_engine"
GIF_PATH = f"{OUT_DIR}/moojoco_physics_handshake.gif"

FPS = 20
APPROACH_S = 4.0
HOLD_S = 3.0
N_APPROACH = int(APPROACH_S * FPS)
N_HOLD = int(HOLD_S * FPS)
N_TOTAL = N_APPROACH + N_HOLD
SUBSTEPS = 10  # model timestep 0.002s * 10 = 0.02s per rendered frame (FPS=20)

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

A_START, A_END = -0.20, 0.036
B_START, B_END = -0.20, 0.036
# 참고: 기존 스크립트들의 A_END/B_END=-0.024는 handB_wrist가 handA와 완전히
# 겹쳐 시작하던 구(舊) XML(pos="0 0 0.05" quat="0 0 0 1") 기준 보정값이었다.
# 오늘 Aegis의 OOPS 엔진 커밋(30c4a1d)이 handB_wrist를 pos="0.007 0.12 0.05"
# euler="0 0 3.14159"로 바꿔 도킹 기준점이 이동했고, 옛 목표값으로는 실제
# 접촉이 전혀 발생하지 않음을 실측으로 확인(ncon=0)했다. 새 기하구조에서
# 실측 스윕(end=0.022~0.045)으로 손가락끼리 처음 맞물리는 지점을 재보정했다.

CAPSULE_RADIUS = 0.006
CONTACT_FORCE_GREEN_N = 0.005  # 이 값 이상 실측 접촉력이 있어야 shield가 녹색으로 전환

KP_WRIST, KD_WRIST = 40.0, 4.0
KP_FINGER, KD_FINGER = 1.2, 0.06


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


class CollisionShield:
    """OOPS의 색상-only 클래스와 달리, 실측 접촉력(N)이 색을 결정한다."""

    def __init__(self):
        self.color_hex = "0x38bdf8"
        self.last_force_n = 0.0
        self.contact_now = False

    def update(self, force_n, is_orange_side=False):
        self.last_force_n = force_n
        self.contact_now = force_n > CONTACT_FORCE_GREEN_N
        if self.contact_now:
            self.color_hex = "0x34d399"  # 실측 접촉 시에만 녹색
        else:
            self.color_hex = "0xf97316" if is_orange_side else "0x38bdf8"


class TcpFrameAxes:
    """실제 body 프레임(xpos/xmat)을 읽어오는 래퍼. 장식용 axisLength 없음."""

    def __init__(self, model, data, body_id):
        self.model = model
        self.data = data
        self.body_id = body_id

    @property
    def position_m(self):
        return self.data.xpos[self.body_id].copy()

    @property
    def euler_rad(self):
        mat = self.data.xmat[self.body_id].reshape(3, 3)
        sy = math.sqrt(mat[0, 0] ** 2 + mat[1, 0] ** 2)
        rx = math.atan2(mat[2, 1], mat[2, 2])
        ry = math.atan2(-mat[2, 0], sy)
        rz = math.atan2(mat[1, 0], mat[0, 0])
        return np.array([rx, ry, rz])


class FingerJointLink:
    """currentCurlAngle을 대입받는 게 아니라 mj_step 결과로부터 실측한다."""

    def __init__(self, model, data, name, joint_id, actuator_id, geom_id):
        self.model = model
        self.data = data
        self.name = name
        self.joint_id = joint_id
        self.actuator_id = actuator_id
        self.geom_id = geom_id
        self.shield = CollisionShield()
        self.max_angle = float(model.jnt_range[joint_id][1])
        self.mass_kg = float(model.body_mass[model.geom_bodyid[geom_id]])

    @property
    def current_curl_angle(self):
        return float(self.data.qpos[self.model.jnt_qposadr[self.joint_id]])

    @property
    def angular_velocity(self):
        return float(self.data.qvel[self.model.jnt_dofadr[self.joint_id]])

    def drive_pd(self, target_angle):
        q, qd = self.current_curl_angle, self.angular_velocity
        ctrl = np.clip(KP_FINGER * (target_angle - q) - KD_FINGER * qd, -2, 2)
        self.data.ctrl[self.actuator_id] = float(ctrl)


class PalmBase:
    """PalmBase(w,h,d) 하드코딩 치수 대신 실제 geom size + body mass를 읽는다."""

    def __init__(self, model, data, body_id, geom_id):
        self.model = model
        self.data = data
        self.body_id = body_id
        self.geom_id = geom_id
        self.shield = CollisionShield()

    @property
    def mass_kg(self):
        return float(self.model.body_mass[self.body_id])

    @property
    def size_m(self):
        return self.model.geom_size[self.geom_id].copy()


class RobotHandObject:
    """OOPS의 SetPosition/SetFingerCurl은 즉시 대입이지만, 여기서는 '목표'일
    뿐이며 실제 상태는 PD 제어 + mj_step 물리 적분을 거쳐야만 변한다."""

    def __init__(self, model, data, hand_prefix, is_orange_side, jid, aid, geom_id):
        self.model = model
        self.data = data
        self.name = "Hand A" if not is_orange_side else "Hand B"
        self.prefix = hand_prefix
        self.is_orange_side = is_orange_side
        self.wrist_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"{hand_prefix}_wrist")
        self.wrist_joint_id = jid[f"{hand_prefix}_approach"]
        self.wrist_actuator_id = aid[f"{hand_prefix}_approach_ctrl"]
        self.tcp_axes = TcpFrameAxes(model, data, self.wrist_body_id)
        palm_geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{hand_prefix}_palm")
        self.palm = PalmBase(model, data, self.wrist_body_id, palm_geom_id)
        self.fingers = {
            fn: FingerJointLink(model, data, fn, jid[f"{hand_prefix}_{fn}_curl"],
                                 aid[f"{hand_prefix}_{fn}_ctrl"], geom_id[(hand_prefix, fn)])
            for fn in FINGER_JOINTS
        }
        self.last_max_force_n = {fn: 0.0 for fn in FINGER_JOINTS}
        self.last_worst_dist_m = 0.0

    def drive_approach_pd(self, target_x):
        q = float(self.data.qpos[self.model.jnt_qposadr[self.wrist_joint_id]])
        qd = float(self.data.qvel[self.model.jnt_dofadr[self.wrist_joint_id]])
        ctrl = np.clip(KP_WRIST * (target_x - q) - KD_WRIST * qd, -5, 5)
        self.data.ctrl[self.wrist_actuator_id] = float(ctrl)

    def update_shields_from_contact(self, finger_force):
        max_palm_force = 0.0
        for fn in FINGER_JOINTS:
            f = finger_force[(self.prefix, fn)]
            self.last_max_force_n[fn] = f
            self.fingers[fn].shield.update(f, self.is_orange_side)
            max_palm_force = max(max_palm_force, f)
        self.palm.shield.update(max_palm_force, self.is_orange_side)

    def print_telemetry(self, step_label):
        pos = self.tcp_axes.position_m
        rot = np.degrees(self.tcp_axes.euler_rad)
        n_contact = sum(1 for fn in FINGER_JOINTS if self.fingers[fn].shield.contact_now)
        total_force = sum(self.last_max_force_n.values())
        print(f"[{self.name}] Pos: ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})m | "
              f"Rot: ({rot[0]:.1f}deg, {rot[1]:.1f}deg, {rot[2]:.1f}deg) | "
              f"Mass(palm): {self.palm.mass_kg:.3f}kg | "
              f"실측 접촉력 합: {total_force:.4f}N | 실측 접촉 손가락: {n_contact}/5 | "
              f"Shield: {self.palm.shield.color_hex}")

    def export_telemetry_json(self, filepath, worst_dist_m):
        pos = self.tcp_axes.position_m
        rot = self.tcp_axes.euler_rad
        payload = {
            "handName": self.name,
            "px": round(float(pos[0]), 6), "py": round(float(pos[1]), 6), "pz": round(float(pos[2]), 6),
            "rx": round(float(rot[0]), 6), "ry": round(float(rot[1]), 6), "rz": round(float(rot[2]), 6),
            "palm_mass_kg": round(self.palm.mass_kg, 4),
            "finger_mass_kg": {fn: round(self.fingers[fn].mass_kg, 4) for fn in FINGER_JOINTS},
            "measured_contact_force_n": {fn: round(self.last_max_force_n[fn], 6) for fn in FINGER_JOINTS},
            "measured_worst_penetration_m": round(worst_dist_m, 6),
            "measured_worst_penetration_ratio_of_radius": round(abs(worst_dist_m) / CAPSULE_RADIUS, 4) if worst_dist_m < 0 else 0.0,
            "source": "MuJoCo mj_step physics integration (real mass/force/contact), not scripted interpolation",
        }
        with open(filepath, "w") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)
        print(f"[Moojoco Physics Engine] Exported {self.name} REAL telemetry to {filepath}")


def render_frame(renderer, cam, data, font_small, t, phase, worst_dist, handA, handB):
    renderer.update_scene(data, camera=cam)
    img = Image.fromarray(renderer.render()).convert("RGB")
    draw = ImageDraw.Draw(img)
    ratio = abs(worst_dist) / CAPSULE_RADIUS if worst_dist < 0 else 0.0
    color = (255, 90, 90) if worst_dist < 0 else (140, 230, 160)
    phase_kr = "접근(실물리)" if phase == "approach" else "유지(실물리)"
    force_a = sum(handA.last_max_force_n.values())
    force_b = sum(handB.last_max_force_n.values())
    lines = [
        f"Moojoco 실물리 엔진 (mj_step, 질량/힘/접촉 실측) — {phase_kr}",
        f"t={t:.2f}s  실측힘 A={force_a:.3f}N B={force_b:.3f}N  최악침투={worst_dist*1000:.3f}mm ({ratio*100:.1f}%)",
    ]
    draw.rectangle([0, 0, 960, 54], fill=(10, 12, 20))
    draw.text((12, 4), lines[0], fill=(120, 220, 255), font=font_small)
    draw.text((12, 28), lines[1], fill=color, font=font_small)
    return img


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 960
    data = mujoco.MjData(model)

    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in [
        "handA_approach", "handB_approach",
        *[f"handA_{f}_curl" for f in FINGER_JOINTS],
        *[f"handB_{f}_curl" for f in FINGER_JOINTS],
    ]}
    aid = {n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"): mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"))
        for n in jid}
    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    handA = RobotHandObject(model, data, "handA", False, jid, aid, geom_id)
    handB = RobotHandObject(model, data, "handB", True, jid, aid, geom_id)

    print("=========================================================")
    print("  Moojoco 실물리 OOPS 엔진 (MuJoCo mj_step, 실측 질량/힘/접촉)  ")
    print("=========================================================")
    print(f"\n[Init] Hand A palm mass = {handA.palm.mass_kg:.3f}kg (실측, XML inertial)")
    print(f"[Init] Hand B palm mass = {handB.palm.mass_kg:.3f}kg (실측, XML inertial)")
    handA.print_telemetry("init")
    handB.print_telemetry("init")

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = -55, -18, 0.25
    cam.lookat[:] = [0.0, 0.0, 0.06]
    try:
        font_small = ImageFont.truetype(
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 18, index=1)  # index 1 = KR
    except OSError:
        font_small = ImageFont.load_default()

    frames = []
    worst_dist_all = 0.0
    max_ncon = 0
    checkpoint_steps = {int(round(k * (N_APPROACH - 1))) for k in np.linspace(0, 1, 6)}
    trajectory = []

    for f in range(N_TOTAL):
        t_frac = min(f / (N_APPROACH - 1), 1.0)
        t = f / FPS
        frame_worst = 0.0
        for _ in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (A_END - A_START) * approach_frac
            b_target = B_START + (B_END - B_START) * approach_frac
            handA.drive_approach_pd(a_target)
            handB.drive_approach_pd(b_target)

            finger_force = {k: 0.0 for k in geom_id}
            for ci in range(data.ncon):
                con = data.contact[ci]
                wrench = np.zeros(6)
                mujoco.mj_contactForce(model, data, ci, wrench)
                nf = abs(float(wrench[0]))
                for key, gid_ in geom_id.items():
                    if con.geom1 == gid_ or con.geom2 == gid_:
                        finger_force[key] = max(finger_force[key], nf)

            for hand, obj in (("handA", handA), ("handB", handB)):
                for fn in FINGER_JOINTS:
                    seek_frac = ease(t_frac - CURL_PHASE[fn])
                    target = CURL_TARGET[fn] * seek_frac
                    obj.fingers[fn].drive_pd(target)

            mujoco.mj_step(model, data)
            max_ncon = max(max_ncon, int(data.ncon))
            for ci in range(data.ncon):
                dist = float(data.contact[ci].dist)
                frame_worst = min(frame_worst, dist)
                worst_dist_all = min(worst_dist_all, dist)

        handA.update_shields_from_contact(finger_force)
        handB.update_shields_from_contact(finger_force)

        phase = "approach" if f < N_APPROACH else "hold"
        frames.append(render_frame(renderer, cam, data, font_small, t, phase, frame_worst, handA, handB))
        trajectory.append({"t": round(t, 3), "phase": phase, "n_contact": int(data.ncon),
                            "frame_worst_dist_m": round(frame_worst, 6)})

        if f in checkpoint_steps or f == N_TOTAL - 1:
            step_idx = sorted(checkpoint_steps).index(f) if f in checkpoint_steps else "final"
            print(f"\n--- Step {step_idx} (t={t:.2f}s, phase={phase}) — 실측(스크립트가 대입한 값 아님) ---")
            handA.print_telemetry(str(step_idx))
            handB.print_telemetry(str(step_idx))

    renderer.close()
    frames[0].save(GIF_PATH, save_all=True, append_images=frames[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"\nGIF 저장: {GIF_PATH} ({len(frames)}프레임)")

    handA.export_telemetry_json(f"{OUT_DIR}/tcp_handA_moojoco.json", worst_dist_all)
    handB.export_telemetry_json(f"{OUT_DIR}/tcp_handB_moojoco.json", worst_dist_all)

    hold_frames = [r for r in trajectory if r["phase"] == "hold"]
    worst_hold = min((r["frame_worst_dist_m"] for r in hold_frames), default=0.0)
    summary = {
        "engine": "Moojoco Physics Engine (MuJoCo mj_step, real mass/force/contact)",
        "contrast": "aegis_science_demo/handshake_oops_engine.cpp uses linear interpolation, no physics integration",
        "worst_overall_dist_m": round(worst_dist_all, 6),
        "worst_overall_penetration_ratio_of_radius": round(abs(worst_dist_all) / CAPSULE_RADIUS, 4) if worst_dist_all < 0 else 0.0,
        "worst_hold_dist_m": round(worst_hold, 6),
        "worst_hold_penetration_ratio_of_radius": round(abs(worst_hold) / CAPSULE_RADIUS, 4) if worst_hold < 0 else 0.0,
        "max_simultaneous_contacts": max_ncon,
        "palm_mass_kg": round(handA.palm.mass_kg, 4),
    }
    with open(f"{OUT_DIR}/moojoco_physics_engine_report.json", "w") as fp:
        json.dump({"summary": summary, "frames": trajectory}, fp, indent=1)
    print("\n[Moojoco Physics Engine Execution Completed — REAL mj_step physics 🟢]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
