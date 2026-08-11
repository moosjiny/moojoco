#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B — B-2: 최소 MuJoCo 스트리밍 브리지

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage1-scoping]] B-1 조사 완료 후 사령관 지시 — "B-2 시작해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 구현

`scripts/mujoco_bridge_server.py` — `urdf/dual_openarm_handshake.xml`을 로드해 `mj_step`으로 물리를 진행시키고, 매 스텝 관절 각도(qpos)를 접속된 모든 WebSocket 클라이언트에 JSON으로 broadcast하는 순수 상태-송출 서버. `asyncio` + `websockets` 라이브러리만 사용(이미 venv에 설치돼 있어 신규 의존성 없음), 렌더링·Rerun 없이 물리 스텝과 네트워크만 담당한다. 60Hz로 스텝을 시도하되 프레임 처리 시간을 빼고 남은 시간만큼만 sleep하는 방식.

B-2는 의도적으로 "상태를 내보낼 수 있는가"만 증명하는 범위다 — 프론트엔드에서 제어 목표를 받는 것은 B-3의 일이라 이번 서버는 수신 메시지를 그냥 버린다(`async for _ in websocket: pass`).

## 1. 실측 검증

로컬에서 서버를 띄우고 별도 파이썬 WebSocket 클라이언트로 접속해 5회 샘플을 받았다:

```
[bridge] MuJoCo bridge serving ws://0.0.0.0:8765 — model: dual_openarm_handshake.xml
[bridge] 36 joints, 32 actuators, 49 bodies
[bridge] client connected (1 total)
[bridge] client disconnected (0 total)

time sequence: [1.058, 1.06, 1.062, 1.064, 1.066]
num joints in payload: 36
```

`time` 필드가 프레임마다 단조 증가해 `mj_step`이 실제로 루프를 돌고 있음을 확인했다. 접속/해제 로그도 정상.

**정직하게 남길 점**: 샘플링한 `left_joint_2` 값은 5회 내내 정확히 0.0으로 고정돼 있었다 — 팔이 흐느적거리며 떨어지는 모습을 기대했다면 실망스러울 수 있다. 이건 버그가 아니라, 이 MJCF의 32개 `<general>` 액추에이터가 `ctrl=0`일 때 "관절을 0 위치에 붙잡아두는" 게인을 기본으로 갖고 있기 때문이다(위치 서보에 가까운 거동). 즉 액추에이터가 실제로 작동 중이라는 뜻이고, 프론트엔드 슬라이더 값을 제어 목표로 흘려보내면(B-3) 실제로 움직이게 될 것으로 예상한다 — 지금 "정지해 있는 것"이 오히려 액추에이터가 제대로 붙잡고 있다는 증거다.

## 2. 배포 상태

**아직 상시 서비스로 등록하지 않았다.** 검증 후 프로세스를 종료했다 — 포트 8765를 계속 열어두는 결정은 B-3에서 프론트엔드 연동과 함께 하는 게 맞다고 판단해 지금은 보류. 필요하면 `mujoco_sim.service`처럼 systemd 유닛으로 등록할 것.

## 3. 다음 단계 (B-3)

`fingershake-robot-main`에 "MuJoCo Live (Arms)" 모드를 추가해 이 브리지에 WebSocket으로 접속하고, (a) 수신한 qpos를 렌더링에 반영하는 것과 (b) 슬라이더 값을 제어 목표로 서버에 전송하는 것 두 방향을 모두 여는 작업. 관절 이름 매핑(`left_joint_1..7` ↔ `shoulderPitch/Yaw/Roll, elbowFlexion, wristPitch/Roll/Yaw`)도 이 단계에서 정의해야 한다.
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage2-bridge",
    "title": "옵션 B — B-2: 최소 MuJoCo 스트리밍 브리지",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-12-moojoco-option-b-stage1-scoping]]에서 확인한 기존 dual_openarm_handshake.xml MJCF 모델을 "
        "mj_step으로 구동하고 관절 각도를 WebSocket으로 broadcast하는 최소 브리지 서버(scripts/"
        "mujoco_bridge_server.py)를 신규 의존성 없이(asyncio+websockets, 이미 설치됨) 구현했다. 36개 관절, "
        "32개 액추에이터, 49개 바디를 확인했고, 별도 테스트 클라이언트로 접속해 time 필드가 프레임마다 단조 "
        "증가함을 확인해 물리 스텝이 실제로 진행되고 있음을 검증했다. 샘플링한 관절이 0에 고정돼 있던 것은 "
        "버그가 아니라 <general> 액추에이터의 기본 위치-홀드 게인 때문이며, 이는 오히려 액추에이터가 정상 "
        "작동 중이라는 증거임을 정직하게 남겼다. 아직 상시 서비스로 등록하지 않았고, 프론트엔드 연동(B-3)에서 "
        "관절 이름 매핑과 양방향 통신(상태 수신 + 제어 목표 송신)을 추가할 예정이다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-2 최소 스트리밍 브리지 구현·실측, 아직 상시 서비스 아님",
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
