#!/usr/bin/env python3
"""
Operation Basin: 2-Axis (Pose Error x Hand Shape Scale) Monte Carlo Accuracy Budget Sweep
Co-developed by Gravity (EC2) & Geminy (hb5u Chief Systems & AI Architect)
Hardware: hb5u NVIDIA GeForce RTX 5060 + 14-core CPU + MuJoCo 3.7.0
Target: AmazingHand v4 Contact-Driven Grasp Controller v1
"""

import os
import sys
import json
import time
import math
import numpy as np
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

import mujoco

sys.path.insert(0, "/home/moos/dev_ws/dual_arms/scripts")
import contact_driven_grasp_controller_v1 as cdgc

XML_TEMPLATE_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v4.xml"
OUTPUT_DIR = "/home/moos/dev_ws/dual_arms/data/operation_basin_2axis_sweep"

def generate_perturbed_xml(xml_base_str: str, dx: float, dy: float, dz: float,
                           d_roll: float, d_pitch: float, d_yaw: float,
                           scale: float) -> str:
    root = ET.fromstring(xml_base_str)
    
    # 1. Pose Perturbation on handB_wrist
    for body in root.iter("body"):
        name = body.get("name", "")
        if name == "handB_wrist":
            body.set("pos", f"{dx:.6f} {0.12 + dy:.6f} {0.070 + dz:.6f}")
            body.set("euler", f"{3.14159 + d_roll:.6f} {d_pitch:.6f} {d_yaw:.6f}")
        elif scale != 1.0 and (name.startswith("handB_finger") or name.startswith("handB_thumb") or name.endswith("distal")):
            pos = [float(x) * scale for x in body.get("pos", "0 0 0").split()]
            body.set("pos", f"{pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}")

    # 2. Shape Scale Perturbation on handB geoms
    if scale != 1.0:
        for geom in root.iter("geom"):
            name = geom.get("name", "")
            if name.startswith("handB_"):
                if geom.get("type") == "box":
                    size = [float(x) * scale for x in geom.get("size").split()]
                    geom.set("size", f"{size[0]:.6f} {size[1]:.6f} {size[2]:.6f}")
                elif geom.get("type") == "capsule":
                    fromto = [float(x) * scale for x in geom.get("fromto").split()]
                    geom.set("fromto", " ".join(f"{x:.6f}" for x in fromto))
                    size = float(geom.get("size")) * scale
                    geom.set("size", f"{size:.6f}")

    return ET.tostring(root, encoding="unicode")

def run_single_simulation(trial_params: Dict) -> Dict:
    xml_base_str = trial_params["xml_base_str"]
    scale = trial_params["scale"]
    p_err_mm = trial_params["p_err_mm"]
    th_err_deg = trial_params["th_err_deg"]
    trial_idx = trial_params["trial_idx"]
    seed = trial_params["seed"]

    rng = np.random.default_rng(seed)
    # Sample translation on sphere
    if p_err_mm == 0.0:
        dp = np.zeros(3)
    else:
        v = rng.normal(0, 1, 3)
        v /= np.linalg.norm(v)
        r = (p_err_mm / 1000.0) * (rng.uniform(0, 1) ** (1.0 / 3.0))
        dp = v * r

    # Sample rotation euler in degrees -> radians
    if th_err_deg == 0.0:
        d_euler = np.zeros(3)
    else:
        d_euler = np.radians(rng.uniform(-th_err_deg, th_err_deg, 3))

    xml_str = generate_perturbed_xml(
        xml_base_str,
        dx=float(dp[0]), dy=float(dp[1]), dz=float(dp[2]),
        d_roll=float(d_euler[0]), d_pitch=float(d_euler[1]), d_yaw=float(d_euler[2]),
        scale=scale
    )

    model = mujoco.MjModel.from_xml_string(xml_str)
    data = mujoco.MjData(model)

    jid, aid = {}, {}
    joint_names = ["handA_approach", "handB_approach", "handB_lateral", "handB_height"]
    for h in ("handA", "handB"):
        for fn in cdgc.FINGER_JOINTS:
            joint_names += [f"{h}_{fn}_mcp", f"{h}_{fn}_pip"]
    for name in joint_names:
        jid[name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        aid[name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name + "_ctrl")

    geom_owner = {}
    for h in ("handA", "handB"):
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_palm")
        geom_owner[gid] = (h, "palm", "palm")
        for fn in cdgc.FINGER_JOINTS:
            for seg in ("prox", "dist"):
                gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{fn}_{seg}_geom")
                geom_owner[gid] = (h, fn, seg)

    res, _ = cdgc.run(model, data, jid, aid, joint_names, geom_owner)
    n_hold_fingers = sum(1 for v in res["hold_finger_contact_rates"].values() if v >= 0.8)
    
    # Gate Evaluation:
    # 1. Penetration Gate: <= 5% (capsule radius)
    # 2. Palm contact ever + hold rate >= 90%
    # 3. Fingers wrapped >= 8
    # 4. Hold fingers >= 8
    success = bool(
        res["gate_pass"]
        and res["palm_contact_ever"]
        and res["hold_palm_contact_rate"] >= 0.9
        and res["fingers_wrapped"] >= 8
        and n_hold_fingers >= 8
    )

    return {
        "scale": scale,
        "p_err_mm": p_err_mm,
        "th_err_deg": th_err_deg,
        "trial_idx": trial_idx,
        "dx_mm": float(dp[0] * 1000.0),
        "dy_mm": float(dp[1] * 1000.0),
        "dz_mm": float(dp[2] * 1000.0),
        "d_roll_deg": float(np.degrees(d_euler[0])),
        "d_pitch_deg": float(np.degrees(d_euler[1])),
        "d_yaw_deg": float(np.degrees(d_euler[2])),
        "penetration_ratio": res["worst_penetration_ratio_of_radius"],
        "palm_hold_rate": res["hold_palm_contact_rate"],
        "fingers_wrapped": res["fingers_wrapped"],
        "fingers_hold_80pct": n_hold_fingers,
        "success": success
    }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(XML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        xml_base_str = f.read()

    # 2-Axis Parameters Grid
    scale_levels = [0.85, 0.92, 1.00, 1.08, 1.15]      # 5 Shape levels (-15% ~ +15%)
    trans_levels = [0.0, 2.0, 4.0, 6.0, 8.0]           # 5 Position error levels (mm)
    rot_levels   = [0.0, 1.5, 3.0, 5.0]                # 4 Rotation error levels (deg)
    trials_per_cell = 5                                 # 5 Monte Carlo trials per cell

    total_tasks = len(scale_levels) * len(trans_levels) * len(rot_levels) * trials_per_cell
    print(f"=== [Operation Basin] 2-Axis Monte Carlo Sweep Launch ===")
    print(f"• Hardware: hb5u (RTX 5060, 14 CPU cores)")
    print(f"• Shape Scales: {scale_levels}")
    print(f"• Translation Levels (mm): {trans_levels}")
    print(f"• Rotation Levels (deg): {rot_levels}")
    print(f"• Total Rollout Count: {total_tasks} simulations")
    
    tasks = []
    base_seed = 20260914
    idx = 0
    for s in scale_levels:
        for p in trans_levels:
            for th in rot_levels:
                for t in range(trials_per_cell):
                    tasks.append({
                        "xml_base_str": xml_base_str,
                        "scale": s,
                        "p_err_mm": p,
                        "th_err_deg": th,
                        "trial_idx": t,
                        "seed": base_seed + idx
                    })
                    idx += 1

    t0 = time.time()
    results = []
    num_workers = min(10, os.cpu_count() or 4)
    print(f"[*] Dispatching to {num_workers} parallel workers...")

    completed = 0
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(run_single_simulation, t): t for t in tasks}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            completed += 1
            if completed % 50 == 0 or completed == total_tasks:
                elapsed = time.time() - t0
                fps = completed / elapsed
                print(f"  -> Progress: {completed}/{total_tasks} ({completed/total_tasks*100:.1f}%) | Speed: {fps:.1f} rollouts/sec | Elapsed: {elapsed:.1f}s")

    total_time = time.time() - t0
    print(f"\n✅ All {total_tasks} rollouts completed in {total_time:.2f} seconds ({total_tasks/total_time:.1f} rollouts/s)!")

    # Process and Aggregate Matrix
    # Matrix: scale -> (trans, rot) -> success_rate
    matrix_by_scale = {}
    for s in scale_levels:
        matrix_by_scale[s] = np.zeros((len(trans_levels), len(rot_levels)))

    for r in results:
        s = r["scale"]
        p_idx = trans_levels.index(r["p_err_mm"])
        th_idx = rot_levels.index(r["th_err_deg"])
        if r["success"]:
            matrix_by_scale[s][p_idx, th_idx] += 1.0 / trials_per_cell

    # Overall Robust Matrix (across all scales)
    combined_matrix = np.zeros((len(trans_levels), len(rot_levels)))
    for p_idx in range(len(trans_levels)):
        for th_idx in range(len(rot_levels)):
            rates = [matrix_by_scale[s][p_idx, th_idx] for s in scale_levels]
            combined_matrix[p_idx, th_idx] = np.mean(rates)

    # Derive Recommended Budget (@ >= 85% and >= 90% confidence)
    def derive_max_budget(grid, conf=0.90):
        best_p, best_th = 0.0, 0.0
        best_area = -1.0
        for i, p in enumerate(trans_levels):
            for j, th in enumerate(rot_levels):
                if grid[i, j] >= conf:
                    area = (p + 0.1) * (th + 0.1)
                    if area > best_area:
                        best_area = area
                        best_p = p
                        best_th = th
        return best_p, best_th

    budget_nominal_90 = derive_max_budget(matrix_by_scale[1.00], 0.90)
    budget_robust_90  = derive_max_budget(combined_matrix, 0.90)
    budget_robust_80  = derive_max_budget(combined_matrix, 0.80)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": "hb5u (NVIDIA RTX 5060, 14 CPU Cores)",
        "total_rollouts": total_tasks,
        "elapsed_seconds": round(total_time, 2),
        "rollouts_per_sec": round(total_tasks / total_time, 2),
        "scale_levels": scale_levels,
        "trans_levels_mm": trans_levels,
        "rot_levels_deg": rot_levels,
        "trials_per_cell": trials_per_cell,
        "matrices_by_scale": {str(s): matrix_by_scale[s].tolist() for s in scale_levels},
        "combined_robust_matrix": combined_matrix.tolist(),
        "derived_accuracy_budgets": {
            "nominal_hand_90pct": {
                "max_trans_error_mm": budget_nominal_90[0],
                "max_rot_error_deg": budget_nominal_90[1],
                "confidence": 0.90,
                "note": "Scale = 1.0 (Nominal)"
            },
            "shape_robust_90pct": {
                "max_trans_error_mm": budget_robust_90[0],
                "max_rot_error_deg": budget_robust_90[1],
                "confidence": 0.90,
                "note": "All Hand Scales [0.85 ~ 1.15]"
            },
            "shape_robust_80pct": {
                "max_trans_error_mm": budget_robust_80[0],
                "max_rot_error_deg": budget_robust_80[1],
                "confidence": 0.80,
                "note": "All Hand Scales [0.85 ~ 1.15]"
            }
        }
    }

    summary_path = os.path.join(OUTPUT_DIR, "accuracy_budget_2axis_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n📁 Saved summary to: {summary_path}")

    print("\n" + "="*75)
    print("📊 [Operation Basin] 실측 2축 정확도 예산(Accuracy Budget) 확정 보고")
    print("="*75)
    print(f"1. 기준 형상 (Nominal Scale 1.0, 90% 신뢰도):")
    print(f"   ➔ 허용 위치 오차: ±{budget_nominal_90[0]:.1f} mm | 허용 회전 오차: ±{budget_nominal_90[1]:.1f}°")
    print(f"2. 전 형상 통합 강건 예산 (Shape-Robust 0.85~1.15, 90% 신뢰도):")
    print(f"   ➔ 허용 위치 오차: ±{budget_robust_90[0]:.1f} mm | 허용 회전 오차: ±{budget_robust_90[1]:.1f}°")
    print(f"3. 전 형상 통합 허용 예산 (Shape-Robust 0.85~1.15, 80% 신뢰도):")
    print(f"   ➔ 허용 위치 오차: ±{budget_robust_80[0]:.1f} mm | 허용 회전 오차: ±{budget_robust_80[1]:.1f}°")
    print("="*75)

if __name__ == "__main__":
    main()
