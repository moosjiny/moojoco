#!/usr/bin/env bash
# PostToolUse 훅(Bash|Edit|Write 전용) — 활동 한 줄을 jsonl에 append.
# 반드시 가볍게: 전체 명령/출력은 저장하지 않고, Bash는 프로그램명(+비-플래그 다음 토큰)만,
# Edit/Write는 파일 경로만 남긴다. 혹시 남더라도 토큰/키 패턴은 정규식으로 한 번 더 마스킹한다.
set -uo pipefail

LOG="/home/moos/.hb5u_activity/moojoco_activity.jsonl"
mkdir -p "$(dirname "$LOG")"

input=$(cat)
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
tool=$(printf '%s' "$input" | jq -r '.tool_name // "unknown"' 2>/dev/null)

summary=$(printf '%s' "$input" | jq -r '
  if .tool_name == "Bash" then
    (.tool_input.command // "" | split(" ") | map(select(length > 0)))
    as $w | ($w[0] // "") + (if ($w[1] // "" | startswith("-") | not) and ($w[1] // "" | length) > 0 then " " + $w[1] else "" end)
  elif .tool_name == "Edit" or .tool_name == "Write" then
    (.tool_input.file_path // "")
  else "" end
' 2>/dev/null)

# 방어적 마스킹(2차): 혹시 토큰류 패턴이 남아있으면 가림
summary=$(printf '%s' "$summary" | sed -E \
  -e 's/(Bearer|bearer)[[:space:]]+[A-Za-z0-9_.-]+/\1 [redacted]/g' \
  -e 's/([Tt]oken|[Kk]ey)[=:][A-Za-z0-9_.-]+/[redacted]/g')

jq -nc --arg ts "$ts" --arg tool "$tool" --arg summary "$summary" \
  '{ts:$ts, agent:"moojoco", tool:$tool, summary:$summary}' >> "$LOG" 2>/dev/null

# 로그 크기 제한(최근 500줄만 유지)
if [ -f "$LOG" ]; then
  tail -n 500 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
fi

exit 0
