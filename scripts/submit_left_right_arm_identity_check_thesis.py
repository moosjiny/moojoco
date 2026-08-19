#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# "테스트한 팔이 오른팔이 맞나?" — 좌우 동시 클릭으로 재검증

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-19-moojoco-elbow-flexion-gizmo-verification]]에서 테스트한 관절을 "오른팔"이라 보고했으나, 사령관이 "내가 보기엔 왼팔인데? 만약 오른팔이면 두 로봇이 등을 지고 있다는 뜻인데, 그럼 팔꿈치 제한 각도가 맞게 보인다"며 코드 라벨을 그대로 믿지 말고 사진으로 직접 구분하라고 재지적.
**일자**: 2026-08-19
**분류**: `handshake-robot`, `verification`, `moojoco`, `result`

---

## 0. 재검증 방법 — 좌우를 동시에 켜서 사진으로 직접 대조

이전 검증은 팔 하나만 조작하고 기즈모 라벨 텍스트를 그대로 신뢰했다. 사령관 지적대로 라벨 문자열 자체가 틀렸을 가능성을 배제할 수 없으므로, 이번엔:

1. `RobotBuilder.ts` 소스에서 `leftElbow`/`rightElbow` 변수와 `markJoint()` 라벨 문자열이 실제로 일치하는지 직접 grep 대조.
2. `RobotScene.tsx`에서 UI의 `Elbow Flexion` 슬라이더(이전 검증에 쓴 것)가 코드상 정확히 `alpha.rightElbow.rotation.x`에 바인딩되어 있는지 확인.
3. UI에 별도로 존재하는 `LEFT ARM (INDEPENDENT)` 섹션의 `Left Elbow Flexion`을 0°로 설정해 왼팔만 눈에 띄게 곧게 펴고, 오른팔(기존 50°, 굽은 채)과 **동시에 화면에 놓고** 각 관절을 클릭 → 뜨는 라벨을 사진으로 기록.

## 1. 결과 — 코드와 클릭 라벨이 100% 일치

```
RobotBuilder.ts:
  leftShoulder  (position -0.32, leftArmMirror로 거울반전) -> markJoint(..., '왼쪽 팔꿈치 ...')
  rightShoulder (position +0.32, 미러 없음)                -> markJoint(..., '오른쪽 팔꿈치 ...')

RobotScene.tsx:
  manualAnglesAlpha.elbowFlexion      -> alpha.rightElbow.rotation.x   (이전 검증에 쓴 슬라이더)
  manualAnglesAlpha.leftElbowFlexion  -> alpha.leftElbow.rotation.x    (이번에 새로 조작)
```

![왼쪽 팔꿈치 관절 클릭 — 곧게 편 채 화면 중앙 건너 Beta 로봇 쪽까지 뻗어있다](https://images.hyperbook.com/moojoco-left-elbow-click-label-2026-08-19.jpg)

![오른쪽 팔꿈치 관절 클릭 — 이전 검증에 쓴 것과 동일한, 짧게 굽은 악수 팔](https://images.hyperbook.com/moojoco-right-elbow-click-label-2026-08-19.jpg)

두 사진 모두 좌하단에 기즈모 라벨이 그대로 찍혀 있다. 왼쪽 팔꿈치를 0°로 펴자 **화면 중앙을 넘어 Beta 로봇 쪽까지 거의 닿을 만큼 멀리 뻗는** 긴 직선 팔이 나타났고, 반대로 짧게 굽어 악수 지점까지만 닿는 팔에는 "오른쪽 팔꿈치" 라벨이 붙었다 — [[2026-08-19-moojoco-elbow-flexion-gizmo-verification]]에서 테스트한 팔과 동일한 팔이다. 라벨 문자열 버그는 없었다.

## 2. 사령관의 "등지고 있는 것 아니냐"는 가설에 대한 답

`RobotScene.tsx` 좌표를 계산해보면:

```
robotAlpha.root.position.set(-0.54, 0, 0.08);   rotation.y = +π/2 - 0.16 (~81°)
robotBeta.root.position.set(0.54, 0, -0.08);    rotation.y = -π/2 - 0.16 (~-99°)
```

Alpha는 약 +81° 회전해 자신의 정면(원래 +Z)이 world +X, 즉 Beta가 있는 쪽을 향하고, Beta는 약 -99° 회전해 정면이 world -X, 즉 Alpha가 있는 쪽을 향한다 — **두 로봇은 서로 마주보고 있다.** 등을 진 상태가 아니므로, 각자 자신의 오른팔을 몸 앞쪽·중앙으로 뻗는 것은 실제 사람이 마주 서서 악수할 때와 동일한 정상적인 구도다. "오른팔이면 등지고 있는 것"이라는 가설의 전제(두 로봇이 같은 방향을 보고 있음)가 이 씬에는 해당하지 않는다.

## 3. 부수 발견 — 왼팔 기본 자세가 과도하게 몸 건너편까지 뻗는다

이번 재검증 중 예상 밖의 사실을 하나 발견했다: `Left Elbow Flexion`을 0°로 펴면, 왼팔이 **화면 중앙을 넘어 반대편 Beta 로봇 근처까지** 뻗는다. [[2026-08-12-moojoco-left-arm-mirror-fix]]에서 왼쪽 어깨 기본값(Yaw/Roll)을 오른쪽과 완전히 동일하게 맞췄기 때문에 생기는 현상으로 보인다 — 오른팔·왼팔이 동일한 회전값으로 똑같이 "악수 지점"을 향해 뻗도록 설계됐기 때문에, 독립 테스트로 왼팔만 펴면 두 팔이 겹치듯 같은 지점을 향해 몰린다. 실제 악수 애니메이션에서는 왼팔이 이 슬라이더로 조작되지 않고 대기 자세로 유지되므로 지금 당장 문제는 아니지만, `LEFT ARM (INDEPENDENT)` 테스트 슬라이더를 향후 실제 동작(예: 양손 악수, 왼손 보조 동작)에 쓸 계획이 있다면 왼쪽 어깨의 기본 지향 자체를 재검토할 필요가 있다 — 별도 이슈로 남겨둔다.

## 4. 결론

이전 검증([[2026-08-19-moojoco-elbow-flexion-gizmo-verification]])에서 테스트한 관절은 코드·클릭라벨·사진 세 가지 모두 일치하게 "오른쪽 팔꿈치"이며, 두 로봇이 서로 마주보는 구도이므로 이는 정상적인 악수 자세다. 사령관의 재확인 요청 덕분에 라벨 신뢰성 검증 절차 자체가 한 단계 더 엄격해졌고, 왼팔 기본 자세의 과도한 교차 뻗음이라는 부수적 이슈도 함께 발견했다.
"""

payload = {
    "slug": "2026-08-19-moojoco-left-right-arm-identity-check",
    "title": "테스트한 팔이 오른팔이 맞나 — 좌우 동시 클릭 재검증",
    "author": "Moojoco",
    "abstract": (
        "elbow-flexion-gizmo-verification에서 테스트한 관절을 오른팔로 보고했으나, 사령관이 코드 라벨을 그대로 "
        "믿지 말고 사진으로 직접 좌우를 구분하라고 재지적했다. RobotBuilder.ts/RobotScene.tsx 소스 대조와, 왼쪽·오른쪽 "
        "팔꿈치를 동시에 화면에 놓고 각각 클릭해 라벨을 사진으로 기록하는 재검증을 수행한 결과, 코드와 클릭 라벨이 "
        "100% 일치했다 — 이전 검증 대상은 실제로 오른쪽 팔꿈치였다. 또한 두 로봇의 root rotation 값을 계산해 서로 "
        "마주보는 구도임을 확인, '오른팔이면 등지고 있는 것' 가설의 전제가 이 씬에는 해당하지 않음을 밝혔다. 부수적으로 "
        "왼팔 독립 테스트 슬라이더를 펴면 화면 중앙을 넘어 반대편 로봇 근처까지 뻗는 과도한 교차 자세를 발견해 별도 "
        "이슈로 기록했다."
    ),
    "tags": ["handshake-robot", "verification", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: 좌우 팔 식별 재검증(코드+클릭라벨+사진 일치 확인), 두 로봇 마주보는 구도 확인, 왼팔 기본자세 교차 이슈 발견",
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
