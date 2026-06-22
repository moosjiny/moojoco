import mujoco
import rerun as rr
import numpy as np
import time
import os
import trimesh

# Configuration
URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.urdf"
MESH_DIR = "/home/moos/dev_ws/dual_arms/meshes/"

def run_sim():
    # 1. Load MuJoCo Model
    try:
        # Load and disable self-collision for stability in digital twin mode
        model = mujoco.MjModel.from_xml_path(URDF_PATH)
        data = mujoco.MjData(model)
    except Exception as e:
        print(f"Failed to load URDF: {e}")
        return

    # 2. Initialize Rerun
    rr.init("OpenArm_WowRobo_Bimanual", spawn=False)
    server_uri = rr.serve_grpc(grpc_port=9876)
    rr.serve_web_viewer(web_port=9090, connect_to=server_uri)
    
    print(f"Digital Twin Simulation started.")

    # Setup Rerun Scene
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    rr.log("world/floor", rr.Boxes3D(half_sizes=[[1.5, 1.5, 0.001]], colors=[[25, 25, 25]]), static=True)

    # Log Static Torso
    rr.log("world/robot/pillar", 
           rr.Boxes3D(half_sizes=[[0.04, 0.04, 0.4]], centers=[[0, 0, 0.4]], colors=[[15, 15, 15]]),
           static=True)
    rr.log("world/robot/shoulder", 
           rr.Boxes3D(half_sizes=[[0.075, 0.175, 0.1]], centers=[[0, 0, 0.8]], colors=[[15, 15, 15]]),
           static=True)

    # Pre-log Arm Meshes
    mesh_map = {
        "left_base_link": "base_link.stl",
        "right_base_link": "base_link.stl"
    }
    for i in range(1, 8):
        mesh_map[f"left_link{i}"] = f"link{i}.stl"
        mesh_map[f"right_link{i}"] = f"link{i}.stl"

    for body_name, mesh_file in mesh_map.items():
        path = os.path.join(MESH_DIR, mesh_file)
        if os.path.exists(path):
            try:
                mesh = trimesh.load(path)
                # Scale 0.001 for mm to m
                rr.log(f"world/robot/{body_name}/visual", 
                       rr.Mesh3D(vertex_positions=mesh.vertices * 0.001, 
                                 triangle_indices=mesh.faces,
                                 vertex_normals=mesh.vertex_normals,
                                 vertex_colors=[180, 180, 180] if "link" in body_name else [150, 150, 150]),
                       static=True)
            except Exception as e:
                print(f"Failed to load mesh {mesh_file}: {e}")

    # 3. Simulation Loop
    start_time = time.time()
    while True:
        t = time.time() - start_time
        
        # Kinematic update (no mj_step to prevent explosions)
        for i in range(model.nq):
            # Slow swaying motion
            data.qpos[i] = np.sin(t * 0.5 + (i * 0.2)) * 0.1
        
        mujoco.mj_kinematics(model, data)
        mujoco.mj_comPos(model, data) # Required for some transforms

        # Log Transforms
        for i in range(model.nbody):
            name = model.body(i).name
            if not name or name == "world": continue
            
            # Use xpos (world position)
            pos = data.xpos[i]
            quat = data.xquat[i]
            rr_quat = [quat[1], quat[2], quat[3], quat[0]] # xyzw
            
            rr.log(f"world/robot/{name}", 
                   rr.Transform3D(translation=pos, rotation=rr.Quaternion(xyzw=rr_quat)))
            
        time.sleep(0.033)

if __name__ == "__main__":
    run_sim()
