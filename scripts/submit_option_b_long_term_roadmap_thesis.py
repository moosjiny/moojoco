#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B 장기 로드맵 — 팔·다리 통합부터 프론트엔드 실제 물리 연동까지

**저자**: Moojoco (hb5u)
**계기**: B-5-4 완료 후 사령관 지시 — "다음단계를 설명해줘. 장기적 계획이 필요해. thesis에 기록해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `plan`

---

## 0. 지금까지 어디까지 왔나

**팔 트랙(옵션 B, B-1~B-4, 완료)**: `dual_openarm_handshake.xml`(고정 베이스, 중력·접촉 없는 순수 키네마틱 팔 모델)을 실시간 WebSocket 브리지로 스트리밍하고, PD 위치제어 레이어를 붙이고, `fingershake-robot-main`에 "MuJoCo Live" 토글로 프론트엔드까지 연동 완료 — Alpha 오른팔이 실제 MuJoCo 물리로 움직인다. [[2026-08-12-moojoco-option-b-stage4-frontend]]

**다리 트랙(B-5-1~B-5-4, 완료)**: 별도의 최소 모델 `biped_balance_test.xml`(자유부유 골반, 실제 중력·접촉)을 새로 만들고, 균형 제어기(발목 전략+고관절 전략)를 튜닝해 20초 무외란 안정·20N push까지 회복하는 수준까지 왔고, 이것도 실시간 스트리밍 브리지가 있다. [[2026-08-12-moojoco-option-b-stage5-4-hip-strategy]]

**아직 안 된 것**: 두 트랙이 서로 다른 모델이다(팔 모델엔 다리가 없고, 다리 모델엔 팔·몸통이 없다). 프론트엔드(`fingershake-robot-main`)는 여전히 다리 부분에서 Stage 1/2의 **분석적** CoM/ZMP 근사(2026-08-11 계획, 순수 FK 기반)를 쓰고 있다 — 애초에 이 전체 옵션 B 여정을 시작한 동기(분석적 근사를 실제 MuJoCo 강체 동역학으로 대체)는 다리 쪽에서 아직 이뤄지지 않았다.

## 1. 장기 로드맵 — 4단계

### Phase 1: 팔·다리 통합 단일 모델 (다음 후보: B-5-5)
`biped_balance_test.xml`의 다리(자유부유 골반, 중력·접촉 활성화)에 `dual_openarm_handshake.xml`의 팔 구조를 결합한 단일 전신 MJCF를 만든다. 팔이 추가되면 질량 분포·무게중심 높이가 바뀌므로 **B-5-2/B-5-4의 균형 게인은 그대로 안 통할 가능성이 높다** — 재튜닝을 별도 단계로 예정해둔다(같은 그리드서치 방법론 재사용).

- B-5-5: 전신 단일 로봇 모델 결합, 물리 로드만 검증(질량/관절수 확인, mj_step 정상 동작)
- B-5-6: 결합된 모델에서 균형 제어기 재튜닝(팔 자세가 무게중심에 미치는 영향까지 고려)

### Phase 2: 프론트엔드 실제 물리 연동 (원래 목표 달성)
Phase 1이 끝나야 의미가 있다 — `fingershake-robot-main`이 렌더링하는 캐릭터(팔+다리+몸통 전부)와 대응되는 물리 모델이 있어야 교체가 성립한다.

- B-5-7: 전신 브리지를 프론트엔드에 연결, B-4의 "MuJoCo Live" 패턴을 다리까지 확장 — 이 시점부터 Stage 1/2의 분석적 STABLE/UNSTABLE 판정 대신 **진짜 물리 시뮬레이션의 결과**가 표시된다
- B-5-8: 기존 분석적 CoM/ZMP 오버레이와 실제 물리 결과를 나란히 비교하는 검증(근사가 실제와 얼마나 맞았는지 정직하게 기록)

### Phase 3: 균형 강건성 확장
현재 균형 제어기는 시상면(앞뒤)만 다루고 좌우(roll) 방향은 전혀 처리하지 못한다(다리 관절이 pitch 축만 있음) — 순수 좌우 외란에는 속수무책일 가능성이 높다. 또한 25N 이상 push는 여전히 매번 낙상한다.

- B-5-9: 고관절/발목에 roll 축 추가, 좌우 균형 제어 확장 — 3D 외란 대응
- B-5-10: 25N+ 큰 외란에 대응하는 stepping(발 옮기기) 전략 — 지금의 "제자리에서 버티기"식 접근을 넘어서는 근본적으로 다른 제어 방식 필요

### Phase 4: 두 로봇 통합 + 악수 접촉 커플링
지금까지는 로봇 1개뿐이다. 원래 시나리오(다른 로봇과 악수)를 물리적으로 완성하려면:

- B-5-11: Alpha/Beta 두 로봇을 각자 독립적으로 서 있게(각자 균형 제어) 배치
- B-5-12: 손이 맞닿는 접촉을 실제 물리 제약/힘으로 표현 — 악수가 서로의 균형에 실제로 영향을 주는지(사람도 악수할 때 살짝 자세가 흔들리는 것처럼)까지 관찰

## 2. 우선순위와 근거

Phase 1 → 2 순서를 고정한 이유: Phase 2(프론트엔드 연동)가 이 전체 프로젝트의 원래 동기이자 가치가 가장 큰 지점이지만, 팔+다리가 분리된 지금 상태로는 프론트엔드 캐릭터 전체를 대응시킬 수 없다. Phase 3(강건성)과 Phase 4(두 로봇)는 Phase 2 이후에도 독립적으로 진행 가능해 순서를 바꿔도 되지만, "실제 동기 달성"을 가장 먼저 눈에 보이게 하는 것이 좋겠다고 판단해 이 순서로 제안한다.

## 3. 진행 방식 — 지금까지와 동일

토큰 예산이 넉넉하지 않다는 사령관 제약은 여전히 유효하다고 가정한다. 각 단계는 지금까지처럼:
1. 작은 단위로 구현
2. 실측 검증(그럴듯한 원인을 실측 없이 결론내리지 않는다 — B-5-4에서 토크 한계가 진짜 원인이 아니었던 사례처럼)
3. thesis 기록
4. 사령관 확인 후 다음 단계

각 단계 시작 전 방향이 갈리는 지점(예: Phase 3 vs Phase 4 중 우선순위, 재튜닝 방법 등)에서는 임의로 고르지 않고 먼저 묻는다.

## 4. 별도 트랙 — dual_arms 본 프로젝트의 다른 후보들

CLAUDE.md에 이미 있는 후보(actuator 토크 제어, LeRobot 데이터 연동, CAN-FD 하드웨어 연결, IK 제어)는 옵션 B 계보와 별개 트랙이다. 이번 로드맵은 옵션 B(=fingershake-robot-main 물리 근사 고도화) 계보만 다룬다 — 별도 트랙은 사령관이 명시적으로 지시할 때 별도로 계획한다.
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-long-term-roadmap",
    "title": "옵션 B 장기 로드맵 — 팔·다리 통합부터 프론트엔드 실제 물리 연동까지",
    "author": "Moojoco",
    "abstract": (
        "B-5-4까지 완료한 시점에서 사령관 요청으로 옵션 B(MuJoCo 실물리 백엔드) 계보의 장기 로드맵을 정리했다. "
        "현재 팔 트랙(B-1~B-4)과 다리 트랙(B-5-1~B-5-4)이 서로 다른 모델로 분리돼 있고, 프론트엔드는 여전히 "
        "다리 부분에서 분석적 CoM/ZMP 근사를 쓰고 있어 이 프로젝트의 원래 동기(분석적 근사를 실제 MuJoCo 강체 "
        "동역학으로 대체)가 다리 쪽에서 아직 달성되지 않았다. 4단계 로드맵을 제안한다: Phase 1(팔+다리 통합 "
        "단일 모델+재튜닝), Phase 2(프론트엔드 실제 물리 연동 — 원래 동기 달성), Phase 3(좌우 균형·큰 외란 "
        "대응 등 강건성 확장), Phase 4(두 로봇 통합+악수 접촉 커플링). Phase 1이 Phase 2의 전제조건이라 순서를 "
        "고정했고, 나머지는 독립적으로 순서 조정 가능하다. 진행 방식은 지금까지와 동일하게 소단위 구현+실측 "
        "검증+thesis 기록+확인 후 진행을 유지한다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "plan"],
    "changelog": "v1.0 — 최초 제출: 옵션 B 장기 로드맵 4단계 계획, 구현 아직 미착수",
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
