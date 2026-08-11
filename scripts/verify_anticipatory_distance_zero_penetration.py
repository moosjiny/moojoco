"""거리 기반 예측 감속(proximity-anticipatory deceleration)으로 겹침 없는 악수가
가능한지 실측.

## 배경 — 왜 반응형(force-compliant) 제어는 실패했나
`verify_force_compliant_zero_penetration.py`에서 접촉력이 문턱값을 넘으면 목표각을
동결하는 방식을 시도했으나, baseline(5.18% 침투)보다 오히려 나빠졌다(8.76%). 원인은
접촉력이 `mj_step` *이후*에만 측정 가능해 최소 1-substep 지연이 있고, 소프트 콘택트
모델의 반발력이 그보다 빨리 치솟기 때문이었다 — 즉 "닿은 뒤에 반응"하는 방식 자체의
구조적 한계.

## 이번 방법 — 접촉 전에 미리 보고 감속
`mj_geomDistance(m, d, geom1, geom2, distmax, fromto)` — MuJoCo가 제공하는 두 geom 간
부호 있는 최단거리를 직접 질의하는 함수를 쓴다. 최초 시도는 geom `margin`/`gap` 설정으로
`data.contact` 목록에 사전 접촉을 잡으려 했으나, 실측 결과 상대편 손가락이 시뮬레이션
내내 단 한 번도 그 목록에 잡히지 않았다(원인 미상 — margin/gap 상호작용 추정, §참고
실행 로그). `mj_geomDistance`는 margin 설정과 무관하게 항상 정확한 기하 거리를 직접
반환하므로 이 문제를 완전히 우회한다.

각 손가락마다 **반대쪽 손**의 5개 손가락 전부와의 거리를 매 스텝 질의해 최솟값을
"이 손가락이 상대와 얼마나 가까운가"의 신호로 쓴다 — 힘이 아니라 순수 기하학이므로
`mj_step` 이후를 기다릴 필요 없이 스텝 시작 시점의 현재 자세만으로 선제적으로 계산
가능하다. SLOW_START_DIST(6mm) 이내로 들어오면 목표각 전진 스텝을 "남은 거리 비례"로
선형 감속시킨다(거리가 0에 가까워질수록 전진 속도도 0에 수렴). 같은 손 안의 인접
손가락(원래부터 1mm 안팎으로 가까움, 손 폭 13mm·캡슐 반경 6mm+6mm=12mm)은 감속
신호에서 반드시 제외한다 — 섞으면 손가락이 전혀 오므리지 못하는 가짜 결과가 나온다
(1차 시도에서 실제로 이 함정에 빠졌었음).
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/data/anticipatory_distance_zero_penetration_report.json"

FPS = 20
TOTAL_S = 4.0
N_TOTAL = int(TOTAL_S * FPS)
SUBSTEPS = 10

# 2026-08-06 커밋(30c4a1d)에서 handB_wrist 기준위치가 Y축으로 +0.12m 이동해
# 기존 접근좌표(A_END=B_END=-0.028)로는 더 이상 접촉이 발생하지 않음(실측 확인).
# B_END를 재보정 스윕(0.092~0.108)해 옛 baseline 침투율(5.18%)과 가장 가까운
# 값(5.15%)을 채택 — §참고 재보정 로그.
A_START, A_END = -0.20, -0.028
B_START, B_END = -0.20, 0.0952

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006

# 감속 시작 거리 — 캡슐 반경과 동일하게 잡아 "표면이 닿기 시작할 만한 거리"부터 감속
SLOW_START_DIST = 0.006


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

    # 손가락별 "지금까지 도달한 진행률" — 감속 로직이 여기서부터 증분만 계산
    use_frac_state = {(h, f): 0.0 for h in ("handA", "handB") for f in FINGER_JOINTS}

    worst_dist = 0.0
    worst_info = None
    per_frame = []
    all_dists_finger_pair = []
    max_ncon = 0
    min_proximity_seen = {(h, f): SLOW_START_DIST for h in ("handA", "handB") for f in FINGER_JOINTS}
    slow_events = []
    slow_triggered = {(h, f): False for h in ("handA", "handB") for f in FINGER_JOINTS}

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

            # mj_geomDistance로 손가락별 "반대쪽 손과의 최단 거리" 직접 질의(margin/gap 무관)
            finger_proximity = {(h, fn): SLOW_START_DIST for h in ("handA", "handB") for fn in FINGER_JOINTS}
            for hand in ("handA", "handB"):
                other = "handB" if hand == "handA" else "handA"
                for fn in FINGER_JOINTS:
                    g_self = geom_id[(hand, fn)]
                    best = SLOW_START_DIST
                    for ofn in FINGER_JOINTS:
                        g_other = geom_id[(other, ofn)]
                        d_geom = mujoco.mj_geomDistance(model, data, g_self, g_other, SLOW_START_DIST, None)
                        if d_geom < best:
                            best = d_geom
                    finger_proximity[(hand, fn)] = best

            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    key = (hand, fn)
                    prox = finger_proximity[key]
                    min_proximity_seen[key] = min(min_proximity_seen[key], prox)
                    if prox < SLOW_START_DIST and not slow_triggered[key]:
                        slow_triggered[key] = True
                        slow_events.append({"t": round(t_frac * TOTAL_S, 3), "hand": hand, "finger": fn,
                                             "proximity_at_trigger_m": round(prox, 6)})

                    free_frac = ease(t_frac - CURL_PHASE[fn])
                    free_step = max(free_frac - use_frac_state[key], 0.0)

                    # 감속 계수: 여유거리가 SLOW_START_DIST 이상이면 1.0(무감속),
                    # 0에 가까워질수록 0에 선형 수렴(음수 clip으로 실제 침투 중엔 전진 정지)
                    slow_factor = float(np.clip(prox / SLOW_START_DIST, 0.0, 1.0))
                    step = free_step * slow_factor
                    use_frac_state[key] = min(use_frac_state[key] + step, 1.0)
                    use_frac = use_frac_state[key]

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
        "method": "proximity_anticipatory_deceleration_geomDistance",
        "slow_start_dist_m": SLOW_START_DIST,
        "capsule_radius_m": CAPSULE_RADIUS,
        "worst_overall_dist_m": round(worst_dist, 6),
        "worst_overall_penetration_ratio_of_radius": round(worst_ratio, 4),
        "worst_overall_contact": worst_info,
        "worst_finger_finger_dist_m": round(finger_pair_worst, 6),
        "worst_finger_finger_penetration_ratio_of_radius": round(finger_pair_worst_ratio, 4),
        "n_finger_finger_penetrating_samples": len(all_dists_finger_pair),
        "max_simultaneous_contacts": max_ncon,
        "n_slow_trigger_events": len(slow_events),
        "slow_events": slow_events,
        "min_proximity_seen_by_finger_m": {f"{h}_{fn}": round(v, 6) for (h, fn), v in min_proximity_seen.items()},
    }
    with open(OUT_PATH, "w") as fp:
        json.dump({"summary": report, "per_frame": per_frame}, fp, indent=1)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 프레임 로그 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
