#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 실제 접촉 동역학(마찰·ZMP·무게중심) 도입 계획

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-ground-lock-physics-approximation]]의 "지면 고정"은 발바닥 Y좌표 하나만 해석적으로 고정하는 근사였다. 사령관 지시 — "실제 마찰·ZMP·무게중심 같은 접촉 동역학은 시뮬레이션에 적용하기 위한 계획을 세워줘." **이 문서는 계획만 다룬다 — 아직 구현하지 않았다.**
**일자**: 2026-08-11
**분류**: `handshake-robot`, `physics`, `kinematics`, `moojoco`, `plan`

---

## 0. 현재 상태 — 무엇이 없는가

`RobotBuilder.ts`의 모든 메시는 순수 `THREE.Mesh`(지오메트리+머티리얼)뿐이다. 질량(mass), 관성(inertia), 마찰계수(friction), 강체 충돌(collision shape) 어느 것도 정의돼 있지 않다. `package.json`에도 물리엔진 의존성이 전혀 없다(`three`만 렌더링용으로 존재). 즉 지금까지의 모든 "포즈"는 카메라 앞에서 팔다리를 접었다 펴는 애니메이션일 뿐, 중력도 접촉력도 실재하지 않는다. 지면 고정 버튼조차 "발바닥 Y=0"이라는 기구학적 제약 하나만 매 프레임 풀어주는 수학적 트릭이었다.

"진짜" 접촉 동역학이라면 최소한 다음이 필요하다:

1. **무게중심(CoM)** — 각 신체 분절의 질량과 위치로부터 전신 무게중심을 계산
2. **지지 다각형(Support Polygon)** — 바닥에 닿은 발(들)이 만드는 볼록 다각형
3. **ZMP(Zero Moment Point)** — 무게중심의 가속도까지 고려한, 실제 동적 안정성 판정 기준(정적인 CoM 투영보다 한 단계 위)
4. **마찰(Friction)** — 접촉면에서 미끄러짐이 일어나는지 판정하는 마찰원뿔(Coulomb friction cone) 조건
5. **강체 동역학 솔버** — 이 넷을 매 프레임 실제로 풀어 자세를 갱신하는 엔진(현재는 존재하지 않음 — 지금까지의 "물리"는 전부 슬라이더 값을 그대로 회전에 대입하는 애니메이션이었다)

## 1. 3단계 로드맵

전면적인 물리엔진 도입은 이 프로젝트의 성격(Google AI Studio에서 내보낸 단일 React 앱, 백엔드 없음)을 크게 벗어난다. 그래서 "정적 분석 근사"부터 "진짜 강체 시뮬레이션"까지 비용이 점증하는 3단계로 나눈다. 이전 DOF 로드맵([[2026-08-11-moojoco-dof-expansion-roadmap]])과 동일하게, 각 단계는 별도 thesis로 계획→구현→결과를 남기고 사령관이 순서를 정한다.

### 1단계 — CoM + 지지 다각형 + 정적 안정성 판정 (분석적, 신규 의존성 없음)

가장 저비용. 이미 있는 `RobotJointRefs`의 각 관절 그룹 world position만으로 계산 가능:

- 신체 분절별 질량 비율을 상수로 정의(예: 머리 7%, 몸통 40%, 팔 각 8%, 다리 각 18.5% — 인체 분절 질량비 관행값 참고, 실측이 아니므로 근사임을 명시)
- 매 프레임 각 분절 그룹의 `getWorldPosition()`에 질량 가중 평균 → 전신 CoM
- 양발 `footMesh`의 4개 모서리 월드 좌표 → XZ 평면 지지 다각형(두 발이 모두 닿아 있으면 두 사각형의 convex hull)
- CoM의 XZ 투영이 지지 다각형 안에 있는지 점-다각형 판정(ray casting 또는 winding number) → "정적으로 서 있을 수 있는 자세인가"를 즉시 판정
- UI: 바닥에 반투명 지지 다각형 오버레이 + CoM 투영점 마커(안이면 초록, 밖이면 빨강) — 기존 `contactVectorRef`(ArrowHelper) 패턴과 동일하게 `THREE.Line`/`THREE.Mesh`로 구현

**한계**: 정적 판정이다. 실제로 다리를 빠르게 움직이면 관성력 때문에 CoM이 지지 다각형을 벗어나도 안 넘어질 수 있고, 반대로 다각형 안에 있어도 급격한 가속에서는 넘어질 수 있다 — 그게 2단계에서 ZMP가 필요한 이유다.

### 2단계 — 동적 ZMP + 마찰원뿔 경고 (분석적, 프레임 간 미분 필요)

1단계의 CoM에 시간 미분을 더한다:

- 매 프레임 CoM 위치를 이전 프레임과 비교해 속도 → 가속도를 수치 미분(`(pos - prevPos) / dt`, 다시 한 번 미분)
- 단순화된 도립진자(inverted pendulum) ZMP 공식 적용: `ZMP_x = CoM_x - (CoM_height / g) * CoM_accel_x` (z축도 동일)
- ZMP가 지지 다각형을 벗어나면 "동적으로 불안정 — 실제라면 넘어짐" 경고를 텔레메트리 패널에 표시
- 마찰원뿔: 접촉점에서 필요한 수평 반력 대 수직 반력의 비율이 가정된 마찰계수 μ(예: 콘크리트-고무 기준 μ≈0.6)를 넘으면 "미끄러짐 위험" 플래그. 실제 접촉력을 풀지 않으므로, 필요 수평력을 `m * CoM_accel_x`로 근사하고 수직력을 `m * g`로 근사해 비율만 비교하는 방식(정확한 접촉 반력 분배는 3단계 없이는 불가능함을 명시)

**한계**: 여전히 강체 동역학 솔버가 아니라 후처리 분석이다 — 판정만 하지, 불안정하다고 자세를 스스로 고치거나 진짜로 넘어지게 만들지는 못한다. 슬라이더로 사령관이 만든 포즈를 "이게 실제 물리에서 서 있을 수 있는 자세냐"고 진단하는 도구에 가깝다.

### 3단계 — 진짜 강체 동역학 (아키텍처 변경, 2개 옵션)

여기서부터는 "판정"이 아니라 "시뮬레이션"이 필요하다. 두 갈래 옵션이 있고 성격이 다르다:

**옵션 A: 클라이언트 사이드 JS 물리엔진 (예: `rapier3d` 또는 `cannon-es`)**
- 장점: 백엔드 불필요, 기존 React 앱 안에서 npm 패키지 하나 추가로 시작 가능
- 방식: 각 신체 분절을 강체(rigid body)로, 관절을 constraint(revolute joint)로 정의하고 바닥을 정적 평면으로 등록. 슬라이더 값은 각 관절에 목표 각도를 주는 PD 컨트롤러(스프링-댐퍼 토크)로 변환해 관절에 걸어준다. 엔진이 매 스텝 중력·접촉력·마찰·관절 제약을 실제로 풀어 자세를 갱신 → 이때는 "지면 고정" 버튼 자체가 불필요해진다(물리가 알아서 발을 붙이거나, 못 붙이면 실제로 자빠진다).
- 비용: 관절 20여 개의 질량/관성/마찰계수를 전부 튜닝해야 하고, PD 게인이 안 맞으면 로봇이 발작하듯 떨거나 폭발적으로 발산하는 문제가 흔함 — 안정된 바이페달 스탠딩 튜닝 자체가 별도의 반복 작업.

**옵션 B: MuJoCo 백엔드 실시간 연동**
- 이 hb5u 인스턴스의 원래 임무(CLAUDE.md: "MuJoCo 메인 서버")와 직결. `dual_arms` 프로젝트에서 이미 진행 중인 MuJoCo EGL 렌더링·mj_step 동역학 작업과 같은 축.
- 방식: 실제 인간형 바이페달 MJCF 모델을 MuJoCo에서 `mj_step`으로 물리 스텝, 접촉력·마찰·ZMP를 MuJoCo 솔버가 정확히 계산. 결과 관절 각도/위치를 WebSocket 등으로 이 React 앱에 스트리밍해 렌더링만 담당시킨다.
- 장점: 물리적으로 정확함(MuJoCo는 접촉 마찰·강체 동역학에 특화된 검증된 솔버). CLAUDE.md의 "다음 단계 후보 1: actuator 토크 제어(mj_step 기반 동역학)"와 자연스럽게 합류.
- 비용: 가장 큼 — 별도 Python/MuJoCo 서버 프로세스, 상태 스트리밍 프로토콜, 이 React 앱과 MJCF 모델의 관절 매핑(현재 21개 슬라이더 ↔ MuJoCo 액추에이터) 설계가 전부 새로 필요. `fingershake-robot-main`은 원래 완전히 독립된 프론트엔드 전용 프로젝트라 백엔드 연동 자체가 아키텍처 확장임.

## 2. 권장 순서와 다음 결정 지점

1단계와 2단계는 이번 세션의 "지면 고정" 작업과 같은 성격(분석적 계산, 새 의존성 없음)이라 바로 이어서 진행 가능하다. 3단계는 옵션 A/B 중 어느 쪽이든 별도의 설계 논의와 상당한 작업량이 필요하므로, 1·2단계 완료 후 사령관과 별도로 방향을 정하는 게 맞다고 판단한다.

**다음에 "1단계 시작해줘" 같은 지시가 오면**: 위 1단계 설계대로 CoM/지지 다각형/정적 안정성 판정부터 착수. thesis 계획→구현→결과 패턴 계속 적용.

**다음에 "진짜 물리엔진 붙여줘" 같은 지시가 오면**: 3단계 옵션 A(클라이언트 JS 물리)와 옵션 B(MuJoCo 백엔드) 중 어느 쪽을 원하는지 먼저 확인 — 비용과 정확도, 그리고 이 웹 시뮬레이터를 독립 프로젝트로 유지할지 dual_arms MuJoCo 작업과 합류시킬지가 걸린 결정이라 임의로 고르지 않는다.
"""

payload = {
    "slug": "2026-08-11-moojoco-contact-dynamics-plan",
    "title": "실제 접촉 동역학(마찰·ZMP·무게중심) 도입 계획",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-ground-lock-physics-approximation]]의 지면 고정 버튼은 발바닥 Y좌표 하나만 "
        "해석적으로 고정하는 근사였을 뿐, 실제 마찰·ZMP·무게중심 동역학은 전혀 반영하지 않았다. 이 문서는 "
        "구현 없이 계획만 다룬다. 신체 분절 질량비로 무게중심(CoM)을 계산하고 두 발의 지지 다각형(support "
        "polygon)과 비교해 정적 안정성을 판정하는 1단계, CoM 가속도로부터 단순화된 도립진자 ZMP를 구해 동적 "
        "안정성과 마찰원뿔 초과 여부를 판정하는 2단계, 그리고 진짜 강체 동역학이 필요한 3단계(클라이언트 JS "
        "물리엔진 rapier/cannon-es 옵션 A, 또는 MuJoCo 백엔드 실시간 연동 옵션 B)로 비용이 점증하는 로드맵을 "
        "제시했다. 1·2단계는 새 의존성 없이 바로 착수 가능하고, 3단계는 아키텍처 결정이 필요해 별도 논의가 "
        "선행되어야 한다고 정리했다."
    ),
    "tags": ["handshake-robot", "physics", "kinematics", "moojoco", "plan"],
    "changelog": "v1.0 — 최초 제출: 접촉 동역학 도입 3단계 로드맵 계획 (구현 전)",
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
