#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B — B-4: 프론트엔드 연동 (MuJoCo Live, Alpha 오른팔)

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage3-pd-control]] B-3 완료 후 사령관 지시 — "이어가."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 구현

`fingershake-robot-main`에 "MuJoCo Live" 토글(우측 상단 CPU 아이콘, 수동 조작 모드 전용)을 추가했다. 켜면:

1. 브라우저가 `ws://<host>:8765`(B-2/B-3 브리지 서버)로 WebSocket 연결
2. Alpha 로봇 오른팔 슬라이더 7개(Shoulder Pitch/Yaw/Roll, Elbow Flexion, Wrist Pitch/Roll/Yaw) 값을 10Hz로 `{"target": {"right_joint1_ctrl": rad, ...}}` 메시지로 전송 — [[2026-08-12-moojoco-option-b-stage1-scoping]]에서 정한 대로 관절 이름 1:1 순서 매핑(해부학적으로 정확하지 않은 근사)
3. 브리지가 매 프레임 broadcast하는 `qpos`를 받아 같은 4개 그룹(rightShoulder/rightElbow/rightWrist)의 회전에 그대로 적용 — 슬라이더 값을 직접 반영하던 기존 로직을 대체

껐을 때는 즉시 기존 방식(슬라이더 → 회전 직접 매핑)으로 복귀한다. 소켓 연결/해제는 `mujocoLive` 토글에만 반응하는 별도 useEffect가 담당하고, 목표 전송·qpos 반영은 기존 애니메이션 루프 안에서 매 프레임 처리한다 — 소켓을 슬라이더 조작마다 재연결하지 않기 위한 구조.

## 1. 실측 검증

로컬에서 브리지 서버를 기동한 뒤(수동 실행, 아직 systemd 아님), 배포된 프론트엔드를 새 탭에서 열어(같은 URL 재사용이 아니라 `?cachebust=` — [[feedback_browser_verification_fresh_tab]] 교훈 적용) 확인했다:

- MuJoCo Live 토글 클릭 → 상태 문구가 "연결 중..." → "ON — 실제 물리 브리지 연결됨"으로 전환, 브리지 서버 로그에 `client connected` 기록
- Shoulder Pitch 슬라이더를 -64°→20°로 변경 → 로봇 오른팔이 브리지가 반환한 qpos를 따라 자세를 바꿈(직접 스냅이 아니라 브리지의 PD 제어를 거친 값)
- 콘솔에 WebSocket/JS 에러 없음
- MuJoCo Live를 다시 끔 → 상태 문구 사라지고, 팔은 마지막 qpos 값 그대로 유지된 채(마지막 각도가 이미 슬라이더 값과 거의 일치하는 상태였음) 이후 슬라이더 조작에 다시 직접 반응 — 회귀 없이 정상 폴백 확인

## 2. 정직하게 남길 한계

- KP=8.0/KD=0.5 게인은 B-3에서 `right_joint_1` 하나로만 튜닝됐다. 이번 검증은 Shoulder Pitch(joint_1) 위주였고, 나머지 6개 관절이 같은 게인으로 동일하게 잘 settle되는지는 개별 확인하지 않았다 — 크게 벗어난 진동/오버슈트가 관찰되면 관절별 게인 분리가 다음 과제가 될 수 있다.
- 관절 이름 매핑은 여전히 순서 기반 근사다. 실제 로봇 팔의 자유도 축 방향(회전축)이 fingershake 캐릭터의 어깨/팔꿈치/손목 회전축과 정확히 일치한다는 보장은 없다 — "그럴듯하게 움직인다"는 것만 확인했다.
- 브리지 서버는 검증 후 다시 종료했다. **상시 서비스(systemd) 등록 여부는 이번 단계에서도 결정하지 않았다** — 외부에 새 포트(8765)를 상시 열어두는 결정이라 사령관 확인 후 진행한다.

## 3. 다음 단계

- 사령관 승인 시: `mujoco_bridge_server.py`를 `mujoco_sim.service`/`fingershake_web.service`와 같은 패턴의 systemd 유닛으로 등록해 상시 서비스화
- (장기, 별도 승인) B-5: 다리/몸통이 있는 바이페달 MJCF를 신설해 Stage 1/2의 분석적 CoM/ZMP 근사를 실제 MuJoCo 강체 동역학으로 대체
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage4-frontend",
    "title": "옵션 B — B-4: 프론트엔드 연동 (MuJoCo Live, Alpha 오른팔)",
    "author": "Moojoco",
    "abstract": (
        "B-3에서 검증한 PD 위치제어 브리지를 fingershake-robot-main에 연동했다. 수동 조작 모드에 "
        "'MuJoCo Live' 토글을 추가해, 켜면 Alpha 로봇 오른팔 슬라이더 7개 값을 10Hz로 브리지에 목표각으로 "
        "전송하고 브리지가 broadcast하는 qpos를 그대로 렌더링에 반영한다(관절 이름 1:1 순서 매핑, 해부학적으로 "
        "정확하지 않은 근사). 새 탭 검증에서 연결 상태 전환, 슬라이더 변경에 따른 팔 자세 갱신, 토글 해제 시 "
        "직접 제어로의 정상 폴백을 모두 확인했고 콘솔 에러는 없었다. PD 게인은 여전히 관절 1개로만 튜닝된 "
        "상태이고, 브리지 서버의 상시 서비스화(systemd, 포트 8765 상시 개방) 여부는 사령관 확인 후 진행하기로 "
        "결정을 미뤘다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-4 프론트엔드 연동(MuJoCo Live 토글) 구현·실측, 상시 서비스화는 보류",
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
