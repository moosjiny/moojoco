"""Stage 1.5 (LeRobot/ACT Phase 2 계획, v2 개정) — Stage 1이 표현하지 못했던 두
축을 실측한다: (A) 두 손이 정확히 마주보지 않고 좌우/상하로 어긋나 접근하면
성공/실패 경계가 달라지는가, (B) 두 손 사이에 장애물이 있어 완전히 접근하지
못하면 어떻게 되는가.

Stage 1(`generate_procedural_curl_dataset.py`)과 동일한 사전-감속
(mj_geomDistance 기반) 제어기를 그대로 재사용하되, 새 모델
`urdf/amazinghand_5finger_docking_v2.xml`(handB에 lateral/height 2-DOF 추가,
kinematic 장애물 mocap body 추가)로 두 개의 서브 스윕을 실행한다.

## 서브 스윕 A — 좌우/상하 오프셋
Stage 1에서 "거의 통과/근소하게 실패"였던 baseline 근처 경계 사례
(a_off=0, b_off=0, total_s=4.0 → 침투비 0.0535, FAIL)를 고정하고, handB의
lateral/height 오프셋만 5x5로 스윕한다 — "오프셋 0"이 이미 Stage 1의 실패
사례이므로, 오프셋이 그 실패를 완화하는지 악화하는지를 직접 관찰할 수 있다.

## 서브 스윕 B — 장애물
Stage 1에서 여유 있게 통과했던 사례(a_off=0, b_off=-0.01, 모든 속도 PASS)를
고정하고, 장애물(고정 벽)을 "없음"부터 "완전히 접근을 막는 위치"까지
스윕한다.

관찰(observation.state, 15차원) = Stage 1의 12차원 + [lateral_offset,
height_offset, obstacle_proximity_m]
행동(action, 10차원) = Stage 1과 동일(손가락별 curl 사용비율)
"""
import itertools
import json
import os
import time

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v2.xml"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset_stage1_5"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

FPS = 20
SUBSTEPS = 10

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
SLOW_START_DIST = 0.006
PENETRATION_GATE_RATIO = 0.05

A_START, B_START = -0.20, -0.20
A_END_BASELINE, B_END_BASELINE = -0.028, 0.0952

OBSTACLE_PARK_Y = 5.0  # Stage 1과 동일한 물리를 재현하려면 이 정도로 멀리 치워두면 충분
OBSTACLE_PROXIMITY_CLAMP = 0.05  # mj_geomDistance query distmax


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def run_episode(model, data, jid, aid, geom_id, obstacle_geom, obstacle_mocap_id,
                 a_end, b_end, total_s, lateral_offset, height_offset, obstacle_y):
    n_total = int(total_s * FPS)

    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    if obstacle_mocap_id is not None:
        data.mocap_pos[obstacle_mocap_id] = [0.0, obstacle_y if obstacle_y is not None else OBSTACLE_PARK_Y, 0.05]
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    # handB_lateral/handB_height only need to *hold* a static offset against
    # contact-force perturbation (they don't track a moving ramp like
    # handB_approach), so kp=40 is far too soft — under finger-finger contact
    # force it visibly "gives way" and the hand dodges collisions that a
    # rigid hand at the same offset would not, which erased almost all
    # penetration regardless of the offset value (confirmed empirically:
    # kp=40 -> 0.0000 for every one of 25 offset combos, vs kp=2000 showing
    # real variation incl. up to 0.17). Both actuators keep ctrlrange="-5 5"
    # in the XML, so this doesn't add unbounded force — it just reaches that
    # same 5N-equivalent saturation limit reliably instead of staying soft.
    kp_lat, kd_lat = 2000.0, 40.0
    kp_finger, kd_finger = 1.2, 0.06

    use_frac_state = {(h, f): 0.0 for h in ("handA", "handB") for f in FINGER_JOINTS}

    rows = []
    worst_dist = 0.0

    all_hand_geoms = [geom_id[(h, f)] for h in ("handA", "handB") for f in FINGER_JOINTS]
    all_hand_geoms += [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handA_palm"),
                        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handB_palm")]

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

            for side, target in (("handB_lateral", lateral_offset), ("handB_height", height_offset)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_lat * (target - q) - kd_lat * qd, -5, 5))

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
                dist = float(data.contact[ci].dist)
                if dist < worst_dist:
                    worst_dist = dist

        obstacle_prox = OBSTACLE_PROXIMITY_CLAMP
        if obstacle_y is not None:
            for g_self in all_hand_geoms:
                d_geom = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, OBSTACLE_PROXIMITY_CLAMP, None)
                if d_geom < obstacle_prox:
                    obstacle_prox = d_geom

        prox_vec = []
        action_vec = []
        for hand in ("handA", "handB"):
            for fn in FINGER_JOINTS:
                prox_vec.append(float(finger_proximity[(hand, fn)]))
                action_vec.append(float(use_frac_state[(hand, fn)]))
        obs = [float(ease(t_frac)), float(ease(t_frac))] + prox_vec + [
            float(lateral_offset), float(height_offset), float(obstacle_prox)
        ]

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


def build_model():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)

    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in [
        "handA_approach", "handB_approach", "handB_lateral", "handB_height",
        *[f"handA_{f}_curl" for f in FINGER_JOINTS],
        *[f"handB_{f}_curl" for f in FINGER_JOINTS],
    ]}
    aid = {}
    for n in jid:
        actuator_name = n.replace("_curl", "_ctrl")
        if actuator_name == n:  # handA_approach / handB_approach / handB_lateral / handB_height
            actuator_name = n + "_ctrl"
        aid[actuator_name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)

    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}
    obstacle_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "obstacle_geom")
    obstacle_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "obstacle")
    obstacle_mocap_id = int(model.body_mocapid[obstacle_body])

    return model, data, jid, aid, geom_id, obstacle_geom, obstacle_mocap_id


def save_episode(ep_idx, rows, out_dir):
    n = len(rows)
    table = pa.table({
        "episode_index": pa.array([ep_idx] * n, type=pa.int32()),
        "frame_index": pa.array([r["frame_index"] for r in rows], type=pa.int32()),
        "timestamp": pa.array([r["timestamp"] for r in rows], type=pa.float32()),
        "observation.state": pa.array([r["observation.state"] for r in rows], type=pa.list_(pa.float32())),
        "action": pa.array([r["action"] for r in rows], type=pa.list_(pa.float32())),
        "frame_worst_dist_m": pa.array([r["frame_worst_dist_m"] for r in rows], type=pa.float32()),
    })
    path = os.path.join(out_dir, f"episode_{ep_idx:04d}.parquet")
    pq.write_table(table, path)
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model, data, jid, aid, geom_id, obstacle_geom, obstacle_mocap_id = build_model()

    manifest = []
    ep_idx = 0
    t0 = time.time()

    # --- 서브 스윕 A: lateral/height 오프셋 (Stage 1 경계 사례 고정) ---
    a_end = A_END_BASELINE
    b_end = B_END_BASELINE
    total_s = 4.0
    LATERAL_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]
    HEIGHT_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]

    for lat, hei in itertools.product(LATERAL_OFFSETS, HEIGHT_OFFSETS):
        rows, worst_ratio = run_episode(
            model, data, jid, aid, geom_id, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lat, hei, obstacle_y=None,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "A_lateral_height",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": lat, "height_offset_m": hei, "obstacle_y_m": None,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[A][{ep_idx}] lat={lat:+.4f} hei={hei:+.4f} -> worst_ratio={worst_ratio:.4f} "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    # --- 서브 스윕 B: 장애물 (Stage 1 여유통과 사례 고정) ---
    a_end = A_END_BASELINE
    b_end = B_END_BASELINE - 0.01  # Stage 1에서 모든 속도 PASS했던 사례
    total_s = 4.0
    # 장애물 y좌표: None(없음) -> baseline 접근 경로(A_END~B_END world 근방)를
    # 점점 침범하는 위치까지. handA/handB가 만나는 지점은 대략 world y ~= 0.03
    # (A_END=-0.028 부근) 이므로 그 앞뒤로 스윕한다.
    OBSTACLE_Y_VALUES = [None, 0.06, 0.045, 0.03, 0.015, 0.0]

    for obs_y in OBSTACLE_Y_VALUES:
        rows, worst_ratio = run_episode(
            model, data, jid, aid, geom_id, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lateral_offset=0.0, height_offset=0.0, obstacle_y=obs_y,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "B_obstacle",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": 0.0, "height_offset_m": 0.0, "obstacle_y_m": obs_y,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[B][{ep_idx}] obstacle_y={obs_y} -> worst_ratio={worst_ratio:.4f} "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    n_pass = sum(1 for m in manifest if m["passed_5pct_gate"])
    summary = {
        "xml": XML_PATH,
        "capsule_radius_m": CAPSULE_RADIUS,
        "penetration_gate_ratio_of_radius": PENETRATION_GATE_RATIO,
        "observation_dims": (
            ["a_progress", "b_progress"]
            + [f"{h}_{fn}_proximity_m" for h in ("handA", "handB") for fn in FINGER_JOINTS]
            + ["handB_lateral_offset_m", "handB_height_offset_m", "obstacle_proximity_m"]
        ),
        "action_dims": [f"{h}_{fn}_use_frac" for h in ("handA", "handB") for fn in FINGER_JOINTS],
        "n_episodes": ep_idx,
        "n_passed_gate": n_pass,
        "n_failed_gate": ep_idx - n_pass,
        "elapsed_s": round(time.time() - t0, 2),
        "episodes": manifest,
    }
    with open(MANIFEST_PATH, "w") as fp:
        json.dump(summary, fp, indent=1)

    print(f"\n{n_pass}/{ep_idx} 에피소드가 5% 침투 게이트 통과 (Stage 1.5)")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
