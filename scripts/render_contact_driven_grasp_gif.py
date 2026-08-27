"""접촉 주도형 파지 v1 성공 궤적(trajectory.json)을 EGL로 렌더링해 GIF 생성.
contact_driven_grasp_controller_v1.py가 만든 관절 궤적의 순수 운동학 재생 —
같은 궤적을 2단계(fingershake 웹앱 브릿지)에서도 재생하게 되므로 그 예행이기도 하다.
"""
import json
import os

os.environ["MUJOCO_GL"] = "egl"

import mujoco
import numpy as np
from PIL import Image

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v4.xml"
TRAJ_PATH = "/home/moos/dev_ws/dual_arms/data/contact_driven_grasp_v1/trajectory.json"
OUT_PATH = "/home/moos/dev_ws/images/contact-driven-grasp-v1-2026-08-28.gif"


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    model.vis.global_.offwidth = 720
    model.vis.global_.offheight = 720
    data = mujoco.MjData(model)

    traj = json.load(open(TRAJ_PATH))
    joints = traj["joints"]
    jadr = {n: model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)]
            for n in joints}
    obstacle_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "obstacle")
    mocap_id = int(model.body_mocapid[obstacle_body])

    renderer = mujoco.Renderer(model, height=720, width=720)
    frames = []
    for fr in traj["frames"]:
        data.qpos[:] = 0.0
        for name, val in fr["qpos"].items():
            data.qpos[jadr[name]] = val
        data.mocap_pos[mocap_id] = [0.0, 5.0, 0.05]
        mujoco.mj_forward(model, data)
        renderer.update_scene(data, camera="cam_dock")
        frames.append(Image.fromarray(renderer.render()))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    frames[0].save(OUT_PATH, save_all=True, append_images=frames[1:],
                   duration=int(1000 / traj["fps"]), loop=0)
    print(f"{len(frames)}프레임 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
