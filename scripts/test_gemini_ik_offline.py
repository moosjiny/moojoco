"""
IK 대체 오프라인 실험(1차): 로봇 팔을 실제로 움직이지 않고, Gemini 2.5 Flash에게
"retract 자세" 뷰포트 스냅샷 + 관절 상태만 주고 악수를 위한 손끝(right_link7)
목표 6D 포즈를 추론시킨 뒤, 기존에 수치 프로빙으로 확보해둔 정답
(J2_FINAL=0, hand_distance_m=0.032)과 비교한다.

제어 루프에 넣지 않는 완전 오프라인/저위험 검증 — 로봇은 움직이지 않고
추론 결과만 비교. mujoco_sim.service(라이브)는 미간섭.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import io
import json
import numpy as np
import mujoco
from PIL import Image
from google import genai
from google.genai import types

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"
KEY_PATH = "/home/moos/dev_ws/dual_arms/Gemini_API_moosjiny.key"
OUT_SNAPSHOT = "/tmp/claude-1000/-home-moos-dev-ws-dual-arms/54d39449-6cf4-4ae9-9d90-5aa2e3f0283c/scratchpad/gemini_ik_retract_snapshot.png"
OUT_RESULT = "/tmp/claude-1000/-home-moos-dev-ws-dual-arms/54d39449-6cf4-4ae9-9d90-5aa2e3f0283c/scratchpad/gemini_ik_offline_result.json"

J2_RETRACT = 1.3
J2_FINAL = 0.0

RIGHT_JOINTS_INFO = [
    ("right_joint_1", "z", [-3.14, 3.14]),
    ("right_joint_2", "x", [-1.57, 1.57]),
    ("right_joint_3", "z", [-3.14, 3.14]),
    ("right_joint_4", "y", [-1.57, 1.57]),
    ("right_joint_5", "z", [-3.14, 3.14]),
    ("right_joint_6", "x", [-1.57, 1.57]),
    ("right_joint_7", "y", [-3.14, 3.14]),
]


def quat_angle_deg(q1, q2):
    dot = abs(float(np.dot(q1, q2)))
    dot = min(1.0, dot)
    return np.degrees(2 * np.arccos(dot))


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 960
    data = mujoco.MjData(model)

    j2 = {p: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{p}right_joint_2") for p in ("", "r2_")}

    # ── retract 자세로 세팅 후 스냅샷 ──
    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[j2[""]]] = J2_RETRACT
    data.qpos[model.jnt_qposadr[j2["r2_"]]] = J2_RETRACT
    mujoco.mj_kinematics(model, data)
    mujoco.mj_fwdPosition(model, data)

    hide_bids = set()
    for name in ("target_left", "target_right", "r2_target_left", "r2_target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=960, width=960)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.azimuth, cam.elevation, cam.distance = 15, -12, 2.2
    cam.lookat[:] = [0.0, 0.52, 0.85]
    renderer.update_scene(data, camera=cam)
    for i in range(renderer.scene.ngeom):
        g = renderer.scene.geoms[i]
        if g.objtype == mujoco.mjtObj.mjOBJ_GEOM and model.geom_bodyid[g.objid] in hide_bids:
            g.rgba[3] = 0.0
    img = Image.fromarray(renderer.render())
    img.save(OUT_SNAPSHOT)
    renderer.close()

    # r2(로봇B) 손 위치/자세 — Gemini에게 텍스트로 알려줄 참고 정보
    r2_hand_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "r2_right_link7")
    r2_hand_pos = data.xpos[r2_hand_bid].copy()
    r2_hand_quat = data.xquat[r2_hand_bid].copy()

    # ── 정답(ground truth): 기존 수치 프로빙으로 확보한 J2_FINAL=0 자세의 robot A 손끝 목표 ──
    gt_data = mujoco.MjData(model)
    gt_data.qpos[:] = 0.0
    gt_data.qpos[model.jnt_qposadr[j2[""]]] = J2_FINAL
    gt_data.qpos[model.jnt_qposadr[j2["r2_"]]] = J2_FINAL
    mujoco.mj_kinematics(model, gt_data)
    hand_a_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_link7")
    gt_pos = gt_data.xpos[hand_a_bid].copy()
    gt_quat = gt_data.xquat[hand_a_bid].copy()

    joints_desc = "\n".join(
        f"- {name}: 회전축 world-{axis}, range=[{lo}, {hi}] rad, 현재값={J2_RETRACT if name=='right_joint_2' else 0.0}"
        for name, axis, (lo, hi) in RIGHT_JOINTS_INFO
    )

    prompt = f"""당신은 로봇 팔 역기구학(IK) 추론을 돕는 비전-언어 모델입니다.
첨부된 이미지는 MuJoCo 3D 시뮬레이션 스냅샷으로, 로봇 2대(A: 왼쪽/앞, B: 오른쪽/반대편)가
서로를 향해 오른팔을 뻗어 악수를 시도하려는 "팔을 젖힌(retract)" 시작 자세입니다.

로봇 A의 오른팔은 7개의 회전 관절(right_joint_1~7, 직렬 링크)로 구성되어 있습니다:
{joints_desc}

로봇 B의 오른손(right_link7, world frame) 현재 위치: {r2_hand_pos.round(4).tolist()} (m)
로봇 B의 오른손 현재 자세(quaternion wxyz): {r2_hand_quat.round(4).tolist()}

질문: 로봇 A가 팔을 뻗어 로봇 B의 손과 맞닿아 악수하려면, 로봇 A의 오른손(right_link7)이
world frame에서 도달해야 할 목표 위치(x,y,z, 미터)와 목표 자세(quaternion wxyz)를 추론하세요.
로봇 B와 정확히 맞닿되 관통하지 않아야 하며, 두 손이 서로 마주보는 자연스러운 악수 방향을
고려하세요. JSON으로만 답하세요."""

    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "target_position_m": types.Schema(
                type=types.Type.ARRAY, items=types.Schema(type=types.Type.NUMBER), min_items=3, max_items=3
            ),
            "target_quat_wxyz": types.Schema(
                type=types.Type.ARRAY, items=types.Schema(type=types.Type.NUMBER), min_items=4, max_items=4
            ),
            "reasoning": types.Schema(type=types.Type.STRING),
        },
        required=["target_position_m", "target_quat_wxyz", "reasoning"],
    )

    api_key = open(KEY_PATH).read().strip()
    client = genai.Client(api_key=api_key)

    with open(OUT_SNAPSHOT, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    result = json.loads(response.text)
    pred_pos = np.array(result["target_position_m"])
    pred_quat = np.array(result["target_quat_wxyz"])
    pred_quat = pred_quat / np.linalg.norm(pred_quat)

    pos_error_m = float(np.linalg.norm(pred_pos - gt_pos))
    ori_error_deg = float(quat_angle_deg(pred_quat, gt_quat))

    report = {
        "model": "gemini-2.5-flash",
        "ground_truth": {
            "position_m": gt_pos.round(4).tolist(),
            "quat_wxyz": gt_quat.round(4).tolist(),
            "source": "수치 프로빙으로 확보한 J2_FINAL=0 rest pose (hand_distance_m=0.032)",
        },
        "gemini_prediction": {
            "position_m": pred_pos.round(4).tolist(),
            "quat_wxyz": pred_quat.round(4).tolist(),
            "reasoning": result["reasoning"],
        },
        "position_error_m": round(pos_error_m, 4),
        "orientation_error_deg": round(ori_error_deg, 2),
    }
    with open(OUT_RESULT, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
