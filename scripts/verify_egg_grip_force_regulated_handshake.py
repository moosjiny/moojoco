""""계란을 쥐듯" 겹침 없는 악수 — 접촉력 순응 제어(admittance/force-regulation) 실측.

## 배경
`diag_finger_interpenetration.py`/`verify_post_contact_penetration.py`의 손가락
컨트롤러는 접촉 여부와 무관하게 고정 목표각(CURL_TARGET)까지 PD로 계속 밀어붙인다.
소프트 콘택트 모델(solimp/solref)에서는 미는 힘이 클수록 모델이 허용하는 침투
depth도 커지므로, 침투의 근본 원인은 "닿았는데도 계속 미는 목표"에 있다.

## 방법 — 2단계 컨트롤러 전환
1. **탐색(seeking) 단계**: 접촉이 없는 동안은 기존과 동일하게 ease 곡선을 따라
   목표각을 전진시켜 상대 손가락을 "찾아간다".
2. **순응(admittance) 단계**: 해당 손가락 geom에 접촉력(법선력, mj_contactForce)이
   처음 감지되는 순간부터, 목표각을 더 이상 고정 최종값으로 밀어붙이지 않고
   힘 목표(GRIP_FORCE_TARGET_N, 예: 0.3N — 계란을 깨지 않을 정도)를 유지하도록
   목표각을 매 스텝 미세 조정한다:

       target += K_ADM * (GRIP_FORCE_TARGET_N - measured_force_N) * dt

   측정력이 목표보다 크면 목표각을 뒤로 물리고(retract), 작으면 계속 전진한다 —
   즉 "닿는 순간부터는 위치가 아니라 힘을 추종"하는 순응 제어로 전환한다.

## 검증 방식
`verify_post_contact_penetration.py`와 동일한 접근(4.0s)+유지(3.0s) 안무 위에
본 컨트롤러를 적용해, hold 구간에서 ①침투가 고정-목표 방식보다 줄어드는지
②접촉이 계속 유지되는지(그냥 힘이 약해서 안 닿는 가짜 해결이 아닌지)를 함께 측정한다.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import json

import numpy as np
import mujoco

XML_PATH = "/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/data/egg_grip_force_regulated_report.json"

FPS = 20
APPROACH_S = 4.0
HOLD_S = 3.0
N_APPROACH = int(APPROACH_S * FPS)
N_HOLD = int(HOLD_S * FPS)
N_TOTAL = N_APPROACH + N_HOLD
SUBSTEPS = 10

A_START, A_END = -0.20, -0.024
B_START, B_END = -0.20, -0.024

FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
CURL_TARGET = {"thumb": 1.55, "index": 1.75, "middle": 1.8, "ring": 1.7, "pinky": 1.45}
CURL_PHASE = {"thumb": 0.0, "index": 0.05, "middle": 0.08, "ring": 0.11, "pinky": 0.14}

CAPSULE_RADIUS = 0.006

GRIP_FORCE_TARGET_N = 0.3   # "계란을 쥐듯" — 파지력 목표(낮을수록 부드러움)
CONTACT_DETECT_N = 0.02     # 접촉 개시로 간주하는 최소 힘(노이즈 문턱)
K_ADM = 0.6                 # 순응 게인: rad/s per N of force error
RETRACT_MARGIN_RAD = 0.35   # 접촉 개시 각도 대비 최대 후퇴 허용폭(관절이 완전히 풀리지 않도록)


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def main():
    model = mujoco.MjModel.from_xml_path(XML_PATH)
    data = mujoco.MjData(model)
    dt = model.opt.timestep

    jid = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in [
        "handA_approach", "handB_approach",
        *[f"handA_{f}_curl" for f in FINGER_JOINTS],
        *[f"handB_{f}_curl" for f in FINGER_JOINTS],
    ]}
    aid = {n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"): mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, n.replace("_curl", "_ctrl").replace("_approach", "_approach_ctrl"))
        for n in jid}
    geom_id = {(h, f): mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{h}_{f}_geom")
               for h in ("handA", "handB") for f in FINGER_JOINTS}

    data.qpos[:] = 0.0
    data.qpos[model.jnt_qposadr[jid["handA_approach"]]] = A_START
    data.qpos[model.jnt_qposadr[jid["handB_approach"]]] = B_START
    mujoco.mj_forward(model, data)

    kp_wrist, kd_wrist = 40.0, 4.0
    kp_finger, kd_finger = 1.2, 0.06

    # 손가락별 순응 모드 상태: None=아직 탐색 중, float=순응모드 진입 후 현재 목표각(rad)
    adm_target = {(h, f): None for h in ("handA", "handB") for f in FINGER_JOINTS}
    engage_angle = {(h, f): None for h in ("handA", "handB") for f in FINGER_JOINTS}

    per_frame = []
    first_contact_t = None
    force_log = {k: [] for k in adm_target}

    for f in range(N_TOTAL):
        t_frac = min(f / (N_APPROACH - 1), 1.0)
        t = f / FPS
        for _ in range(SUBSTEPS):
            approach_frac = ease(t_frac)
            a_target = A_START + (A_END - A_START) * approach_frac
            b_target = B_START + (B_END - B_START) * approach_frac
            for side, target in (("handA_approach", a_target), ("handB_approach", b_target)):
                q = data.qpos[model.jnt_qposadr[jid[side]]]
                qd = data.qvel[model.jnt_dofadr[jid[side]]]
                data.ctrl[aid[f"{side}_ctrl"]] = float(np.clip(kp_wrist * (target - q) - kd_wrist * qd, -5, 5))

            # 직전 스텝 결과 기준 손가락별 최대 법선 접촉력
            finger_force = {k: 0.0 for k in adm_target}
            for ci in range(data.ncon):
                con = data.contact[ci]
                wrench = np.zeros(6)
                mujoco.mj_contactForce(model, data, ci, wrench)
                nf = abs(float(wrench[0]))
                for key, gid_ in geom_id.items():
                    if con.geom1 == gid_ or con.geom2 == gid_:
                        finger_force[key] = max(finger_force[key], nf)

            for hand in ("handA", "handB"):
                for fn in FINGER_JOINTS:
                    key = (hand, fn)
                    jname = f"{hand}_{fn}_curl"
                    q = data.qpos[model.jnt_qposadr[jid[jname]]]
                    qd = data.qvel[model.jnt_dofadr[jid[jname]]]
                    force = finger_force[key]

                    if adm_target[key] is None:
                        # 탐색 단계: 기존 ease 위치 추종
                        seek_frac = ease(t_frac - CURL_PHASE[fn])
                        target = CURL_TARGET[fn] * seek_frac
                        if force > CONTACT_DETECT_N:
                            adm_target[key] = target
                            engage_angle[key] = target
                    else:
                        # 순응 단계: 힘 목표를 추종하도록 목표각 미세 조정
                        adm_target[key] += K_ADM * (GRIP_FORCE_TARGET_N - force) * dt
                        lo = engage_angle[key] - RETRACT_MARGIN_RAD
                        hi = CURL_TARGET[fn]
                        adm_target[key] = float(np.clip(adm_target[key], lo, hi))
                        target = adm_target[key]

                    ctrl_name = f"{hand}_{fn}_ctrl"
                    data.ctrl[aid[ctrl_name]] = float(np.clip(kp_finger * (target - q) - kd_finger * qd, -2, 2))

            mujoco.mj_step(model, data)

            for key in force_log:
                force_log[key].append(finger_force[key])

        frame_worst = 0.0
        contacts_fingerpair = []
        for ci in range(data.ncon):
            con = data.contact[ci]
            dist = float(con.dist)
            if dist < frame_worst:
                frame_worst = dist
            g1 = model.geom(con.geom1).name
            g2 = model.geom(con.geom2).name
            is_finger_pair = ("_thumb_" in g1 or "_index_" in g1 or "_middle_" in g1 or "_ring_" in g1 or "_pinky_" in g1) and \
                              ("_thumb_" in g2 or "_index_" in g2 or "_middle_" in g2 or "_ring_" in g2 or "_pinky_" in g2)
            if is_finger_pair and dist < 0:
                contacts_fingerpair.append(dist)

        phase = "approach" if f < N_APPROACH else "hold"
        if contacts_fingerpair and first_contact_t is None:
            first_contact_t = round(t, 3)

        per_frame.append({
            "t": round(t, 3), "phase": phase, "n_contact": int(data.ncon),
            "frame_worst_dist_m": round(frame_worst, 6),
            "n_finger_pair_penetrating": len(contacts_fingerpair),
        })

    worst_overall = min(pf["frame_worst_dist_m"] for pf in per_frame)
    hold_frames = [pf for pf in per_frame if pf["phase"] == "hold"]
    worst_during_hold = min((pf["frame_worst_dist_m"] for pf in hold_frames), default=0.0)
    hold_contact_frames = sum(1 for pf in hold_frames if pf["n_contact"] > 0)

    engaged_fingers = {f"{h}_{fn}": (adm_target[(h, fn)] is not None) for h in ("handA", "handB") for fn in FINGER_JOINTS}
    steady_force = {}
    for key, log in force_log.items():
        tail = log[-int(1.0 * FPS * SUBSTEPS):]  # 마지막 1초 평균
        steady_force[f"{key[0]}_{key[1]}"] = round(float(np.mean(tail)), 4) if tail else 0.0

    summary = {
        "method": "admittance_force_regulation_after_contact",
        "grip_force_target_n": GRIP_FORCE_TARGET_N,
        "k_adm": K_ADM,
        "capsule_radius_m": CAPSULE_RADIUS,
        "approach_s": APPROACH_S,
        "hold_s": HOLD_S,
        "first_contact_t_s": first_contact_t,
        "worst_dist_overall_m": round(worst_overall, 6),
        "worst_dist_overall_ratio_of_radius": round(abs(worst_overall) / CAPSULE_RADIUS, 4) if worst_overall < 0 else 0.0,
        "worst_dist_during_hold_m": round(worst_during_hold, 6),
        "worst_dist_during_hold_ratio_of_radius": round(abs(worst_during_hold) / CAPSULE_RADIUS, 4) if worst_during_hold < 0 else 0.0,
        "hold_contact_persistence": f"{hold_contact_frames}/{len(hold_frames)}",
        "engaged_fingers": engaged_fingers,
        "steady_state_force_last_1s_n": steady_force,
    }

    with open(OUT_PATH, "w") as fp:
        json.dump({"summary": summary, "per_frame": per_frame}, fp, indent=1)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n리포트: {OUT_PATH}")


if __name__ == "__main__":
    main()
