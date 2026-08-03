import os
os.environ["MUJOCO_GL"] = "egl"
import mujoco
from PIL import Image

model = mujoco.MjModel.from_xml_path("/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml")
model.vis.global_.offwidth = 900
model.vis.global_.offheight = 900
data = mujoco.MjData(model)
data.qpos[:] = 0.0
mujoco.mj_kinematics(model, data)
mujoco.mj_fwdPosition(model, data)

hide_bids = set()
for name in ("target_left", "target_right", "r2_target_left", "r2_target_right"):
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if bid != -1:
        hide_bids.add(bid)

renderer = mujoco.Renderer(model, height=900, width=900)
cam = mujoco.MjvCamera()
mujoco.mjv_defaultFreeCamera(model, cam)
cam.azimuth, cam.elevation, cam.distance = 0, -8, 1.6
cam.lookat[:] = [0.0, 0.52, 0.77]

renderer.update_scene(data, camera=cam)
for i in range(renderer.scene.ngeom):
    g = renderer.scene.geoms[i]
    if g.objtype == mujoco.mjtObj.mjOBJ_GEOM and model.geom_bodyid[g.objid] in hide_bids:
        g.rgba[3] = 0.0
img = renderer.render()
renderer.close()
Image.fromarray(img).save("/tmp/claude-1000/-home-moos-dev-ws-dual-arms/54d39449-6cf4-4ae9-9d90-5aa2e3f0283c/scratchpad/handshake_static.png")
print("저장 완료")
