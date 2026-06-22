import mujoco
import mujoco.viewer
import numpy as np
import time

def run_interactive_ik():
    URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
    
    try:
        model = mujoco.MjModel.from_xml_path(URDF_PATH)
        data = mujoco.MjData(model)
    except Exception as e:
        print(f"Failed to load XML. Make sure to run build_mjcf.py first! Error: {e}")
        return

    # Target bodies (End effectors)
    body_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "left_link7")
    body_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    
    # Mocap bodies (User drags these)
    mocap_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_left")
    mocap_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_right")
    
    if mocap_left < 0 or mocap_right < 0:
        print("Mocap bodies not found! Please run build_mjcf.py.")
        return

    mocap_left_id = model.body_mocapid[mocap_left]
    mocap_right_id = model.body_mocapid[mocap_right]

    # Pre-allocate jacobian arrays (3 x nv)
    jacp_left = np.zeros((3, model.nv))
    jacr_left = np.zeros((3, model.nv))
    jacp_right = np.zeros((3, model.nv))
    jacr_right = np.zeros((3, model.nv))

    # Initial kinematics calculation
    mujoco.mj_kinematics(model, data)
    
    # Move mocap targets to current arm positions initially
    data.mocap_pos[mocap_left_id] = data.xpos[body_left]
    data.mocap_pos[mocap_right_id] = data.xpos[body_right]

    print("=========================================================")
    print("Interactive IK Mode Started!")
    print("Usage: ")
    print("  1. Double click on the red/blue sphere (Mocap target).")
    print("  2. Hold 'Ctrl' and drag with the Right Mouse Button.")
    print("  3. The arm will follow the target using IK.")
    print("=========================================================")

    # Launch native viewer
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            step_start = time.time()
            
            # --- IK for Left Arm ---
            err_pos_left = data.mocap_pos[mocap_left_id] - data.xpos[body_left]
            mujoco.mj_jacBody(model, data, jacp_left, jacr_left, body_left)
            
            # Damped Least Squares
            lambda_sq = 0.01
            J = jacp_left
            J_T = J.T
            J_hash_left = J_T @ np.linalg.inv(J @ J_T + lambda_sq * np.eye(3))
            dq_left = J_hash_left @ err_pos_left
            
            # --- IK for Right Arm ---
            err_pos_right = data.mocap_pos[mocap_right_id] - data.xpos[body_right]
            mujoco.mj_jacBody(model, data, jacp_right, jacr_right, body_right)
            
            J = jacp_right
            J_T = J.T
            J_hash_right = J_T @ np.linalg.inv(J @ J_T + lambda_sq * np.eye(3))
            dq_right = J_hash_right @ err_pos_right
            
            # Sum up velocities (they operate on orthogonal joints mostly, 
            # so summing is fine for independent arms)
            dq = dq_left + dq_right
            dq = np.clip(dq, -1.0, 1.0) # Prevent explosive jumps
            
            # Integrate qpos
            dt = 0.05
            mujoco.mj_integratePos(model, data.qpos, dq, dt)
            
            # Enforce joint limits
            for i in range(model.njnt):
                if model.jnt_type[i] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE):
                    q_idx = model.jnt_qposadr[i]
                    data.qpos[q_idx] = np.clip(data.qpos[q_idx], model.jnt_range[i, 0], model.jnt_range[i, 1])

            # Update kinematics
            mujoco.mj_kinematics(model, data)
            viewer.sync()

            # Control loop rate (approx 30 FPS)
            time_until_next_step = 0.033 - (time.time() - step_start)
            if time_until_next_step > 0:
                time.sleep(time_until_next_step)

if __name__ == "__main__":
    run_interactive_ik()
