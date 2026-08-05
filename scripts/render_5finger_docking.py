"""5손가락(AmazingHand 스타일) 물리 도킹 시뮬레이션.

기존 aistudio의 "amazinghand_handshake_simulation.gif"는 정적 seed 좌표를
matplotlib으로 360도 회전시킨 시각화일 뿐 실제 물리 스텝이 없었다(URDF도
엄지 관절 1개만 정의돼 있고 나머지 4손가락은 주석에만 존재).

이 스크립트는 실제 MuJoCo 모델(urdf/amazinghand_5finger_docking.xml)로:
1) 접근 구간 — 두 손목을 운동학적으로 맞닿는 거리까지 이동(qpos 직접 대입)
2) 도킹 구간 — mj_step 실제 물리로 전환, 손가락 10개(양손 5개씩)를 PD로
   말아 쥐며 상대 손과 실제 geom-geom 접촉(weld 없음)으로 맞물리게 함
매 물리 프레임마다 관절 궤적(qpos)과 접촉력을 실측해 JSON으로 저장한다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco
from PIL import Image

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
GIF_PATH = "/home/moos/dev_ws/images/amazinghand_5finger_docking-2026-08-05.gif"
TRAJ_PATH = "/home/moos/dev_ws/dual_arms/data/amazinghand_5finger_docking_trajectory.json"

FPS = 20
APPROACH_S = 1.5
DOCK_S = 2.5
N_APPROACH = int(APPROACH_S * FPS)
N_DOCK = int(DOCK_S * FPS)
SUBSTEPS = 10  # mj_step calls per rendered frame during dock phase (timestep=0.002 -> 100Hz render)

A_START, A_END = -0.20, -0.028
# handB_wrist는 quat 180(Z축)으로 뒤집혀 있어 로컬 +Y 슬라이드가 글로벌 -Y로 매핑된다.
# 즉 global_y = -qpos 이므로, 원하는 글로벌 시작/종료 위치(+0.20 -> +0.028)를 얻으려면 부호를 반대로 준다.
B_START, B_END = -0.20, -0.028

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
# 엄지부터 순차적으로 말리기 시작하도록 위상차를 둠(실제 그립 동작과 유사)
CURL_PHASE = {"thumb": 0.0, "index": 0.15, "middle": 0.25, "ring": 0.35, "pinky": 0.45}


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


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
    bid_A = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "handA_wrist")
    bid_B = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "handB_wrist")

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = -55, -18, 0.25
    cam.lookat[:] = [0.0, 0.0, 0.06]

    def render_frame():
        renderer.update_scene(data, camera=cam)
        return Image.fromarray(renderer.render())

    frames = []
    trajectory = []

    # ── 접근 구간: 운동학, 물리 비활성(qpos 직접 대입) ──
    data.qpos[:] = 0.0
    for f in range(N_APPROACH):
        frac = ease(f / (N_APPROACH - 1))
        data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START + (A_END - A_START) * frac
        data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START + (B_END - B_START) * frac
        mujoco.mj_kinematics(model, data)
        mujoco.mj_fwdPosition(model, data)
        frames.append(render_frame())
        gap = float(np.linalg.norm(data.xpos[bid_A] - data.xpos[bid_B]))
        trajectory.append({
            "t": round(f / FPS, 3), "phase": "approach",
            "handA_wrist_y": round(float(data.xpos[bid_A][1]), 5),
            "handB_wrist_y": round(float(data.xpos[bid_B][1]), 5),
            "wrist_gap_m": round(gap, 5),
            **{f"handA_{fn}_curl": 0.0 for fn in FINGER_JOINTS},
            **{f"handB_{fn}_curl": 0.0 for fn in FINGER_JOINTS},
            "n_contact": 0, "sum_contact_force_N": 0.0,
        })

    # ── 도킹 구간: 실제 mj_step 물리, 손가락 PD로 말아쥐기 (weld 없음, 실접촉) ──
    data.qvel[:] = 0.0
    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06
    a_target = A_END
    b_target = B_END

    for f in range(N_DOCK):
        t = f / FPS
        for _ in range(SUBSTEPS):
            # 손목 위치 유지(PD)
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))
            # 손가락 순차 말아쥐기(PD)
            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    jname = f"{hand}_{fn}_curl"
                    frac = ease((t - CURL_PHASE[fn]) / (DOCK_S - 0.6))
                    target = CURL_TARGET[fn] * frac
                    q = data.qpos[model.jnt_qposadr[jid[jname]]]
                    qd = data.qvel[model.jnt_dofadr[jid[jname]]]
                    ctrl_name = f"{hand}_{fn}_ctrl"
                    data.ctrl[aid[ctrl_name]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))
            mujoco.mj_step(model, data)

        # 실측 접촉력: 활성 접촉의 법선력 크기 합
        total_force = 0.0
        for ci in range(data.ncon):
            f6 = np.zeros(6)
            mujoco.mj_contactForce(model, data, ci, f6)
            total_force += float(np.linalg.norm(f6[:3]))

        frames.append(render_frame())
        gap = float(np.linalg.norm(data.xpos[bid_A] - data.xpos[bid_B]))
        row = {
            "t": round(N_APPROACH / FPS + t, 3), "phase": "dock",
            "handA_wrist_y": round(float(data.xpos[bid_A][1]), 5),
            "handB_wrist_y": round(float(data.xpos[bid_B][1]), 5),
            "wrist_gap_m": round(gap, 5),
            "n_contact": int(data.ncon), "sum_contact_force_N": round(total_force, 4),
        }
        for hand in ("handA", "handB"):
            for fn in FINGER_JOINTS:
                row[f"{hand}_{fn}_curl"] = round(float(data.qpos[model.jnt_qposadr[jid[f'{hand}_{fn}_curl']]]), 5)
        trajectory.append(row)

    renderer.close()
    frames[0].save(GIF_PATH, save_all=True, append_images=frames[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"GIF 저장 완료: {GIF_PATH} ({len(frames)}프레임)")

    peak_force = max(r["sum_contact_force_N"] for r in trajectory)
    peak_contacts = max(r["n_contact"] for r in trajectory)
    summary = {
        "model": XML_PATH, "fps": FPS, "n_frames": len(trajectory),
        "approach_s": APPROACH_S, "dock_s": DOCK_S,
        "peak_contact_force_N": round(peak_force, 4),
        "peak_n_contact": peak_contacts,
        "note": "실제 mj_step 물리(weld 미사용, geom-geom 접촉)로 생성된 실측 궤적. "
                "이전 aistudio GIF는 정적 seed 회전 시각화였고 URDF도 엄지 관절 1개만 실존했음.",
    }
    with open(TRAJ_PATH, "w") as fp:
        json.dump({"summary": summary, "frames": trajectory}, fp, indent=1)
    print(f"궤적 데이터 저장 완료: {TRAJ_PATH} ({len(trajectory)}프레임)")
    print(f"실측 최대 접촉력: {peak_force:.3f} N, 최대 동시 접촉점: {peak_contacts}")


if __name__ == "__main__":
    main()
