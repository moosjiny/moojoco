"""5손가락 도킹 시뮬레이션의 손가락 겹침(interpenetration) 실측 진단 — v2 (root-cause fix 적용).

## v1 → v2 변경 이력 (2026-08-05)
v1은 "접근 구간(물리 비활성, qpos 직접 대입) → 도킹 구간(mj_step)" 2단계 구조였다.
실측 결과 worst_overall_dist=-14mm(캡슐 반경의 233%)의 심각한 관통이 있었는데,
Aegis의 "표면 투과 방지 4대 솔루션"(solref/solimp 강성화, substep 증가, Voronoi
클램핑, WebGL 클램핑)을 적용해도 수치가 전혀 개선되지 않았다. 원인을 직접
재현·분석한 결과, 진짜 원인은 접촉 솔버 파라미터가 아니라 **안무(choreography)
자체**였다: 접근 구간이 순수 운동학(콜리전 무시)으로 손목을 최종 거리까지
이동시키는 동안 손가락은 전혀 말리지 않은 채(curl=0, 쭉 편 상태) 상대 손바닥
쪽으로 뻗어있어, 도킹 물리가 시작되기도 전에 이미 52개 접촉쌍이 최대 -14mm
겹친 상태로 출발했다. 부가적으로 동일 손 내 인접 손가락 body 간격(9~11mm)이
캡슐 지름(12mm)보다 좁아 정지 자세에서도 자체 겹침이 있었다(URDF에서 13mm로
확장 수정).

v2는 접근과 말아쥐기를 처음부터 끝까지 mj_step 물리 하에서 1:1로 동기 진행시켜
(손가락이 항상 손목 접근 진행률만큼만 뻗어나가도록) 손가락이 상대 손 쪽으로
"쭉 편 채" 다가가는 구간 자체를 없앴다. 그 결과 worst_overall_dist가
-14mm(233%)에서 -0.3mm(5%)로 개선되었고, 실제 접촉(max_simultaneous_contacts=2)은
유지된다 — 즉 "닿지 않아서 0"이 아니라 "닿았는데 거의 안 겹치는" 진짜 해결이다.
(curl을 approach보다 먼저 끝내면 겹침은 0이 되지만 손이 아예 안 닿아버리는
가짜 해결이 됨 — 튜닝 스윕으로 확인 후 폐기)
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/data/finger_interpenetration_report.json"

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
    data = mujoco.MjData(model)

    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in [
        "handA_approach", "handB_approach",
        *[f"handA_{f}_curl" for f in FINGER_JOINTS],
        *[f"handB_{f}_curl" for f in FINGER_JOINTS],
    ]}
    aid = {n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"): mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"))
        for n in jid}

    # ── 전 구간 mj_step 실물리: 손목 접근과 손가락 말아쥐기를 처음부터 끝까지 1:1 동기 진행 ──
    # (v1의 "운동학적 접근 후 도킹" 2단계 구조를 폐기 — 그 경계에서 손가락이 편 채로
    #  이미 -14mm 겹쳐 시작하는 것이 진짜 원인이었음)
    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    worst_dist = 0.0
    worst_info = None
    per_frame = []
    all_dists_finger_pair = []  # 손가락-손가락 접촉만 별도 추적(손가락 vs 손바닥 제외)
    max_ncon = 0

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
                    worst_info = {
                        "t": round(t_frac * TOTAL_S, 3), "sub": sub,
                        "geom1": g1, "geom2": g2, "dist_m": round(dist, 6),
                    }
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
        "capsule_radius_m": CAPSULE_RADIUS,
        "worst_overall_dist_m": round(worst_dist, 6),
        "worst_overall_penetration_ratio_of_radius": round(worst_ratio, 4),
        "worst_overall_contact": worst_info,
        "worst_finger_finger_dist_m": round(finger_pair_worst, 6),
        "worst_finger_finger_penetration_ratio_of_radius": round(finger_pair_worst_ratio, 4),
        "n_finger_finger_penetrating_samples": len(all_dists_finger_pair),
        "max_simultaneous_contacts": max_ncon,
        "note": "dist<0은 solimp/solref 연성 접촉모델상의 정상 침투(소프트 콘택트). "
                "max_simultaneous_contacts>0은 실제로 손이 맞닿았음을 뜻함(0이면 안 닿아서 "
                "침투가 0인 가짜 결과이므로 반드시 함께 확인할 것).",
    }
    with open(OUT_PATH, "w") as fp:
        json.dump({"summary": report, "per_frame": per_frame}, fp, indent=1)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n상세 프레임 로그 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
