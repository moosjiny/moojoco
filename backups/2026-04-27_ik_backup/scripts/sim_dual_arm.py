import mujoco
import rerun as rr
import numpy as np
import time
import os
import trimesh

# Configuration
URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
MESH_DIR = "/home/moos/dev_ws/dual_arms/meshes/"

# VERSIONED PATHS
ROBOT_ROOT = "world/robot_v4"

# FINAL TUNED OFFSETS (mm)
OFFSETS_LEFT = {
    "base_link": 0, "link1": 62.5, "link2": 121.5, "link3": 188.0,
    "link4": 342.5, "link5": 438.0, "link6": 558.5, "link7": 558.5
}
OFFSETS_RIGHT = {
    "base_link": 0, "link1": 62.5, "link2": 120.5, "link3": 187.0,
    "link4": 342.5, "link5": 438.0, "link6": 558.5, "link7": 558.5
}

def run_sim():
    # 1. Load MuJoCo Model
    try:
        model = mujoco.MjModel.from_xml_path(URDF_PATH)
        data = mujoco.MjData(model)
    except Exception as e:
        print(f"Failed to load URDF: {e}")
        return

    # 2. Initialize Rerun
    rr.init("OpenArm_WowRobo_V4", spawn=False)
    server_uri = rr.serve_grpc(grpc_port=9876)
    rr.serve_web_viewer(web_port=9090, connect_to=server_uri)
    
    print(f"Full-Color Zero-Gap Digital Twin V4 started.")


    
    ROBOT_ROOT = "world/robot_v4"
    rr.log("world/floor", rr.Boxes3D(half_sizes=[[1.5, 1.5, 0.001]], colors=[[25, 25, 25]]), static=True)
    
    # Unified Central Base Mesh
    base_mesh_path = os.path.join(MESH_DIR, "base_link.stl")
    if os.path.exists(base_mesh_path):
        base_mesh = trimesh.load(base_mesh_path)
        rr.log(f"{ROBOT_ROOT}/central_base/visual", 
               rr.Mesh3D(vertex_positions=base_mesh.vertices * 0.001,
                         triangle_indices=base_mesh.faces,
                         vertex_normals=base_mesh.vertex_normals,
                         vertex_colors=np.tile([80, 80, 80], (len(base_mesh.vertices), 1))), static=True)

    # Mesh Mapping
    mesh_map = {
        "link1": "link1.stl",
        "link2": "link2.stl",
        "link3": "link3.stl",
        "link4": "link4.stl",
        "link5": "link5.stl",
        "link6": "link6.stl",
        "link7": "link7.stl"
    }

    # Pre-log Arm Meshes with FULL VERTEX COLORING
    for name, file in mesh_map.items():
        path = os.path.join(MESH_DIR, file)
        if os.path.exists(path):
            try:
                mesh = trimesh.load(path)
                num_v = len(mesh.vertices)
                # EXACT 3D CAD OFFSETS
                # The STLs are exported from a global assembly. We must subtract the exact 3D coordinate 
                # of the joint to center the mesh at (0,0,0) before applying MuJoCo kinematics.
                # Format: [X, Y, Z] in mm.
                STL_OFFSETS = {
                    "base_link": [0.0, 0.0, 0.0],
                    "link1": [0.0, 0.0, 62.5],
                    "link2": [-30.1, 0.0, 122.5],
                    "link3": [0.0, 0.0, 188.75],
                    "link4": [0.0, 31.5, 342.5],
                    "link5": [0.0, 0.0, 438.0],
                    "link6": [37.5, 0.0, 558.5],
                    "link7": [0.0, 0.0, 558.5]
                }
                
                offset_3d = np.array(STL_OFFSETS.get(name, [0.0, 0.0, 0.0]))
                n_mesh = mesh.vertex_normals
                
                # LEFT (Deep Metallic Blue)
                v_l = (mesh.vertices - offset_3d) * 0.001
                colors_l = np.tile([40, 80, 200], (num_v, 1))
                rr.log(f"{ROBOT_ROOT}/left_{name}/visual", 
                       rr.Mesh3D(vertex_positions=v_l, 
                                 triangle_indices=mesh.faces,
                                 vertex_normals=n_mesh,
                                 vertex_colors=colors_l), static=True)

                # RIGHT (Deep Metallic Red)
                # The right arm is physically a mirror of the left arm in the X-axis ONLY for the lower arm.
                # links 4, 5, 6, 7 are assembled identically for both arms.
                v_r_raw = mesh.vertices.copy()
                offset_3d_r = offset_3d.copy()
                
                if name in ["link1", "link2", "link3"]:
                    v_r_raw[:, 0] = -v_r_raw[:, 0]
                    offset_3d_r[0] = -offset_3d[0]
                
                v_r = (v_r_raw - offset_3d_r) * 0.001
                colors_r = np.tile([200, 40, 40], (num_v, 1))
                rr.log(f"{ROBOT_ROOT}/right_{name}/visual", 
                       rr.Mesh3D(vertex_positions=v_r, 
                                 triangle_indices=mesh.faces,
                                 vertex_normals=n_mesh,
                                 vertex_colors=colors_r), static=True)

            except Exception as e: print(f"Error loading {file}: {e}")

    # Pre-log Gripper Finger Meshes (real OBJ from reazon-research/openarm-mjcf)
    # Each finger body uses two visual parts (gray body + black accent), both translated
    # by the official geom offsets in the finger body frame.
    finger_dir = os.path.join(MESH_DIR, "gripper")
    finger_parts = [
        ("finger_0.obj", [180, 180, 180]),  # robot_gray
        ("finger_1.obj", [30, 30, 30]),     # matte_black
    ]
    # Subtracted from raw mesh vertices (mm) to anchor mesh at the finger BODY origin.
    # Equivalent to MuJoCo geom pos (0, ∓0.05, -0.673001) m applied as v_body = v_mesh + geom_pos.
    NF_OFFSET_MM = np.array([0.0,  50.0, 673.001])    # non-flipped (used on *_finger_1, +Y body)
    FL_OFFSET_MM = np.array([0.0, -50.0, 673.001])    # Y-flipped (used on *_finger_2, -Y body)
    for part_file, color in finger_parts:
        p = os.path.join(finger_dir, part_file)
        if not os.path.exists(p):
            print(f"Missing finger mesh: {p}"); continue
        try:
            fmesh = trimesh.load(p)
            v_raw = np.asarray(fmesh.vertices)
            n_v = len(v_raw)
            # Non-flipped variant -> attached to *_finger_1 body (y > 0 side, joint axis +y)
            v_nf = (v_raw - NF_OFFSET_MM) * 0.001
            # Y-flipped variant -> attached to *_finger_2 body (y < 0 side, joint axis -y)
            v_fl_raw = v_raw.copy(); v_fl_raw[:, 1] = -v_fl_raw[:, 1]
            v_fl = (v_fl_raw - FL_OFFSET_MM) * 0.001
            # Flip face winding for the mirrored mesh so normals stay outward
            faces_fl = fmesh.faces[:, ::-1]

            for side in ("left", "right"):
                rr.log(f"{ROBOT_ROOT}/{side}_finger_1/visual_{part_file}",
                       rr.Mesh3D(vertex_positions=v_nf,
                                 triangle_indices=fmesh.faces,
                                 vertex_normals=fmesh.vertex_normals,
                                 vertex_colors=np.tile(color, (n_v, 1))), static=True)
                rr.log(f"{ROBOT_ROOT}/{side}_finger_2/visual_{part_file}",
                       rr.Mesh3D(vertex_positions=v_fl,
                                 triangle_indices=faces_fl,
                                 vertex_colors=np.tile(color, (n_v, 1))), static=True)
        except Exception as e:
            print(f"Error loading finger mesh {part_file}: {e}")

    # 3. Sequential joint-limit sweep
    # Drive one joint at a time through its full [lower, upper] range using a sine wave,
    # leaving all other joints at home (qpos=0). Finger pairs are swept together.
    SWEEP_DURATION = 4.0  # seconds per joint
    sweep_items = []      # list of (joint_idx, label, pair_joint_idx_or_None)
    for i in range(model.njnt):
        jn = model.joint(i).name
        if "finger_joint2" in jn:
            continue  # coupled with joint1
        pair_idx = None
        label = jn
        if "finger_joint1" in jn:
            side = jn.split("_")[0]
            pair_idx = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{side}_finger_joint2")
            label = f"{side}_gripper (open/close)"
        sweep_items.append((i, label, pair_idx))

    start_time = time.time()
    while True:
        t = time.time() - start_time
        cycle_t = t % (SWEEP_DURATION * len(sweep_items))
        item_idx = int(cycle_t // SWEEP_DURATION)
        phase = (cycle_t % SWEEP_DURATION) / SWEEP_DURATION

        j_idx, label, pair_idx = sweep_items[item_idx]
        lo, hi = model.jnt_range[j_idx]
        center = (lo + hi) / 2.0
        amp = (hi - lo) / 2.0
        target = center + amp * np.sin(phase * 2 * np.pi)

        data.qpos[:] = 0.0
        data.qpos[model.jnt_qposadr[j_idx]] = target
        if pair_idx is not None:
            data.qpos[model.jnt_qposadr[pair_idx]] = target

        mujoco.mj_kinematics(model, data)

        rr.log("status/sweep", rr.TextDocument(
            f"[{item_idx + 1}/{len(sweep_items)}] {label}\n"
            f"qpos = {target:+.3f}   range = [{lo:+.3f}, {hi:+.3f}]"
        ))

        for i in range(model.nbody):
            b_name = model.body(i).name
            if not b_name or b_name == "world": continue
            pos = data.xpos[i]
            quat = data.xquat[i]
            rr_quat = [quat[1], quat[2], quat[3], quat[0]]
            rr.log(f"{ROBOT_ROOT}/{b_name}", rr.Transform3D(translation=pos, rotation=rr.Quaternion(xyzw=rr_quat)))

        time.sleep(0.033)

if __name__ == "__main__":
    run_sim()
