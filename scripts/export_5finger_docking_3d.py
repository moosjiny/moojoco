"""5손가락 도킹 시뮬레이션의 실제 geom 3D 궤적(xpos/xmat/접촉) 추출 — v2.

diag_finger_interpenetration.py(v2, root-cause fix)와 동일하게 손목 접근과
손가락 말아쥐기를 처음부터 끝까지 mj_step 실물리 하에서 1:1 동기 진행시킨다.
구 버전(접근: 운동학 qpos 대입 → 도킹: mj_step)은 손가락이 편 채로 먼저
접근해 -14mm(반경 233%) 침투로 시작하는 것이 실측 근본원인이었으므로 폐기.
매 렌더 프레임마다 전체 geom의 world position/orientation과 침투 접촉쌍을
기록해 웹 3D 뷰어(/viz/finger-docking-3d)가 실제 시뮬레이션을 그대로
재생할 수 있게 한다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json
import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/data/finger_docking_3d_scene.json"

FPS = 20
TOTAL_S = 4.0
N_TOTAL = int(TOTAL_S * FPS)
SUBSTEPS = 10

A_START, A_END = -0.20, -0.028
B_START, B_END = -0.20, -0.028

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

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
    CAPSULE_RADIUS = 0.006

    geoms_static = []
    for n in GEOM_NAMES:
        i = gid[n]
        gtype = "box" if n.endswith("_palm") else "capsule"
        size = model.geom_size[i].tolist()
        rgba = model.geom_rgba[i].tolist()
        geoms_static.append({"name": n, "type": gtype, "size": size, "rgba": rgba})

    frames = []

    def capture_frame(t, phase, contacts):
        row = {"t": round(t, 3), "phase": phase, "geoms": [], "contacts": contacts}
        for n in GEOM_NAMES:
            i = gid[n]
            xpos = data.geom_xpos[i].tolist()
            xmat = data.geom_xmat[i].tolist()
            row["geoms"].append({"n": n, "p": [round(v, 5) for v in xpos],
                                  "m": [round(v, 5) for v in xmat]})
        frames.append(row)

    # ── 전 구간 mj_step 실물리: 손목 접근과 손가락 말아쥐기를 처음부터 끝까지
    #    1:1 동기 진행 (diag_finger_interpenetration.py v2와 동일 안무) ──
    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    for f in range(N_TOTAL):
        t_frac = f / (N_TOTAL - 1)
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
                    ctrl_name = f"{hand}_{fn}_ctrl"
                    data.ctrl[aid[ctrl_name]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))
            mujoco.mj_step(model, data)

        contacts = []
        for ci in range(data.ncon):
            con = data.contact[ci]
            dist = float(con.dist)
            if dist >= 0.0:
                continue
            g1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom1)
            g2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, con.geom2)
            if g1 not in gid or g2 not in gid:
                continue
            contacts.append({"g1": g1, "g2": g2, "d": round(dist, 5)})

        capture_frame(t_frac * TOTAL_S, "dock", contacts)

    out = {
        "capsule_radius_m": CAPSULE_RADIUS,
        "fps": FPS,
        "geoms_static": geoms_static,
        "frames": frames,
        "note": "전 구간 mj_step 실물리(v2, 접근+말아쥐기 동기 진행)로 생성된 geom world xpos/xmat 실측 궤적. "
                "contacts는 diag_finger_interpenetration.py와 동일 기준(dist<0)인 접촉쌍을 프레임별로 기록.",
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fp:
        json.dump(out, fp)
    print(f"3D 씬 데이터 저장 완료: {OUT_PATH} ({len(frames)}프레임)")


if __name__ == "__main__":
    main()
