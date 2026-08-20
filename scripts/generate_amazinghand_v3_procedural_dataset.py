"""손바닥 접촉 v3 모델([[2026-08-20-moojoco-handshake-geometry-redesign-v3]]) —
Stage 1과 같은 발상으로, curl 각도 하나를 손으로 맞추려다 트레이드오프에
막혀서(많이 굽히면 손바닥은 가까워지지만 그립 실패, 적게 굽히면 방향은
그럴듯해도 접근 자체를 막음) 사령관이 "1번"(넓게 스윕해서 데이터로 풀자)을
선택했다.

Stage 1의 접근 거리·속도 스윕에 **손가락 굽힘 최대각(curl_scale)** 스윕을
새로 추가한다 — 이번엔 굽힘 각도 자체가 정답을 모르는 축이라 이걸 직접
스윕 대상으로 삼는다. 다른 스윕 축(좌우/상하 오프셋, 장애물)은 이번 1차
데이터셋에는 포함하지 않는다(Stage 1.5/1.75에 해당하는 확장은 다음 단계).

행동(action, 22차원) = [handA_approach_use_frac, handB_approach_use_frac]
  + 손가락별(양손×5) × 관절별(MCP, PIP) 사용비율 20
관찰(observation.state, 16차원) — Stage 1.75/스키마재설계와 같은 형태:
  [elapsed_time_frac, handA_qpos_frac, handB_qpos_frac]
  + 손가락별(양손×5) 근접도 10(그 손가락의 두 세그먼트 중 더 가까운 쪽 ~
    상대 손의 모든 손가락 세그먼트·손바닥 중 가장 가까운 것)
  + [lateral_offset(항상 0), height_offset(항상 0), obstacle_proximity(항상 안전값)]
  — 이번 스윕엔 오프셋·장애물이 없어 뒤 3차원은 상수지만, 다음 단계(Stage
  1.5/1.75에 해당)에서 그대로 재사용할 수 있도록 스키마를 맞춰뒀다.

성공 기준은 지금까지와 동일(침투비 5% 이내)이지만, "손가락이 실제로 상대
손바닥에 닿았는가"(finger_to_palm_contact)도 별도로 기록한다 — 침투가
없다고 그립에 성공했다는 뜻은 아니라는 걸 이번 세션에서 두 번(Stage 3
거짓양성, 이번 curl 트레이드오프) 배웠기 때문이다.
"""
import itertools
import json
import os
import time

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v3.xml"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/amazinghand_v3_procedural_dataset"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

FPS = 20
SUBSTEPS = 10

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
SLOW_START_DIST = 0.006
PENETRATION_GATE_RATIO = 0.05

A_START, B_START = -0.20, -0.20
# [[2026-08-20-moojoco-handshake-geometry-redesign-v3]]에서 실측 확인한
# "손바닥이 정확히 맞닿는" 지점(0.0mm 간격) — Stage 1의 baseline에 해당.
A_END_BASELINE, B_END_BASELINE = -0.028, 0.114

A_END_OFFSETS = [-0.008, 0.0, 0.008]
B_END_OFFSETS = [-0.010, 0.0, 0.010]
TOTAL_S_VALUES = [3.0, 4.5]
CURL_SCALE_VALUES = [0.4, 0.55, 0.7, 0.9, 1.2]
MCP_BASE, PIP_BASE = 1.4, 1.5  # curl_scale=1.0일 때의 기준값(원래 시도했던 값)


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def build_model():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)

    jid = {}
    for name in ["handA_approach", "handB_approach", "handB_lateral", "handB_height"]:
        jid[name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    for h in ("handA", "handB"):
        for fn in FINGER_JOINTS:
            jid[f"{h}_{fn}_mcp"] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{h}_{fn}_mcp")
            jid[f"{h}_{fn}_pip"] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{h}_{fn}_pip")

    aid = {}
    for name in jid:
        actuator_name = name + "_ctrl"
        aid[actuator_name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)

    finger_geoms = {}
    for h in ("handA", "handB"):
        for fn in FINGER_JOINTS:
            finger_geoms[(h, fn)] = [
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{fn}_prox_geom"),
                mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{fn}_dist_geom"),
            ]
    palm_geom = {
        "handA": mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handA_palm"),
        "handB": mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handB_palm"),
    }
    obstacle_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "obstacle_geom")
    obstacle_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "obstacle")
    obstacle_mocap_id = int(model.body_mocapid[obstacle_body])

    return model, data, jid, aid, finger_geoms, palm_geom, obstacle_geom, obstacle_mocap_id


def run_episode(model, data, jid, aid, finger_geoms, palm_geom, obstacle_geom, obstacle_mocap_id,
                 a_end, b_end, total_s, curl_scale):
    n_total = int(total_s * FPS)
    mcp_max, pip_max = MCP_BASE * curl_scale, PIP_BASE * curl_scale

    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    data.mocap_pos[obstacle_mocap_id] = [0.0, 5.0, 0.05]  # 이번 스윕엔 장애물 없음(멀리 치워둠)
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_lat, kd_lat = 2000.0, 40.0
    kp_finger, kd_finger = 1.2, 0.06

    use_frac_state = {(h, fn, j): 0.0 for h in ("handA", "handB") for fn in FINGER_JOINTS for j in ("mcp", "pip")}
    approach_state = {"handA": 0.0, "handB": 0.0}

    rows = []
    worst_dist = 0.0
    finger_to_palm_contact = False

    for f in range(n_total):
        t_frac = f / max(n_total - 1, 1)
        for sub in range(SUBSTEPS):
            for hand, (start, end) in (("handA", (A_START, a_end)), ("handB", (B_START, b_end))):
                free_frac = ease(t_frac)
                free_step = max(free_frac - approach_state[hand], 0.0)
                approach_state[hand] = min(approach_state[hand] + free_step, 1.0)
                target = start + (end - start) * approach_state[hand]
                jn = f"{hand}_approach"
                q = data.qpos[model.jnt_qposadr[jid[jn]]]
                qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                data.ctrl[aid[f"{jn}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            for side in ("handB_lateral", "handB_height"):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_lat * (0.0 - q) - kd_lat * qd, -5, 5))

            finger_proximity = {}
            for hand in ("handA", "handB"):
                other = "handB" if hand == "handA" else "handA"
                for fn in FINGER_JOINTS:
                    best = SLOW_START_DIST
                    for g_self in finger_geoms[(hand, fn)]:
                        for ofn in FINGER_JOINTS:
                            for g_other in finger_geoms[(other, ofn)]:
                                d = mujoco.mj_geomDistance(model, data, g_self, g_other, SLOW_START_DIST, None)
                                if d < best:
                                    best = d
                        d_palm = mujoco.mj_geomDistance(model, data, g_self, palm_geom[other], SLOW_START_DIST, None)
                        if d_palm < best:
                            best = d_palm
                    finger_proximity[(hand, fn)] = best

            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    prox = finger_proximity[(hand, fn)]
                    slow_factor = float(np.clip(prox / SLOW_START_DIST, 0.0, 1.0))
                    free_frac = ease(t_frac - CURL_PHASE[fn])
                    for j, tgt_max in (("mcp", mcp_max), ("pip", pip_max)):
                        key = (hand, fn, j)
                        free_step = max(free_frac - use_frac_state[key], 0.0)
                        use_frac_state[key] = min(use_frac_state[key] + free_step * slow_factor, 1.0)
                        jn = f"{hand}_{fn}_{j}"
                        target = tgt_max * use_frac_state[key]
                        q = data.qpos[model.jnt_qposadr[jid[jn]]]
                        qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                        data.ctrl[aid[f"{jn}_ctrl"]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))

            mujoco.mj_step(model, data)
            for ci in range(data.ncon):
                dist = float(data.contact[ci].dist)
                if dist < worst_dist:
                    worst_dist = dist
                g1 = model.geom(data.contact[ci].geom1).name
                g2 = model.geom(data.contact[ci].geom2).name
                is_finger_palm = ("palm" in g1) != ("palm" in g2)
                if is_finger_palm:
                    finger_to_palm_contact = True

        qa = data.qpos[model.jnt_qposadr[jid["handA_approach"]]]
        qb = data.qpos[model.jnt_qposadr[jid["handB_approach"]]]
        a_qpos_frac = float(np.clip((qa - A_START) / (a_end - A_START), 0.0, 1.0))
        b_qpos_frac = float(np.clip((qb - B_START) / (b_end - B_START), 0.0, 1.0))
        prox_vec = [finger_proximity[(h, fn)] for h in ("handA", "handB") for fn in FINGER_JOINTS]
        obs = [float(ease(t_frac)), a_qpos_frac, b_qpos_frac] + prox_vec + [0.0, 0.0, SLOW_START_DIST]
        action_vec = [float(approach_state["handA"]), float(approach_state["handB"])] + [
            float(use_frac_state[(h, fn, j)]) for h in ("handA", "handB") for fn in FINGER_JOINTS for j in ("mcp", "pip")
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
    return rows, worst_ratio, finger_to_palm_contact


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
    model, data, jid, aid, finger_geoms, palm_geom, obstacle_geom, obstacle_mocap_id = build_model()

    combos = list(itertools.product(A_END_OFFSETS, B_END_OFFSETS, TOTAL_S_VALUES, CURL_SCALE_VALUES))
    manifest = []
    t0 = time.time()

    for ep_idx, (a_off, b_off, total_s, curl_scale) in enumerate(combos):
        a_end = A_END_BASELINE + a_off
        b_end = B_END_BASELINE + b_off
        rows, worst_ratio, f2p = run_episode(
            model, data, jid, aid, finger_geoms, palm_geom, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, curl_scale,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx,
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "curl_scale": curl_scale,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "passed_5pct_gate": passed, "finger_to_palm_contact": f2p, "path": path,
        })
        print(f"[{ep_idx:3d}/{len(combos)}] a_off={a_off:+.3f} b_off={b_off:+.3f} total_s={total_s} "
              f"curl_scale={curl_scale} -> worst_ratio={worst_ratio:.4f} "
              f"{'PASS' if passed else 'FAIL'} {'F2P' if f2p else '---'}", flush=True)

    n_pass = sum(1 for m in manifest if m["passed_5pct_gate"])
    n_f2p = sum(1 for m in manifest if m["finger_to_palm_contact"])
    n_both = sum(1 for m in manifest if m["passed_5pct_gate"] and m["finger_to_palm_contact"])

    by_curl_scale = {}
    for m in manifest:
        cs = m["curl_scale"]
        by_curl_scale.setdefault(cs, {"n": 0, "passed": 0, "f2p": 0, "both": 0})
        by_curl_scale[cs]["n"] += 1
        by_curl_scale[cs]["passed"] += int(m["passed_5pct_gate"])
        by_curl_scale[cs]["f2p"] += int(m["finger_to_palm_contact"])
        by_curl_scale[cs]["both"] += int(m["passed_5pct_gate"] and m["finger_to_palm_contact"])

    summary = {
        "xml": XML_PATH,
        "capsule_radius_m": CAPSULE_RADIUS,
        "penetration_gate_ratio_of_radius": PENETRATION_GATE_RATIO,
        "observation_dims": (
            ["elapsed_time_frac", "handA_qpos_frac", "handB_qpos_frac"]
            + [f"{h}_{fn}_proximity_m" for h in ("handA", "handB") for fn in FINGER_JOINTS]
            + ["handB_lateral_offset_m", "handB_height_offset_m", "obstacle_proximity_m"]
        ),
        "action_dims": (
            ["handA_approach_use_frac", "handB_approach_use_frac"]
            + [f"{h}_{fn}_{j}_use_frac" for h in ("handA", "handB") for fn in FINGER_JOINTS for j in ("mcp", "pip")]
        ),
        "n_episodes": len(combos),
        "n_passed_gate": n_pass,
        "n_finger_to_palm_contact": n_f2p,
        "n_passed_and_f2p": n_both,
        "by_curl_scale": by_curl_scale,
        "elapsed_s": round(time.time() - t0, 2),
        "episodes": manifest,
    }
    with open(MANIFEST_PATH, "w") as fp:
        json.dump(summary, fp, indent=1)

    print(f"\n{n_pass}/{len(combos)} 게이트 통과, {n_f2p}/{len(combos)} 손가락-손바닥 접촉 발생, "
          f"{n_both}/{len(combos)} 둘 다(진짜 성공)")
    print("curl_scale별:")
    for cs, v in sorted(by_curl_scale.items()):
        print(f"  {cs}: 통과 {v['passed']}/{v['n']}  F2P {v['f2p']}/{v['n']}  둘다 {v['both']}/{v['n']}")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
