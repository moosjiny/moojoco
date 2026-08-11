#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 접촉 동역학 1단계 — 무게중심(CoM) + 지지 다각형 + 정적 안정성 판정

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-contact-dynamics-plan]] 1단계 착수. 사령관 지시 — "1단계 시작해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `kinematics`, `moojoco`, `result`

---

## 0. 구현 내역

계획 문서에 적은 설계를 그대로 구현했다. `RobotScene.tsx`에 순수 함수 형태로 추가:

- `SEGMENT_MASS_FRACTIONS` — 머리 7%, 몸통 40%, 팔 각 8%, 다리 각 18.5% (합 100%, 실측 아닌 근사값, 계획 문서에서 이미 선언)
- `computeCenterOfMass(robot)` — `robot.head`/`robot.torso`의 월드 위치와, 팔은 (어깨+팔꿈치[+오른팔은 손목]) 평균, 다리는 (고관절+무릎+발목) 평균을 각 분절의 대표 위치로 삼아 질량 가중 합산
- `getFootWorldCorners(ankle)` — Ground Lock에서 쓴 것과 동일한 유도로 발바닥 4개 모서리의 월드 좌표 계산
- `convexHull2D(points)` — Andrew's monotone chain 알고리즘. 오늘의 대칭 다리 형태에서는 사실 두 발 사각형의 결합이 단순 직사각형으로 축소되지만, 다리가 비대칭이 되는 후속 작업에서도 깨지지 않도록 일반 convex hull로 구현
- `pointInPolygon2D` / `distanceToPolygonBoundary2D` — 레이캐스팅 point-in-polygon 판정과 점-다각형 최단거리(마진) 계산
- `createBalanceOverlay()` / `updateBalanceOverlay()` — 로봇당 지지 다각형 외곽선(LineLoop), 반투명 채움(삼각형 팬으로 월드 좌표에 직접 지오메트리 생성 — `THREE.Shape` 로컬 회전을 쓰지 않아 좌우 반전 버그 여지를 원천 차단), 무게중심 마커(구, 안정 시 초록/불안정 시 빨강)로 구성

`KinematicControls.tsx`에 Ground Lock 옆에 `Scale`(저울) 아이콘 토글 버튼 추가, `TelemetryPanel.tsx`에 "STATIC BALANCE" 블록을 추가해 Alpha/Beta 각각의 `STABLE`/`UNSTABLE` 상태와 다각형 경계까지의 여유(mm)를 표시한다.

## 1. 실측 검증

기본 포즈(양쪽 로봇 모두)에서 두 로봇 모두 STABLE, 여유값은 약 100~120mm:

![기본 포즈 — 두 로봇 모두 STABLE](https://images.hyperbook.com/balance_stable.jpg)

Alpha의 Hip Flexion을 최댓값(90°)까지 올려 상체를 앞으로 크게 숙이자, 무게중심이 작은 발 지지 다각형(가로 0.14m×세로 0.28m 두 개 뿐이라 매우 좁음)을 크게 벗어나며 UNSTABLE로 전환되고 마진이 -850mm까지 떨어졌다 — 실제 물리라면 이 자세는 앞으로 고꾸라질 자세라는 뜻이다. CoM 마커가 빨간 점으로 바뀌어 지지 다각형(파란 사각형)에서 한참 벗어난 것이 육안으로 확인된다:

![Hip Flexion 90° — Alpha UNSTABLE (-850mm)](https://images.hyperbook.com/balance_unstable.jpg)

Torso Pitch 30°만 단독으로 올렸을 때는 마진이 107mm→55mm로 줄었지만 여전히 STABLE이었다 — 몸통만 기울이는 것보다 고관절을 굽혀 상체 전체를 이동시키는 쪽이 무게중심에 훨씬 크게 영향을 준다는, 실제 인체 균형과도 부합하는 결과였다.

## 2. 배포

`npm run build` → `sudo systemctl restart fingershake_web.service`(사령관 재시작 확인) → 프로덕션 새 탭에서 재검증: 저울 아이콘 버튼과 STATIC BALANCE 텔레메트리 블록이 정상 동작.

## 3. 한계 (계획 문서에서 이미 예고한 대로)

- **정적 판정일 뿐이다.** 실제로는 관성력 때문에 다리를 빠르게 움직이면 CoM이 지지 다각형을 벗어나도 안 넘어질 수 있고, 반대로 다각형 안에 있어도 급가속 시 넘어질 수 있다 — 이 문제를 풀려면 2단계(동적 ZMP)가 필요하다.
- 질량 비율은 실측이 아니라 인체 분절 질량비 관행값을 참고한 근사이며, 각 분절의 대표 위치도 진짜 메시 중심이 아니라 관절 피벗(들)의 평균으로 단순화했다.
- 양쪽 다리가 항상 대칭이라는 전제는 여전히 유효하다 — 두 발 지지만 다루고 외발서기 등은 다루지 않는다.
- 판정만 할 뿐 자세를 스스로 고치지 않는다 — "이 자세가 실제 물리에서 서 있을 수 있는가"를 진단하는 도구다.

다음은 [[2026-08-11-moojoco-contact-dynamics-plan]] 2단계(동적 ZMP + 마찰원뿔 경고)다.
"""

payload = {
    "slug": "2026-08-12-moojoco-com-support-polygon-result",
    "title": "접촉 동역학 1단계 — 무게중심(CoM) + 지지 다각형 + 정적 안정성 판정",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-contact-dynamics-plan]] 1단계를 구현했다. 신체 분절 질량비(머리 7%/몸통 40%/팔 "
        "각 8%/다리 각 18.5%)로 무게중심을 계산하고, Andrew's monotone chain으로 두 발 접촉점의 지지 다각형을 "
        "구해 무게중심의 XZ 투영이 다각형 안에 있는지 판정하는 '무게중심/지지 다각형' 토글을 KinematicControls에, "
        "STABLE/UNSTABLE 상태와 마진(mm)을 TelemetryPanel에 추가했다. 기본 포즈는 두 로봇 모두 STABLE(약 "
        "100~120mm 여유)이었고, Hip Flexion을 90°까지 올리자 UNSTABLE(-850mm)로 전환되는 것을 실측 확인했다. "
        "Torso Pitch 단독 조작보다 Hip Flexion이 무게중심에 훨씬 크게 영향을 준다는 점도 확인했다. 정적 판정일 "
        "뿐 관성력을 고려하지 않는다는 한계를 남겼고, 2단계(동적 ZMP)로 이어질 예정이다."
    ),
    "tags": ["handshake-robot", "physics", "kinematics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: 1단계(CoM+지지다각형+정적 안정성 판정) 구현·실측·배포",
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
