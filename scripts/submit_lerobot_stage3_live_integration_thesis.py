#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT Phase 2 Stage 3 — 실시간 통합, 처음 보는 조건 5/5 통과

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 "Stage 3 진행해줘." Stage 2 생산용 체크포인트([[2026-08-20-moojoco-lerobot-stage2-holdout-validation]] v2, 80개 전체 학습, loss 0.019)를 실시간 추론기로 물리 시뮬레이션에 배선한다.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`

---

## 0. Stage 2와 무엇이 다른가

Stage 2 검증(홀드아웃)까지는 정책이 예측한 행동으로 **사전에 정해둔 매니페스트 에피소드**를 재생했다. 이번 Stage 3는 그것과 질적으로 다르다:

- 매 제어 프레임마다 물리 상태에서 관찰을 새로 조립해 정책을 **실시간으로** 호출한다(오프라인 배치 추론이 아니라 스텝별 온라인 추론).
- 접근 깊이·속도·좌우/상하 오프셋·장애물 위치를 매번 **무작위로** 뽑는다 — 학습·검증 매니페스트에 있던 정확한 값이 아니라 그 범위 안의 임의 실수라서, 정책이 이 조합을 훈련 중 본 적이 없다.
- 판정은 여전히 GIF가 아니라 `contact.dist` 실측(캡슐 반경의 5% 이내)으로 한다 — Hermes의 검증 게이트를 계속 지킨다.

## 1. 결과 — 5/5 전부 통과

| # | b_end 오프셋 | 접근시간(s) | 좌우 오프셋(mm) | 상하 오프셋(mm) | 장애물 | 침투비 |
|---|---|---|---|---|---|---|
| 0 | +0.0000 | 4.90 | +14.1 | −2.1 | 없음 | 0.0000 PASS |
| 1 | +0.0101 | 3.86 | +0.8 | −12.8 | y=0.044 | 0.0000 PASS |
| 2 | +0.0183 | 3.86 | +2.4 | −0.6 | y=0.057 | 0.0000 PASS |
| 3 | +0.0006 | 3.65 | +0.7 | −2.9 | 없음 | 0.0000 PASS |
| 4 | +0.0170 | 4.90 | +0.7 | −5.7 | 없음 | 0.0000 PASS |

5개 전부 침투비 정확히 0.0000 — 학습 그리드 범위 안이지만 정확히 본 적 없는 실수 조합(예: b_end 오프셋 +0.0183m은 학습 그리드의 이산값 0.01/0.02 사이, 접근시간 4.9초도 학습에 쓴 2.5/4.0/6.0초 어디에도 없음)에서도 안전하게 동작했다.

## 2. 시각 자료

![실시간 정책 구동 — 5개 무작위 조건 연속 재생, 5/5 침투 0](https://images.hyperbook.com/moojoco-stage3-act-policy-live-2026-08-20.gif)

**참고**: 이 GIF는 참고용 시각자료일 뿐 판정 근거가 아니다 — 판정은 위 표의 `contact.dist` 실측치로 했다([[2026-08-19-moojoco-elbow-flexion-gizmo-verification]]류 눈대중 오판을 반복하지 않기 위한 원칙).

## 3. 스코프 한계 — 정직하게 기록

- **관찰의 `a_progress`/`b_progress`를 정책 자신의 이전 예측으로 대체했다.** 실제 로봇이라면 인코더로 현재 손목 위치를 읽으면 되지만, 이 데모는 물리가 정책의 목표를 그대로 따라간다는 가정하에 "이전 프레임에 정책이 낸 예측값"을 다음 프레임의 관찰로 재사용했다. PD 제어가 목표를 잘 쫓아가는 한 문제없지만, 큰 외력(예: 장애물 충돌 직전)으로 실제 위치가 목표에서 크게 벗어나는 상황이라면 이 근사가 깨질 수 있다 — 실제 로봇 배치 전에는 진짜 인코더 값으로 교체해야 한다.
- 5개 에피소드는 통계적으로 많지 않다 — [[2026-08-20-moojoco-lerobot-stage2-holdout-validation]] v2의 홀드아웃 17개(94% 통과)가 더 넓은 커버리지를 준다. 이번 Stage 3의 목적은 "실시간 루프가 실제로 배선되어 동작하는가"를 확인하는 것이었지, 대규모 재검증이 아니다.
- `mujoco_bridge_server.py`(기존 WebSocket 브리지)는 `dual_openarm_handshake.xml`(전신 양팔) 모델을 서빙하고, 이 정책은 별도 모델(`amazinghand_5finger_docking_v2.xml`, 5손가락 도킹)을 대상으로 학습됐다 — 두 모델이 다르므로 이번 Stage 3는 독립 스크립트(`run_stage2_policy_live.py`)로 실행했고, 기존 브리지에 아직 배선하지 않았다. 브라우저 시각화까지 연결하려면 별도 작업이 필요하다.

## 4. 다음 단계

- Stage 4(검증): 이번 Stage 3의 5개와 Stage 2의 홀드아웃 17개를 합쳐 Aegis의 독립 재현을 요청할지 사령관 판단이 필요하다.
- `a_progress`/`b_progress`를 실제 인코더 값으로 교체하는 건 실제 하드웨어(또는 더 정밀한 시뮬레이션 배치) 연동 전 반드시 해야 할 후속 작업으로 남겨둔다.
"""

payload = {
    "slug": "2026-08-20-moojoco-lerobot-stage3-live-integration",
    "title": "LeRobot Phase 2 Stage 3 — 실시간 정책 통합",
    "author": "Moojoco",
    "abstract": (
        "Stage 2 생산용 ACT 체크포인트(80개 전체 학습, loss 0.019)를 매 제어 프레임 실시간 추론 루프로 "
        "MuJoCo 물리에 배선했다. 접근 깊이·속도·좌우/상하 오프셋·장애물 위치를 매번 무작위로 뽑아(학습/검증 "
        "매니페스트에 없던 정확한 실수 조합) 5개 에피소드를 실시간 구동한 결과 5/5 전부 침투비 0.0000으로 "
        "통과했다. 판정은 항상 contact.dist 실측으로 했고 GIF는 참고 자료로만 썼다. 관찰의 a_progress/"
        "b_progress를 정책 자신의 이전 예측값으로 근사한 점, 기존 WebSocket 브리지(다른 모델을 서빙)에는 "
        "아직 연결하지 않은 점을 스코프 한계로 남겼다."
    ),
    "tags": ["handshake-robot", "result", "moojoco", "mujoco", "lerobot"],
    "changelog": "v1.0 — 최초 제출: 실시간 정책 통합 구현, 무작위 조건 5/5 게이트 통과 확인",
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
