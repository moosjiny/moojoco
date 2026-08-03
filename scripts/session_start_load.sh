#!/usr/bin/env bash
# SessionStart 훅 — 이전 SessionEnd 훅이 남긴 스냅샷을 읽어 새 세션 컨텍스트에 주입한다.
# 스냅샷이 없으면(첫 실행 등) 아무 출력 없이 조용히 종료 — 세션 시작을 절대 막지 않는다.
set -uo pipefail

STATE_FILE="/home/moos/.hb5u_session/moojoco_state.json"

if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

SUMMARY=$(jq -r '
  "지난 세션 스냅샷 (" + (.timestamp // "unknown") + ")\n" +
  "- git HEAD: " + (.git.head // "unknown") +
    (if ((.git.status // []) | length) > 0
     then " (미커밋 변경 " + ((.git.status|length)|tostring) + "개)"
     else " (clean)" end) + "\n" +
  "- mujoco_sim: " + (.services.mujoco_sim // "unknown") +
    " / viz_server: " + (.services.viz_server // "unknown") + "\n" +
  "- 최근 ntfy(roops-comm) " + ((.recent_ntfy // [])|length|tostring) + "건: " +
    (([.recent_ntfy[]?.title] | join(" | ")) // "")
' "$STATE_FILE" 2>/dev/null)

if [ -z "$SUMMARY" ]; then
  exit 0
fi

jq -n --arg ctx "$SUMMARY" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
exit 0
