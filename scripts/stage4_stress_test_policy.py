"""Stage 4 (LeRobot/ACT Phase 2 계획) — Hermes의 검증 게이트를 이 정책에도
그대로 적용한다: "screenshot/loss/5개짜리 데모는 증거 아님, 더 넓은 범위의
실측 재현과 독립 교차검증을 요구."

이 스크립트는 두 축 중 Moojoco가 직접 할 수 있는 절반(더 큰 표본의 실측
재현)을 담당한다. Stage 3(무작위 5개, 전부 통과)은 "루프가 배선되어
동작하는가"만 확인했을 뿐 통계적으로 의미 있는 표본이 아니었다 — 이번엔
50개 무작위 조건(렌더링 없이, 물리+정책 추론만)으로 늘리고, 일부러 학습
그리드 경계 바로 바깥(경계값의 110~130%)까지도 포함해 정책이 경계 밖에서
어떻게 무너지는지도 함께 기록한다. 나머지 절반(다른 에이전트의 독립
재현)은 이 스크립트가 아니라 Aegis에게 별도로 요청한다(§thesis 참고).

## 실행 중 발견 — Stage 3의 "5/5 통과"는 사실 퇴화 해법이었다
`run_stage2_policy_live.py`(Stage 3)는 a_progress/b_progress에 "정책 자신의
직전 예측값"을 그대로 되먹임했다. 이 스크립트의 첫 버전도 물리 qpos로 계산한
"진짜" 진행률을 되먹였다. 둘 다 손목이 시작 위치에서 단 1mm도 움직이지
않는 채로 "침투 0"을 보고했다 — 손가락도 전혀 오므라들지 않았다(악수
자체를 시도하지 않았을 뿐이다). 원인: 학습 데이터의 모든 프레임에서
`observation.state[0:2]`가 바로 그 프레임의 `action[0:2]`와 항상 같은 값이라
(둘 다 같은 시점의 approach_state), 정책이 "obs가 0이면 action도 0"이라는
지름길을 배웠고, obs를 물리·자기예측 어느 쪽으로 되먹이든 0에서 시작하는
루프는 0에 갇혀버렸다. 반대로 정책의 출력과 무관하게 항상 전진하는 경과시간
신호(`sim.ease(t_frac)`, Stage 2 검증에서 쓴 것과 동일)를 쓰면 이 고정점을
벗어나 실제로 접근·파지가 일어난다 — 아래 코드는 이 수정을 반영했다.
"""
import json
import random
import time

import mujoco
import numpy as np
import torch

import generate_procedural_curl_dataset_stage1_75 as sim
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_ENV_STATE, OBS_STATE

CHECKPOINT_DIR = "/home/moos/dev_ws/dual_arms/data/lerobot_stage2_act_policy/checkpoint"
REPORT_PATH = "/home/moos/dev_ws/dual_arms/data/stage4_stress_test_report.json"

N_IN_RANGE = 40
N_BEYOND_RANGE = 10  # 학습 그리드 경계 바로 바깥 — 일부러 실패를 유도해 한계를 기록

random.seed(20260821)


def sample_condition(beyond=False):
    scale = 1.25 if beyond else 1.0
    a_off = random.uniform(-0.01, 0.01) * scale
    b_off = random.uniform(-0.02, 0.02) * scale
    total_s = random.uniform(2.5, 6.0)
    lateral = random.uniform(-0.015, 0.015) * scale
    height = random.uniform(-0.015, 0.015) * scale
    obstacle_y = random.choice([None, None, random.uniform(0.0, 0.06 * scale)])
    return {
        "a_end": round(sim.A_END_BASELINE + a_off, 5),
        "b_end": round(sim.B_END_BASELINE + b_off, 5),
        "total_s": round(total_s, 3),
        "lateral_offset_m": round(lateral, 5),
        "height_offset_m": round(height, 5),
        "obstacle_y_m": None if obstacle_y is None else round(obstacle_y, 5),
        "beyond_trained_range": beyond,
    }


def run_episode(policy, device, cond, model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id):
    a_end, b_end, total_s = cond["a_end"], cond["b_end"], cond["total_s"]
    lateral_offset, height_offset = cond["lateral_offset_m"], cond["height_offset_m"]
    obstacle_y = cond["obstacle_y_m"]
    n_total = int(total_s * sim.FPS)

    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = sim.A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = sim.B_START
    data.mocap_pos[obstacle_mocap_id] = [
        0.0, obstacle_y if obstacle_y is not None else sim.OBSTACLE_PARK_Y, 0.05
    ]
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_lat, kd_lat = 2000.0, 40.0
    kp_finger, kd_finger = 1.2, 0.06

    worst_dist = 0.0
    max_finger_frac = 0.0
    final_a_frac, final_b_frac = 0.0, 0.0

    for f in range(n_total):
        t_frac = f / max(n_total - 1, 1)
        finger_proximity = {}
        for hand in ("handA", "handB"):
            other = "handB" if hand == "handA" else "handA"
            for fn in sim.FINGER_JOINTS:
                g_self = geom_id[(hand, fn)]
                best = sim.SLOW_START_DIST
                for ofn in sim.FINGER_JOINTS:
                    g_other = geom_id[(other, ofn)]
                    d = mujoco.mj_geomDistance(model, data, g_self, g_other, sim.SLOW_START_DIST, None)
                    if d < best:
                        best = d
                d_obs = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, sim.OBSTACLE_SLOW_START, None)
                eq = sim.obstacle_slow_factor(d_obs) * sim.SLOW_START_DIST
                if eq < best:
                    best = eq
                finger_proximity[(hand, fn)] = best

        obstacle_prox = sim.OBSTACLE_PROXIMITY_CLAMP
        for hand in ("handA", "handB"):
            for g_self in hand_geoms[hand]:
                d = mujoco.mj_geomDistance(model, data, g_self, obstacle_geom, sim.OBSTACLE_PROXIMITY_CLAMP, None)
                if d < obstacle_prox:
                    obstacle_prox = d

        # a_progress/b_progress: 실제 물리 위치도, 정책 자신의 이전 예측도
        # 아니라 경과시간 신호 sim.ease(t_frac)을 쓴다 — §스크립트 상단 docstring
        # 참고, 둘 다 시도했으나 모두 obs[0:2]==그 프레임 action[0:2]인 학습
        # 데이터 특성 때문에 "가만히 있기"라는 퇴화 고정점에 갇혔다. 시계 신호는
        # 정책의 출력과 무관하게 항상 전진하므로 그 고정점을 강제로 벗어난다.
        prox_vec = [finger_proximity[(h, fn)] for h in ("handA", "handB") for fn in sim.FINGER_JOINTS]
        obs = [sim.ease(t_frac), sim.ease(t_frac)] + prox_vec + [
            lateral_offset, height_offset, obstacle_prox
        ]
        obs_t = torch.tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
        batch = {OBS_STATE: obs_t, OBS_ENV_STATE: obs_t}

        with torch.no_grad():
            action_chunk = policy.predict_action_chunk(batch)[0, 0].cpu().numpy()
        action_chunk = np.clip(action_chunk, 0.0, 1.0)
        a_frac, b_frac = float(action_chunk[0]), float(action_chunk[1])
        finger_fracs = {
            (h, fn): float(action_chunk[2 + i])
            for i, (h, fn) in enumerate([(h, fn) for h in ("handA", "handB") for fn in sim.FINGER_JOINTS])
        }
        max_finger_frac = max(max_finger_frac, max(finger_fracs.values()))
        final_a_frac, final_b_frac = a_frac, b_frac

        for sub in range(sim.SUBSTEPS):
            for hand, (start, end, frac) in (
                ("handA", (sim.A_START, a_end, a_frac)),
                ("handB", (sim.B_START, b_end, b_frac)),
            ):
                target = start + (end - start) * frac
                jn = f"{hand}_approach"
                q = data.qpos[model.jnt_qposadr[jid[jn]]]
                qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                data.ctrl[aid[f"{jn}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            for side, target in (("handB_lateral", lateral_offset), ("handB_height", height_offset)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_lat * (target - q) - kd_lat * qd, -5, 5))

            for hand in ("handA", "handB"):
                for fn in sim.FINGER_JOINTS:
                    frac = finger_fracs[(hand, fn)]
                    jn = f"{hand}_{fn}_curl"
                    target = sim.CURL_TARGET[fn] * frac
                    q = data.qpos[model.jnt_qposadr[jid[jn]]]
                    qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                    data.ctrl[aid[f"{hand}_{fn}_ctrl"]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))

            mujoco.mj_step(model, data)
            for ci in range(data.ncon):
                d = float(data.contact[ci].dist)
                if d < worst_dist:
                    worst_dist = d

    worst_ratio = abs(worst_dist) / sim.CAPSULE_RADIUS if worst_dist < 0 else 0.0
    return worst_ratio, max_finger_frac, final_a_frac, final_b_frac


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    policy = ACTPolicy.from_pretrained(CHECKPOINT_DIR).to(device)
    policy.eval()
    print(f"loaded policy, device={device}")

    model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id = sim.build_model()

    conditions = [sample_condition(beyond=False) for _ in range(N_IN_RANGE)] + \
                 [sample_condition(beyond=True) for _ in range(N_BEYOND_RANGE)]

    results = []
    t0 = time.time()
    for i, cond in enumerate(conditions):
        worst_ratio, max_finger_frac, final_a_frac, final_b_frac = run_episode(
            policy, device, cond, model, data, jid, aid, geom_id,
            hand_geoms, obstacle_geom, obstacle_mocap_id,
        )
        passed = worst_ratio <= sim.PENETRATION_GATE_RATIO
        # "안전"이 "손을 아예 안 움직였다"는 뜻이 아니어야 진짜 성공이다 —
        # Stage 3에서 이 구분을 안 해서 퇴화 해법을 놓쳤다(§docstring 참고).
        engaged = final_a_frac > 0.5 and final_b_frac > 0.5 and max_finger_frac > 0.3
        results.append({
            **cond,
            "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
            "passed_5pct_gate": passed,
            "max_finger_frac": round(max_finger_frac, 3),
            "final_a_frac": round(final_a_frac, 3),
            "final_b_frac": round(final_b_frac, 3),
            "genuinely_engaged": engaged,
        })
        tag = "BEYOND" if cond["beyond_trained_range"] else "in-range"
        print(f"[{i:3d}][{tag}] worst_ratio={worst_ratio:.4f} final_a/b={final_a_frac:.2f}/{final_b_frac:.2f} "
              f"max_finger={max_finger_frac:.2f} {'PASS' if passed else 'FAIL'} "
              f"{'ENGAGED' if engaged else 'NO-OP!'}", flush=True)

    elapsed = time.time() - t0
    in_range = [r for r in results if not r["beyond_trained_range"]]
    beyond = [r for r in results if r["beyond_trained_range"]]
    n_pass_in_range = sum(1 for r in in_range if r["passed_5pct_gate"])
    n_pass_beyond = sum(1 for r in beyond if r["passed_5pct_gate"])
    n_engaged = sum(1 for r in results if r["genuinely_engaged"])

    report = {
        "checkpoint_dir": CHECKPOINT_DIR,
        "n_in_range": len(in_range),
        "n_passed_in_range": n_pass_in_range,
        "n_beyond_range": len(beyond),
        "n_passed_beyond_range": n_pass_beyond,
        "n_genuinely_engaged": n_engaged,
        "n_total": len(results),
        "elapsed_s": round(elapsed, 2),
        "episodes": results,
    }
    with open(REPORT_PATH, "w") as fp:
        json.dump(report, fp, indent=2)

    print(f"\n학습 범위 내: {n_pass_in_range}/{len(in_range)} 게이트 통과")
    print(f"학습 범위 밖(경계 outside 1.25x): {n_pass_beyond}/{len(beyond)} 게이트 통과")
    print(f"실제로 접근·파지를 시도함(퇴화 no-op 아님): {n_engaged}/{len(results)}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
