"""
dual_openarm_2robots.xml(로봇 2대 씬)로 양쪽 로봇이 함께 웨이브하는 GIF 렌더링.
mujoco_sim.service(라이브, 로봇 1대 모델)는 완전히 별개 — 건드리지 않음.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
from PIL import Image

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_2robots.xml"
OUT_PATH = "/home/moos/dev_ws/images/dual_openarm-two-robots-wave-2026-08-03.gif"

DURATION_S = 3.0
FPS = 20
N_FRAMES = int(DURATION_S * FPS)


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 960
    data = mujoco.MjData(model)

    def joint_ids(prefix=""):
        return {
            n: {s: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{prefix}{s}_joint_{n}")
                for s in ("left", "right")}
            for n in (2, 4, 6)
        }

    j_r1 = joint_ids("")
    j_r2 = joint_ids("r2_")

    hide_bids = set()
    for name in ("target_left", "target_right", "r2_target_left", "r2_target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = 60, -16, 3.4
    cam.lookat[:] = [0.8, 0.0, 0.45]

    def set_wave(jmap, phase_offset, amp_scale):
        for side, sign in (("left", 1.0), ("right", -1.0)):
            ph = phase_offset
            data.qpos[model.jnt_qposadr[jmap[2][side]]] = sign * 0.9 * amp_scale * np.sin(ph)
            data.qpos[model.jnt_qposadr[jmap[4][side]]] = -0.9 + 0.6 * amp_scale * np.sin(ph + np.pi / 2)
            data.qpos[model.jnt_qposadr[jmap[6][side]]] = 0.7 * amp_scale * np.sin(ph + np.pi)

    frames = []
    for f in range(N_FRAMES):
        t = f / FPS
        phase = 2 * np.pi * t / DURATION_S

        data.qpos[:] = 0.0
        set_wave(j_r1, phase, 1.0)
        set_wave(j_r2, phase + np.pi, 1.0)  # 로봇2는 반대 위상 — 서로 다른 리듬으로 확실히 구분
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
