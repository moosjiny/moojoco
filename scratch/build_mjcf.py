"""Convert dual_openarm.urdf to MJCF with actuators, tendons, equality, and contact disabled.

Re-run after editing the URDF (joint axes, links, etc.) to regenerate dual_openarm.xml.
"""
import mujoco

URDF = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.urdf"
OUT  = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"

ACTUATORS = [
    ("left_joint1_ctrl",   "left_joint_1",        -10,   10),
    ("left_joint2_ctrl",   "left_joint_2",        -12,   12),
    ("left_joint3_ctrl",   "left_joint_3",        -10,   10),
    ("left_joint4_ctrl",   "left_joint_4",        -10,   10),
    ("left_joint5_ctrl",   "left_joint_5",        -10,   10),
    ("left_joint6_ctrl",   "left_joint_6",        -10,   10),
    ("left_joint7_ctrl",   "left_joint_7",        -10,   10),
    ("left_finger_ctrl",   "left_finger_joint1",  -0.1,  0.1),
    ("right_joint1_ctrl",  "right_joint_1",       -10,   10),
    ("right_joint2_ctrl",  "right_joint_2",       -12,   12),
    ("right_joint3_ctrl",  "right_joint_3",       -10,   10),
    ("right_joint4_ctrl",  "right_joint_4",       -10,   10),
    ("right_joint5_ctrl",  "right_joint_5",       -10,   10),
    ("right_joint6_ctrl",  "right_joint_6",       -10,   10),
    ("right_joint7_ctrl",  "right_joint_7",       -10,   10),
    ("right_finger_ctrl",  "right_finger_joint1", -0.1,  0.1),
]

spec = mujoco.MjSpec.from_file(URDF)

# Physics-level contact is now enabled by default so we can detect collisions.
# We will still drive via mj_kinematics, but use mj_collision to check for overlaps.
for name, joint, lo, hi in ACTUATORS:
    a = spec.add_actuator()
    a.name = name
    a.target = joint
    a.trntype = mujoco.mjtTrn.mjTRN_JOINT
    a.ctrlrange = [lo, hi]
    a.ctrllimited = 1

for side in ("left", "right"):
    t = spec.add_tendon()
    t.name = f"{side}_finger_split"
    t.wrap_joint(f"{side}_finger_joint1", 0.5)
    t.wrap_joint(f"{side}_finger_joint2", 0.5)

for side in ("left", "right"):
    eq = spec.add_equality()
    eq.type = mujoco.mjtEq.mjEQ_JOINT
    eq.name1 = f"{side}_finger_joint1"
    eq.name2 = f"{side}_finger_joint2"
    eq.solimp = [0.95, 0.99, 0.001, 0.5, 2]
    eq.solref = [0.005, 1]
    eq.data = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]

# --- Add Mocap Targets for IK ---
for side in ("left", "right"):
    b = spec.worldbody.add_body()
    b.name = f"target_{side}"
    b.mocap = True
    # Initial positions matching the robot hands at qpos=0
    b.pos = [0, -0.541, 0.773] if side == "left" else [0, 0.541, 0.773]
    g = b.add_geom()
    g.type = mujoco.mjtGeom.mjGEOM_SPHERE
    g.pos = [0, 0, 0]
    g.size = [0.08, 0, 0]
    g.rgba = [1, 0, 0, 0.5] if side == "left" else [0, 0, 1, 0.5]
    # contype=2 so it can be selected by mouse, but conaffinity=0 so it doesn't physically collide with the robot.
    g.contype = 2
    g.conaffinity = 0

m = spec.compile()
xml_str = spec.to_xml()

# --- Set background to light grey ---
visual_xml = """
  <visual>
    <skybox rgb="0.6 0.6 0.6"/>
  </visual>
"""
if "<mujoco>" in xml_str:
    xml_str = xml_str.replace("<mujoco>", "<mujoco>" + visual_xml)

with open(OUT, "w") as f:
    f.write(xml_str)
print(f"Saved {OUT} ({len(xml_str)} bytes)")
print(f"  njnt={m.njnt}  nu={m.nu}  ntendon={m.ntendon}  neq={m.neq}")
print(f"  contact disabled: {bool(m.opt.disableflags & mujoco.mjtDisableBit.mjDSBL_CONTACT)}")
