"""Stage 1 (LeRobot/ACT Phase 2 계획) — 사람 시연 대신 이 레포의 MuJoCo 시뮬레이션
자체로 "절차적 시연(procedural demonstration)" 데이터셋을 생성한다.

## 배경
`verify_anticipatory_distance_zero_penetration.py`가 이미 mj_geomDistance 기반
사전-감속(anticipatory deceleration) 제어로 거의 0에 가까운 침투율을 달성했다
(§참고: 해당 스크립트의 anticipatory_distance_zero_penetration_report.json).
이 스크립트는 그 제어 로직을 하나의 "전문가(expert)" 궤적 생성기로 재사용하되,
접근 자세(두 손의 최종 접근 거리)와 접근 속도(총 소요 시간)를 다양하게 스윕해
서로 다른 초기조건에서도 안전한 손가락 curl 스케줄이 어떻게 달라지는지 기록한다.

각 스텝마다 다음을 (observation, action) 쌍으로 저장한다:
  observation = [양손 접근 진행률 2 + 손가락별(양손 x 5개) 상대 근접도 10] = 12차원
  action      = 손가락별(양손 x 5개) curl 목표 사용비율(use_frac, 0~1)       = 10차원
즉 "지금 손이 얼마나 가까이 왔는가"로부터 "지금 손가락을 얼마나 오므려도
안전한가"를 예측하는 정책을 학습하기 위한 데이터셋 — CURL_TARGET을 고정값이
아니라 이 매핑으로 대체하는 것이 Phase 2의 목표(§submit_lerobot_act_phase2_plan
_thesis.py 참고).

물리 계산만 수행하고 렌더링은 하지 않으므로 GPU가 필요 없다(Stage 1 요건).
"""
import itertools
import json
import os
import time

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

FPS = 20
SUBSTEPS = 10

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
SLOW_START_DIST = 0.006
PENETRATION_GATE_RATIO = 0.05  # Hermes 검증 게이트: 캡슐 반경의 5% 이내

A_START, B_START = -0.20, -0.20
# 기존 baseline(2026-08-06 재보정, 5.15% 침투): A_END=-0.028, B_END=0.0952
A_END_BASELINE, B_END_BASELINE = -0.028, 0.0952

# 스윕 그리드 — 접근 최종거리(두 값 모두 baseline 대비 오프셋)와 접근 소요시간(속도)
A_END_OFFSETS = [-0.01, 0.0, 0.01]
B_END_OFFSETS = [-0.02, -0.01, 0.0, 0.01, 0.02]
TOTAL_S_VALUES = [2.5, 4.0, 6.0]


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def run_episode(model, data, jid, aid, geom_id, a_end, b_end, total_s):
    n_total = int(total_s * FPS)

    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    use_frac_state = {(h, f): 0.0 for h in ("handA", "handB") for f in FINGER_JOINTS}

    rows = []
    worst_dist = 0.0

    for f in range(n_total):
        t_frac = f / max(n_total - 1, 1)
        for sub in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (a_end - A_START) * approach_frac
            b_target = B_START + (b_end - B_START) * approach_frac
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            finger_proximity = {}
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
                    free_frac = ease(t_frac - CURL_PHASE[fn])
                    free_step = max(free_frac - use_frac_state[key], 0.0)
                    slow_factor = float(np.clip(prox / SLOW_START_DIST, 0.0, 1.0))
                    use_frac_state[key] = min(use_frac_state[key] + free_step * slow_factor, 1.0)

                    jname = f"{hand}_{fn}_curl"
                    target = CURL_TARGET[fn] * use_frac_state[key]
                    q = data.qpos[model.jnt_qposadr[jid[jname]]]
                    qd = data.qvel[model.jnt_dofadr[jid[jname]]]
                    ctrl_name = f"{hand}_{fn}_ctrl"
                    data.ctrl[aid[ctrl_name]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))

            mujoco.mj_step(model, data)

            for ci in range(data.ncon):
                con = data.contact[ci]
                dist = float(con.dist)
                if dist < worst_dist:
                    worst_dist = dist

        # 프레임(제어주기) 끝에서 한 번만 (observation, action) 기록 — FPS=20Hz 데이터셋
        obs = [float(ease(t_frac)), float(ease(t_frac))]  # a_progress, b_progress (동일 easing 공유)
        prox_vec = []
        action_vec = []
        for hand in ("handA", "handB"):
            for fn in FINGER_JOINTS:
                prox_vec.append(float(finger_proximity[(hand, fn)]))
                action_vec.append(float(use_frac_state[(hand, fn)]))
        obs = obs + prox_vec

        frame_worst = 0.0
        for ci in range(data.ncon):
            dist = float(data.contact[ci].dist)
            if dist < frame_worst:
                frame_worst = dist

        rows.append({
            "frame_index": f,
            "timestamp": float(f / FPS),
            "observation.state": obs,
            "action": action_vec,
            "frame_worst_dist_m": frame_worst,
        })

    worst_ratio = abs(worst_dist) / CAPSULE_RADIUS if worst_dist < 0 else 0.0
    return rows, worst_ratio


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

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

    combos = list(itertools.product(A_END_OFFSETS, B_END_OFFSETS, TOTAL_S_VALUES))
    manifest = []
    t0 = time.time()

    for ep_idx, (a_off, b_off, total_s) in enumerate(combos):
        a_end = A_END_BASELINE + a_off
        b_end = B_END_BASELINE + b_off

        rows, worst_ratio = run_episode(model, data, jid, aid, geom_id, a_end, b_end, total_s)
        passed = worst_ratio <= PENETRATION_GATE_RATIO

        n = len(rows)
        table = pa.table({
            "episode_index": pa.array([ep_idx] * n, type=pa.int32()),
            "frame_index": pa.array([r["frame_index"] for r in rows], type=pa.int32()),
            "timestamp": pa.array([r["timestamp"] for r in rows], type=pa.float32()),
            "observation.state": pa.array([r["observation.state"] for r in rows], type=pa.list_(pa.float32())),
            "action": pa.array([r["action"] for r in rows], type=pa.list_(pa.float32())),
            "frame_worst_dist_m": pa.array([r["frame_worst_dist_m"] for r in rows], type=pa.float32()),
        })
        ep_path = os.path.join(OUT_DIR, f"episode_{ep_idx:04d}.parquet")
        pq.write_table(table, ep_path)

        manifest.append({
            "episode_index": ep_idx,
            "a_end": round(a_end, 4),
            "b_end": round(b_end, 4),
            "total_s": total_s,
            "n_frames": n,
            "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "passed_5pct_gate": passed,
            "path": ep_path,
        })
        print(f"[{ep_idx+1}/{len(combos)}] a_end={a_end:+.4f} b_end={b_end:+.4f} total_s={total_s} "
              f"-> worst_ratio={worst_ratio:.4f} {'PASS' if passed else 'FAIL'}", flush=True)

    n_pass = sum(1 for m in manifest if m["passed_5pct_gate"])
    summary = {
        "xml": XML_PATH,
        "capsule_radius_m": CAPSULE_RADIUS,
        "penetration_gate_ratio_of_radius": PENETRATION_GATE_RATIO,
        "observation_dims": ["a_progress", "b_progress"] + [f"{h}_{fn}_proximity_m" for h in ("handA", "handB") for fn in FINGER_JOINTS],
        "action_dims": [f"{h}_{fn}_use_frac" for h in ("handA", "handB") for fn in FINGER_JOINTS],
        "n_episodes": len(combos),
        "n_passed_gate": n_pass,
        "n_failed_gate": len(combos) - n_pass,
        "elapsed_s": round(time.time() - t0, 2),
        "episodes": manifest,
    }
    with open(MANIFEST_PATH, "w") as fp:
        json.dump(summary, fp, indent=1)

    print(f"\n{n_pass}/{len(combos)} 에피소드가 5% 침투 게이트 통과")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
