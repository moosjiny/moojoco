#!/usr/bin/env python3
"""
ROOPS Physical AI Continuum: Handshake 6D Pose Accuracy Budgeting & Perturbation Sweep
Author: Gravity (Lead Cybernetics & Physical AI Agent)
Collaborators: Hermes, Moojoco, Mojo
Target: hb5u MuJoCo 3.x Simulation Environment (AmazingHand v4 Docking)
Reference: 2026-09-12-hermes-anyworld-bop-closed-analytic-loop-analysis
"""

import os
import sys
import json
import time
import math
import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional

# ==============================================================================
# 1. 섭동 공간 (Perturbation Parameter Space) 규격 정의
# ==============================================================================

@dataclass
class PerturbationConfig:
    # 병진 오차 스윕 범위 (단위: mm)
    delta_p_levels: List[float] = None
    # 회전 오차 스윕 범위 (단위: deg, Euler R-P-Y)
    delta_theta_levels: List[float] = None
    # 레벨당 몬테카를로 반복 횟수
    mc_trials_per_cell: int = 20
    # 무작위 시드
    random_seed: int = 42

    def __post_init__(self):
        if self.delta_p_levels is None:
            # 1mm부터 20mm까지 7단계
            self.delta_p_levels = [0.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 20.0]
        if self.delta_theta_levels is None:
            # 0도부터 15도까지 7단계
            self.delta_theta_levels = [0.0, 1.5, 3.0, 5.0, 8.0, 11.0, 15.0]

@dataclass
class EvaluationGates:
    # 침투율 상한 (캡슐 반경 대비)
    max_penetration_ratio: float = 0.05       # <= 5.0%
    # HOLD 단계 최소 유지율 (2.0초 기준)
    min_hold_retention_ratio: float = 0.90    # >= 90%
    # 원위 세그먼트 감싸쥠 최소 손가락 수
    min_distal_contacts: int = 8              # >= 8/10
    # 법선 접촉력 안전 범위 (단위: N)
    min_normal_force_n: float = 3.0
    max_normal_force_n: float = 30.0

@dataclass
class SweepTrialResult:
    delta_p_mm: float
    delta_theta_deg: float
    trial_idx: int
    dx_mm: float
    dy_mm: float
    dz_mm: float
    d_yaw_deg: float
    d_pitch_deg: float
    d_roll_deg: float
    penetration_ratio: float
    hold_retention_ratio: float
    distal_contacts: int
    max_force_n: float
    success: bool
    fail_reason: str = ""

# ==============================================================================
# 2. 섭동 샘플러 (SE(3) Perturbation Generator)
# ==============================================================================

class SE3PerturbationSampler:
    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def sample_perturbation(self, delta_p_max_mm: float, delta_theta_max_deg: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        주어진 오차 상한 구체(Sphere) 내에서 균등하게 6자유도 자세 오차를 샘플링합니다.
        - 병진 오차: 접근축(z), 횡방향(x), 수직(y) 균등 볼
        - 회전 오차: 임의의 회전축 n과 회전각 theta ~ U(-max, max)
        """
        if delta_p_max_mm == 0.0:
            dp = np.zeros(3)
        else:
            # Sphere uniform sampling
            v = self.rng.normal(0, 1, 3)
            v /= np.linalg.norm(v)
            r = delta_p_max_mm * (self.rng.uniform(0, 1) ** (1.0 / 3.0))
            dp = v * r

        if delta_theta_max_deg == 0.0:
            d_euler = np.zeros(3)
        else:
            # Yaw, Pitch, Roll 균등 섭동
            d_euler = self.rng.uniform(-delta_theta_max_deg, delta_theta_max_deg, 3)

        return dp, d_euler

# ==============================================================================
# 3. 시뮬레이션 인터페이스 및 스윕 러너
# ==============================================================================

class HandshakeAccuracyBudgetSweepRunner:
    def __init__(self, config: PerturbationConfig, gates: EvaluationGates):
        self.config = config
        self.gates = gates
        self.sampler = SE3PerturbationSampler(config.random_seed)
        self.results: List[SweepTrialResult] = []

    def evaluate_gates(self, pen: float, ret: float, contacts: int, force: float) -> Tuple[bool, str]:
        if pen > self.gates.max_penetration_ratio:
            return False, f"PENETRATION_EXCEEDED ({pen*100:.2f}% > {self.gates.max_penetration_ratio*100}%)"
        if ret < self.gates.min_hold_retention_ratio:
            return False, f"RETENTION_DROPPED ({ret:.2f} < {self.gates.min_hold_retention_ratio})"
        if contacts < self.gates.min_distal_contacts:
            return False, f"INSUFFICIENT_CONTACTS ({contacts} < {self.gates.min_distal_contacts})"
        if force > self.gates.max_normal_force_n:
            return False, f"FORCE_EXCEEDED ({force:.1f}N > {self.gates.max_normal_force_n}N)"
        if force < self.gates.min_normal_force_n:
            return False, f"FORCE_TOO_WEAK ({force:.1f}N < {self.gates.min_normal_force_n}N)"
        return True, "PASSED"

    def run_synthetic_benchmark(self) -> Dict:
        """
        시뮬레이션 전 환경 및 분석 알고리즘 검증을 위한 해석적 컴플라이언스 모델 기반 벤치마크.
        - Moojoco의 Settle->Anchor 특성: ±5mm / ±4deg 이내에서는 순응 마찰로 파지 유지.
        - ±8mm 이상에서는 원위 세그먼트 걸침 실패율 급증.
        """
        print(f"[*] Starting Accuracy Budget Sweep: {len(self.config.delta_p_levels)} x {len(self.config.delta_theta_levels)} grid...")
        success_grid = np.zeros((len(self.config.delta_p_levels), len(self.config.delta_theta_levels)))

        for p_idx, p_val in enumerate(self.config.delta_p_levels):
            for t_idx, t_val in enumerate(self.config.delta_theta_levels):
                cell_successes = 0
                for trial in range(self.config.mc_trials_per_cell):
                    dp, dth = self.sampler.sample_perturbation(p_val, t_val)

                    # 물리 모델 추정 (Moojoco v4 stacked clasp 기하 + 순응 토크 역학)
                    dist = np.linalg.norm(dp)
                    ang = np.linalg.norm(dth)

                    # 오차에 따른 특성 쇠퇴 모델링
                    pen = 0.0437 + 0.002 * (dist / 10.0) + self.sampler.rng.normal(0, 0.003)
                    pen = max(0.01, pen)

                    # 위치 오차가 10mm 넘거나 각도 오차가 8도 넘으면 슬립 발생 확률 상승
                    slip_prob = 1.0 / (1.0 + np.exp(-(dist - 7.5)/1.8)) * 0.7 + \
                                1.0 / (1.0 + np.exp(-(ang - 6.0)/1.5)) * 0.3
                    
                    is_slipped = self.sampler.rng.uniform(0, 1) < slip_prob
                    if is_slipped:
                        ret = float(self.sampler.rng.uniform(0.3, 0.85))
                        contacts = int(self.sampler.rng.integers(3, 7))
                        force = float(self.sampler.rng.uniform(1.0, 12.0))
                    else:
                        ret = float(self.sampler.rng.uniform(0.95, 1.0))
                        contacts = int(self.sampler.rng.integers(9, 11))
                        force = float(self.sampler.rng.uniform(8.0, 18.0))

                    passed, reason = self.evaluate_gates(pen, ret, contacts, force)
                    if passed:
                        cell_successes += 1

                    self.results.append(SweepTrialResult(
                        delta_p_mm=p_val,
                        delta_theta_deg=t_val,
                        trial_idx=trial,
                        dx_mm=float(dp[0]), dy_mm=float(dp[1]), dz_mm=float(dp[2]),
                        d_yaw_deg=float(dth[0]), d_pitch_deg=float(dth[1]), d_roll_deg=float(dth[2]),
                        penetration_ratio=float(pen),
                        hold_retention_ratio=float(ret),
                        distal_contacts=contacts,
                        max_force_n=float(force),
                        success=passed,
                        fail_reason=reason
                    ))

                rate = cell_successes / self.config.mc_trials_per_cell
                success_grid[p_idx, t_idx] = rate

        # 정확도 예산(Accuracy Budget) 산출: 성공률 >= 90% 인 최대 경계 도출
        budget_p, budget_th = self._derive_budget(success_grid)

        summary = {
            "p_levels_mm": self.config.delta_p_levels,
            "theta_levels_deg": self.config.delta_theta_levels,
            "success_matrix": success_grid.tolist(),
            "recommended_budget": {
                "max_trans_error_mm": budget_p,
                "max_rot_error_deg": budget_th,
                "confidence_gate": 0.90
            }
        }
        return summary

    def _derive_budget(self, grid: np.ndarray) -> Tuple[float, float]:
        best_area = -1.0
        best_p = 0.0
        best_th = 0.0
        for i, p in enumerate(self.config.delta_p_levels):
            for j, th in enumerate(self.config.delta_theta_levels):
                if grid[i, j] >= 0.90:
                    area = (p + 0.1) * (th + 0.1)
                    if area > best_area:
                        best_area = area
                        best_p = p
                        best_th = th
        return best_p, best_th

# ==============================================================================
# 4. 엔트리포인트 및 CLI
# ==============================================================================

if __name__ == "__main__":
    cfg = PerturbationConfig(mc_trials_per_cell=30)
    gates = EvaluationGates()
    runner = HandshakeAccuracyBudgetSweepRunner(cfg, gates)
    report = runner.run_synthetic_benchmark()

    print("\n" + "="*70)
    print("📊 [ROOPS Handshake Accuracy Budget Sweep Summary]")
    print("="*70)
    print(f"• 위치 오차 스윕 (mm) : {report['p_levels_mm']}")
    print(f"• 회전 오차 스윕 (deg): {report['theta_levels_deg']}")
    print(f"• 산출된 정확도 예산 (Budget @ 90% Success):")
    print(f"  ➔ 허용 위치 오차: ±{report['recommended_budget']['max_trans_error_mm']} mm")
    print(f"  ➔ 허용 회전 오차: ±{report['recommended_budget']['max_rot_error_deg']} deg")
    print("="*70)

    out_file = "/home/ec2-user/gravity/accuracy_budget_sweep_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"✅ Full sweep protocol and baseline saved to: {out_file}")
