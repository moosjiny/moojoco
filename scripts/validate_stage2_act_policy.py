"""Stage 2 검증 — 홀드아웃 에피소드 + 폐루프 시뮬레이터 재실행.

지난 학습(`train_stage2_act_policy.py`)은 게이트 통과 48개 에피소드 **전부**로
학습했다 — 그 결과의 loss 하락은 정책이 "봤던" 궤적을 얼마나 잘 재현하는지만
보여줄 뿐, 처음 보는 조건에서도 안전한지는 전혀 증명하지 않는다. 이번
검증에서는:

1. 48개 중 20%(11개, 세 서브 스윕에서 층화 추출)를 학습에서 완전히 제외하고
   나머지 37개로만 재학습한다.
2. 홀드아웃 11개에 대해 (a) 오프라인 L1 행동 예측 오차, (b) **폐루프 시뮬레이터
   재실행** — 학습된 정책이 예측한 행동으로 실제 MuJoCo 물리를 다시 돌려
   `contact.dist`를 재측정 — 두 가지를 모두 확인한다. (b)가 진짜 검증이다:
   Hermes의 검증 게이트("screenshot/L1 loss는 증거 아님, 실측 재현 요구")를
   그대로 이 정책에도 적용하는 것.

폐루프 실행에서는 매 제어 프레임마다 현재 관찰(15차원)을 정책에 넣어 행동
청크를 예측하고, 첫 스텝의 예측값을 그 프레임의 목표 use_frac으로 그대로
사용한다(전문가 데이터 생성 스크립트의 손수 설계한 감속 공식을 정책 예측으로
완전히 대체) — 그 값으로 기존과 동일한 PD 제어를 적용해 물리를 진행시킨다.

## 알려진 데이터 설계 결함(검증 중 발견, 정직하게 기록)
학습 데이터의 `a_progress`/`b_progress` 두 관찰 차원은 실제로는 손의 진행률이
아니라 **단순 시간 신호** `ease(t_frac)`을 양쪽에 그대로 복제한 값이다(원본
`generate_procedural_curl_dataset_stage1_75.py`의 버그) — 장애물 감속이
걸려 실제 `approach_state`가 시간 신호보다 뒤처질 때조차 정책은 "시간이 얼마나
지났는지"만 보고 "손이 실제로 얼마나 왔는지"는 보지 못한다. 이번 폐루프
평가에서는 학습 분포와 일치시키기 위해 추론 때도 동일하게 `ease(t_frac)`을
넣는다 — 즉 이 결함을 감춘 채로 정합성만 맞춘 것이며, 결과 해석 시 감안해야
한다(§결과 참고).
"""
import json
import os
import time

import mujoco
import numpy as np
import pyarrow.parquet as pq
import torch
from torch.utils.data import DataLoader, Dataset

import generate_procedural_curl_dataset_stage1_75 as sim
from lerobot.configs.types import FeatureType, PolicyFeature
from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import ACTION, OBS_ENV_STATE, OBS_STATE

MANIFEST_PATH = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset_unified/manifest.json"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/lerobot_stage2_act_policy_holdout"
REPORT_PATH = "/home/moos/dev_ws/dual_arms/data/lerobot_stage2_act_policy_holdout/validation_report.json"

OBS_DIM = 16
ACTION_DIM = 12
CHUNK_SIZE = 20
BATCH_SIZE = 64
N_EPOCHS = 150
LR = 1e-4
HOLDOUT_STRIDE = 5  # sub_sweep 내에서 5개마다 1개를 홀드아웃(층화 추출)


class ChunkDataset(Dataset):
    def __init__(self, episodes, chunk_size):
        self.samples = []
        for ep in episodes:
            table = pq.read_table(ep["path"])
            obs = np.array(table.column("observation.state").to_pylist(), dtype=np.float32)
            act = np.array(table.column("action").to_pylist(), dtype=np.float32)
            n = obs.shape[0]
            for t in range(n):
                end = min(t + chunk_size, n)
                chunk = act[t:end].copy()
                pad_len = chunk_size - chunk.shape[0]
                is_pad = np.zeros(chunk_size, dtype=bool)
                if pad_len > 0:
                    last = chunk[-1:]
                    chunk = np.concatenate([chunk, np.repeat(last, pad_len, axis=0)], axis=0)
                    is_pad[chunk_size - pad_len:] = True
                self.samples.append((obs[t], chunk, is_pad))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        obs, chunk, is_pad = self.samples[idx]
        obs_t = torch.from_numpy(obs)
        return {
            OBS_STATE: obs_t,
            OBS_ENV_STATE: obs_t,
            ACTION: torch.from_numpy(chunk),
            "action_is_pad": torch.from_numpy(is_pad),
        }


def build_policy(device):
    config = ACTConfig(
        n_obs_steps=1,
        chunk_size=CHUNK_SIZE,
        n_action_steps=CHUNK_SIZE,
        input_features={
            OBS_STATE: PolicyFeature(FeatureType.STATE, (OBS_DIM,)),
            OBS_ENV_STATE: PolicyFeature(FeatureType.ENV, (OBS_DIM,)),
        },
        output_features={ACTION: PolicyFeature(FeatureType.ACTION, (ACTION_DIM,))},
        dim_model=256, n_heads=8, dim_feedforward=1024,
        n_encoder_layers=2, n_decoder_layers=1,
        use_vae=True, latent_dim=16, n_vae_encoder_layers=2,
        dropout=0.1, kl_weight=10.0,
        device=device, push_to_hub=False,
    )
    return ACTPolicy(config).to(device)


def split_holdout(manifest):
    passed = [e for e in manifest["episodes"] if e["passed_5pct_gate"]]
    by_sweep = {}
    for e in passed:
        by_sweep.setdefault(e["sub_sweep"], []).append(e)

    holdout, train = [], []
    for sweep, eps in by_sweep.items():
        eps_sorted = sorted(eps, key=lambda e: e["episode_index"])
        for i, e in enumerate(eps_sorted):
            (holdout if i % HOLDOUT_STRIDE == 0 else train).append(e)
    return train, holdout


def offline_l1_error(policy, holdout_eps, device):
    ds = ChunkDataset(holdout_eps, CHUNK_SIZE)
    loader = DataLoader(ds, batch_size=128, shuffle=False)
    policy.eval()
    total_err, total_n = 0.0, 0
    with torch.no_grad():
        for batch in loader:
            batch_dev = {k: v.to(device) for k, v in batch.items()}
            actions_hat = policy.predict_action_chunk(batch_dev)
            err = (actions_hat - batch_dev[ACTION]).abs()
            mask = ~batch_dev["action_is_pad"].unsqueeze(-1)
            total_err += (err * mask).sum().item()
            total_n += mask.sum().item()
    policy.train()
    return total_err / total_n


def closed_loop_rollout(policy, device, ep):
    model, data, jid, aid, geom_id, hand_geoms, obstacle_geom, obstacle_mocap_id = sim.build_model()

    a_end, b_end, total_s = ep["a_end"], ep["b_end"], ep["total_s"]
    lateral_offset, height_offset = ep["lateral_offset_m"], ep["height_offset_m"]
    obstacle_y = ep["obstacle_y_m"]
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
    policy.eval()

    for f in range(n_total):
        t_frac = f / max(n_total - 1, 1)

        # 관찰 조립 — 학습 데이터와 동일한 스키마(및 동일한 a/b_progress 결함)
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

        # [[2026-08-20-moojoco-lerobot-schema-redesign]] 반영 — a/b_progress
        # 자리에 시계 신호 하나 + 실측 qpos 비율 두 개(총 3차원)를 넣는다.
        qa = data.qpos[model.jnt_qposadr[jid["handA_approach"]]]
        qb = data.qpos[model.jnt_qposadr[jid["handB_approach"]]]
        a_qpos_frac = float(np.clip((qa - sim.A_START) / (a_end - sim.A_START), 0.0, 1.0))
        b_qpos_frac = float(np.clip((qb - sim.B_START) / (b_end - sim.B_START), 0.0, 1.0))
        prox_vec = [finger_proximity[(h, fn)] for h in ("handA", "handB") for fn in sim.FINGER_JOINTS]
        obs = [sim.ease(t_frac), a_qpos_frac, b_qpos_frac] + prox_vec + [lateral_offset, height_offset, obstacle_prox]
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

    policy.train()
    worst_ratio = abs(worst_dist) / sim.CAPSULE_RADIUS if worst_dist < 0 else 0.0
    return worst_ratio


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = json.load(open(MANIFEST_PATH))
    train_eps, holdout_eps = split_holdout(manifest)
    print(f"train episodes: {len(train_eps)}, holdout episodes: {len(holdout_eps)}")
    print("holdout indices:", [e["episode_index"] for e in holdout_eps])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    policy = build_policy(device)
    n_params = sum(p.numel() for p in policy.parameters())
    print(f"device: {device}, model params: {n_params:,}")

    train_ds = ChunkDataset(train_eps, CHUNK_SIZE)
    loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    optimizer = torch.optim.AdamW(policy.parameters(), lr=LR, weight_decay=1e-4)

    t0 = time.time()
    loss_history = []
    for epoch in range(N_EPOCHS):
        epoch_losses = []
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            loss, _ = policy.forward(batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_losses.append(loss.item())
        mean_loss = float(np.mean(epoch_losses))
        loss_history.append(mean_loss)
        if epoch % 30 == 0 or epoch == N_EPOCHS - 1:
            print(f"epoch {epoch:4d}  loss={mean_loss:.5f}", flush=True)
    train_elapsed = time.time() - t0

    l1_err = offline_l1_error(policy, holdout_eps, device)
    print(f"holdout offline L1 action error: {l1_err:.5f}")

    rollout_results = []
    for ep in holdout_eps:
        worst_ratio = closed_loop_rollout(policy, device, ep)
        passed = worst_ratio <= sim.PENETRATION_GATE_RATIO
        rollout_results.append({
            "episode_index": ep["episode_index"],
            "sub_sweep": ep["sub_sweep"],
            "a_end": ep["a_end"], "b_end": ep["b_end"], "total_s": ep["total_s"],
            "lateral_offset_m": ep["lateral_offset_m"], "height_offset_m": ep["height_offset_m"],
            "obstacle_y_m": ep["obstacle_y_m"],
            "expert_worst_ratio": ep["worst_penetration_ratio_of_radius"],
            "policy_worst_ratio": round(worst_ratio, 4),
            "policy_passed_5pct_gate": passed,
        })
        print(f"[holdout {ep['episode_index']}] ({ep['sub_sweep']}) expert={ep['worst_penetration_ratio_of_radius']:.4f} "
              f"policy={worst_ratio:.4f} {'PASS' if passed else 'FAIL'}", flush=True)

    n_pass = sum(1 for r in rollout_results if r["policy_passed_5pct_gate"])
    ckpt_dir = os.path.join(OUT_DIR, "checkpoint")
    policy.save_pretrained(ckpt_dir)

    report = {
        "n_train_episodes": len(train_eps),
        "n_holdout_episodes": len(holdout_eps),
        "n_params": n_params,
        "n_epochs": N_EPOCHS,
        "train_elapsed_s": round(train_elapsed, 2),
        "final_train_loss": loss_history[-1],
        "holdout_offline_l1_action_error": round(l1_err, 5),
        "holdout_closed_loop_n_passed_gate": n_pass,
        "holdout_closed_loop_n_total": len(rollout_results),
        "holdout_closed_loop_results": rollout_results,
        "checkpoint_dir": ckpt_dir,
    }
    with open(REPORT_PATH, "w") as fp:
        json.dump(report, fp, indent=2)

    print(f"\n홀드아웃 폐루프: {n_pass}/{len(rollout_results)} 5% 게이트 통과")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
