"""접촉 주도형(contact-driven) 파지 컨트롤러 v1 — 8600 실악수 로드맵 1단계.

[[2026-08-20-moojoco-handshake-v3-curl-sweep-failure]]의 근본 진단(사전-감속은
회피 도구, 그립엔 정반대)에 따라 제어 전략을 뒤집는다:

  구버전: 근접도가 줄면 굽힘을 감속 → 접촉 직전 동결 → 90/90 접촉 실패
  신버전: 감속 없이 일정 속도로 폐쇄 → 손가락별 접촉 감지 시 래치 + 스퀴즈 유지
          (과도한 힘은 감속이 아니라 토크 상한이 막는다 — 컴플라이언스)

상태 기계: APPROACH(y 정렬, B는 4mm 위에서 진입) → DESCEND(손바닥 접촉까지 하강,
접촉 시 착지 래치 + 미세 프리로드) → CLOSE(손가락 폐쇄) → HOLD(유지).
DESCEND가 필요한 이유(실측): B손은 height 슬라이드에 매달려 중력으로 ~1.8mm
처지므로, 같은 높이로 진입시키면 손바닥 면이 겹쳐 모서리 충돌로 접근이 막힌다.

기하는 v4 적층 맞잡기(stacked clasp)를 쓴다 — v3의 맞물림(interleave)은 실측 결과
손바닥 접촉 자세에서 반대손 손가락끼리 -5~-6mm(반경의 83~100%) 상시 침투하는
기하 결함이라 컨트롤러로 풀 수 없었다. v4는 손바닥을 z로 포개 면접촉시키고
(A 위면 = B 아래면, z=0.058), 각 손의 손가락이 상대 손바닥의 반대쪽 모서리를
감싼다. 실측: 접근 무충돌(여유 +2mm), curl≈0.8rad에서 10지 전부 손바닥 도달.

성공 판정은 게이트와 실행 여부를 분리 측정한다
([[feedback_verify_engagement_not_just_gate]]):
  - 침투 게이트(캡슐 반경 5% 이내)  ← 필요조건
  - 손바닥-손바닥 접촉 발생 + HOLD 중 유지율
  - 손가락 10개 중 상대 손 접촉 수(래치 수)  ← 실제 그립 여부
2단계(fingershake 재생 브릿지)를 위해 전체 관절 궤적을 JSON으로도 내보낸다.
"""
import json
import os
import time

import mujoco
import numpy as np

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v4.xml"
OUT_DIR = "/home/moos/dev_ws/dual_arms/data/contact_driven_grasp_v1"

FPS = 20
SUBSTEPS = 25  # 물리 스텝 0.002s × 25 = 프레임당 0.05s (FPS=20과 정합)
DT = 0.002

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CAPSULE_RADIUS = 0.006
PENETRATION_GATE_RATIO = 0.05

A_START, B_START = -0.20, -0.20
# v4 실측: 손바닥 면이 z=0.058 평면에서 정확히 맞닿는 지점(x-y 완전 정렬)
A_END, B_END = -0.028, 0.148
PALM_DOCK_EPS = 0.0005  # 면접촉은 접촉 페어가 안 생길 수 있어 거리 기반으로 판정

APPROACH_S = 2.5      # 손목 접근(y 정렬)에 쓰는 시간
DESCEND_RATE = 0.010  # 하강 속도 (m/s)
DESCEND_PRELOAD = 0.0003  # 착지 후 손바닥 프리로드용 추가 목표(m)
MAX_DESCEND_S = 1.5
CLOSE_RATE = 0.4      # 손가락 use_frac 증가 속도 (1/s) — 감속 없음(접촉 충격만 고려해 완만하게)
HOLD_TORQUE = 0.03    # 감싸쥠 후 유지 토크(N·m). 관절 frictionloss 0.01의 3배 —
                      # 0.015로는 마찰에 막혀 settle이 표면 0.2~0.8mm 앞에서 멈춤(실측)
# 짧은 손가락(엄지·소지)은 도달 자세가 빠듯해 같은 토크로는 눌림이 부족 — 차등 상향
HOLD_TORQUE_BY_FINGER = {"thumb": 0.04, "pinky": 0.038}
HOLD_S = 2.0          # 그립 유지 구간
MAX_CLOSE_S = 4.0     # CLOSE 상한(미접촉 손가락이 있어도 HOLD로 전환)

MCP_MAX, PIP_MAX = 1.6, 1.6  # v4에서 관절 범위 1.7로 확장(감싸쥐기 여유)


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def build():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)

    jid, aid = {}, {}
    joint_names = ["handA_approach", "handB_approach", "handB_lateral", "handB_height"]
    for h in ("handA", "handB"):
        for fn in FINGER_JOINTS:
            joint_names += [f"{h}_{fn}_mcp", f"{h}_{fn}_pip"]
    for name in joint_names:
        jid[name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        aid[name] = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name + "_ctrl")

    # geom id → (hand, finger|palm, segment) 분류표: 접촉을 관절 단위로 귀속시키기 위함
    geom_owner = {}
    for h in ("handA", "handB"):
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_palm")
        geom_owner[gid] = (h, "palm", "palm")
        for fn in FINGER_JOINTS:
            for seg in ("prox", "dist"):
                gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{fn}_{seg}_geom")
                geom_owner[gid] = (h, fn, seg)

    return model, data, jid, aid, joint_names, geom_owner


def classify_contacts(model, data, geom_owner):
    """이번 스텝의 접촉을 (손바닥-손바닥 여부, 손가락 세그먼트별 접촉 집합,
    최악 dist, 최악 페어 이름)으로 분류."""
    palm_palm = False
    finger_hits = set()  # {(hand, finger, segment)} — 상대 손과 닿은 손가락 세그먼트
    worst = 0.0
    worst_pair = None
    for ci in range(data.ncon):
        c = data.contact[ci]
        d = float(c.dist)
        if d < worst:
            worst = d
            worst_pair = (model.geom(int(c.geom1)).name, model.geom(int(c.geom2)).name)
        o1 = geom_owner.get(int(c.geom1))
        o2 = geom_owner.get(int(c.geom2))
        if o1 is None or o2 is None or o1[0] == o2[0]:
            continue  # 같은 손 내부 접촉·바닥 등은 제외
        if o1[1] == "palm" and o2[1] == "palm":
            palm_palm = True
            continue
        for o in (o1, o2):
            if o[1] != "palm":
                finger_hits.add(o)
    return palm_palm, finger_hits, worst, worst_pair


def run(model, data, jid, aid, joint_names, geom_owner):
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    obstacle_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "obstacle")
    data.mocap_pos[int(model.body_mocapid[obstacle_body])] = [0.0, 5.0, 0.05]
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_lat, kd_lat = 2000.0, 40.0
    # 손가락 토크 상한을 구버전(±2)보다 낮춰 접촉 후 압력을 힘으로 제한한다
    kp_finger, kd_finger, finger_torque_cap = 1.2, 0.06, 0.25

    palm_gid_a = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handA_palm")
    palm_gid_b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "handB_palm")

    phase = "APPROACH"
    phase_t = 0.0
    last_palm_docked = False
    last_finger_hits = set()
    height_target = 0.0      # handB_height 목표(+ = 하강)
    descend_latched = None   # 착지 시점의 height qpos + 프리로드
    close_frac = {(h, fn): 0.0 for h in ("handA", "handB") for fn in FINGER_JOINTS}
    # 힘 제한 순응 파지: 접촉해도 관절을 얼리지 않고 낮은 토크 상한으로 계속
    # 폐쇄 구동한다(근위가 모서리를 타고 미끄러져 올라가 감싸쥠). 원위(dist)
    # 접촉 = 감싸쥠 완료. 이후 2단계 유지:
    #   settle(0.4s): 미세 정토크로 힘 평형점을 찾게 두고
    #   anchor: 그 평형 위치를 스프링 앵커로 승격(+미세 바이어스)
    # — 손가락마다 다른 평형점은 힘이 찾고, 유지·과압착 방지는 스프링이 맡는다.
    first_prox_contact = {}  # (hand, finger) → 첫 prox 접촉 시점 mcp_q (계측용)
    wrap_hold = {}           # (hand, finger) → 감싸쥠 감지 시점 (mcp_q, pip_q) (계측용)
    wrap_t = {}              # (hand, finger) → 감싸쥠 감지 시각(t_sim)
    wrap_anchor = {}         # (hand, finger) → settle 후 확정된 (mcp_anchor, pip_anchor)
    SETTLE_S = 0.4
    t_sim = 0.0
    palm_contact_ever = False
    palm_contact_hold_frames = 0
    hold_frames_total = 0
    hold_finger_contact_frames = {k: 0 for k in close_frac}
    worst_dist = 0.0
    worst_pair = None
    trajectory = []

    n_total = int((APPROACH_S + MAX_DESCEND_S + MAX_CLOSE_S + HOLD_S + 1.0) * FPS)
    frame = 0
    done = False

    while frame < n_total and not done:
        for _ in range(SUBSTEPS):
            # --- 손목: APPROACH 동안 ease 프로파일로 전진, 이후 목표 유지 ---
            appr_frac = ease(phase_t / APPROACH_S) if phase == "APPROACH" else 1.0
            for hand, (start, end) in (("handA", (A_START, A_END)), ("handB", (B_START, B_END))):
                jn = f"{hand}_approach"
                target = start + (end - start) * appr_frac
                q = data.qpos[model.jnt_qposadr[jid[jn]]]
                qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                data.ctrl[aid[jn]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))
            q = data.qpos[model.jnt_qposadr[jid["handB_lateral"]]]
            qd = data.qvel[model.jnt_dofadr[jid["handB_lateral"]]]
            data.ctrl[aid["handB_lateral"]] = float(np.clip(kp_lat * (0.0 - q) - kd_lat * qd, -5, 5))

            if descend_latched is not None:
                height_target = descend_latched
            elif phase == "DESCEND":
                height_target += DESCEND_RATE * DT
            q = data.qpos[model.jnt_qposadr[jid["handB_height"]]]
            qd = data.qvel[model.jnt_dofadr[jid["handB_height"]]]
            data.ctrl[aid["handB_height"]] = float(np.clip(kp_lat * (height_target - q) - kd_lat * qd, -5, 5))

            # --- 손가락: CLOSE/HOLD에서만 구동. 감속 없음, 관절별 래치 + 스퀴즈 ---
            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    key = (hand, fn)
                    hold_tau = HOLD_TORQUE_BY_FINGER.get(fn, HOLD_TORQUE)
                    if key in wrap_anchor:
                        # anchor 단계: settle이 찾은 평형 위치를 스프링으로 유지
                        for j, q_a in (("mcp", wrap_anchor[key][0]), ("pip", wrap_anchor[key][1])):
                            jn = f"{hand}_{fn}_{j}"
                            q = data.qpos[model.jnt_qposadr[jid[jn]]]
                            qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                            data.ctrl[aid[jn]] = float(np.clip(
                                kp_finger * (q_a - q) - 0.25 * qd + hold_tau,
                                -finger_torque_cap, finger_torque_cap))
                        continue
                    if key in wrap_hold:
                        # settle 단계: 미세 정토크로 힘 평형점 탐색
                        if t_sim - wrap_t[key] >= SETTLE_S:
                            wrap_anchor[key] = (
                                float(data.qpos[model.jnt_qposadr[jid[f"{hand}_{fn}_mcp"]]]),
                                float(data.qpos[model.jnt_qposadr[jid[f"{hand}_{fn}_pip"]]]),
                            )
                        for j in ("mcp", "pip"):
                            jn = f"{hand}_{fn}_{j}"
                            qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                            data.ctrl[aid[jn]] = float(np.clip(
                                hold_tau - 0.1 * qd,
                                -finger_torque_cap, finger_torque_cap))
                        continue
                    if phase in ("CLOSE", "HOLD"):
                        if phase == "CLOSE":
                            close_frac[key] = min(close_frac[key] + CLOSE_RATE * DT, 1.0)
                        mcp_t = MCP_MAX * close_frac[key]
                        pip_t = PIP_MAX * close_frac[key]
                    else:
                        mcp_t = pip_t = 0.0
                    for j, tgt in (("mcp", mcp_t), ("pip", pip_t)):
                        jn = f"{hand}_{fn}_{j}"
                        q = data.qpos[model.jnt_qposadr[jid[jn]]]
                        qd = data.qvel[model.jnt_dofadr[jid[jn]]]
                        data.ctrl[aid[jn]] = float(np.clip(
                            kp_finger * (tgt - q) - kd_finger * qd,
                            -finger_torque_cap, finger_torque_cap))

            mujoco.mj_step(model, data)
            phase_t += DT
            t_sim += DT

            palm_palm, finger_hits, step_worst, step_pair = classify_contacts(model, data, geom_owner)
            palm_dist = mujoco.mj_geomDistance(model, data, palm_gid_a, palm_gid_b,
                                               PALM_DOCK_EPS * 4, None)
            palm_palm = palm_palm or palm_dist <= PALM_DOCK_EPS
            if step_worst < worst_dist:
                worst_dist, worst_pair = step_worst, step_pair
            palm_contact_ever = palm_contact_ever or palm_palm
            last_palm_docked = palm_palm
            last_finger_hits = {(h, fn) for (h, fn, _seg) in finger_hits}

            # 계측 + 감싸쥠 판정: dist 접촉 시 유지 목표 고정(관절 동결은 없음)
            if phase in ("CLOSE", "HOLD"):
                for (h, fn, seg) in finger_hits:
                    key = (h, fn)
                    if key not in first_prox_contact:
                        first_prox_contact[key] = float(
                            data.qpos[model.jnt_qposadr[jid[f"{h}_{fn}_mcp"]]])
                    if seg == "dist" and key not in wrap_hold:
                        wrap_hold[key] = (
                            float(data.qpos[model.jnt_qposadr[jid[f"{h}_{fn}_mcp"]]]),
                            float(data.qpos[model.jnt_qposadr[jid[f"{h}_{fn}_pip"]]]),
                        )
                        wrap_t[key] = t_sim

            # --- 상태 전이 ---
            if phase == "APPROACH" and phase_t >= APPROACH_S + 0.3:
                phase, phase_t = "DESCEND", 0.0
            elif phase == "DESCEND" and (palm_palm or phase_t >= MAX_DESCEND_S):
                if palm_palm and descend_latched is None:
                    descend_latched = float(
                        data.qpos[model.jnt_qposadr[jid["handB_height"]]]) + DESCEND_PRELOAD
                phase, phase_t = "CLOSE", 0.0
            elif phase == "CLOSE" and (len(wrap_hold) == 10 or phase_t >= MAX_CLOSE_S):
                phase, phase_t = "HOLD", 0.0
            elif phase == "HOLD":
                if phase_t >= HOLD_S:
                    done = True
                    break

        # 프레임 단위 기록 (HOLD 유지율 + 궤적)
        if phase == "HOLD":
            hold_frames_total += 1
            palm_contact_hold_frames += int(last_palm_docked)
            for key in last_finger_hits:
                hold_finger_contact_frames[key] += 1

        trajectory.append({
            "t": round(frame / FPS, 3),
            "phase": phase,
            "qpos": {name: float(data.qpos[model.jnt_qposadr[jid[name]]]) for name in joint_names},
        })
        frame += 1

    worst_ratio = abs(worst_dist) / CAPSULE_RADIUS if worst_dist < 0 else 0.0
    hold_palm_rate = palm_contact_hold_frames / hold_frames_total if hold_frames_total else 0.0
    hold_finger_rates = {f"{h}_{fn}": (hold_finger_contact_frames[(h, fn)] / hold_frames_total
                                       if hold_frames_total else 0.0)
                         for h in ("handA", "handB") for fn in FINGER_JOINTS}

    return {
        "gate_pass": worst_ratio <= PENETRATION_GATE_RATIO,
        "worst_penetration_ratio_of_radius": round(worst_ratio, 4),
        "worst_penetration_pair": worst_pair,
        "palm_contact_ever": palm_contact_ever,
        "hold_palm_contact_rate": round(hold_palm_rate, 3),
        "fingers_touched": len(first_prox_contact),
        "fingers_wrapped": len(wrap_hold),
        "wrap_detail": {f"{h}_{fn}": {"first_contact_mcp": round(first_prox_contact[(h, fn)], 4),
                                       "hold_mcp": round(wrap_hold[(h, fn)][0], 4)
                                       if (h, fn) in wrap_hold else None,
                                       "hold_pip": round(wrap_hold[(h, fn)][1], 4)
                                       if (h, fn) in wrap_hold else None}
                           for (h, fn) in sorted(first_prox_contact)},
        "hold_finger_contact_rates": {k: round(v, 3) for k, v in hold_finger_rates.items()},
        "hold_frames": hold_frames_total,
        "n_frames": len(trajectory),
    }, trajectory


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    model, data, jid, aid, joint_names, geom_owner = build()
    t0 = time.time()
    result, trajectory = run(model, data, jid, aid, joint_names, geom_owner)
    result["elapsed_s"] = round(time.time() - t0, 2)

    # 실제 그립 성공 = 게이트 + 손바닥 접촉 유지 + 손가락 8/10 이상 감싸쥠(래치)
    # + HOLD 중 접촉을 유지한 손가락 8/10 이상
    n_hold_fingers = sum(1 for v in result["hold_finger_contact_rates"].values() if v >= 0.8)
    result["fingers_hold_contact_80pct"] = n_hold_fingers
    result["grasp_success"] = bool(
        result["gate_pass"]
        and result["palm_contact_ever"]
        and result["hold_palm_contact_rate"] >= 0.9
        and result["fingers_wrapped"] >= 8
        and n_hold_fingers >= 8
    )

    with open(os.path.join(OUT_DIR, "result.json"), "w") as fp:
        json.dump(result, fp, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "trajectory.json"), "w") as fp:
        json.dump({"fps": FPS, "joints": joint_names, "frames": trajectory}, fp)

    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
