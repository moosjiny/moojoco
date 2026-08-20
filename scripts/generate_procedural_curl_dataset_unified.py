"""Stage 1/1.5/1.75을 하나의 스키마로 재통합한다.

지금까지 세 데이터셋(Stage 1: 접근 거리·속도, Stage 1.5: 좌우/상하 오프셋 +
장애물 관찰 추가, Stage 1.75: 장애물 인지형 손목 컨트롤러)은 서로 다른
컨트롤러 코드와 행동 스키마(Stage 1/1.5는 손가락 curl 10차원, Stage 1.75는
손목 2차원을 더한 12차원)로 생성됐다. 사령관 지시("1.75로 통일해서
재생성해줘")로, Stage 1.75의 장애물 인지형 컨트롤러(`generate_procedural_
curl_dataset_stage1_75.py`)를 유일한 컨트롤러로 삼아 Stage 1의 접근
거리·속도 그리드까지 같은 스키마로 재생성한다.

Stage 1의 원래 그리드(장애물 없음, lateral/height=0)에서는 obstacle_slow_
factor가 항상 1.0이 되므로(장애물이 OBSTACLE_PARK_Y=5.0로 멀리 있어 hop이
항상 OBSTACLE_SLOW_START로 클램프됨), approach_state의 점화식
state += (ease(t) - state) * 1.0 = ease(t)가 정확히 성립해 Stage 1의 원래
"장애물 미인지" 손목 궤적과 수학적으로 동일하다 — 즉 이 재생성은 Stage 1의
결과를 바꾸지 않으면서 스키마만 통일하는 작업이다(§실측으로 재확인).

세 서브 스윕을 전부 이 스크립트 하나에서 실행해 단일 디렉터리에 저장한다:
  - stage1_approach   (45 에피소드, Stage 1과 동일한 그리드)
  - A_lateral_height  (25 에피소드, Stage 1.5/1.75와 동일)
  - B_obstacle        (6 에피소드, Stage 1.5/1.75와 동일)
"""
import itertools
import json
import os
import time

import generate_procedural_curl_dataset_stage1_75 as core

OUT_DIR = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset_unified"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

PENETRATION_GATE_RATIO = core.PENETRATION_GATE_RATIO

# Stage 1과 동일한 그리드(§generate_procedural_curl_dataset.py)
A_END_OFFSETS = [-0.01, 0.0, 0.01]
B_END_OFFSETS = [-0.02, -0.01, 0.0, 0.01, 0.02]
TOTAL_S_VALUES = [2.5, 4.0, 6.0]


def run_sweep(model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
              manifest, ep_idx_start):
    ep_idx = ep_idx_start

    # --- Stage 1 그리드: 접근 거리·속도, 장애물 없음, 오프셋 없음 ---
    for a_off, b_off, total_s in itertools.product(A_END_OFFSETS, B_END_OFFSETS, TOTAL_S_VALUES):
        a_end = core.A_END_BASELINE + a_off
        b_end = core.B_END_BASELINE + b_off
        rows, worst_ratio, final_approach = core.run_episode(
            model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lateral_offset=0.0, height_offset=0.0, obstacle_y=None,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = core.save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "stage1_approach",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": 0.0, "height_offset_m": 0.0, "obstacle_y_m": None,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "final_approach_frac": {k: round(v, 4) for k, v in final_approach.items()},
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[stage1][{ep_idx}] a_off={a_off:+.3f} b_off={b_off:+.3f} total_s={total_s} "
              f"-> worst_ratio={worst_ratio:.4f} {'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    # --- 서브 스윕 A: lateral/height 오프셋 ---
    a_end = core.A_END_BASELINE
    b_end = core.B_END_BASELINE
    total_s = 4.0
    LATERAL_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]
    HEIGHT_OFFSETS = [-0.015, -0.0075, 0.0, 0.0075, 0.015]
    for lat, hei in itertools.product(LATERAL_OFFSETS, HEIGHT_OFFSETS):
        rows, worst_ratio, final_approach = core.run_episode(
            model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lat, hei, obstacle_y=None,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = core.save_episode(ep_idx, rows, OUT_DIR)
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

    # --- 서브 스윕 B: 장애물 ---
    a_end = core.A_END_BASELINE
    b_end = core.B_END_BASELINE - 0.01
    total_s = 4.0
    OBSTACLE_Y_VALUES = [None, 0.06, 0.045, 0.03, 0.015, 0.0]
    for obs_y in OBSTACLE_Y_VALUES:
        rows, worst_ratio, final_approach = core.run_episode(
            model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
            a_end, b_end, total_s, lateral_offset=0.0, height_offset=0.0, obstacle_y=obs_y,
        )
        passed = worst_ratio <= PENETRATION_GATE_RATIO
        path = core.save_episode(ep_idx, rows, OUT_DIR)
        manifest.append({
            "episode_index": ep_idx, "sub_sweep": "B_obstacle",
            "a_end": round(a_end, 4), "b_end": round(b_end, 4), "total_s": total_s,
            "lateral_offset_m": 0.0, "height_offset_m": 0.0, "obstacle_y_m": obs_y,
            "n_frames": len(rows), "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "final_approach_frac": {k: round(v, 4) for k, v in final_approach.items()},
            "passed_5pct_gate": passed, "path": path,
        })
        print(f"[B][{ep_idx}] obstacle_y={obs_y} -> worst_ratio={worst_ratio:.4f} "
              f"{'PASS' if passed else 'FAIL'}", flush=True)
        ep_idx += 1

    return ep_idx


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id = core.build_model()

    manifest = []
    t0 = time.time()
    n_total = run_sweep(model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id,
                         manifest, ep_idx_start=0)

    n_pass = sum(1 for m in manifest if m["passed_5pct_gate"])
    by_sweep = {}
    for m in manifest:
        s = m["sub_sweep"]
        by_sweep.setdefault(s, {"n": 0, "passed": 0})
        by_sweep[s]["n"] += 1
        by_sweep[s]["passed"] += int(m["passed_5pct_gate"])

    summary = {
        "xml": core.XML_PATH,
        "obstacle_slow_start_m": core.OBSTACLE_SLOW_START,
        "obstacle_hard_stop_margin_m": core.HARD_STOP_MARGIN,
        "capsule_radius_m": core.CAPSULE_RADIUS,
        "penetration_gate_ratio_of_radius": PENETRATION_GATE_RATIO,
        "observation_dims": (
            ["a_progress", "b_progress"]
            + [f"{h}_{fn}_proximity_m" for h in ("handA", "handB") for fn in core.FINGER_JOINTS]
            + ["handB_lateral_offset_m", "handB_height_offset_m", "obstacle_proximity_m"]
        ),
        "action_dims": (
            ["handA_approach_use_frac", "handB_approach_use_frac"]
            + [f"{h}_{fn}_use_frac" for h in ("handA", "handB") for fn in core.FINGER_JOINTS]
        ),
        "n_episodes": n_total,
        "n_passed_gate": n_pass,
        "n_failed_gate": n_total - n_pass,
        "by_sub_sweep": by_sweep,
        "elapsed_s": round(time.time() - t0, 2),
        "episodes": manifest,
    }
    with open(MANIFEST_PATH, "w") as fp:
        json.dump(summary, fp, indent=1)

    print(f"\n{n_pass}/{n_total} 에피소드가 5% 침투 게이트 통과 (통합 데이터셋)")
    for s, v in by_sweep.items():
        print(f"  {s}: {v['passed']}/{v['n']}")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
