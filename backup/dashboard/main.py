import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager

# Global state for the robot
robot_state = {
    "left": {"joints": [0.0]*7, "torque": [0.0]*7, "gripper": 0.0},
    "right": {"joints": [0.0]*7, "torque": [0.0]*7, "gripper": 0.0},
    "status": "OPERATIONAL"
}

async def update_robot_data():
    """
    Background task to update robot state.
    In the future, this will interface with the DamiaoMotorsBus.
    """
    global robot_state
    while True:
        for side in ["left", "right"]:
            # Mock joint movements
            robot_state[side]["joints"] = [random.uniform(-1, 1) for i in range(7)]
            # Mock torque data
            robot_state[side]["torque"] = [1.2 + random.uniform(-0.1, 0.1) for i in range(7)]
        await asyncio.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background task
    task = asyncio.create_task(update_robot_data())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(lifespan=lifespan)

# Setup templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/")
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps(robot_state))
            await asyncio.sleep(0.05)
    except Exception as e:
        print(f"WebSocket closed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
