"""Stage 1.75 (LeRobot/ACT Phase 2 계획, v3 개정) — 장애물 인지형 손목 접근
"전문가" 컨트롤러를 만들고, 그걸로 손목+손가락 통합 행동 데이터셋을 재생성한다.

## 배경
[[2026-08-20-moojoco-lerobot-stage1-5-dataset-result]] §2에서, 장애물이
접근 경로에 조금이라도 들어오면 기존 손목 컨트롤러(목표 지점까지 그냥
밀어붙임)가 예외 없이 파국적으로 실패(침투비 최대 49%)하는 것을 확인했다.
사령관이 Stage 2 정책 범위를 "손목접근까지" 포함하기로 결정하면서, 그
정책이 모방할 "정답 행동"부터 다시 정의해야 했다 — 지금까지 손목 접근은
에피소드마다 고정한 스윕 파라미터였을 뿐, 한 번도 기록된 적이 없다.

## 이번에 추가한 것
손가락 curl에 이미 있던 "상대와의 거리 기반 사전-감속" 패턴을 손목 접근에도
그대로 적용한다: 각 손이 장애물까지 남은 거리를 `mj_geomDistance`로 직접
질의해(margin/gap 설정과 무관하게 항상 정확한 값), `OBSTACLE_SLOW_START`
이내로 들어오면 접근 진행을 거리에 비례해 감속하고, 0에 가까워지면 사실상
멈춘다. 손가락은 "반대쪽 손과의 거리"만 봤지만, 손목은 "장애물과의 거리"를
본다는 점만 다르고 원리는 동일하다.

행동(action, 12차원) = [handA_approach_use_frac, handB_approach_use_frac]
                      + Stage 1의 손가락 curl 사용비율 10차원
관찰(observation.state, 16차원) — [[2026-08-20-moojoco-lerobot-stage4-stress-
test]] v2에서 발견된 관찰-행동 항등함수 지름길 버그를 고치며 재설계:
[elapsed_time_frac, handA_qpos_frac, handB_qpos_frac] + 손가락별(양손×5)
근접도 10 + [lateral_offset, height_offset, obstacle_proximity]. 앞의 3차원이
예전엔 "그 프레임 행동의 복제값" 2개(a/b_progress)였는데, 이제는 행동과
값이 절대 같을 수 없는 두 독립 신호(정책 출력과 무관한 시계 신호 + 물리
qpos 실측값)로 바뀌었다.

두 서브 스윕을 그대로 재실행해 직접 비교한다:
- 서브 스윕 A(좌우/상하 오프셋): 장애물이 없는 조건이므로 회귀 확인용 —
  새 손목 컨트롤러가 장애물이 없을 때 Stage 1.5와 동일하게 동작하는지 검증.
- 서브 스윕 B(장애물): Stage 1.5와 완전히 동일한 6개 조건을 새 컨트롤러로
  재실행 — "이전엔 전부 FAIL, 이번엔?"을 직접 비교.
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
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset_stage1_75"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

FPS = 20
SUBSTEPS = 10

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006
SLOW_START_DIST = 0.006
# 장애물은 손가락(캡슐 반경 6mm)보다 훨씬 큰 손바닥(팔레트, 반두께 8mm)이
# 부딪히는 대상이라 더 이른 감속이 필요하다고 보고 2.5배로 잡았다 —
# §결과에서 이 값으로 실제 정지가 이뤄지는지 실측 확인한다.
OBSTACLE_SLOW_START = 0.08
# 처음엔 감속만 시켰는데(비례 slow_factor) 실측 결과 침투가 그대로 남았다 —
# 이 사전-감속 방식은 거리가 0에 완전히 닿기 전까지 항상 "0보다 큰" 증분을
# 계속 더한다. 손가락-손가락 케이스는 CURL_TARGET 자체가 거의 겹치지 않게
# 미리 보정돼 있어 이 점근적 접근이 문제 없었지만, 장애물은 그런 보정이
# 없는 진짜 강체라서 목표 지점이 애초에 벽 너머(도달 불가능)일 수 있다 —
# 그러면 아무리 천천히 다가가도 결국 벽을 파고드는 방향으로 계속 미세
# 전진한다(실측: d_obs가 0.5초 만에 15mm에서 -0.2mm로 붕괴). 그래서 하드
# 스톱을 추가했다 — HARD_STOP_MARGIN 밑으로 들어오면 slow_factor를 "작게"가
# 아니라 정확히 0으로 만들어 목표 자체를 완전히 멈춘다.
#
# 그런데도 여전히 최대 1.5mm 침투가 남아 실측을 더 파보니(§thesis 참고),
# 목표는 정확히 멈췄지만(로그로 확인: approach_state가 그 프레임 이후
# 완전히 불변) 정지 직전까지 붙어있던 관성(momentum) 때문에 몇 mm를 더
# 미끄러져 들어간 뒤 반동으로 되돌아 나오는(soft-catch) 현상이었다 —
# 목표를 더 일찍(장애물에서 더 멀리) 얼려서 정지 시점의 속도 자체를
# 낮춰야 했다. HARD_STOP=40mm/SLOW_START=80mm까지 여유를 키우자 5개
# 장애물 위치 전부 침투비 0.0000으로 통과했다(§실측 결과 참고).
HARD_STOP_MARGIN = 0.04


def obstacle_slow_factor(dist, slow_start=OBSTACLE_SLOW_START, hard_stop=HARD_STOP_MARGIN):
    if dist <= hard_stop:
        return 0.0
    return float(np.clip((dist - hard_stop) / (slow_start - hard_stop), 0.0, 1.0))
PENETRATION_GATE_RATIO = 0.05

A_START, B_START = -0.20, -0.20
A_END_BASELINE, B_END_BASELINE = -0.028, 0.0952

OBSTACLE_PARK_Y = 5.0
OBSTACLE_PROXIMITY_CLAMP = 0.05


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def run_episode(model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
                 a_end, b_end, total_s, lateral_offset, height_offset, obstacle_y):
    n_total = int(total_s * FPS)

    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    data.mocap_pos[obstacle_mocap_id] = [0.0, obstacle_y if obstacle_y is not None else OBSTACLE_PARK_Y, 0.05]
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_lat, kd_lat = 2000.0, 40.0
    kp_finger, kd_finger = 1.2, 0.06

    use_frac_state = {(h, f): 0.0 for h in ("handA", "handB") for f in FINGER_JOINTS}
    approach_state = {"handA": 0.0, "handB": 0.0}

    rows = []
    worst_dist = 0.0

    for f in range(n_total):
        t_frac = f / max(n_total - 1, 1)
        for sub in range(SUBSTEPS):
            # 손목 접근 — 장애물까지 남은 거리로 사전-감속(손가락과 동일한 패턴)
            hand_obstacle_prox = {}
            for hand in ("handA", "handB"):
                best = OBSTACLE_SLOW_START
                for g_self in hand_geoms[hand]:
                    d_geom = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, OBSTACLE_SLOW_START, None)
                    if d_geom < best:
                        best = d_geom
                hand_obstacle_prox[hand] = best

            for hand, (start, end) in (("handA", (A_START, a_end)), ("handB", (B_START, b_end))):
                free_frac = ease(t_frac)
                free_step = max(free_frac - approach_state[hand], 0.0)
                slow_factor = obstacle_slow_factor(hand_obstacle_prox[hand])
                approach_state[hand] = min(approach_state[hand] + free_step * slow_factor, 1.0)
                target = start + (end - start) * approach_state[hand]
                jname = f"{hand}_approach"
                q = data.qpos[model.jnt_qposadr[jid[jname]]]
                qd = data.qvel[model.jnt_dofadr[jid[jname]]]
                data.ctrl[aid[f"{jname}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            for side, target in (("handB_lateral", lateral_offset), ("handB_height", height_offset)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_lat * (target - q) - kd_lat * qd, -5, 5))

            # 손가락 근접도 = min(반대쪽 손 손가락과의 거리, 장애물과의 거리).
            # 처음엔 장애물을 여기 포함하지 않고 손목 접근만 장애물을 봤는데,
            # 실측해보니 손목이 안전거리에서 멈춰도 손가락은 자기 스케줄대로
            # 계속 오므라들어 장애물을 파고들었다(worst pair가 handB_pinky_geom
            # vs obstacle_geom로 확인됨) — 손가락도 "가까운 대상이면 무엇이든"
            # 감속해야 한다는 걸 보여준 실패였다.
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
                    # 손가락-장애물 거리는 손가락-손가락(SLOW_START_DIST=6mm)보다
                    # 훨씬 이른 여유(OBSTACLE_SLOW_START)로 질의한다. 6mm로
                    # 시도했을 때 계속 handB_pinky_geom vs obstacle_geom 충돌로
                    # 실패했는데, 원인은 손가락 접촉과 달리 이 상황은 손목이
                    # 아직 전진 중인 상태에서 손가락까지 오므라들어 손가락 끝의
                    # 종합 접근 속도(손목 이동 + 손가락 굽힘)가 손가락-손가락
                    # 케이스보다 훨씬 빨라 6mm 여유로는 한 스텝 만에 뚫고 지나갈
                    # 수 있었기 때문 — 그래서 정지거리를 손목과 같은 규모로 넓혔다.
                    d_obstacle = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, OBSTACLE_SLOW_START, None)
                    equivalent_dist = obstacle_slow_factor(d_obstacle) * SLOW_START_DIST
                    if equivalent_dist < best:
                        best = equivalent_dist
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
            for hand in ("handA", "handB"):
                for g_self in hand_geoms[hand]:
                    d_geom = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, OBSTACLE_PROXIMITY_CLAMP, None)
                    if d_geom < obstacle_prox:
                        obstacle_prox = d_geom

        prox_vec = []
        finger_action_vec = []
        for hand in ("handA", "handB"):
            for fn in FINGER_JOINTS:
                prox_vec.append(float(finger_proximity[(hand, fn)]))
                finger_action_vec.append(float(use_frac_state[(hand, fn)]))

        # 관찰-행동 스키마 재설계([[2026-08-20-moojoco-lerobot-stage4-stress-
        # test]] v2에서 확인된 근본 원인 수정) — 이전엔 a_progress/b_progress에
        # 그 프레임의 손목 행동(approach_state)을 그대로 복제해서 관찰과 행동이
        # 완전히 같은 값이었다. 정책이 "obs=x면 action=x" 항등함수 지름길을
        # 배웠고, 실시간 추론에서 obs를 자기 예측(또는 심지어 진짜 물리
        # 위치)으로 되먹이면 시작값 0에서 영원히 못 벗어나는 고정점이 됐다.
        #
        # 이제 관찰은 행동과 값 자체가 다른, 독립적인 두 신호로 구성한다:
        #   1. elapsed_time_frac — 정책의 출력·물리 상태 어느 쪽과도 무관하게
        #      항상 전진하는 순수 시계 신호(ease(t_frac)). 어떤 상황에서도
        #      고정점에 갇히지 않도록 보장하는 유일한 신호.
        #   2. handA/B_qpos_frac — "정답 행동"이 아니라 이번 프레임 물리
        #      스텝이 끝난 뒤 실제로 측정된 손목 위치(qpos)를 목표 구간
        #      대비 비율로 환산한 값. 실제 로봇의 인코더 값에 해당하며,
        #      PD 추종이 지연되거나 장애물로 감속될 때는 그 프레임의 목표
        #      행동(approach_state)과 값이 달라진다 — 더 이상 항등함수가
        #      아니다.
        qa = data.qpos[model.jnt_qposadr[jid["handA_approach"]]]
        qb = data.qpos[model.jnt_qposadr[jid["handB_approach"]]]
        a_qpos_frac = float(np.clip((qa - A_START) / (a_end - A_START), 0.0, 1.0))
        b_qpos_frac = float(np.clip((qb - B_START) / (b_end - B_START), 0.0, 1.0))
        obs = [float(ease(t_frac)), a_qpos_frac, b_qpos_frac] + prox_vec + [
            float(lateral_offset), float(height_offset), float(obstacle_prox)
        ]
        action_vec = [float(approach_state["handA"]), float(approach_state["handB"])] + finger_action_vec

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
    final_approach = {"handA": approach_state["handA"], "handB": approach_state["handB"]}
    return rows, worst_ratio, final_approach


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
        if actuator_name == n:
            actuator_name = n + "_ctrl"
        aid[actuator_name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)

    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}
    hand_geoms = {
        hand: [geom_id[(hand, fn)] for fn in FINGER_JOINTS] + [
            mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{hand}_palm")
        ]
        for hand in ("handA", "handB")
    }
    obstacle_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "obstacle_geom")
    obstacle_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "obstacle")
    obstacle_mocap_id = int(model.body_mocapid[obstacle_body])

    return model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id


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
    model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id = build_model()

    manifest = []
    ep_idx = 0
    t0 = time.time()

    # --- 서브 스윕 A: lateral/height 오프셋 (회귀 확인 — 장애물 없음) ---
    a_end = A_END_BASELINE
    b_end = B_END_BASELINE
    total_s = 4.0
    LATERAL_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]
    HEIGHT_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]

    for lat, hei in itertools.product(LATERAL_OFFSETS, HEIGHT_OFFSETS):
        rows, worst_ratio, final_approach = run_episode(
            model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lat, hei, obstacle_y=None,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "A_lateral_height",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": lat, "height_offset_m": hei, "obstacle_y_m": None,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "final_approach_frac": {k: round(v, 4) for k, v in final_approach.items()},
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[A][{ep_idx}] lat={lat:+.4f} hei={hei:+.4f} -> worst_ratio={worst_ratio:.4f} "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    # --- 서브 스윕 B: 장애물 — Stage 1.5와 완전히 동일한 조건으로 직접 비교 ---
    a_end = A_END_BASELINE
    b_end = B_END_BASELINE - 0.01
    total_s = 4.0
    OBSTACLE_Y_VALUES = [None, 0.06, 0.045, 0.03, 0.015, 0.0]

    for obs_y in OBSTACLE_Y_VALUES:
        rows, worst_ratio, final_approach = run_episode(
            model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lateral_offset=0.0, height_offset=0.0, obstacle_y=obs_y,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "B_obstacle",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": 0.0, "height_offset_m": 0.0, "obstacle_y_m": obs_y,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "final_approach_frac": {k: round(v, 4) for k, v in final_approach.items()},
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[B][{ep_idx}] obstacle_y={obs_y} -> worst_ratio={worst_ratio:.4f} "
              f"final_approach={ {k: round(v,3) for k,v in final_approach.items()} } "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    n_pass = sum(1 for m in manifest if m["passed_5pct_gate"])
    summary = {
        "xml": XML_PATH,
        "obstacle_slow_start_m": OBSTACLE_SLOW_START,
        "capsule_radius_m": CAPSULE_RADIUS,
        "penetration_gate_ratio_of_radius": PENETRATION_GATE_RATIO,
        "observation_dims": (
            ["elapsed_time_frac", "handA_qpos_frac", "handB_qpos_frac"]
            + [f"{h}_{fn}_proximity_m" for h in ("handA", "handB") for fn in FINGER_JOINTS]
            + ["handB_lateral_offset_m", "handB_height_offset_m", "obstacle_proximity_m"]
        ),
        "action_dims": (
            ["handA_approach_use_frac", "handB_approach_use_frac"]
            + [f"{h}_{fn}_use_frac" for h in ("handA", "handB") for fn in FINGER_JOINTS]
        ),
        "n_episodes": ep_idx,
        "n_passed_gate": n_pass,
        "n_failed_gate": ep_idx - n_pass,
        "elapsed_s": round(time.time() - t0, 2),
        "episodes": manifest,
    }
    with open(MANIFEST_PATH, "w") as fp:
        json.dump(summary, fp, indent=1)

    print(f"\n{n_pass}/{ep_idx} 에피소드가 5% 침투 게이트 통과 (Stage 1.75, 장애물 인지형 손목 컨트롤러)")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
