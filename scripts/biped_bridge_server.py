#!/usr/bin/env python3
"""B-5-3: real-time streaming bridge for the tuned biped balance controller.

Same broadcast-only pattern as mujoco_bridge_server.py (B-2), but for
urdf/biped_balance_test.xml on a separate port (8766, so it can run
alongside the arm bridge on 8765). Unlike the arm bridge, the balance
controller here isn't optional/client-driven — it runs every physics step
by default, since B-5-2 established that without it the biped falls within
seconds. Clients can additionally send a one-shot {"push_n": N, "duration":
s} message to apply a horizontal test disturbance to the pelvis, matching
the offline push-recovery test in the B-5-2 thesis (stable to ~15N, falls
at >=20N over 0.15s).
"""
import asyncio
import json
import time

import mujoco
import websockets

from biped_balance_controller import BipedBalanceController

MODEL_PATH = "/home/moos/dev_ws/dual_arms/urdf/biped_balance_test.xml"
HOST = "0.0.0.0"
PORT = 8766
BROADCAST_HZ = 60

model = mujoco.MjModel.from_xml_path(MODEL_PATH)
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

controller = BipedBalanceController(model)
controller.prev_pitch = controller.pitch(data)

pelvis_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
joint_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)]

active_push_remaining_s = 0.0
active_push_n = 0.0

clients = set()


async def physics_loop():
    global active_push_remaining_s
    dt = model.opt.timestep
    substeps = max(1, round(1.0 / (BROADCAST_HZ * dt)))
    tick = 1.0 / BROADCAST_HZ
    while True:
        start = time.perf_counter()
        for _ in range(substeps):
            controller.step(data, dt)
            if active_push_remaining_s > 0:
                data.xfrc_applied[pelvis_id][0] = active_push_n
                active_push_remaining_s -= dt
            else:
                data.xfrc_applied[pelvis_id][0] = 0.0
            mujoco.mj_step(model, data)
        if clients:
            payload = json.dumps(
                {
                    "time": round(float(data.time), 4),
                    "pelvis_z": round(float(data.xpos[pelvis_id][2]), 5),
                    "pitch_deg": round(float(controller.prev_pitch) * 57.29578, 3),
                    "qpos": {
                        name: round(float(data.qpos[model.jnt_qposadr[i]]), 5)
                        for i, name in enumerate(joint_names)
                        if name and name != "pelvis_free"
                    },
                }
            )
            await asyncio.gather(*(c.send(payload) for c in list(clients)), return_exceptions=True)
        elapsed = time.perf_counter() - start
        await asyncio.sleep(max(0.0, tick - elapsed))


def apply_message(raw: str) -> None:
    global active_push_remaining_s, active_push_n
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return
    if "push_n" in msg:
        try:
            active_push_n = float(msg["push_n"])
            active_push_remaining_s = float(msg.get("duration", 0.15))
        except (TypeError, ValueError):
            pass


async def handler(websocket):
    clients.add(websocket)
    print(f"[biped-bridge] client connected ({len(clients)} total)", flush=True)
    try:
        async for message in websocket:
            apply_message(message)
    finally:
        clients.discard(websocket)
        print(f"[biped-bridge] client disconnected ({len(clients)} total)", flush=True)


async def main():
    async with websockets.serve(handler, HOST, PORT):
        print(f"[biped-bridge] serving ws://{HOST}:{PORT} — model: {MODEL_PATH}", flush=True)
        print(f"[biped-bridge] balance controller active (KP_POSE=600/KD_POSE=60, KP_ANKLE=200/KD_ANKLE=50)", flush=True)
        await physics_loop()


if __name__ == "__main__":
    asyncio.run(main())
