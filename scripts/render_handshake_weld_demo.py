"""
악수 데모 확장: 손끝이 맞닿는 순간 MuJoCo <weld> 구속을 활성화해 실제로
"붙잡힌" 상태로 전환하고, 로봇1의 손목만 흔들어 로봇2가 weld로 인해
끌려오는지(=구속이 실제로 작동하는지) 물리 스텝으로 검증한다.

1) 접근 구간: 기존과 동일한 운동학 스크립트 재생(qpos 직접 대입) — weld 비활성
2) 웰드 구간: 맞닿는 순간의 두 바디 상대 포즈를 relpose로 굳힌 weld를 활성화하고
   실제 물리(mj_step)로 전환. 로봇1은 PD로 자세 유지(+손목 흔들기), 로봇2는
   ctrl=0(완전 수동) — 로봇2 관절이 weld 때문에 따라 움직이면 구속이 실제로
   작동한다는 뜻.
mujoco_sim.service(라이브)는 완전히 별개 XML·프로세스라 미간섭.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import copy
import xml.etree.ElementTree as ET

import numpy as np
import mujoco
from PIL import Image

BASE_XML = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"
WELD_XML = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake_weld.xml"
OUT_PATH = "/home/moos/dev_ws/images/dual_openarm-handshake-weld-2026-08-03.gif"

FPS = 20
APPROACH_S = 2.0
WELD_S = 2.0
N_APPROACH = int(APPROACH_S * FPS)
N_WELD = int(WELD_S * FPS)
SUBSTEPS = 25  # per rendered frame during physics phase

J2_RETRACT = 1.3
J2_FINAL = 0.0

RIGHT_JOINTS = [f"right_joint_{i}" for i in range(1, 8)]


def ease(t):
    return 0.5 - 0.5 * np.cos(np.pi * t)


def quat_conj(q):
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_mul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def build_weld_xml(p1, q1, p2, q2):
    """right_link7(p1,q1) 기준 r2_right_link7(p2,q2)의 상대 포즈를 relpose로 굳혀 <equality><weld> 추가."""
    rel_pos = quat_mul(quat_mul(quat_conj(q1), np.array([0.0, *(p2 - p1)])), q1)[1:]
    rel_quat = quat_mul(quat_conj(q1), q2)

    tree = ET.parse(BASE_XML)
    root = tree.getroot()
    eq = ET.SubElement(root, "equality")
    weld = ET.SubElement(eq, "weld")
    weld.set("name", "handshake_weld")
    weld.set("body1", "right_link7")
    weld.set("body2", "r2_right_link7")
    weld.set("relpose", " ".join(f"{v:.6f}" for v in [*rel_pos, *rel_quat]))
    weld.set("active", "false")
    weld.set("solref", "0.02 1")
    tree.write(WELD_XML, encoding=None, xml_declaration=False)


def main():
    # ── pass 1: 접근 자세로 두 손 상대 포즈 계산 (weld 없는 모델) ──
    m0 = mujoco.MjModel.from_xml_path(BASE_XML)
    d0 = mujoco.MjData(m0)
    j2_0 = {p: mujoco.mj_name2id(m0, mujoco.mjtObj.mjOBJ_JOINT, f"{p}right_joint_2") for p in ("", "r2_")}
    d0.qpos[:] = 0.0
    d0.qpos[m0.jnt_qposadr[j2_0[""]]] = J2_FINAL
    d0.qpos[m0.jnt_qposadr[j2_0["r2_"]]] = J2_FINAL
    mujoco.mj_kinematics(m0, d0)
    b1 = mujoco.mj_name2id(m0, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    b2 = mujoco.mj_name2id(m0, mujoco.mjtObj.mjOBJ_BODY, "r2_right_link7")
    p1, q1 = d0.xpos[b1].copy(), d0.xquat[b1].copy()
    p2, q2 = d0.xpos[b2].copy(), d0.xquat[b2].copy()
    build_weld_xml(p1, q1, p2, q2)
    print(f"weld relpose 계산 완료 (손끝 거리 {np.linalg.norm(p2-p1):.4f}m)")

    # ── pass 2: weld 포함 모델로 렌더 ──
    model = mujoco.MjModel.from_xml_path(WELD_XML)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 960
    data = mujoco.MjData(model)

    j2 = {p: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{p}right_joint_2") for p in ("", "r2_")}
    weld_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "handshake_weld")

    r1_jids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in RIGHT_JOINTS]
    r1_actids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{j}_ctrl".replace("joint_", "joint")) for j in RIGHT_JOINTS]
    # 액추에이터 이름 규칙 확인: right_joint1_ctrl (밑줄 없음) — 위 치환으로 맞춤

    hide_bids = set()
    for name in ("target_left", "target_right", "r2_target_left", "r2_target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = 15, -12, 2.0
    cam.lookat[:] = [0.0, 0.52, 0.85]

    def render_frame():
        renderer.update_scene(data, camera=cam)
        for i in range(renderer.scene.ngeom):
            g = renderer.scene.geoms[i]
            if g.objtype == mujoco.mjtObj.mjOBJ_GEOM and model.geom_bodyid[g.objid] in hide_bids:
                g.rgba[3] = 0.0
        return Image.fromarray(renderer.render())

    frames = []
    r2_qpos_log = []

    # ── 접근 구간: 운동학 스크립트, weld 비활성 ──
    model.eq_active0[weld_id] = 0
    for f in range(N_APPROACH):
        frac = f / (N_APPROACH - 1)
        val = J2_RETRACT + (J2_FINAL - J2_RETRACT) * ease(frac)
        data.qpos[:] = 0.0
        data.qpos[model.jnt_qposadr[j2[""]]] = val
        data.qpos[model.jnt_qposadr[j2["r2_"]]] = val
        mujoco.mj_kinematics(model, data)
        mujoco.mj_fwdPosition(model, data)
        frames.append(render_frame())

    # ── weld 활성화 후 물리 전환 ──
    data.qvel[:] = 0.0
    data.eq_active[weld_id] = 1
    kp, kd = 8.0, 0.6
    targets = data.qpos[[model.jnt_qposadr[j] for j in r1_jids]].copy()

    for f in range(N_WELD):
        t = f / FPS
        wiggle = 0.15 * np.sin(2 * np.pi * t / 1.0)  # 손목(마지막 관절) 흔들기
        step_targets = targets.copy()
        step_targets[-1] += wiggle  # right_joint_7 (마지막)

        for _ in range(SUBSTEPS):
            qpos_idx = [model.jnt_qposadr[j] for j in r1_jids]
            qvel_idx = [model.jnt_dofadr[j] for j in r1_jids]
            q = data.qpos[qpos_idx]
            qd = data.qvel[qvel_idx]
            torque = kp * (step_targets - q) - kd * qd
            for aid, tq in zip(r1_actids, torque):
                data.ctrl[aid] = float(np.clip(tq, -8, 8))
            mujoco.mj_step(model, data)

        r2_j7 = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "r2_right_joint_7")
        r2_qpos_log.append(round(float(data.qpos[model.jnt_qposadr[r2_j7]]), 4))
        frames.append(render_frame())

    renderer.close()
    frames[0].save(OUT_PATH, save_all=True, append_images=frames[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"저장 완료: {OUT_PATH} ({len(frames)}프레임)")
    print("weld 구간 동안 r2_right_joint_7 qpos 변화(로봇2는 ctrl=0, 순수 weld로만 끌려옴):")
    print(r2_qpos_log)


if __name__ == "__main__":
    main()
