"""접촉 성립 이후 침투가 시간에 따라 커지는지(발산) vs 유지되는지(수렴)를 검증.

diag_finger_interpenetration.py(v2)의 도킹 안무(4.0s, 접근+말아쥐기 mj_step 동기
진행)를 그대로 재생한 뒤, 최종 목표 자세를 HOLD_S만큼 추가로 유지하며 접촉이
안정 상태에서 더 깊어지지 않는지를 프레임별로 기록한다. 원 안무는 접촉이
마지막 프레임 근처에서야 성립해 "접촉 이후" 구간을 관찰하기 어려웠던 것을
보완한다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json
import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
REPORT_OUT = "/home/moos/dev_ws/dual_arms/data/post_contact_penetration_report.json"
SCENE_OUT = "/home/moos/dev_ws/dual_arms/data/finger_docking_3d_scene.json"

FPS = 20
APPROACH_S = 4.0
HOLD_S = 3.0
N_APPROACH = int(APPROACH_S * FPS)
N_HOLD = int(HOLD_S * FPS)
N_TOTAL = N_APPROACH + N_HOLD
SUBSTEPS = 10

# 접근값은 -0.20(멀리)→A_END(가까이)로 증가하는 방향이므로, -0.028(diag의 "닿는 지점")보다
# 더 깊이 밀어넣으려면 덜 음수인 값이 필요하다. -0.028은 스치기만 하고 즉시 떨어지는 목표라
# hold 구간에서 접촉이 끊겨(n_contact=0) "접촉 이후 안 겹침"을 검증할 수 없었음 — 4mm 더
# 깊게(-0.024) 밀어넣는 지속 가압 목표로 재검증.
A_START, A_END = -0.20, -0.024
B_START, B_END = -0.20, -0.024

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
GEOM_NAMES = ["handA_palm", "handB_palm"] + [
    f"hand{h}_{fn}_geom" for h in ("A", "B") for fn in FINGER_JOINTS
]


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)

    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in [
        "handA_approach", "handB_approach",
        *[f"handA_{f}_curl" for f in FINGER_JOINTS],
        *[f"handB_{f}_curl" for f in FINGER_JOINTS],
    ]}
    aid = {n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"): mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"))
        for n in jid}
    gid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, n) for n in GEOM_NAMES}

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    geoms_static = []
    for n in GEOM_NAMES:
        i = gid[n]
        gtype = "box" if n.endswith("_palm") else "capsule"
        geoms_static.append({"name": n, "type": gtype, "size": model.geom_size[i].tolist(),
                              "rgba": model.geom_rgba[i].tolist()})

    per_frame = []
    scene_frames = []
    first_contact_t = None
    worst_after_first_contact = 0.0

    for f in range(N_TOTAL):
        # N_APPROACH-1 이후로는 목표를 최종값(frac=1.0)에 고정해 접촉 유지 구간을 관찰
        t_frac = min(f / (N_APPROACH - 1), 1.0)
        t = f / FPS
        for _ in range(SUBSTEPS):
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
                    data.ctrl[aid[f"{hand}_{fn}_ctrl"]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))
            mujoco.mj_step(model, data)

        frame_worst = 0.0
        contacts = []
        for ci in range(data.ncon):
            con = data.contact[ci]
            dist = float(con.dist)
            if dist < frame_worst:
                frame_worst = dist
            if dist < 0.0:
                g1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom1)
                g2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom2)
                if g1 in gid and g2 in gid:
                    contacts.append({"g1": g1, "g2": g2, "d": round(dist, 5)})

        phase = "approach" if f < N_APPROACH else "hold"
        if contacts and first_contact_t is None:
            first_contact_t = round(t, 3)
        if first_contact_t is not None:
            worst_after_first_contact = min(worst_after_first_contact, frame_worst)

        per_frame.append({
            "t": round(t, 3), "phase": phase, "n_contact": int(data.ncon),
            "frame_worst_dist_m": round(frame_worst, 6),
        })

        row = {"t": round(t, 3), "phase": phase, "geoms": [], "contacts": contacts}
        for n in GEOM_NAMES:
            i = gid[n]
            row["geoms"].append({
                "n": n,
                "p": [round(v, 5) for v in data.geom_xpos[i].tolist()],
                "m": [round(v, 5) for v in data.geom_xmat[i].tolist()],
            })
        scene_frames.append(row)

    worst_overall = min(pf["frame_worst_dist_m"] for pf in per_frame)
    hold_frames = [pf for pf in per_frame if pf["phase"] == "hold"]
    worst_during_hold = min((pf["frame_worst_dist_m"] for pf in hold_frames), default=0.0)

    summary = {
        "capsule_radius_m": CAPSULE_RADIUS,
        "approach_s": APPROACH_S,
        "hold_s": HOLD_S,
        "first_contact_t_s": first_contact_t,
        "worst_dist_overall_m": round(worst_overall, 6),
        "worst_dist_overall_ratio_of_radius": round(abs(worst_overall) / CAPSULE_RADIUS, 4) if worst_overall < 0 else 0.0,
        "worst_dist_during_hold_m": round(worst_during_hold, 6),
        "worst_dist_during_hold_ratio_of_radius": round(abs(worst_during_hold) / CAPSULE_RADIUS, 4) if worst_during_hold < 0 else 0.0,
        "verdict": (
            "접촉 성립 이후(hold 구간) 최악 침투가 전체 구간 최악 침투보다 커지지 않음 → 발산 없음"
            if abs(worst_during_hold) <= abs(worst_overall) + 1e-9
            else "hold 구간에서 침투가 approach 구간보다 더 깊어짐 → 발산 의심, 재확인 필요"
        ),
    }

    with open(REPORT_OUT, "w") as fp:
        json.dump({"summary": summary, "per_frame": per_frame}, fp, indent=1)

    with open(SCENE_OUT, "w") as fp:
        json.dump({
            "capsule_radius_m": CAPSULE_RADIUS, "fps": FPS,
            "geoms_static": geoms_static, "frames": scene_frames,
            "note": "접근(4.0s)+접촉 유지(3.0s) 전 구간 mj_step 실물리. "
                    "접촉 성립 이후에도 침투가 발산하지 않는지 검증하기 위해 최종 목표 자세를 hold 구간 동안 유지.",
        }, fp)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n리포트: {REPORT_OUT}\n3D 씬: {SCENE_OUT}")


if __name__ == "__main__":
    main()
