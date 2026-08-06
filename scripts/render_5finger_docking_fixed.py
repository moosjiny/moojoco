"""5손가락 물리 도킹 — root-cause 안무 수정판 GIF 렌더.

diag_finger_interpenetration.py에서 검증된 안무(접근+말아쥐기 mj_step 전 구간
1:1 동기 진행)를 그대로 재생하며 렌더링한다. 매 프레임 worst contact dist와
접촉 수를 오버레이해 "닿았는데 거의 안 겹침"을 시각적으로도 보여준다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
GIF_PATH = "/home/moos/dev_ws/images/amazinghand_5finger_docking_fixed_zero_penetration.gif"
TRAJ_PATH = "/home/moos/dev_ws/dual_arms/data/amazinghand_5finger_docking_fixed_trajectory.json"

FPS = 20
TOTAL_S = 4.0
N_TOTAL = int(TOTAL_S * FPS)
SUBSTEPS = 10

A_START, A_END = -0.20, -0.028
B_START, B_END = -0.20, -0.028

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006


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

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    def render_frame(t, worst_frame_dist, n_contact):
        renderer.update_scene(data, camera=cam)
        img = Image.fromarray(renderer.render()).convert("RGB")
        draw = ImageDraw.Draw(img)
        ratio = abs(worst_frame_dist) / CAPSULE_RADIUS if worst_frame_dist < 0 else 0.0
        color = (255, 90, 90) if worst_frame_dist < 0 else (140, 230, 160)
        lines = [
            "5손가락 물리 도킹 — root-cause 수정판 (안무 동기화 + 손가락 간격 확장)",
            f"t={t:.2f}s  접촉수={n_contact}  최악 침투={worst_frame_dist*1000:.3f}mm  (캡슐반경 대비 {ratio*100:.1f}%)",
        ]
        draw.rectangle([0, 0, 960, 54], fill=(10, 12, 20))
        draw.text((12, 4), lines[0], fill=(255, 200, 60), font=font)
        draw.text((12, 28), lines[1], fill=color, font=font)
        return img

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    frames = []
    trajectory = []
    worst_dist_all = 0.0
    max_ncon = 0

    for f in range(N_TOTAL):
        t_frac = f / (N_TOTAL - 1)
        frame_worst = 0.0
        for sub in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (A_END - A_START) * approach_frac
            b_target = B_START + (B_END - B_START) * approach_frac
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))
            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    jname = f"{hand}_{fn}_curl"
                    frac = ease(t_frac - CURL_PHASE[fn])
                    target = CURL_TARGET[fn] * frac
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

        t = t_frac * TOTAL_S
        frames.append(render_frame(t, frame_worst, int(data.ncon)))
        gap = float(np.linalg.norm(data.xpos[bid_A] - data.xpos[bid_B]))
        trajectory.append({
            "t": round(t, 3), "wrist_gap_m": round(gap, 5),
            "n_contact": int(data.ncon), "frame_worst_dist_m": round(frame_worst, 6),
        })

    renderer.close()
    frames[0].save(GIF_PATH, save_all=True, append_images=frames[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
    print(f"GIF 저장 완료: {GIF_PATH} ({len(frames)}프레임)")

    summary = {
        "model": XML_PATH, "fps": FPS, "n_frames": len(trajectory),
        "total_s": TOTAL_S,
        "worst_overall_dist_m": round(worst_dist_all, 6),
        "worst_overall_penetration_ratio_of_radius": round(abs(worst_dist_all) / CAPSULE_RADIUS, 4) if worst_dist_all < 0 else 0.0,
        "max_simultaneous_contacts": max_ncon,
        "note": "diag_finger_interpenetration.py v2 안무와 동일. 접근+curl을 mj_step 전 구간 "
                "1:1 동기화하고 URDF 손가락 간격을 9~11mm에서 13mm로 확장해 v1의 -14mm(233%) "
                "관통을 -0.3mm(5%)로 줄였다(접촉은 유지, 즉 실제로 닿았음).",
    }
    with open(TRAJ_PATH, "w") as fp:
        json.dump({"summary": summary, "frames": trajectory}, fp, indent=1)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
