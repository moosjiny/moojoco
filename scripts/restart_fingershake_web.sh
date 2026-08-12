#!/bin/bash
# fingershake-robot-main 웹 서비스 재시작 편의 스크립트.
# 에이전트(Moojoco)는 sudo 권한이 없어 항상 사령관이 직접 systemctl을 실행해야 했다 —
# 매번 전체 명령을 타이핑하는 대신 이 스크립트 하나로 재시작+상태 확인까지 처리.
set -e
sudo systemctl restart fingershake_web.service
echo "---"
systemctl status fingershake_web.service --no-pager
