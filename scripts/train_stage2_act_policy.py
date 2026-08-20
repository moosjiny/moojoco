"""Stage 2 (LeRobot/ACT Phase 2 계획) — 통합 데이터셋(132 에피소드, 16차원 관찰/
12차원 행동)으로 소규모 ACT 정책을 학습한다.

## v2 — 스키마 재설계 반영
[[2026-08-20-moojoco-lerobot-schema-redesign]]에서 관찰-행동 항등함수 지름길
버그(a/b_progress가 그 프레임 행동과 항상 같은 값이던 문제, Aegis 독립
재현으로 확인)를 고치며 관찰이 15→16차원으로 바뀌었다: `a_progress`/
`b_progress`(행동 복제값) 대신 `elapsed_time_frac`(정책 출력과 무관한
시계 신호) + `handA/B_qpos_frac`(실측 물리 위치, 행동과 인과관계가 다름)
3차원을 쓴다.

## 스코프 축소 — 정직하게 기록
- lerobot의 공식 `LeRobotDataset`/훈련 CLI(`lerobot-train` 등)는 HF Hub 저장소
  포맷(비디오 인코딩, 메타 json 등)을 요구한다. 우리 데이터는 이미
  Parquet(episode_index/frame_index/timestamp/observation.state/action)로
  충분히 구조화돼 있어, 그 인프라를 그대로 쓰는 대신 `ACTPolicy`/`ACTConfig`를
  직접 임포트해 최소한의 커스텀 학습 루프로 붙였다.
- lerobot의 정규화 파이프라인(`processor_act.py`, Normalize/Unnormalize,
  데이터셋 평균·표준편차 필요)도 이번엔 붙이지 않았다 — 관찰(거리, 0~0.08m대)과
  행동(사용비율, 0~1)이 이미 스케일이 크게 다르지 않아 원본값을 그대로 넣었다.
  더 큰 데이터셋으로 갈 때는 붙이는 걸 권장.
- 카메라 입력이 없으므로(`image_features` 빈 채로) ResNet 백본은 아예 생성되지
  않는다 — 다운로드도, VRAM도 필요 없다.
- 필터링 방침([[2026-08-20-moojoco-lerobot-act-phase2-plan]] v2)대로 5% 침투
  게이트를 통과한 궤적(48/76)의 행동만 모방학습 대상으로 쓴다. 실패 궤적의
  관찰을 안전-경계 분류기로 재사용하는 건 이번 스코프에 넣지 않았다(다음 단계).

관찰(observation.environment_state, 16차원) = elapsed_time_frac,
  handA/B_qpos_frac, 손가락별(양손×5) 근접도, handB lateral/height 오프셋,
  장애물 근접도
행동(action, 12차원) = handA/B 접근 사용비율 + 손가락별(양손×5) curl 사용비율
"""
import json
import os
import time

import numpy as np
import pyarrow.parquet as pq
import torch
from torch.utils.data import DataLoader, Dataset

from lerobot.configs.types import FeatureType, PolicyFeature
from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import ACTION, OBS_ENV_STATE, OBS_STATE

DATA_DIR = "/home/moos/dev_ws/dual_arms/data/procedural_curl_dataset_unified"
MANIFEST_PATH = os.path.join(DATA_DIR, "manifest.json")
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/lerobot_stage2_act_policy"

OBS_DIM = 16
ACTION_DIM = 12
CHUNK_SIZE = 20
BATCH_SIZE = 64
N_EPOCHS = 200
LR = 1e-4


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
            # lerobot 0.6.1의 ACT 순전파(modeling_act.py:433,457)가
            # env_state_feature만 있고 robot_state_feature가 없을 때도
            # batch[OBS_STATE]를 무조건 참조하는 버그가 있어(KeyError로 실측
            # 확인) observation.state에도 같은 값을 중복으로 넣어 우회한다 —
            # 우리 데이터는 애초에 "로봇 자체 상태"와 "환경 상대 상태"가 명확히
            # 분리돼 있지 않으므로(전부 근접도/오프셋) 의미상으로도 문제없다.
            OBS_STATE: obs_t,
            OBS_ENV_STATE: obs_t,
            ACTION: torch.from_numpy(chunk),
            "action_is_pad": torch.from_numpy(is_pad),
        }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = json.load(open(MANIFEST_PATH))
    all_episodes = manifest["episodes"]
    passed = [e for e in all_episodes if e["passed_5pct_gate"]]
    print(f"episodes: {len(all_episodes)} total, {len(passed)} passed 5% gate (used for training)")

    dataset = ChunkDataset(passed, CHUNK_SIZE)
    print(f"training samples (per-frame chunks): {len(dataset)}")
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    config = ACTConfig(
        n_obs_steps=1,
        chunk_size=CHUNK_SIZE,
        n_action_steps=CHUNK_SIZE,
        input_features={
            OBS_STATE: PolicyFeature(FeatureType.STATE, (OBS_DIM,)),
            OBS_ENV_STATE: PolicyFeature(FeatureType.ENV, (OBS_DIM,)),
        },
        output_features={ACTION: PolicyFeature(FeatureType.ACTION, (ACTION_DIM,))},
        # 기본 ACT(이미지+실제 로봇용)는 dim_model=512, feedforward=3200 등 훨씬
        # 크다 — 우리 문제는 저차원 상태->행동 매핑뿐이라 8GB VRAM 문제도 아니고,
        # 이 정도로 소규모화하는 게 데이터 규모(76 에피소드)에도 더 맞다.
        dim_model=256,
        n_heads=8,
        dim_feedforward=1024,
        n_encoder_layers=2,
        n_decoder_layers=1,
        use_vae=True,
        latent_dim=16,
        n_vae_encoder_layers=2,
        dropout=0.1,
        kl_weight=10.0,
        device=device,
        push_to_hub=False,
    )
    policy = ACTPolicy(config)
    policy.to(device)
    policy.train()

    n_params = sum(p.numel() for p in policy.parameters())
    print(f"device: {device}, model params: {n_params:,}")

    optimizer = torch.optim.AdamW(policy.parameters(), lr=LR, weight_decay=1e-4)

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    t0 = time.time()
    loss_history = []
    for epoch in range(N_EPOCHS):
        epoch_losses = []
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            loss, loss_dict = policy.forward(batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_losses.append(loss.item())
        mean_loss = float(np.mean(epoch_losses))
        loss_history.append(mean_loss)
        if epoch % 20 == 0 or epoch == N_EPOCHS - 1:
            print(f"epoch {epoch:4d}  loss={mean_loss:.5f}", flush=True)

    elapsed = time.time() - t0
    peak_vram_mb = torch.cuda.max_memory_allocated() / 1e6 if device == "cuda" else 0.0

    ckpt_dir = os.path.join(OUT_DIR, "checkpoint")
    policy.save_pretrained(ckpt_dir)

    summary = {
        "device": device,
        "n_params": n_params,
        "n_episodes_total": len(all_episodes),
        "n_episodes_used": len(passed),
        "n_training_samples": len(dataset),
        "n_epochs": N_EPOCHS,
        "batch_size": BATCH_SIZE,
        "chunk_size": CHUNK_SIZE,
        "final_loss": loss_history[-1],
        "loss_history_every_20_epochs": loss_history[::20] + [loss_history[-1]],
        "elapsed_s": round(elapsed, 2),
        "peak_vram_mb": round(peak_vram_mb, 1),
        "checkpoint_dir": ckpt_dir,
    }
    with open(os.path.join(OUT_DIR, "train_summary.json"), "w") as fp:
        json.dump(summary, fp, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
