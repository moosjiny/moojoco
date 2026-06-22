import mujoco
import mujoco.viewer
import numpy as np
import time
import threading
import csv

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import JointState
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

class DualArmIKNode(Node):
    def __init__(self):
        super().__init__('dual_arm_ik_sim')
        
        self.left_vel = np.zeros(3)
        self.right_vel = np.zeros(3)
        
        self.left_pose = None
        self.right_pose = None
        
        self.sub_left_vel = self.create_subscription(
            Twist, '/target_left/cmd_vel', self.left_cmd_callback, 10)
        self.sub_right_vel = self.create_subscription(
            Twist, '/target_right/cmd_vel', self.right_cmd_callback, 10)
            
        self.sub_left_pose = self.create_subscription(
            PoseStamped, '/target_left/pose_cmd', self.left_pose_callback, 10)
        self.sub_right_pose = self.create_subscription(
            PoseStamped, '/target_right/pose_cmd', self.right_pose_callback, 10)
            
        # Use Best Effort QoS for high-frequency state updates
        js_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=1
        )
        self.pub_joint_states = self.create_publisher(JointState, '/joint_states', js_qos)
        
        # Publishers to sync hand position back to RViz markers
        self.pub_left_hand = self.create_publisher(PoseStamped, '/target_left/hand_pose', 10)
        self.pub_right_hand = self.create_publisher(PoseStamped, '/target_right/hand_pose', 10)
            
        self.get_logger().info("DualArmIKNode Initialized. Listening to cmd_vel and pose_cmd")

    def left_cmd_callback(self, msg):
        self.left_vel[0] = msg.linear.x
        self.left_vel[1] = msg.linear.y
        self.left_vel[2] = msg.linear.z

    def right_cmd_callback(self, msg):
        self.right_vel[0] = msg.linear.x
        self.right_vel[1] = msg.linear.y
        self.right_vel[2] = msg.linear.z
        
    def left_pose_callback(self, msg):
        self.left_pose = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z])
        
    def right_pose_callback(self, msg):
        self.right_pose = np.array([msg.pose.position.x, msg.pose.position.y, msg.pose.position.z])

def run_ros2_ik():
    URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
    
    try:
        model = mujoco.MjModel.from_xml_path(URDF_PATH)
        data = mujoco.MjData(model)
    except Exception as e:
        print(f"Failed to load XML: {e}")
        return

    # Initialize ROS2 Node in a background thread
    rclpy.init()
    node = DualArmIKNode()
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    # Find IDs
    body_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "left_link7")
    body_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    mocap_left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_left")
    mocap_right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target_right")
    
    mocap_left_id = model.body_mocapid[mocap_left]
    mocap_right_id = model.body_mocapid[mocap_right]

    # Extract all joint names for ROS2 JointState publishing
    joint_names = []
    for i in range(model.njnt):
        if model.jnt_type[i] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
            joint_names.append(name)

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
    print("ROS2 IK SIMULATION RUNNING")
    print("Use teleop_twist_keyboard to publish to /target_left/cmd_vel")
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
            update_overlay()

    # IK Hyperparameters (Ultra-stable)
    step_size = 0.05 # Significantly reduced to 5% to eliminate oscillations
    damping = 0.5    # Maintain high damping
    max_dq = 0.05    # Further limit joint speed (rad/step)

    log_file = open("/home/moos/dev_ws/dual_arms/scratch/ik_debug_log.csv", "w", newline="")
    log_writer = csv.writer(log_file)
    log_writer.writerow(["time", "l_err", "r_err", "dq_norm", "ncon", "l_x", "l_y", "l_z", "tl_x", "tl_y", "tl_z", "r_x", "r_y", "r_z", "tr_x", "tr_y", "tr_z"])

    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        viewer_handle = viewer
        update_overlay()
        
        start_time = time.time()
        last_t = start_time
        
        while viewer.is_running():
            current_t = time.time()
            dt = current_t - last_t
            last_t = current_t
            
            # 0. Apply Mouse Perturbations (from Ctrl+Drag)
            mujoco.mjv_applyPerturbPose(model, data, viewer.perturb, 0)
            
            # 1. Update Mocap target positions
            vel_scale = 0.5  # Max speed 0.5 m/s
            
            # Left Arm Mocap
            if node.left_pose is not None:
                data.mocap_pos[mocap_left_id] = node.left_pose
                node.left_pose = None # Consume command
            else:
                # Keyboard Velocity Command (Velocity control mode)
                data.mocap_pos[mocap_left_id] += node.left_vel * vel_scale * dt
                
            # Right Arm Mocap
            if node.right_pose is not None:
                data.mocap_pos[mocap_right_id] = node.right_pose
                node.right_pose = None # Consume command
            else:
                # Keyboard Velocity Command (Velocity control mode)
                data.mocap_pos[mocap_right_id] += node.right_vel * vel_scale * dt
            
            # Reset velocities for IK step
            dq_total = np.zeros(model.nv)
            
            # --- Solve for each arm ---
            for side, body_id, mocap_id in [("left", body_left, mocap_left_id), 
                                            ("right", body_right, mocap_right_id)]:
                target_pos = data.mocap_pos[mocap_id]
                current_pos = data.xpos[body_id]
                error_pos = target_pos - current_pos
                
                mujoco.mj_jacBody(model, data, jacp, jacr, body_id)
                J = jacp  # Only use position Jacobian
                
                JJT = J @ J.T
                dq_side = J.T @ np.linalg.inv(JJT + damping**2 * np.eye(3)) @ error_pos
                
                dq_norm = np.linalg.norm(dq_side)
                if dq_norm > max_dq:
                    dq_side *= (max_dq / dq_norm)
                    
                dq_total += dq_side

            # --- Update state with Collision Check ---
            qpos_backup = data.qpos.copy()
            
            # Integrate and apply limits
            mujoco.mj_integratePos(model, data.qpos, dq_total, step_size)
            for i in range(model.njnt):
                if model.jnt_type[i] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE):
                    q_adr = model.jnt_qposadr[i]
                    data.qpos[q_adr] = np.clip(data.qpos[q_adr], model.jnt_range[i, 0], model.jnt_range[i, 1])
            
            mujoco.mj_kinematics(model, data)
            
            # Collision Check
            if enable_collision:
                mujoco.mj_collision(model, data)
                if data.ncon > 0:
                    data.qpos[:] = qpos_backup
                    mujoco.mj_kinematics(model, data)
                    
            # Publish Joint States to ROS2 (~30Hz or matching loop speed)
            # Use current_t to avoid spamming if loop runs faster, but this loop has time.sleep so it's ~60Hz
            js_msg = JointState()
            js_msg.header.stamp = node.get_clock().now().to_msg()
            js_msg.name = joint_names
            js_msg.position = [data.qpos[model.jnt_qposadr[i]] for i in range(model.njnt) if model.jnt_type[i] in (mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE)]
            node.pub_joint_states.publish(js_msg)
            
            # Publish Actual Hand Poses to RViz
            hp_msg = PoseStamped()
            hp_msg.header.stamp = node.get_clock().now().to_msg()
            hp_msg.header.frame_id = "world"
            
            # Left
            hp_msg.pose.position.x = data.xpos[body_left][0]
            hp_msg.pose.position.y = data.xpos[body_left][1]
            hp_msg.pose.position.z = data.xpos[body_left][2]
            node.pub_left_hand.publish(hp_msg)
            
            # Right
            hp_msg.pose.position.x = data.xpos[body_right][0]
            hp_msg.pose.position.y = data.xpos[body_right][1]
            hp_msg.pose.position.z = data.xpos[body_right][2]
            node.pub_right_hand.publish(hp_msg)
            
            # Write to CSV log
            left_err = np.linalg.norm(data.mocap_pos[mocap_left_id] - data.xpos[body_left])
            right_err = np.linalg.norm(data.mocap_pos[mocap_right_id] - data.xpos[body_right])
            log_writer.writerow([
                current_t - start_time,
                left_err, right_err,
                np.linalg.norm(dq_total),
                data.ncon,
                data.xpos[body_left][0], data.xpos[body_left][1], data.xpos[body_left][2],
                data.mocap_pos[mocap_left_id][0], data.mocap_pos[mocap_left_id][1], data.mocap_pos[mocap_left_id][2],
                data.xpos[body_right][0], data.xpos[body_right][1], data.xpos[body_right][2],
                data.mocap_pos[mocap_right_id][0], data.mocap_pos[mocap_right_id][1], data.mocap_pos[mocap_right_id][2]
            ])

            viewer.sync()

            # Wait to maintain ~60Hz
            elapsed = time.time() - current_t
            if elapsed < 0.016:
                time.sleep(0.016 - elapsed)

    rclpy.shutdown()
    spin_thread.join()

if __name__ == "__main__":
    run_ros2_ik()
