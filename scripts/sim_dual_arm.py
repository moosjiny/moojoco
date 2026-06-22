import os
os.environ['MUJOCO_GL'] = 'egl'  # GPU EGL 렌더링

import mujoco
import rerun as rr
import numpy as np
import time
import trimesh
import gc

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
MESH_DIR  = "/home/moos/dev_ws/dual_arms/meshes/"

ROBOT_ROOT = "world/robot_v4"

OFFSETS_LEFT = {
    "base_link": 0, "link1": 62.5, "link2": 121.5, "link3": 188.0,
    "link4": 342.5, "link5": 438.0, "link6": 558.5, "link7": 558.5
}
OFFSETS_RIGHT = {
    "base_link": 0, "link1": 62.5, "link2": 120.5, "link3": 187.0,
    "link4": 342.5, "link5": 438.0, "link6": 558.5, "link7": 558.5
}

CAM_W, CAM_H = 640, 480
WRIST_W, WRIST_H = 320, 240

def run_sim():
    model = mujoco.MjModel.from_xml_path(URDF_PATH)
    data  = mujoco.MjData(model)

    # GPU EGL 렌더러 생성
    renderer_top   = mujoco.Renderer(model, height=CAM_H,   width=CAM_W)
    renderer_front = mujoco.Renderer(model, height=CAM_H,   width=CAM_W)
    renderer_lw    = mujoco.Renderer(model, height=WRIST_H, width=WRIST_W)
    renderer_rw    = mujoco.Renderer(model, height=WRIST_H, width=WRIST_W)

    rr.init("OpenArm_WowRobo_V4", spawn=False)
    # server_memory_limit: 서버 버퍼 상한 설정 (초과 시 오래된 데이터 자동 제거)
    server_uri = rr.serve_grpc(grpc_port=9876, server_memory_limit="512MB")
    rr.serve_web_viewer(web_port=9090, connect_to=server_uri)
    print("Dual-arm sim started (EGL GPU rendering)")

    # --- 정적 메쉬 사전 로깅 ---
    rr.log("world/floor", rr.Boxes3D(half_sizes=[[1.5, 1.5, 0.001]], colors=[[180, 180, 180]]), static=True)

    base_mesh_path = os.path.join(MESH_DIR, "base_link.stl")
    if os.path.exists(base_mesh_path):
        bm = trimesh.load(base_mesh_path)
        rr.log(f"{ROBOT_ROOT}/central_base/visual",
               rr.Mesh3D(vertex_positions=bm.vertices * 0.001,
                         triangle_indices=bm.faces,
                         vertex_normals=bm.vertex_normals,
                         vertex_colors=np.tile([180, 180, 180], (len(bm.vertices), 1))), static=True)

    mesh_map = {f"link{i}": f"link{i}.stl" for i in range(1, 8)}
    STL_OFFSETS = {
        "base_link": [0.0, 0.0, 0.0],
        "link1": [0.0, 0.0, 62.5],
        "link2": [-30.1, 0.0, 122.5],
        "link3": [0.0, 0.0, 188.75],
        "link4": [0.0, 31.5, 342.5],
        "link5": [0.0, 0.0, 438.0],
        "link6": [37.5, 0.0, 558.5],
        "link7": [0.0, 0.0, 558.5],
    }

    for name, file in mesh_map.items():
        path = os.path.join(MESH_DIR, file)
        if not os.path.exists(path):
            continue
        try:
            mesh = trimesh.load(path)
            num_v = len(mesh.vertices)
            offset = np.array(STL_OFFSETS.get(name, [0.0, 0.0, 0.0]))
            n_mesh = mesh.vertex_normals

            v_l = (mesh.vertices - offset) * 0.001
            rr.log(f"{ROBOT_ROOT}/left_{name}/visual",
                   rr.Mesh3D(vertex_positions=v_l, triangle_indices=mesh.faces,
                             vertex_normals=n_mesh,
                             vertex_colors=np.tile([40, 80, 200], (num_v, 1))), static=True)

            v_r_raw = mesh.vertices.copy()
            offset_r = offset.copy()
            if name in ["link1", "link2", "link3"]:
                v_r_raw[:, 0] = -v_r_raw[:, 0]
                offset_r[0] = -offset[0]
            v_r = (v_r_raw - offset_r) * 0.001
            rr.log(f"{ROBOT_ROOT}/right_{name}/visual",
                   rr.Mesh3D(vertex_positions=v_r, triangle_indices=mesh.faces,
                             vertex_normals=n_mesh,
                             vertex_colors=np.tile([200, 40, 40], (num_v, 1))), static=True)
        except Exception as e:
            print(f"Mesh load error {file}: {e}")

    finger_dir = os.path.join(MESH_DIR, "gripper")
    finger_parts = [("finger_0.obj", [180, 180, 180]), ("finger_1.obj", [30, 30, 30])]
    NF_OFFSET_MM = np.array([0.0,  50.0, 673.001])
    FL_OFFSET_MM = np.array([0.0, -50.0, 673.001])
    for part_file, color in finger_parts:
        p = os.path.join(finger_dir, part_file)
        if not os.path.exists(p):
            continue
        try:
            fmesh = trimesh.load(p)
            v_raw = np.asarray(fmesh.vertices)
            n_v = len(v_raw)
            v_nf = (v_raw - NF_OFFSET_MM) * 0.001
            v_fl_raw = v_raw.copy(); v_fl_raw[:, 1] = -v_fl_raw[:, 1]
            v_fl = (v_fl_raw - FL_OFFSET_MM) * 0.001
            faces_fl = fmesh.faces[:, ::-1]
            for side in ("left", "right"):
                rr.log(f"{ROBOT_ROOT}/{side}_finger_1/visual_{part_file}",
                       rr.Mesh3D(vertex_positions=v_nf, triangle_indices=fmesh.faces,
                                 vertex_normals=fmesh.vertex_normals,
                                 vertex_colors=np.tile(color, (n_v, 1))), static=True)
                rr.log(f"{ROBOT_ROOT}/{side}_finger_2/visual_{part_file}",
                       rr.Mesh3D(vertex_positions=v_fl, triangle_indices=faces_fl,
                                 vertex_colors=np.tile(color, (n_v, 1))), static=True)
        except Exception as e:
            print(f"Finger mesh error {part_file}: {e}")

    # --- 관절 스위프 설정 ---
    SWEEP_DURATION = 4.0
    sweep_items = []
    for i in range(model.njnt):
        jn = model.joint(i).name
        if "finger_joint2" in jn:
            continue
        pair_idx = None
        label = jn
        if "finger_joint1" in jn:
            side = jn.split("_")[0]
            pair_idx = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{side}_finger_joint2")
            label = f"{side}_gripper (open/close)"
        sweep_items.append((i, label, pair_idx))

    # 카메라 ID 확인
    cam_ids = {}
    for cam_name in ("cam_top", "cam_front", "cam_left_wrist", "cam_right_wrist"):
        cid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
        cam_ids[cam_name] = cid
        print(f"  Camera '{cam_name}': id={cid}")

    # --- 메인 루프 ---
    CAM_RENDER_EVERY = 3  # 카메라는 3프레임마다 1회 렌더 (약 10fps)
    start_time = time.time()
    frame = 0
    while True:
        t = time.time() - start_time
        cycle_t = t % (SWEEP_DURATION * len(sweep_items))
        item_idx = int(cycle_t // SWEEP_DURATION)
        phase = (cycle_t % SWEEP_DURATION) / SWEEP_DURATION

        j_idx, label, pair_idx = sweep_items[item_idx]
        lo, hi = model.jnt_range[j_idx]
        center = (lo + hi) / 2.0
        amp    = (hi - lo) / 2.0
        target = center + amp * np.sin(phase * 2 * np.pi)

        data.qpos[:] = 0.0
        data.qpos[model.jnt_qposadr[j_idx]] = target
        if pair_idx is not None:
            data.qpos[model.jnt_qposadr[pair_idx]] = target

        mujoco.mj_kinematics(model, data)

        # 시간 인덱스 설정: 프레임 시퀀스로 덮어쓰기 → 메모리 누적 방지
        rr.set_time("sim", sequence=frame)

        rr.log("status/sweep", rr.TextDocument(
            f"[{item_idx+1}/{len(sweep_items)}] {label}\n"
            f"qpos = {target:+.3f}   range = [{lo:+.3f}, {hi:+.3f}]"
        ))

        # Body transform 스트리밍
        for i in range(model.nbody):
            b_name = model.body(i).name
            if not b_name or b_name == "world":
                continue
            pos  = data.xpos[i]
            quat = data.xquat[i]
            rr.log(f"{ROBOT_ROOT}/{b_name}",
                   rr.Transform3D(translation=pos,
                                  rotation=rr.Quaternion(xyzw=[quat[1], quat[2], quat[3], quat[0]])))

        # GPU EGL 카메라 렌더링 (CAM_RENDER_EVERY 프레임마다 1회)
        if frame % CAM_RENDER_EVERY == 0:
            mujoco.mj_fwdPosition(model, data)

            renderer_top.update_scene(data, camera="cam_top")
            img = renderer_top.render()
            rr.log("cameras/top", rr.Image(img))
            del img

            renderer_front.update_scene(data, camera="cam_front")
            img = renderer_front.render()
            rr.log("cameras/front", rr.Image(img))
            del img

            renderer_lw.update_scene(data, camera="cam_left_wrist")
            img = renderer_lw.render()
            rr.log("cameras/left_wrist", rr.Image(img))
            del img

            renderer_rw.update_scene(data, camera="cam_right_wrist")
            img = renderer_rw.render()
            rr.log("cameras/right_wrist", rr.Image(img))
            del img

        # 300프레임마다 GC 강제 실행
        if frame % 300 == 0:
            gc.collect()

        frame += 1
        if frame % 30 == 0:
            print(f"frame={frame}  t={t:.1f}s  joint={label}")

        time.sleep(0.033)

if __name__ == "__main__":
    run_sim()
