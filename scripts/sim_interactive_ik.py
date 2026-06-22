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
        print(f"Failed to load XML: {e}")
        return

    # Find IDs
    body_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "left_link7")
    body_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    mocap_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_left")
    mocap_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_right")
    
    mocap_left_id = model.body_mocapid[mocap_left]
    mocap_right_id = model.body_mocapid[mocap_right]

    # Pre-allocate
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))

    # Initial Sync
    mujoco.mj_kinematics(model, data)
    data.mocap_pos[mocap_left_id] = data.xpos[body_left].copy()
    data.mocap_pos[mocap_right_id] = data.xpos[body_right].copy()
    data.mocap_quat[mocap_left_id] = data.xquat[body_left].copy()
    data.mocap_quat[mocap_right_id] = data.xquat[body_right].copy()

    print("=========================================================")
    print("INTERACTIVE IK RUNNING")
    print("1. Double-click the RED or BLUE sphere.")
    print("2. Hold CTRL + Right Mouse Button Drag to move.")
    print("3. Press 'C' to toggle Collision Avoidance.")
    print("=========================================================")

    # State variables
    enable_collision = False
    viewer_handle = None
    
    def update_overlay():
        if viewer_handle is not None:
            state_str = "ENABLE" if enable_collision else "DISABLE"
            viewer_handle.set_texts([
                (mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPLEFT, "Collision Avoidance:", state_str)
            ])

    def key_callback(keycode):
        nonlocal enable_collision
        if chr(keycode).lower() == 'c':
            enable_collision = not enable_collision
            state_str = "ON" if enable_collision else "OFF"
            print(f"\n>>> Collision Avoidance: {state_str} <<<\n")
            update_overlay()

    # IK Hyperparameters
    step_size = 1.0  # Integration gain (increased to restore movement speed)
    damping = 0.1    # Increased damping to avoid singularities
    max_dq = 0.5     # Speed limit to prevent shaking

    last_print_time = time.time()

    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        viewer_handle = viewer
        update_overlay()
        while viewer.is_running():
            start_t = time.time()
            
            # Reset velocities for this step
            dq_total = np.zeros(model.nv)
            log_str = ""
            
            # --- Solve for each arm ---
            for side, body_id, mocap_id in [("left", body_left, mocap_left_id), 
                                            ("right", body_right, mocap_right_id)]:
                # 1. Position Error (3D only for stability)
                target_pos = data.mocap_pos[mocap_id]
                current_pos = data.xpos[body_id]
                error_pos = target_pos - current_pos
                err_norm = np.linalg.norm(error_pos)
                
                # 2. Jacobian (3 x nv)
                mujoco.mj_jacBody(model, data, jacp, jacr, body_id)
                J = jacp  # Only use position Jacobian
                
                # 3. Damped Least Squares
                JJT = J @ J.T
                dq_side = J.T @ np.linalg.inv(JJT + damping**2 * np.eye(3)) @ error_pos
                
                # Prevent explosive jumps by scaling the vector (preserves direction)
                dq_norm = np.linalg.norm(dq_side)
                if dq_norm > max_dq:
                    dq_side *= (max_dq / dq_norm)
                    
                dq_total += dq_side
                log_str += f"[{side}] err_pos:{err_norm:.3f} | "

            # Periodic logging
            if start_t - last_print_time > 1.0:
                print(log_str + f"(Collisions: {'ON' if enable_collision else 'OFF'})")
                last_print_time = start_t

            # --- Update state with Collision Check ---
            qpos_backup = data.qpos.copy()
            
            # Integrate and apply limits
            mujoco.mj_integratePos(model, data.qpos, dq_total, step_size)
            for i in range(model.njnt):
                if model.jnt_type[i] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE):
                    q_adr = model.jnt_qposadr[i]
                    data.qpos[q_adr] = np.clip(data.qpos[q_adr], model.jnt_range[i, 0], model.jnt_range[i, 1])
            
            mujoco.mj_kinematics(model, data)
            
            # If collision avoidance is ON, check for contacts
            if enable_collision:
                mujoco.mj_collision(model, data)
                if data.ncon > 0:
                    # Collision detected! Revert to backup
                    data.qpos[:] = qpos_backup
                    mujoco.mj_kinematics(model, data)

            viewer.sync()

            # Wait to maintain ~60Hz
            elapsed = time.time() - start_t
            if elapsed < 0.016:
                time.sleep(0.016 - elapsed)

if __name__ == "__main__":
    run_interactive_ik()
