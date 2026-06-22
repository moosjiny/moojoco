import mujoco
model = mujoco.MjModel.from_xml_path("/home/moos/dev_ws/dual_arms/urdf/dual_openarm.urdf")
print("Bodies:")
for i in range(model.nbody):
    print(model.body(i).name)
