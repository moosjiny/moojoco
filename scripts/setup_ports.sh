#!/bin/bash

# This script helps identify Dynamixel USB devices and creates udev rules
# for consistent naming in the dual-arm setup.

echo "--- Dual-arm USB Device Identification ---"
echo "Please plug in ONE arm at a time and run this script to see its ID."
echo ""

ls -l /dev/serial/by-id/

echo ""
echo "Example udev rule (/etc/udev/rules.d/99-dual-arms.rules):"
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", ATTRS{serial}=="FT789XYZ", SYMLINK+="ttyUSB_left_follower"'
echo ""
echo "To apply changes: sudo udevadm control --reload-rules && sudo udevadm trigger"
