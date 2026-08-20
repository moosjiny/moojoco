"""Stage 3 (LeRobot/ACT Phase 2 계획) — 학습된 ACT 정책을 실시간 추론기로
연결해 MuJoCo 물리를 직접 구동한다.

지금까지(Stage 1~2)는 정책이 예측한 행동으로 사전에 정해둔 매니페스트
에피소드를 재생했을 뿐이다. 이번엔 **한 번도 학습에 쓴 적 없는 무작위
조건**(접근 깊이·속도·좌우/상하 오프셋·장애물 위치를 매번 새로 뽑음)에서
매 제어 프레임마다 정책을 실시간으로 호출해 손목·손가락을 구동하고, 그
결과를 GIF로 렌더링하면서 `contact.dist`를 재측정한다 — "정적 데이터셋
재생"에서 "실시간 추론 루프"로의 전환이 이번 단계의 핵심이다.

성공 기준은 지금까지와 동일: 침투량이 캡슐 반경의 5% 이내(Hermes 검증
게이트). GIF는 참고용 시각자료일 뿐, 판정은 항상 `contact.dist` 실측으로
한다.

## v2 정정 — 최초 버전의 "5/5 통과"는 퇴화 해법이었다
최초 버전은 a/b_progress 관찰에 "정책이 직전 프레임에 낸 예측"을 그대로
되먹였다. 그 결과 손목이 시작 위치에서 전혀 움직이지 않고 손가락도 전혀
오므라들지 않는(악수 자체를 시도하지 않는) 채로 "침투 0"을 보고했다 —
Stage 4 스트레스 테스트(`stage4_stress_test_policy.py`)에서 발견했다.
학습 데이터의 모든 프레임에서 `observation.state[0:2]`가 그 프레임의
`action[0:2]`와 항상 같은 값이라, 정책이 "obs=0이면 action=0"이라는 지름길을
배웠기 때문이다. 이 버전은 그 자리에 경과시간 신호(`sim.ease(t_frac)`)를
넣어 그 고정점을 강제로 벗어나게 고쳤다. 상세: [[2026-08-20-moojoco-lerobot-
stage3-live-integration]] v2.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json
import random
import time

import mujoco
import numpy as np
import torch
from PIL import Image

import generate_procedural_curl_dataset_stage1_75 as sim
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import OBS_ENV_STATE, OBS_STATE

CHECKPOINT_DIR = "/home/moos/dev_ws/dual_arms/data/lerobot_stage2_act_policy/checkpoint"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/stage3_live_policy_runs"
GIF_PATH = "/home/moos/dev_ws/images/moojoco-stage3-act-policy-live-2026-08-20.gif"
REPORT_PATH = os.path.join(OUT_DIR, "live_run_report.json")

RENDER_SIZE = 480
FPS = sim.FPS
N_LIVE_EPISODES = 5

random.seed(20260820)


def sample_condition():
    """학습 그리드 범위 안에서 무작위 추출 — 정확히 매니페스트에 있던 값이
    아니라 그 범위 안의 임의 실수를 뽑아, "본 적 없는 조건"을 보장한다."""
    a_off = random.uniform(-0.01, 0.01)
    b_off = random.uniform(-0.02, 0.02)
    total_s = random.uniform(2.5, 6.0)
    lateral = random.uniform(-0.015, 0.015)
    height = random.uniform(-0.015, 0.015)
    obstacle_y = random.choice([None, None, random.uniform(0.0, 0.06)])
    return {
        "a_end": round(sim.A_END_BASELINE + a_off, 5),
        "b_end": round(sim.B_END_BASELINE + b_off, 5),
        "total_s": round(total_s, 3),
        "lateral_offset_m": round(lateral, 5),
        "height_offset_m": round(height, 5),
        "obstacle_y_m": None if obstacle_y is None else round(obstacle_y, 5),
    }


def load_policy(device):
    policy = ACTPolicy.from_pretrained(CHECKPOINT_DIR)
    policy.to(device)
    policy.eval()
    return policy


def run_live_episode(policy, device, cond, renderer, cam, model, data, jid, aid, geom_id,
                      hand_geoms, obstacle_geom, obstacle_mocap_id):
    a_end, b_end, total_s = cond["a_end"], cond["b_end"], cond["total_s"]
    lateral_offset, height_offset = cond["lateral_offset_m"], cond["height_offset_m"]
    obstacle_y = cond["obstacle_y_m"]
    n_total = int(total_s * FPS)

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
    frames = []

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

        # 실시간 추론 — 매 프레임 현재 물리 상태를 관찰로 조립해 정책에 넣는다.
        # ⚠️ 처음엔 여기에 "정책이 직전 프레임에 낸 예측 자체"를 a/b_progress로
        # 되먹였는데, 그러면 손이 시작 위치에서 단 1mm도 안 움직이는 채로
        # "침투 0"을 내는 퇴화 해법에 빠진다는 걸 Stage 4 스트레스 테스트에서
        # 발견했다([[2026-08-20-moojoco-lerobot-stage3-live-integration]] v2
        # 정정 참고) — 학습 데이터의 모든 프레임에서 observation.state[0:2]가
        # 그 프레임의 action[0:2]와 항상 같아서, 정책이 "obs=0이면 action=0"
        # 이라는 지름길을 배웠고, obs를 0에서 시작해 자기예측으로 되먹이면 그
        # 고정점에 영원히 갇힌다. 정책의 출력과 무관하게 항상 전진하는 경과
        # 시간 신호(sim.ease(t_frac), Stage 2 검증과 동일)로 바꿔 이 고정점을
        # 강제로 벗어나게 했다.
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

        renderer.update_scene(data, camera=cam)
        frames.append(Image.fromarray(renderer.render()))

    worst_ratio = abs(worst_dist) / sim.CAPSULE_RADIUS if worst_dist < 0 else 0.0
    return worst_ratio, frames


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    policy = load_policy(device)
    print(f"loaded policy from {CHECKPOINT_DIR}, device={device}")

    model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id = sim.build_model()
    model.vis.global_.offwidth = RENDER_SIZE
    model.vis.global_.offheight = RENDER_SIZE
    renderer = mujoco.Renderer(model, height=RENDER_SIZE, width=RENDER_SIZE)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = -55, -18, 0.28
    cam.lookat[:] = [0.0, 0.0, 0.06]

    all_frames = []
    results = []
    t0 = time.time()
    for i in range(N_LIVE_EPISODES):
        cond = sample_condition()
        worst_ratio, frames = run_live_episode(
            policy, device, cond, renderer, cam, model, data, jid, aid, geom_id,
            hand_geoms, obstacle_geom, obstacle_mocap_id,
        )
        passed = worst_ratio <= sim.PENETRATION_GATE_RATIO
        results.append({**cond, "worst_penetration_ratio_of_radius": round(worst_ratio, 4), "passed_5pct_gate": passed})
        print(f"[live {i}] {cond} -> worst_ratio={worst_ratio:.4f} {'PASS' if passed else 'FAIL'}", flush=True)
        all_frames.extend(frames)
        # 에피소드 사이에 정지 프레임 몇 장을 넣어 GIF에서 경계가 보이게 한다
        all_frames.extend([frames[-1]] * 3)

    renderer.close()
    elapsed = time.time() - t0

    all_frames[0].save(GIF_PATH, save_all=True, append_images=all_frames[1:],
                        duration=int(1000 / FPS), loop=0, optimize=True)

    n_pass = sum(1 for r in results if r["passed_5pct_gate"])
    report = {
        "checkpoint_dir": CHECKPOINT_DIR,
        "n_live_episodes": N_LIVE_EPISODES,
        "n_passed_gate": n_pass,
        "elapsed_s": round(elapsed, 2),
        "gif_path": GIF_PATH,
        "gif_n_frames": len(all_frames),
        "episodes": results,
    }
    with open(REPORT_PATH, "w") as fp:
        json.dump(report, fp, indent=2)

    print(f"\n실시간 정책 구동: {n_pass}/{N_LIVE_EPISODES} 5% 게이트 통과")
    print(f"GIF: {GIF_PATH} ({len(all_frames)} 프레임)")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
