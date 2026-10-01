import os
os.environ['MUJOCO_GL'] = 'egl'  # GPU EGL 렌더링

import mujoco
import rerun as rr
import rerun.blueprint as rrb
import numpy as np
import time
import trimesh
import gc
import http.server
import socketserver
import threading

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
MESH_DIR  = "/home/moos/dev_ws/dual_arms/meshes/"
WEB_DIR   = "/home/moos/dev_ws/dual_arms/web/rerun"

ROBOT_ROOT = "world/robot_v4"

class AutoConnectHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress verbose access logs

def start_web_viewer(port=9090):
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("0.0.0.0", port), AutoConnectHTTPHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

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
    server_uri = rr.serve_grpc(grpc_port=9876, server_memory_limit="1GB")
    if os.path.exists(os.path.join(WEB_DIR, "re_viewer_bg.wasm")):
        start_web_viewer(port=9090)
    else:
        rr.serve_web_viewer(web_port=9090, connect_to=server_uri)
    print("Dual-arm sim started (EGL GPU rendering)")
    print("Auto-connecting Web Viewer: http://hb5u.hyperbook.com:9090")
    print(f"Direct gRPC Proxy URI: {server_uri}")

    # --- Blueprint 설정: 3D 로봇 뷰어를 기본 중앙 화면으로 강제 배치 ---
    blueprint = rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial3DView(
                origin="world",
                name="🤖 Dual-Arm Robot (3D View)",
            ),
            rrb.Vertical(
                rrb.Spatial2DView(origin="cameras/top", name="Top Camera"),
                rrb.Spatial2DView(origin="cameras/front", name="Front Camera"),
                rrb.TextDocumentView(origin="status/sweep", name="Joint Sweep Status"),
            ),
            column_shares=[3, 1],
        )
    )
    rr.send_blueprint(blueprint)

    # 바닥면
    rr.log("world/floor", rr.Boxes3D(half_sizes=[[1.5, 1.5, 0.001]], colors=[[160, 160, 160]]), static=True)

    # --- 3D 메쉬 데이터 메모리 사전 로드 ---
    mesh_cache = {}
    base_mesh_path = os.path.join(MESH_DIR, "base_link.stl")
    if os.path.exists(base_mesh_path):
        try:
            bm = trimesh.load(base_mesh_path)
            mesh_cache["base"] = {
                "v": bm.vertices * 0.001,
                "f": bm.faces,
                "n": bm.vertex_normals,
                "c": np.tile([180, 180, 180], (len(bm.vertices), 1))
            }
        except Exception as e:
            print(f"Base mesh load error: {e}")

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

    mesh_map = {f"link{i}": f"link{i}.stl" for i in range(1, 8)}
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
            v_r_raw = mesh.vertices.copy()
            offset_r = offset.copy()
            if name in ["link1", "link2", "link3"]:
                v_r_raw[:, 0] = -v_r_raw[:, 0]
                offset_r[0] = -offset[0]
            v_r = (v_r_raw - offset_r) * 0.001

            mesh_cache[f"left_{name}"] = {
                "v": v_l, "f": mesh.faces, "n": n_mesh,
                "c": np.tile([56, 189, 248], (num_v, 1))  # Vivid Sky Blue
            }
            mesh_cache[f"right_{name}"] = {
                "v": v_r, "f": mesh.faces, "n": n_mesh,
                "c": np.tile([244, 63, 94], (num_v, 1))   # Vivid Rose Red
            }
        except Exception as e:
            print(f"Mesh load error {file}: {e}")

    finger_dir = os.path.join(MESH_DIR, "gripper")
    finger_parts = [("finger_0.obj", [200, 200, 200]), ("finger_1.obj", [40, 40, 40])]
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
                mesh_cache[f"{side}_finger_1_{part_file}"] = {
                    "v": v_nf, "f": fmesh.faces, "n": fmesh.vertex_normals,
                    "c": np.tile(color, (n_v, 1))
                }
                mesh_cache[f"{side}_finger_2_{part_file}"] = {
                    "v": v_fl, "f": faces_fl, "n": fmesh.vertex_normals,
                    "c": np.tile(color, (n_v, 1))
                }
        except Exception as e:
            print(f"Finger mesh error {part_file}: {e}")

    def log_robot_meshes(is_static=False):
        """메쉬를 Rerun에 전송 (버퍼 순환 시 재전송하여 신규 접속 클라이언트에도 항상 표시)"""
        if "base" in mesh_cache:
            m = mesh_cache["base"]
            rr.log(f"{ROBOT_ROOT}/base_plate/visual",
                   rr.Mesh3D(vertex_positions=m["v"], triangle_indices=m["f"],
                             vertex_normals=m["n"], vertex_colors=m["c"]), static=is_static)
        for key, m in mesh_cache.items():
            if key == "base":
                continue
            if "finger" in key:
                parts = key.split("_")
                side = parts[0]
                f_idx = parts[2]
                p_file = "_".join(parts[3:])
                rr.log(f"{ROBOT_ROOT}/{side}_finger_{f_idx}/visual_{p_file}",
                       rr.Mesh3D(vertex_positions=m["v"], triangle_indices=m["f"],
                                 vertex_normals=m["n"], vertex_colors=m["c"]), static=is_static)
            else:
                rr.log(f"{ROBOT_ROOT}/{key}/visual",
                       rr.Mesh3D(vertex_positions=m["v"], triangle_indices=m["f"],
                                 vertex_normals=m["n"], vertex_colors=m["c"]), static=is_static)

    # 초기 1회 로깅
    log_robot_meshes(is_static=True)

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

    # --- 메인 루프 ---
    CAM_RENDER_EVERY = 3  # 카메라는 3프레임마다 1회 렌더
    start_time = time.time()
    frame = 0

    # 연결 관계 정의 (스켈레톤 라인용)
    left_chain = ["shoulder_block", "left_base_link", "left_link1", "left_link2", "left_link3", "left_link4", "left_link5", "left_link6", "left_link7", "left_finger_1"]
    right_chain = ["shoulder_block", "right_base_link", "right_link1", "right_link2", "right_link3", "right_link4", "right_link5", "right_link6", "right_link7", "right_finger_1"]

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

        # 시간 인덱스 설정
        rr.set_time("sim", sequence=frame)

        rr.log("status/sweep", rr.TextDocument(
            f"[{item_idx+1}/{len(sweep_items)}] {label}\n"
            f"qpos = {target:+.3f} rad   range = [{lo:+.3f}, {hi:+.3f}]"
        ))

        # Body transform 스트리밍 (axis_length를 부여하여 관절 3D 축 표시)
        body_positions = {}
        for i in range(model.nbody):
            b_name = model.body(i).name
            if not b_name or b_name == "world":
                continue
            pos  = data.xpos[i]
            quat = data.xquat[i]
            body_positions[b_name] = pos
            rr.log(f"{ROBOT_ROOT}/{b_name}",
                   rr.Transform3D(translation=pos,
                                  rotation=rr.Quaternion(xyzw=[quat[1], quat[2], quat[3], quat[0]])))

        # 로봇 뼈대 (Skeleton Bone Lines) 로깅: 항상 선명한 로봇 구조 보장
        l_pts = [body_positions[b] for b in left_chain if b in body_positions]
        if len(l_pts) > 1:
            rr.log("world/skeleton/left_arm", rr.LineStrips3D([l_pts], colors=[[56, 189, 248]], radii=[0.012]))

        r_pts = [body_positions[b] for b in right_chain if b in body_positions]
        if len(r_pts) > 1:
            rr.log("world/skeleton/right_arm", rr.LineStrips3D([r_pts], colors=[[244, 63, 94]], radii=[0.012]))

        # 베이스 필러 라인
        if "base_plate" in body_positions and "shoulder_block" in body_positions:
            rr.log("world/skeleton/torso", rr.LineStrips3D([[body_positions["base_plate"], body_positions["shoulder_block"]]],
                                                         colors=[[200, 200, 200]], radii=[0.02]))

        # 메쉬는 최초 static=True로 gRPC 버퍼에 상주하므로 주기적 재전송 불필요 (네트워크 병목 및 렉 제거)

        # GPU EGL 카메라 렌더링 (RTX 5060 하드웨어 가속)
        if frame % CAM_RENDER_EVERY == 0:
            mujoco.mj_fwdPosition(model, data)

            renderer_top.update_scene(data, camera="cam_top")
            img = renderer_top.render()
            rr.log("cameras/top", rr.Image(img).compress(jpeg_quality=65))
            del img

            renderer_front.update_scene(data, camera="cam_front")
            img = renderer_front.render()
            rr.log("cameras/front", rr.Image(img).compress(jpeg_quality=65))
            del img

            # 손목 카메라는 대역폭 절약을 위해 6프레임마다 렌더
            if frame % (CAM_RENDER_EVERY * 2) == 0:
                renderer_lw.update_scene(data, camera="cam_left_wrist")
                img = renderer_lw.render()
                rr.log("cameras/left_wrist", rr.Image(img).compress(jpeg_quality=60))
                del img

                renderer_rw.update_scene(data, camera="cam_right_wrist")
                img = renderer_rw.render()
                rr.log("cameras/right_wrist", rr.Image(img).compress(jpeg_quality=60))
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
