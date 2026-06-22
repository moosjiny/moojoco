#!/bin/bash

# Kill existing processes on ports 8000 and 9090
echo "Cleaning up ports 8000 and 9090..."
fuser -k 8000/tcp 2>/dev/null
fuser -k 9090/tcp 2>/dev/null

VENV_PATH="/home/moos/venv/dual_arms"
source "$VENV_PATH/bin/activate"

echo "Starting Simulation (Rerun)..."
python3 /home/moos/dev_ws/dual_arms/scripts/sim_dual_arm.py &
SIM_PID=$!

echo "Starting Dashboard (FastAPI)..."
python3 /home/moos/dev_ws/dual_arms/dashboard/main.py &
DASH_PID=$!

echo "------------------------------------------------"
echo "All systems started!"
echo "Dashboard: http://localhost:8000"
echo "Rerun Viewer: http://localhost:9090"
echo "------------------------------------------------"

# Keep the script running to catch logs, or wait for PIDs
wait $SIM_PID $DASH_PID
