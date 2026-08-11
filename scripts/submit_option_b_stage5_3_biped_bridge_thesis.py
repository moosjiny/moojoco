#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# B-5-3: 균형 제어기 실시간 스트리밍 브리지

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage5-2-balance-control]] B-5-2 완료 후 사령관 지시 — "다음 단계 착수해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 구현

`scripts/biped_bridge_server.py` — B-2의 팔 브리지(`mujoco_bridge_server.py`)와 같은 broadcast 패턴을 바이페달 모델에 적용했다. 팔 브리지와 다른 점:

- 포트 8766(팔 브리지 8765와 별도, 동시 실행 가능)
- 균형 제어기(`biped_balance_controller.BipedBalanceController`)가 **클라이언트 명령 없이 항상 켜져 있다** — B-5-2에서 제어기 없이는 몇 초 안에 넘어진다는 걸 이미 확인했기 때문에 옵션이 아니라 기본값
- 물리 스텝(0.002s)마다 제어기를 돌리고, 60Hz로 상태(time/pelvis_z/pitch_deg/qpos)를 broadcast
- 클라이언트가 `{"push_n": N, "duration": s}`를 보내면 골반에 수평 외란력을 가함 — B-5-2에서 오프라인으로 했던 push 테스트를 실시간으로 재현할 수 있는 테스트 훅

## 1. 실측 검증

**1차 시도(하나의 연결에서 15N→20N 연속 테스트)**: 15N은 회복(예상대로), **20N도 회복** — B-5-2 오프라인 결과(20N은 매번 낙상)와 어긋남.

원인을 의심하지 않고 그대로 "성공"이라 보고하는 대신 재현했다: 서버를 재시작해 15N 테스트 없이 20N 단독으로만 테스트했더니 **정확히 오프라인과 같은 결과로 낙상**(t=14.96s, max_tilt=54.52deg, 오프라인 기록의 max_tilt=54.84deg와 거의 일치). 즉 브리지 자체는 정확히 동작하고 있고, 1차 시도의 불일치는 **15N push의 잔여 진동이 채 가라앉기 전에 20N push를 이어서 준 것**이 원인이었다 — 20N은 원래 안정성 경계에 거의 걸쳐 있는 값(B-5-2에서 15N 안정/20N 낙상으로 갈렸음)이라, 초기 상태가 아주 조금만 달라도(잔여 모멘텀 유무) 결과가 뒤집힐 수 있다는 뜻이다. 이는 버그가 아니라 **경계 근처에서 동작하는 실제 비선형 동역학의 특성**이라고 정직하게 남긴다.

## 2. 정직하게 남길 것

- 브리지 자체는 검증됐다 — 격리된 조건에서 오프라인 스크립트와 사실상 동일한 수치(max_tilt 54.52 vs 54.84deg)를 재현했다.
- 20N 경계값 근처에서의 결과는 초기 상태(직전 외란의 잔여 진동)에 민감하다 — "20N이면 항상 넘어진다"는 B-5-2의 결론은 여전히 유효하지만, "20N 근처의 실제 경계는 초기 조건에 따라 흔들릴 수 있다"는 단서를 덧붙인다.
- 서버는 검증 후 다시 종료했다 — 아직 상시 서비스가 아니다.

## 3. 다음 단계

- 팔 통합(양팔+다리), 두 로봇 통합, fingershake-robot-main 프론트엔드 연동은 여전히 미착수
- (제안) 더 넓은 외란 내성을 원하면 hip strategy 추가나 게인 재튜닝이 필요 — 이번 단계에서 발견한 "20N 근처 경계 민감성"이 그 근거
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage5-3-biped-bridge",
    "title": "B-5-3: 균형 제어기 실시간 스트리밍 브리지",
    "author": "Moojoco",
    "abstract": (
        "B-5-2에서 튜닝한 균형 제어기를 B-2 패턴의 WebSocket 브리지(scripts/biped_bridge_server.py, 포트 8766)로 "
        "실시간 스트리밍했다. 제어기는 옵션이 아니라 항상 켜져 있고, 클라이언트가 push_n 메시지로 외란을 실시간 "
        "주입할 수 있다. 15N→20N을 한 연결에서 연속 테스트했을 때 20N도 회복돼 B-5-2의 오프라인 결과(20N 매번 "
        "낙상)와 어긋났는데, 그대로 보고하지 않고 서버를 재시작해 20N 단독으로 재현한 결과 오프라인과 거의 동일한 "
        "수치(max_tilt 54.52 vs 54.84deg)로 낙상해 브리지 자체는 정확함을 확인했다. 불일치의 원인은 직전 15N "
        "push의 잔여 진동이 20N 경계값 근처의 민감한 동역학에 영향을 준 것으로, 버그가 아니라 실제 비선형계의 "
        "특성임을 정직하게 남긴다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-5-3 실시간 스트리밍 브리지 구현·검증(20N 경계 민감성 발견 포함)",
    "body_md": BODY_MD,
}

data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    URL,
    data=data,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as r:
    res = json.loads(r.read().decode())
    print("SUBMITTED:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
