"""
dual_openarm 양팔이 함께 움직이는 모습을 GIF로 렌더링.
mujoco_sim.service(라이브 스트림)는 건드리지 않는 별도 프로세스 —
같은 모델을 별도로 로드해 qpos만 애니메이션시켜 프레임을 뽑는다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
from PIL import Image

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
OUT_PATH = "/home/moos/dev_ws/images/dual_openarm-wave-2026-08-03.gif"

DURATION_S = 3.0
FPS = 20
N_FRAMES = int(DURATION_S * FPS)


def main():
    model = mujoco.MjModel.from_xml_path(URDF_PATH)
    model.vis.global_.offwidth = 800
    model.vis.global_.offheight = 800
    data = mujoco.MjData(model)

    j2 = {s: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{s}_joint_2") for s in ("left", "right")}
    j4 = {s: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{s}_joint_4") for s in ("left", "right")}
    j6 = {s: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{s}_joint_6") for s in ("left", "right")}

    hide_bids = set()
    for name in ("target_left", "target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=800, width=800)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = 135, -18, 2.3
    cam.lookat[:] = [0.0, 0.0, 0.45]

    frames = []
    for f in range(N_FRAMES):
        t = f / FPS
        phase = 2 * np.pi * t / DURATION_S

        data.qpos[:] = 0.0
        for side, sign in (("left", 1.0), ("right", -1.0)):
            data.qpos[model.jnt_qposadr[j2[side]]] = sign * 0.9 * np.sin(phase)
            data.qpos[model.jnt_qposadr[j4[side]]] = -0.9 + 0.6 * np.sin(phase + np.pi / 2)
            data.qpos[model.jnt_qposadr[j6[side]]] = 0.7 * np.sin(phase + np.pi)
        mujoco.mj_kinematics(model, data)
        mujoco.mj_fwdPosition(model, data)

        renderer.update_scene(data, camera=cam)
        for i in range(renderer.scene.ngeom):
            g = renderer.scene.geoms[i]
            if g.objtype == mujoco.mjtObj.mjOBJ_GEOM and model.geom_bodyid[g.objid] in hide_bids:
                g.rgba[3] = 0.0
        img = renderer.render()
        frames.append(Image.fromarray(img))

    renderer.close()

    frames[0].save(
        OUT_PATH, save_all=True, append_images=frames[1:],
        duration=int(1000 / FPS), loop=0, optimize=True,
    )
    print(f"저장 완료: {OUT_PATH} ({N_FRAMES}프레임, {FPS}fps)")


if __name__ == "__main__":
    main()
