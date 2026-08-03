"""
악수(handshake) 최종 포즈(양팔 오른손이 맞닿는 자세)에서 로봇 2대의 씨앗점
30개(로봇당 15개)를 추출해 Vorno에게 전달할 JSON을 만든다.
dual_openarm_handshake.xml 사용, 라이브 mujoco_sim.service는 미간섭.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json
import datetime
import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"

SEED_BODIES = (
    [f"left_link{i}" for i in range(1, 8)]
    + [f"right_link{i}" for i in range(1, 8)]
    + ["shoulder_block"]
)

J2_FINAL = 0.0  # render_handshake_gif.py의 맞닿는 최종 자세와 동일


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)

    j2 = {p: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{p}right_joint_2") for p in ("", "r2_")}
    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[j2[""]]] = J2_FINAL
    data.qpos[model.jnt_qposadr[j2["r2_"]]] = J2_FINAL
    mujoco.mj_kinematics(model, data)

    seeds = []
    for prefix, robot_id in (("", "robot_A"), ("r2_", "robot_B")):
        for name in SEED_BODIES:
            bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"{prefix}{name}")
            if bid == -1:
                print(f"[skip] body not found: {prefix}{name}")
                continue
            pos = data.xpos[bid].tolist()
            seeds.append({"id": f"{prefix}{name}", "robot": robot_id, "position": [round(p, 4) for p in pos]})

    positions = np.array([s["position"] for s in seeds])
    bbox_min = positions.min(axis=0)
    bbox_max = positions.max(axis=0)
    margin = 0.1 * (bbox_max - bbox_min)
    bbox_min -= margin
    bbox_max += margin

    hand_a = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    hand_b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "r2_right_link7")
    hand_distance = float(np.linalg.norm(data.xpos[hand_a] - data.xpos[hand_b]))

    payload = {
        "source": "moojoco",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "unit": "meters",
        "pose": "handshake_final (right arms extended, right_link7 <-> r2_right_link7 meeting)",
        "scene": "dual_openarm_handshake.xml (robot_B offset y=1.05, quat 180deg about z)",
        "hand_distance_m": round(hand_distance, 4),
        "bounding_box": {
            "min": [round(v, 4) for v in bbox_min.tolist()],
            "max": [round(v, 4) for v in bbox_max.tolist()],
        },
        "seeds": seeds,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    main()
