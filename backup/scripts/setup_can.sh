#!/bin/bash

# Script to setup CAN interfaces for Damiao motors (OpenArm)
# Requires sudo privileges

setup_can() {
    INTERFACE=$1
    echo "Setting up $INTERFACE..."
    sudo ip link set $INTERFACE down 2>/dev/null
    sudo ip link set $INTERFACE up type can bitrate 1000000 dbitrate 5000000 fd on
    if [ $? -eq 0 ]; then
        echo "$INTERFACE is UP (CAN-FD 1M/5M)"
    else
        echo "Failed to setup $INTERFACE. Check if hardware is connected."
    fi
}

setup_can can0
setup_can can1

# Show status
ip -details link show can0
ip -details link show can1
