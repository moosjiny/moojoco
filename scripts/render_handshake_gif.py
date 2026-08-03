"""
악수(Handshake) 데모: 양쪽 로봇의 오른팔이 retract 자세에서 시작해 서로를 향해
뻗어 손끝이 맞닿는 자세로 움직이는 GIF. 접촉 물리 없는 순수 운동학 재생 —
2단계(Vorno 제안 로드맵) 1차 시연.
mujoco_sim.service(라이브)는 별도 XML·별도 프로세스라 미간섭.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
from PIL import Image

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"
OUT_PATH = "/home/moos/dev_ws/images/dual_openarm-handshake-2026-08-03.gif"

APPROACH_S = 2.0   # retract -> 맞잡음
HOLD_S = 1.0       # 맞잡은 자세 유지
FPS = 20
N_APPROACH = int(APPROACH_S * FPS)
N_HOLD = int(HOLD_S * FPS)

J2_RETRACT = 1.3   # 팔을 위로 젖혀 retract
J2_FINAL = 0.0      # rest — 손끝이 맞닿는 자세 (build_handshake_scene.py에서 검증됨)


def ease(t):
    return 0.5 - 0.5 * np.cos(np.pi * t)  # smoothstep 유사 완만한 가속/감속


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 960
    data = mujoco.MjData(model)

    j2 = {p: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{p}right_joint_2") for p in ("", "r2_")}

    hide_bids = set()
    for name in ("target_left", "target_right", "r2_target_left", "r2_target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = 15, -12, 2.0
    cam.lookat[:] = [0.0, 0.52, 0.85]

    frames = []
    total = N_APPROACH + N_HOLD
    for f in range(total):
        frac = min(f / N_APPROACH, 1.0)
        val = J2_RETRACT + (J2_FINAL - J2_RETRACT) * ease(frac)

        data.qpos[:] = 0.0
        data.qpos[model.jnt_qposadr[j2[""]]] = val
        data.qpos[model.jnt_qposadr[j2["r2_"]]] = val
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
    print(f"저장 완료: {OUT_PATH} ({total}프레임, {FPS}fps)")


if __name__ == "__main__":
    main()
