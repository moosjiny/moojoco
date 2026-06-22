#!/bin/bash
echo "========================================="
echo "  ROS2 TELEOP KEYBOARD FOR LEFT ARM"
echo "========================================="
echo "Controls:"
echo "  i/k : Forward/Backward (X axis)"
echo "  j/l : Left/Right (Y axis)"
echo "  u/o : Up/Down (Z axis - combined with i/k usually)"
echo "  (teleop_twist_keyboard uses standard drone/robot mapping)"
echo ""
echo "Press Ctrl+C to exit."
echo "========================================="
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/target_left/cmd_vel
