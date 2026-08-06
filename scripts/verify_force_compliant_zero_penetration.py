"""접촉력 기반 순응 제어(force-compliant control)로 "달걀 쥐듯" 겹침 없는 악수가 가능한지 실측.

## 가설
기존(`diag_finger_interpenetration.py`)의 손가락 컨트롤러는 접촉 여부와 무관하게
고정 목표각(CURL_TARGET)까지 계속 밀어붙이는 순수 위치(PD) 제어다. 소프트 콘택트
모델(solimp/solref) 특성상 밀어붙이는 힘이 크면 클수록 모델이 허용하는 침투 depth도
커진다 — 즉 침투의 근본 원인은 "닿았는데도 계속 미는 목표"에 있다.

이를 "닿으면 그 자리에서 멈추는" 순응 제어(admittance control)로 바꾸면 — 마치
계란을 쥘 때 손끝이 계란 표면에 닿는 순간 더 이상 파고들지 않고 압력만 유지하듯 —
침투를 실질적으로 0에 가깝게 만들면서도 실접촉(ncon>0)은 유지할 수 있는지 검증한다.

## 제어 방식
각 손가락 관절마다 접촉력 센서(mj_contactForce)로 해당 손가락 geom이 받는 법선력
크기를 매 스텝 측정한다. 목표각은 기존과 같은 ease 곡선을 따라 전진하되, 측정 법선력이
FORCE_THRESHOLD(N)를 넘으면 그 순간의 목표각에 "동결"시켜 더 이상 전진시키지 않는다
(관용도 FORCE_HYSTERESIS 이내 재하강 시 재개 가능 — 채터링 방지).
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/data/force_compliant_zero_penetration_report.json"

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

# "계란을 쥐듯" — 살짝만 닿아도 멈추는 낮은 힘 문턱값. 너무 낮으면 아예 안 닿고
# 끝나는 가짜 해결이 될 수 있어 스윕으로 확인(본 스크립트 실행 결과 참조).
FORCE_THRESHOLD_N = 0.3
FORCE_HYSTERESIS_N = 0.1  # 재개 문턱(히스테리시스로 채터링 방지)


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
    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    # 손가락별 "동결된 목표 진행률"(None이면 아직 미동결, 자유 전진)
    frozen_frac = {(h, f): None for h in ("handA", "handB") for f in FINGER_JOINTS}

    worst_dist = 0.0
    worst_info = None
    per_frame = []
    all_dists_finger_pair = []
    max_ncon = 0
    max_force_seen = {(h, f): 0.0 for h in ("handA", "handB") for f in FINGER_JOINTS}
    freeze_events = []

    for f in range(N_TOTAL):
        t_frac = f / (N_TOTAL - 1)
        for sub in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (A_END - A_START) * approach_frac
            b_target = B_START + (B_END - B_START) * approach_frac
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            # 현재 스텝 시작 시점(직전 스텝 결과)의 손가락별 법선 접촉력 측정
            finger_force = {(h, fn): 0.0 for h in ("handA", "handB") for fn in FINGER_JOINTS}
            for ci in range(data.ncon):
                con = data.contact[ci]
                wrench = np.zeros(6)
                mujoco.mj_contactForce(model, data, ci, wrench)
                normal_force = abs(float(wrench[0]))
                for h in ("handA", "handB"):
                    for fn in FINGER_JOINTS:
                        gid = geom_id[(h, fn)]
                        if con.geom1 == gid or con.geom2 == gid:
                            finger_force[(h, fn)] = max(finger_force[(h, fn)], normal_force)

            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    key = (hand, fn)
                    force = finger_force[key]
                    max_force_seen[key] = max(max_force_seen[key], force)
                    free_frac = ease(t_frac - CURL_PHASE[fn])

                    if frozen_frac[key] is None:
                        if force > FORCE_THRESHOLD_N:
                            frozen_frac[key] = free_frac
                            freeze_events.append({"t": round(t_frac * TOTAL_S, 3), "hand": hand, "finger": fn,
                                                    "frac_at_freeze": round(free_frac, 4), "force_n": round(force, 4)})
                        use_frac = free_frac
                    else:
                        if force < FORCE_HYSTERESIS_N and free_frac < frozen_frac[key]:
                            # 접촉력이 풀리고 자유 목표가 동결 지점보다 아직 못 미쳤다면 재개
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

            frame_worst = 0.0
            for ci in range(data.ncon):
                con = data.contact[ci]
                dist = float(con.dist)
                g1 = model.geom(con.geom1).name
                g2 = model.geom(con.geom2).name
                if dist < frame_worst:
                    frame_worst = dist
                if dist < worst_dist:
                    worst_dist = dist
                    worst_info = {"t": round(t_frac * TOTAL_S, 3), "sub": sub, "geom1": g1, "geom2": g2, "dist_m": round(dist, 6)}
                is_finger_pair = ("_thumb_" in g1 or "_index_" in g1 or "_middle_" in g1 or "_ring_" in g1 or "_pinky_" in g1) and \
                                  ("_thumb_" in g2 or "_index_" in g2 or "_middle_" in g2 or "_ring_" in g2 or "_pinky_" in g2)
                if is_finger_pair and dist < 0:
                    all_dists_finger_pair.append(dist)

        frame_worst_pair = None
        for ci in range(data.ncon):
            con = data.contact[ci]
            if float(con.dist) == frame_worst:
                frame_worst_pair = f"{model.geom(con.geom1).name}|{model.geom(con.geom2).name}"
                break
        per_frame.append({"t": round(t_frac * TOTAL_S, 3), "n_contact": int(data.ncon), "frame_worst_dist_m": round(frame_worst, 6), "frame_worst_pair": frame_worst_pair})

    worst_ratio = abs(worst_dist) / CAPSULE_RADIUS if worst_dist < 0 else 0.0
    finger_pair_worst = min(all_dists_finger_pair) if all_dists_finger_pair else 0.0
    finger_pair_worst_ratio = abs(finger_pair_worst) / CAPSULE_RADIUS if finger_pair_worst < 0 else 0.0

    report = {
        "method": "force_compliant_admittance_stop",
        "force_threshold_n": FORCE_THRESHOLD_N,
        "force_hysteresis_n": FORCE_HYSTERESIS_N,
        "capsule_radius_m": CAPSULE_RADIUS,
        "worst_overall_dist_m": round(worst_dist, 6),
        "worst_overall_penetration_ratio_of_radius": round(worst_ratio, 4),
        "worst_overall_contact": worst_info,
        "worst_finger_finger_dist_m": round(finger_pair_worst, 6),
        "worst_finger_finger_penetration_ratio_of_radius": round(finger_pair_worst_ratio, 4),
        "n_finger_finger_penetrating_samples": len(all_dists_finger_pair),
        "max_simultaneous_contacts": max_ncon,
        "n_freeze_events": len(freeze_events),
        "freeze_events": freeze_events,
        "max_force_seen_by_finger_n": {f"{h}_{fn}": round(v, 4) for (h, fn), v in max_force_seen.items()},
    }
    with open(OUT_PATH, "w") as fp:
        json.dump({"summary": report, "per_frame": per_frame}, fp, indent=1)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 프레임 로그 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
