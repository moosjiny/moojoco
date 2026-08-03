"""
Vorno와의 3D 보로노이 파티셔닝 POC용 씨앗점 export.
상시 가동 중인 mujoco_sim.service는 건드리지 않고, 별도 프로세스로 같은
모델을 읽어 기준 자세(rest pose, qpos=0)에서의 링크 월드좌표를 뽑는다.
"""
import os
os.environ['MUJOCO_GL'] = 'egl'

import json
import datetime
import numpy as np
import mujoco

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"

SEED_BODIES = (
    [f"left_link{i}" for i in range(1, 8)]
    + [f"right_link{i}" for i in range(1, 8)]
    + ["shoulder_block"]
)


def main():
    model = mujoco.MjModel.from_xml_path(URDF_PATH)
    data = mujoco.MjData(model)

    data.qpos[:] = 0.0  # 기준 자세 — 재현 가능한 상태로 고정
    mujoco.mj_kinematics(model, data)

    seeds = []
    for name in SEED_BODIES:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid == -1:
            print(f"[skip] body not found: {name}")
            continue
        pos = data.xpos[bid].tolist()
        seeds.append({"id": name, "position": [round(p, 4) for p in pos]})

    positions = np.array([s["position"] for s in seeds])
    bbox_min = positions.min(axis=0)
    bbox_max = positions.max(axis=0)
    margin = 0.1 * (bbox_max - bbox_min)  # Vorno 제안 margin=0.1 적용
    bbox_min -= margin
    bbox_max += margin

    payload = {
        "source": "moojoco",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "unit": "meters",
        "pose": "rest (qpos=0)",
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
