#!/bin/bash
echo "========================================="
echo "  LAUNCHING ROBOT STATE PUBLISHER & RVIZ2"
echo "========================================="

# Change to workspace directory
cd /home/moos/dev_ws/dual_arms

# Run robot_state_publisher in the background
echo "Starting robot_state_publisher..."
ros2 run robot_state_publisher robot_state_publisher urdf/dual_openarm.urdf &
RSP_PID=$!

echo "Starting RViz2..."
rviz2

# When RViz2 is closed, kill robot_state_publisher
kill $RSP_PID
echo "Closed RViz2."
