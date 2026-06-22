import mujoco
import rerun as rr
import numpy as np
import time
import os
import trimesh

# Configuration
URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.urdf"
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

    # Setup Rerun Scene
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    rr.log("world/floor", rr.Boxes3D(half_sizes=[[1.5, 1.5, 0.001]], colors=[[25, 25, 25]]), static=True)

    # Mesh Mapping
    mesh_map = {
        "base_link": "base_link.stl", "link1": "link1.stl", "link2": "link2.stl", "link3": "link3.stl",
        "link4": "link4.stl", "link5": "link5.stl", "link6": "link6.stl", "link7": "link7.stl"
    }

    # Pre-log Arm Meshes with FULL VERTEX COLORING
    for name, file in mesh_map.items():
        path = os.path.join(MESH_DIR, file)
        if os.path.exists(path):
            try:
                mesh = trimesh.load(path)
                center_xy = (mesh.bounds[0][:2] + mesh.bounds[1][:2]) / 2.0
                num_v = len(mesh.vertices)
                
                # EXACT OFFSETS (Calculated from URDF cumulative joint positions)
                # These must match the STL's baked-in global position to center them at the joint.
                OFFSETS = {
                    "base_link": 0.0,
                    "link1": 62.5,
                    "link2": 122.5,
                    "link3": 188.75,
                    "link4": 342.5,
                    "link5": 438.0,
                    "link6": 558.5,
                    "link7": 558.5
                }
                z_offset = OFFSETS.get(name, 0.0)
                n_mesh = mesh.vertex_normals
                
                # LEFT (Deep Metallic Blue)
                v_l = (mesh.vertices - np.array([center_xy[0], center_xy[1], z_offset])) * 0.001
                colors_l = np.tile([40, 80, 200], (num_v, 1))
                rr.log(f"{ROBOT_ROOT}/left_{name}/visual", 
                       rr.Mesh3D(vertex_positions=v_l, 
                                 triangle_indices=mesh.faces,
                                 vertex_normals=n_mesh,
                                 vertex_colors=colors_l), static=True)

                # RIGHT (Deep Metallic Red)
                v_r = (mesh.vertices - np.array([center_xy[0], center_xy[1], z_offset])) * 0.001
                colors_r = np.tile([200, 40, 40], (num_v, 1))
                rr.log(f"{ROBOT_ROOT}/right_{name}/visual", 
                       rr.Mesh3D(vertex_positions=v_r, 
                                 triangle_indices=mesh.faces,
                                 vertex_normals=n_mesh,
                                 vertex_colors=colors_r), static=True)
            except Exception as e: print(f"Error loading {file}: {e}")

    # 3. Simulation Loop
    start_time = time.time()
    while True:
        t = time.time() - start_time
        for i in range(model.nq):
            data.qpos[i] = np.sin(t * 0.4 + (i * 0.15)) * 0.1
        
        mujoco.mj_kinematics(model, data)

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
