#!/usr/bin/env python3
"""B-5-2/B-5-4: tuned balance controller for urdf/biped_balance_test.xml.

B-5-1 found that a naive fixed-pose PD (arm-tuned gains, target = straight-leg
qpos=0 for every joint) fails in two ways: (1) it barely resists the pelvis
tipping over at all, because the freejoint that actually falls has no direct
actuator — joint angles barely change during a rigid-body tip-over, so a PD
on joint-angle error sees almost no error signal; and (2) even where it does
apply torque, weak gains let the knee slip off its passive hard-limit lock
and the whole rig collapses vertically.

B-5-2 fixed both:
  - An explicit "ankle strategy" term (classic single-inverted-pendulum
    stabilization): ankle torque proportional to pelvis pitch angle and its
    rate, added on top of the ankle's own pose-hold PD. This is the piece
    that can actually influence the un-actuated freejoint, via the ground
    reaction moment at the foot.
  - Much stiffer hip/knee/ankle pose-hold gains (KP_POSE=600/KD_POSE=60 vs
    B-3's arm-tuned KP=8/KD=0.5) so the legs stay rigid under load instead of
    buckling.

Result: stable standing for 20s+ unperturbed (steady-state pitch settles at
-0.17deg, not diverging), and recovers from a 0.15s horizontal push on the
pelvis up to ~15N but reliably falls at pushes >=20N.

B-5-4 added a "hip strategy" term (same pitch/pitch-rate feedback as the
ankle term, but with the OPPOSITE sign — empirically necessary, since
sign=-1 on the hip is only stable at low gain and destabilizes outright at
higher gain, unlike the ankle where sign=-1 is the correct direction across
gains). Diagnosing the >=20N failure first showed the ankle actuator
saturating at its +-40 torque limit right as the fall became unrecoverable,
which looked like the obvious culprit — but doubling the limit to +-80
changed nothing (identical fall times/angles), so torque headroom was a red
herring. The real bottleneck was relying on a single (ankle-only) strategy.
Adding the hip term at KP_HIP=300/KD_HIP=75 widened the recoverable envelope
from <=15N to <=20N without hurting unperturbed stability (max tilt actually
dropped from 0.30deg to 0.12deg over 20s). Higher hip gains (600, 1000)
overshoot into instability rather than helping further — this is a sweet
spot, not "more gain is better." Still a narrow, characterized envelope
(falls at 25N+), not general-purpose balance. Wiring this into the live
bridge/frontend is deferred to a later stage.
"""
import mujoco
import numpy as np

MODEL_PATH = "/home/moos/dev_ws/dual_arms/urdf/biped_balance_test.xml"

KP_ANKLE = 200.0
KD_ANKLE = 50.0
ANKLE_SIGN = -1
KP_HIP = 300.0
KD_HIP = 75.0
HIP_SIGN = 1
KP_POSE = 600.0
KD_POSE = 60.0


class BipedBalanceController:
    def __init__(self, model: mujoco.MjModel):
        self.model = model
        self.pelvis_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
        actuator_names = [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)
        ]
        self.name_to_idx = {n: i for i, n in enumerate(actuator_names)}
        self.joint_addr = {}
        for name, idx in self.name_to_idx.items():
            joint_id = int(model.actuator_trnid[idx, 0])
            self.joint_addr[name] = (model.jnt_qposadr[joint_id], model.jnt_dofadr[joint_id])
        self.prev_pitch = 0.0

    def pitch(self, data: mujoco.MjData) -> float:
        R = data.xmat[self.pelvis_id].reshape(3, 3)
        up = R[:, 2]  # pelvis local z-axis expressed in world frame
        return float(np.arctan2(up[0], up[2]))

    def step(self, data: mujoco.MjData, dt: float) -> None:
        pitch = self.pitch(data)
        pitch_rate = (pitch - self.prev_pitch) / dt
        self.prev_pitch = pitch
        ankle_balance_term = ANKLE_SIGN * (KP_ANKLE * pitch + KD_ANKLE * pitch_rate)
        hip_balance_term = HIP_SIGN * (KP_HIP * pitch + KD_HIP * pitch_rate)
        for name, idx in self.name_to_idx.items():
            qpos_adr, dof_adr = self.joint_addr[name]
            error = 0.0 - data.qpos[qpos_adr]  # target: straight-leg standing pose
            ctrl = KP_POSE * error - KD_POSE * data.qvel[dof_adr]
            if "ankle" in name:
                ctrl += ankle_balance_term
            elif "hip" in name:
                ctrl += hip_balance_term
            lo, hi = self.model.actuator_ctrlrange[idx]
            data.ctrl[idx] = max(lo, min(hi, ctrl))


if __name__ == "__main__":
    model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    data = mujoco.MjData(model)
    dt = model.opt.timestep
    controller = BipedBalanceController(model)
    mujoco.mj_forward(model, data)
    controller.prev_pitch = controller.pitch(data)

    for i in range(int(10.0 / dt)):
        controller.step(data, dt)
        mujoco.mj_step(model, data)
        if i % int(1.0 / dt) == 0:
            print(
                f"t={data.time:5.1f}s pitch={np.degrees(controller.prev_pitch):6.2f}deg "
                f"pelvis_z={data.xpos[controller.pelvis_id][2]:.3f}"
            )
