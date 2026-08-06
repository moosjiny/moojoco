"""'계란을 쥐듯' 접촉력 순응제어(하드 프리즈) 실험 — 실제 시뮬레이션 GIF 렌더.

thesis(2026-08-05-moojoco-egg-grip-force-compliant-handshake-attempt)에서 실측한
하드 프리즈 방식(접촉력 문턱 초과 시 목표각 동결)을 그대로 재생하며 렌더링한다.
매 프레임 접촉수·최악 침투·동결된 손가락 수를 오버레이해, "닿으면 멈추는" 제어가
실제로 어떻게 동작하고 왜 baseline보다 나빠지는지 시각적으로 보여준다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
GIF_PATH = "/home/moos/dev_ws/images/amazinghand_egg_grip_force_compliant_handshake.gif"
TRAJ_PATH = "/home/moos/dev_ws/dual_arms/data/egg_grip_handshake_gif_trajectory.json"

FPS = 20
APPROACH_S = 4.0
HOLD_S = 3.0
N_APPROACH = int(APPROACH_S * FPS)
N_HOLD = int(HOLD_S * FPS)
N_TOTAL = N_APPROACH + N_HOLD
SUBSTEPS = 10

A_START, A_END = -0.05, 0.035
B_START, B_END = -0.05, 0.035

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
FORCE_THRESHOLD_N = 0.3
FORCE_HYSTERESIS_N = 0.1


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
    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = -55, -18, 0.25
    cam.lookat[:] = [0.0, 0.0, 0.06]

    try:
        font_path = "/home/moos/dev_ws/aegis/fonts/NanumGothic-Bold.ttf"
        font = ImageFont.truetype(font_path, 20)
        font_small = ImageFont.truetype(font_path, 17)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    def render_frame(t, phase, worst_frame_dist, n_contact, n_frozen):
        renderer.update_scene(data, camera=cam)
        img = Image.fromarray(renderer.render()).convert("RGB")
        draw = ImageDraw.Draw(img)
        ratio = abs(worst_frame_dist) / CAPSULE_RADIUS if worst_frame_dist < 0 else 0.0
        color = (255, 90, 90) if worst_frame_dist < 0 else (140, 230, 160)
        phase_kr = "접근" if phase == "approach" else "유지(계란 쥐듯 정지 시도)"
        lines = [
            f"'계란 쥐듯' 접촉력 순응제어 (하드 프리즈, 문턱 {FORCE_THRESHOLD_N}N) — {phase_kr}",
            f"t={t:.2f}s  접촉수={n_contact}  최악 침투={worst_frame_dist*1000:.3f}mm ({ratio*100:.1f}%)  동결된 손가락={n_frozen}/10",
        ]
        draw.rectangle([0, 0, 960, 54], fill=(10, 12, 20))
        draw.text((12, 4), lines[0], fill=(255, 200, 60), font=font_small)
        draw.text((12, 28), lines[1], fill=color, font=font_small)
        return img

    frozen_frac = {(h, f): None for h in ("handA", "handB") for f in FINGER_JOINTS}

    frames = []
    trajectory = []
    worst_dist_all = 0.0
    max_ncon = 0

    for f in range(N_TOTAL):
        t_frac = min(f / (N_APPROACH - 1), 1.0)
        t = f / FPS
        frame_worst = 0.0
        for sub in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (A_END - A_START) * approach_frac
            b_target = B_START + (B_END - B_START) * approach_frac
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            finger_force = {k: 0.0 for k in frozen_frac}
            for ci in range(data.ncon):
                con = data.contact[ci]
                wrench = np.zeros(6)
                mujoco.mj_contactForce(model, data, ci, wrench)
                nf = abs(float(wrench[0]))
                for key, gid_ in geom_id.items():
                    if con.geom1 == gid_ or con.geom2 == gid_:
                        finger_force[key] = max(finger_force[key], nf)

            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    key = (hand, fn)
                    force = finger_force[key]
                    free_frac = ease(t_frac - CURL_PHASE[fn])
                    if frozen_frac[key] is None:
                        if force > FORCE_THRESHOLD_N:
                            frozen_frac[key] = free_frac
                        use_frac = free_frac
                    else:
                        if force < FORCE_HYSTERESIS_N and free_frac < frozen_frac[key]:
                            frozen_frac[key] = None
                            use_frac = free_frac
                        else:
                            use_frac = frozen_frac[key]
                    jname = f"{hand}_{fn}_curl"
                    target = CURL_TARGET[fn] * use_frac
                    q = data.qpos[model.jnt_qposadr[jid[jname]]]
                    qd = data.qvel[model.jnt_dofadr[jid[jname]]]
                    ctrl_name = f"{hand}_{fn}_ctrl"
                    data.ctrl[aid[ctrl_name]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))

            mujoco.mj_step(model, data)
            max_ncon = max(max_ncon, int(data.ncon))
            for ci in range(data.ncon):
                dist = float(data.contact[ci].dist)
                if dist < frame_worst:
                    frame_worst = dist
                if dist < worst_dist_all:
                    worst_dist_all = dist

        n_frozen = sum(1 for v in frozen_frac.values() if v is not None)
        phase = "approach" if f < N_APPROACH else "hold"
        frames.append(render_frame(t, phase, frame_worst, int(data.ncon), n_frozen))
        trajectory.append({
            "t": round(t, 3), "phase": phase, "n_contact": int(data.ncon),
            "frame_worst_dist_m": round(frame_worst, 6), "n_frozen": n_frozen,
        })

    renderer.close()
    frames[0].save(GIF_PATH, save_all=True, append_images=frames[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"GIF 저장 완료: {GIF_PATH} ({len(frames)}프레임)")

    hold_frames = [r for r in trajectory if r["phase"] == "hold"]
    worst_hold = min((r["frame_worst_dist_m"] for r in hold_frames), default=0.0)
    summary = {
        "model": XML_PATH, "fps": FPS, "n_frames": len(trajectory),
        "approach_s": APPROACH_S, "hold_s": HOLD_S,
        "force_threshold_n": FORCE_THRESHOLD_N,
        "worst_overall_dist_m": round(worst_dist_all, 6),
        "worst_overall_penetration_ratio_of_radius": round(abs(worst_dist_all) / CAPSULE_RADIUS, 4) if worst_dist_all < 0 else 0.0,
        "worst_hold_dist_m": round(worst_hold, 6),
        "worst_hold_penetration_ratio_of_radius": round(abs(worst_hold) / CAPSULE_RADIUS, 4) if worst_hold < 0 else 0.0,
        "max_simultaneous_contacts": max_ncon,
    }
    with open(TRAJ_PATH, "w") as fp:
        json.dump({"summary": summary, "frames": trajectory}, fp, indent=1)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
