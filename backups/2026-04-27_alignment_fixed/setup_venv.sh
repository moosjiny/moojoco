#!/bin/bash
# Script to setup/apply the virtual environment for Dual Arm project

VENV_DIR="/home/moos/dev_ws/dual_arms/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing/Updating dependencies..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install fastapi uvicorn websockets python-can mujoco rerun-sdk trimesh scipy
fi

echo "------------------------------------------------"
echo "Virtual Environment is ready!"
echo "To activate, run: source venv/bin/activate"
echo "------------------------------------------------"
