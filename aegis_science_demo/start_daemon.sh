#!/usr/bin/env bash
# Aegis Science Demo Persistent Web Server Supervisor Daemon
# Ensures http://127.0.0.1:8590/ runs continuously without interruption

WEB_DIR="/home/moos/dev_ws/aegis/science_demo"
PORT=8590

echo "🚀 Starting Aegis Science Demo Supervisor Daemon on port $PORT..."
cd "$WEB_DIR" || exit 1

while true; do
    # Check if port 8590 is already bound
    if ! lsof -i:$PORT >/dev/null 2>&1; then
        echo "[$(date)] Starting python3 -m http.server $PORT..."
        python3 -m http.server $PORT >> "$WEB_DIR/server_daemon.log" 2>&1
    fi
    sleep 3
done
