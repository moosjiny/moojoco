#!/bin/bash

# Path to the virtual environment
VENV_PATH="/home/moos/dev_ws/dual_arms/venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Activate venv and run the dashboard
echo "Starting OpenArm Dashboard..."
source "$VENV_PATH/bin/activate"
python3 /home/moos/dev_ws/dual_arms/dashboard/main.py
