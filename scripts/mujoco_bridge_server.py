#!/usr/bin/env python3
"""MuJoCo physics-state WebSocket bridge (Option B, Stage B-2 + B-3).

Steps dual_openarm_handshake.xml forward with mj_step and broadcasts joint
angles (qpos) as JSON to any connected WebSocket client.

The model's <general> actuators have no gaintype/biastype set, so MuJoCo
defaults them to a constant-force motor (force = ctrl), not a position
servo — a sustained nonzero ctrl just drives the joint into its hard limit
and holds it there (confirmed empirically in B-3). To make "send a target
angle" meaningful, this bridge computes its own PD position control each
step: {"target": {actuator_name: angle_rad, ...}} sets a persistent target,
and ctrl = kp*(target - qpos) - kd*qvel is computed every frame. The lower-
level {"ctrl": {...}} message (raw force, one-shot) still works too.
"""
import asyncio
import json
import time

import mujoco
import websockets

MODEL_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"
HOST = "0.0.0.0"
PORT = 8765
STEP_HZ = 60

model = mujoco.MjModel.from_xml_path(MODEL_PATH)
data = mujoco.MjData(model)

joint_names = [
    mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)
]
actuator_index_by_name = {
    mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i for i in range(model.nu)
}
# Per-actuator (qpos address, dof address) of the single joint it drives —
# every actuator here transmits a 1-DOF hinge joint, so this is a direct
# lookup, not a general multi-dof solve.
actuator_joint_addrs = {}
for name, idx in actuator_index_by_name.items():
    joint_id = int(model.actuator_trnid[idx, 0])
    actuator_joint_addrs[name] = (model.jnt_qposadr[joint_id], model.jnt_dofadr[joint_id])

KP = 8.0
KD = 0.5
position_targets: dict[str, float] = {}

clients = set()


async def physics_loop():
    dt = 1.0 / STEP_HZ
    while True:
        start = time.perf_counter()
        for name, target in position_targets.items():
            idx = actuator_index_by_name.get(name)
            qpos_adr, dof_adr = actuator_joint_addrs[name]
            error = target - data.qpos[qpos_adr]
            ctrl = KP * error - KD * data.qvel[dof_adr]
            lo, hi = model.actuator_ctrlrange[idx]
            data.ctrl[idx] = max(lo, min(hi, ctrl))
        mujoco.mj_step(model, data)
        if clients:
            payload = json.dumps(
                {
                    "time": round(float(data.time), 4),
                    "qpos": {
                        name: round(float(data.qpos[model.jnt_qposadr[i]]), 5)
                        for i, name in enumerate(joint_names)
                        if name
                    },
                }
            )
            await asyncio.gather(
                *(c.send(payload) for c in list(clients)), return_exceptions=True
            )
        elapsed = time.perf_counter() - start
        await asyncio.sleep(max(0.0, dt - elapsed))


def apply_ctrl_message(raw: str) -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return

    target = msg.get("target")
    if isinstance(target, dict):
        for name, value in target.items():
            if name in actuator_joint_addrs:
                try:
                    position_targets[name] = float(value)
                except (TypeError, ValueError):
                    pass

    ctrl = msg.get("ctrl")
    if isinstance(ctrl, dict):
        for name, value in ctrl.items():
            idx = actuator_index_by_name.get(name)
            if idx is not None:
                try:
                    data.ctrl[idx] = float(value)
                except (TypeError, ValueError):
                    pass
                position_targets.pop(name, None)  # raw ctrl overrides any PD target


async def handler(websocket):
    clients.add(websocket)
    print(f"[bridge] client connected ({len(clients)} total)", flush=True)
    try:
        async for message in websocket:
            apply_ctrl_message(message)
    finally:
        clients.discard(websocket)
        print(f"[bridge] client disconnected ({len(clients)} total)", flush=True)


async def main():
    async with websockets.serve(handler, HOST, PORT):
        print(f"[bridge] MuJoCo bridge serving ws://{HOST}:{PORT} — model: {MODEL_PATH}", flush=True)
        print(f"[bridge] {model.njnt} joints, {model.nu} actuators, {model.nbody} bodies", flush=True)
        await physics_loop()


if __name__ == "__main__":
    asyncio.run(main())
