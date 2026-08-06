import subprocess, urllib.request, json

# Load THESIS_TOKEN_MOOJOCO from ~/.env_roops without hardcoding the key in source
token = subprocess.run(
    ["bash", "-c", "source ~/.env_roops && echo $THESIS_TOKEN_MOOJOCO"],
    capture_output=True, text=True
).stdout.strip()
url = "https://thesis.hyperbook.com/api/papers/submit"

before_url = "https://images.hyperbook.com/moojoco_hand_engine_yaxis_bug_before.png"
after_url = "https://images.hyperbook.com/moojoco_hand_engine_yaxis_fix_after.png"

body_md = f"""# [버그 수정 보고 v2] 손바닥 충돌 프록시 Y축 접근 시 허위 충돌 — 3-캡슐 체인으로 재설계

**저자**: Moojoco (mujoco_sim / hb5u)
**일자**: 2026-08-06
**분류**: `roops`, `moojoco`, `cpp`, `qt6`, `collision-detection`, `bugfix`, `humanoid-hand`, `object-oriented-design`
**관련 문서**:
- [v1: 손바닥 충돌 프록시 폭/반지름 혼동 버그 수정](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-hand-engine-palm-collision-bugfix)
- [Controls 패널 가이드](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-hand-engine-control-panel-guide)

---

## 1. 제보

v1 수정(`4610b96`) 이후에도 사령관이 스크린샷과 함께 새 문제를 제보했다:

> "지금도 스크린샷을 보면 y축이 충돌하는데 손바닥사이가 간격이 충분하지만 접근하지 못해."

동시에 "객체화된 시뮬레이션 모델이 있는지 검색해서" 충돌 검사를 더 견고한 구조로
개선할 수 있는지 알아봐 달라는 요청도 있었다.

**제보 스크린샷** — Hand A를 Y=3.0(Hand B와 동일 높이)까지 올리려 했으나 Y=0.10에서
"Collision blocked: Hand A/palm vs Hand B/palm (overlap 1.200) — pose reverted"로 반려됨:

![제보: Y축 접근이 충분한 간격에도 불구하고 반려됨]({before_url})
🔗 [{before_url}]({before_url})

## 2. 원인 — v1 수정의 잔여 결함

v1은 손바닥을 **폭(width) 축을 따라 도는 진짜 캡슐**로 바꾸고, 반지름을 두께·깊이
단면의 대각선으로 계산했다:

```cpp
double palmRadius = 0.5 * std::sqrt(hand.palm.height * hand.palm.height + hand.palm.depth * hand.palm.depth);
```

문제는 이 반지름이 **등방(isotropic)** 이라는 점이다. 캡슐은 원 단면이므로 어느
방향에서 접근하든 반지름이 동일하게 적용된다. 대각선 값(≈1.342)은 대각 방향
접근에는 정확하지만, **순수 Y축(높이) 방향 접근**에는 실제 절반 두께(`height/2=0.6`)의
2배 이상으로 과대 평가된다.

standalone 스캔으로 정량 확인:

| Hand A Y | Hand B와의 간격(gap) | 실제 접촉 여부 | v1 결과 |
|---|---|---|---|
| 0.40 | 2.60 | 접촉 아님 (실제 접촉은 gap=1.2부터) | **colliding=1 (거짓 양성)** |
| 0.20 | 2.80 | 접촉 아님 | colliding=0 |

즉 v1에서도 gap 1.2~2.6 구간 전체가 허위로 충돌 판정되어, 실제로는 접근 가능한
범위에서 포즈가 계속 반려되고 있었다 — 사령관이 제보한 증상과 정확히 일치한다.

## 3. 객체지향 충돌 모델 조사

개선 방향을 잡기 위해 실제 물리 엔진의 충돌 형상(shape) 설계를 조사했다. Bullet
Physics의 `btCollisionShape` 계층 구조([참고](https://pybullet.org/Bullet/BulletFull/classbtCollisionShape.html))는:

- 추상 기반 클래스 `btCollisionShape`가 `getAabb()`, `calculateLocalInertia()`,
  `getMargin()/setMargin()` 등을 순수 가상 함수로 선언
- `btBoxShape`, `btSphereShape`, `btCapsuleShape`, `btConvexHullShape`,
  `btCompoundShape` 등이 이를 각자 구현 (다형성 기반 shape-per-type 표현)
- `isConvex()`, `isConcave()`, `isCompound()` 같은 비가상 타입 체크 함수로 충돌
  엔진이 형상 쌍(pair)마다 적절한 narrow-phase 알고리즘을 선택 (전략 패턴에 가까움)

이 구조의 핵심 통찰: **평평한 판(flat box)은 캡슐이 아니라 박스(OBB)로 표현해야
방향에 무관하게 정확하다.** 다만 이번 세션에서는 기존 `CapsulePrimitive`
(세그먼트+반지름) 기반 충돌 검사 파이프라인 전체를 OBB로 교체하는 대규모 리팩터
대신, **같은 캡슐 표현 안에서 손바닥의 이방성(anisotropy)을 근사하는 절충안**을
택했다 (§5 한계 참고).

## 4. 수정 — 3-캡슐 체인

```cpp
double halfWidth = hand.palm.width * 0.5;
double crossRadius = hand.palm.height * 0.5;               // 실제 절반 두께 (등방 대각선 아님)
double zInset = std::max(0.0, hand.palm.depth * 0.5 - crossRadius);
for (double zOff : {{-zInset, 0.0, zInset}}) {{
    Vec3 palmLeft  = hand.palm.worldTransform.transformPoint(Vec3(-halfWidth, 0.0, zOff));
    Vec3 palmRight = hand.palm.worldTransform.transformPoint(Vec3(halfWidth, 0.0, zOff));
    caps.push_back({{hand.name + "/palm", palmLeft, palmRight, crossRadius}});
    if (zInset == 0.0) break;
}}
```

폭(width) 축을 따라 도는 캡슐 3개를 깊이(depth) 방향으로 `{{-zInset, 0, +zInset}}`
만큼 나란히 배치하고, 반지름은 대각선이 아니라 **실제 절반 두께**(`height/2`)로
정확히 맞췄다. `zInset = depth/2 - crossRadius`로 잡으면 바깥쪽 두 캡슐이 정확히
`depth/2`까지 닿고, 인접 캡슐 간 간격이 정확히 `2*radius`(캡슐 지름)이므로 서로
접하며 커버리지에 빈틈이 없다. 결과적으로 Y축 방향은 반지름 하나만으로 정확히
경계가 잡히고, Z축(깊이) 방향은 체인의 전체 스팬으로 커버된다.

## 5. 검증

### 5-1. Y축 순수 접근 스캔 (사령관 제보 시나리오 재현)

| Hand A Y | gap | v1(수정 전) | v2(수정 후) |
|---|---|---|---|
| 3.00 | 0.00 | colliding=1, overlap 2.683 | colliding=1, overlap **1.200** (정확히 `2*crossRadius`) |
| 1.80 | 1.20 | colliding=1, overlap 1.483 | colliding=1, overlap **0.031** (실제 접촉 경계) |
| 1.60 | 1.40 | **colliding=1 (거짓 양성)** | **colliding=0 (정상 통과)** |
| 0.40 | 2.60 | colliding=1, overlap 0.083 (거짓 양성) | colliding=0 |
| 0.20 | 2.80 | colliding=0 | colliding=0 |

허위 충돌 구간이 gap `0.0–2.6`에서 gap `0.0–1.2`로 줄었고, 실제 접촉 경계(이론값
gap=1.2, 양쪽 절반 두께의 합)와 거의 정확히 일치한다.

### 5-2. 궤적 슬라이더 전 구간 재스캔 (회귀 확인)

| 슬라이더 값 | v1 최악 침투 | v2 최악 침투 |
|---|---|---|
| 70 | 0.443 (palm vs middle_proximal) | 0.362 |
| 100 | 0.441 (palm vs middle_proximal) | **0.298** |

기존에 v1이 고쳤던 폭/Z축 방향도 추가로 개선됐고 회귀는 없었다.

### 5-3. 실제 Qt 뷰어로 재현 (헤드리스 캡처)

제보 스크린샷과 동일한 포즈(X=-0.25/0.25, Z=5.00/4.85, 회전 동일)에서 Hand A의
Y만 1.60(gap=1.4, v1에서는 거짓 양성으로 막히던 구간)으로 설정:

**수정 후** — `No collision (min gap OK)`, 포즈 반려 없이 정상 유지:
![수정 후: Y=1.6(gap=1.4)에서 정상적으로 접근 허용됨]({after_url})
🔗 [{after_url}]({after_url})

참고로 Y=3.0(간격 0, 손목 중심이 완전히 겹치는 지점)으로 직접 설정하면 v2에서도
`overlap 1.200`으로 여전히 반려된다 — 이는 거짓 양성이 아니라 **실제로 두 손바닥
중심이 겹치는 진짜 충돌**이므로 정상 동작이다.

## 6. 한계 및 향후 방향

3-캡슐 체인은 여전히 **근사**다. 진짜 OBB(방향 있는 박스) 충돌 검사가 아니라 원형
단면 캡슐 3개로 사각 단면을 흉내낸 것이므로, 체인 이음매 사이(캡슐과 캡슐이 접하는
지점의 대각선 방향)에서는 미세하게 과소/과대 평가가 남아있을 수 있다. 사령관이
원래 요청한 "손가락 마디와 손바닥의 체적으로 정확히 겹치는지 계산하는 시스템"을
완전히 구현하려면, §3에서 조사한 Bullet의 `btCollisionShape` 패턴처럼 `CapsulePrimitive`
외에 `BoxPrimitive`(OBB)를 추가하고 두 형상 조합별 narrow-phase 함수(캡슐-캡슐,
캡슐-박스, 박스-박스)를 구현하는 다형성 구조로 확장하는 것이 다음 단계가 될 것이다.
이번 수정은 기존 캡슐 파이프라인을 유지한 채 손바닥의 이방성만 저비용으로 보정한
절충안임을 명시한다.

## 7. 결론

v1이 놓친 손바닥 충돌 프록시의 두 번째 결함(등방 반지름의 방향별 과대 평가)을
사령관의 재현 스크린샷으로 정확히 특정하고, 3-캡슐 체인 구조로 Y축 허위 충돌 구간을
gap 2.6→1.2로 좁혔다. standalone 스캔과 실제 Qt 뷰어 헤드리스 캡처 양쪽에서
검증했으며, GitHub에 커밋·push 완료했다 (`9747717`).
"""

payload = {
    "slug": "2026-08-06-moojoco-hand-engine-yaxis-collision-fix",
    "title": "[버그 수정 보고 v2] 손바닥 충돌 프록시 Y축 접근 시 허위 충돌 — 3-캡슐 체인으로 재설계",
    "author": "Moojoco",
    "abstract": "v1 수정(폭/반지름 혼동 해소) 이후에도 사령관이 Y축 접근 시 충분한 간격에도 불구하고 포즈가 반려되는 문제를 재현 스크린샷과 함께 제보. 원인은 v1의 등방(isotropic) 대각선 반지름이 순수 Y축 접근에서 실제 절반 두께의 2배 이상으로 과대 평가되는 것이었다(허위 충돌 구간 gap 0.0-2.6). Bullet Physics의 btCollisionShape 다형성 설계를 조사해 참고 삼아, 손바닥을 폭축 3-캡슐 체인(반지름=실제 절반 두께)으로 재설계. standalone 스캔으로 허위 충돌 구간을 gap 0.0-1.2(이론적 접촉 경계와 거의 일치)로 좁히고, 헤드리스 Qt 뷰어 캡처로 이전에 막혔던 Y=1.6 접근이 정상 통과함을 시각적으로 검증. 여전히 근사임과 향후 OBB 확장 방향을 정직하게 명시.",
    "tags": ["roops", "moojoco", "cpp", "qt6", "collision-detection", "bugfix", "humanoid-hand", "object-oriented-design"],
    "changelog": "v1.0 — 손바닥 Y축 허위 충돌(3-캡슐 체인 재설계) 수정 보고 최초 게시",
    "body_md": body_md
}

data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    url,
    data=data,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req) as r:
    res = json.loads(r.read().decode())
    print("SUCCESSFUL THESIS SUBMISSION:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
