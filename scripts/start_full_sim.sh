#!/bin/bash
# ========================================================
# Dual-Arm MuJoCo + ROS2 Full Environment Launcher
# ========================================================

# 이동
cd /home/moos/dev_ws/dual_arms

# 0. 기존 프로세스 완전 정리 (중복 실행 방지)
echo "Cleaning up existing processes..."
pkill -9 -f robot_state_publisher 2>/dev/null
pkill -9 -f rviz2 2>/dev/null
pkill -9 -f sim_ros2_ik.py 2>/dev/null
pkill -9 -f rviz_interactive_marker.py 2>/dev/null
sleep 1

# 1. XML 최신화 (초기 위치 등 반영)
echo "Rebuilding MJCF..."
/home/moos/venv/dual_arms/bin/python scratch/build_mjcf.py

# 2. MuJoCo 시뮬레이터 실행 (Background)
echo "Starting MuJoCo Simulation..."
/home/moos/venv/dual_arms/bin/python scripts/sim_ros2_ik.py &
SIM_PID=$!

# 3. RViz2 화살표 서버 실행 (Background)
echo "Starting Interactive Marker Server..."
/home/moos/venv/dual_arms/bin/python scripts/rviz_interactive_marker.py &
MARKER_PID=$!

# 4. RViz2 및 로봇 모델 배포 실행 (Foreground)
echo "Launching RViz2 and Robot State Publisher..."
./scripts/launch_rviz_robot.sh

# RViz2가 종료되면 나머지 프로세스도 종료
kill $SIM_PID $MARKER_PID
echo "Cleanup complete."
