#!/usr/bin/env bash
# SessionEnd 훅 — git/서비스/최근 ntfy 상태를 JSON 스냅샷으로 저장하고
# RHMS/Memory API에 best-effort로 전송한다. 세션 종료를 절대 막지 않는다(전부 실패 허용).
set -uo pipefail

REPO="/home/moos/dev_ws/dual_arms"
STATE_DIR="/home/moos/.hb5u_session"
STATE_FILE="$STATE_DIR/moojoco_state.json"
NTFY_TOKEN="tk_zytmr8y6e9cr51xufjtw5bqyanv6a"

mkdir -p "$STATE_DIR"

GIT_HEAD=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_STATUS=$(git -C "$REPO" status --short 2>/dev/null | head -20 | jq -R -s -c 'split("\n") | map(select(length > 0))')
MUJOCO_ACTIVE=$(systemctl is-active mujoco_sim 2>/dev/null || echo "unknown")
VIZ_ACTIVE=$(systemctl is-active viz_server 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

NTFY_RECENT=$(curl -s --max-time 5 "https://ntfy.hyperbook.com/roops-comm/json?poll=1&since=6h" \
  -H "Authorization: Bearer $NTFY_TOKEN" 2>/dev/null \
  | tail -5 \
  | jq -s -c '[.[] | {id, time, title}]' 2>/dev/null)
[ -z "$NTFY_RECENT" ] && NTFY_RECENT="[]"

jq -n \
  --arg ts "$TIMESTAMP" \
  --arg head "$GIT_HEAD" \
  --argjson status "${GIT_STATUS:-[]}" \
  --arg mujoco "$MUJOCO_ACTIVE" \
  --arg viz "$VIZ_ACTIVE" \
  --argjson ntfy "$NTFY_RECENT" \
  '{timestamp: $ts, git: {head: $head, status: $status}, services: {mujoco_sim: $mujoco, viz_server: $viz}, recent_ntfy: $ntfy}' \
  > "$STATE_FILE" 2>/dev/null

# best-effort cross-agent persistence — never block/fail session end
if [ -f "$HOME/.env_roops" ]; then
  set -a; source "$HOME/.env_roops" 2>/dev/null; set +a
fi

if [ -n "${RHMS_KEY_MOOJOCO:-}" ] && [ -f "$STATE_FILE" ]; then
  curl -s --max-time 5 -X POST "https://ec2.hyperbook.com/rhms/store" \
    -H "X-Api-Key: $RHMS_KEY_MOOJOCO" \
    -H "Content-Type: application/json" \
    -d "{\"agent\":\"moojoco\",\"text\":$(jq -Rs . < "$STATE_FILE"),\"tags\":[\"session-snapshot\",\"auto\"]}" \
    >/dev/null 2>&1 || true
fi

if [ -n "${MEMORY_API_KEY_MOOJOCO:-}" ] && [ -f "$STATE_FILE" ]; then
  curl -s --max-time 5 -X POST "https://egs2.hyperbook.com/msg?agent=moojoco" \
    -H "x-api-key: $MEMORY_API_KEY_MOOJOCO" \
    -H "Content-Type: application/json" \
    -d "{\"from_agent\":\"moojoco\",\"to_agent\":\"aegis\",\"body\":$(jq -Rs . < "$STATE_FILE")}" \
    >/dev/null 2>&1 || true
fi

exit 0
