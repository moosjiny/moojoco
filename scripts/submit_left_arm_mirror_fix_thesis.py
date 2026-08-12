#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 왼팔 팔꿈치 비대칭 버그 수정 완료 — 음수 스케일 거울 래퍼

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-anatomical-symmetric-arm-search]]에서 `dual_openarm.urdf`가 관절별 origin/axis 부호를 반전해 진짜 거울 구조를 만든다는 걸 확인한 뒤, 사령관 지시 — "왼팔 대칭 리팩터링" 진행.
**일자**: 2026-08-12
**분류**: `handshake-robot`, `bug`, `moojoco`, `result`

---

## 0. 접근 방식 — URDF 패턴을 그대로 옮기지 않았다

`dual_openarm.urdf`는 관절마다 origin X성분과 특정 축(axis)을 손으로 반전해서 거울 구조를 만들었다. fingershake의 왼팔 지오메트리(원기둥/구/박스 같은 순수 도형)는 URDF의 STL 메시와 달리 **키랄성(손잡이)이 없다** — 즉 메시 자체를 반전할 필요가 없다. 대신 Three.js에서 훨씬 적은 코드로 같은 효과를 내는 표준 기법을 썼다: **왼팔 서브트리 전체를 `scale.set(-1, 1, 1)`인 부모 그룹으로 감싼다.**

```ts
// RobotBuilder.ts
const leftArmMirror = new THREE.Group();
leftArmMirror.position.set(-0.32, 0.5, 0);
leftArmMirror.scale.set(-1, 1, 1);
torsoGroup.add(leftArmMirror);

const leftShoulder = new THREE.Group();
leftArmMirror.add(leftShoulder);
// ... 이하 어깨/팔꿈치/손 구조는 오른팔과 완전히 동일한 코드, 변경 없음
```

이렇게 하면 **관절별로 어떤 축을 반전해야 하는지 하나하나 따질 필요가 없다** — 음수 스케일 래퍼가 안쪽의 모든 회전/위치를 자동으로 거울 반전한다. `RobotScene.tsx`의 회전 적용 코드(`leftShoulder.rotation.x/y/z = ...`, `leftElbow.rotation.x = ...`)는 **단 한 줄도 안 바꿨다** — 오른팔과 완전히 같은 부호·같은 공식을 그대로 쓴다. 사령관이 예상한 그대로였다: "제대로 대칭 구조면 그냥 붙이기만 해도 맞다."

## 1. 기본값도 정합화

기존엔 `leftShoulderYaw`/`leftShoulderRoll` 기본값을 오른팔과 반대 부호(+20/+12)로 손으로 맞춰뒀었다 — 지오메트리가 거울 구조가 아니었던 것을 슬라이더 기본값으로 어설프게 보정한 흔적이다. 이제 구조 자체가 거울이므로 이 수동 보정이 오히려 이중 반전이 돼 틀린다. 오른팔과 완전히 같은 값으로 바꿨다:

```
leftShoulderYaw:  +20 → -20  (shoulderYaw와 동일)
leftShoulderRoll: +12 → -12  (shoulderRoll과 동일)
```

## 2. 실측 검증

배포 후 새 탭에서 확인(재시작 불필요 — `vite preview`가 디스크에서 직접 서빙):

- **기본 포즈**: 리셋 직후 양팔이 대칭적으로 악수 지점을 향해 뻗는 원래 모습 그대로 유지됨 — 회귀 없음.
- **오른팔·왼팔 Elbow Flexion을 똑같이 120°로 설정**: 이번엔 **양쪽 다 정상적으로 어깨 쪽으로 말려 올라감** — [[2026-08-12-moojoco-left-arm-elbow-asymmetry-bug]]에서 찍었던 "왼팔이 바깥/아래로 꺾이던" 사진과 정반대 결과.

![수정 후 — 왼팔(화면 왼쪽)과 오른팔(화면 오른쪽) 모두 Elbow Flexion=120°에서 대칭적으로 어깨 쪽으로 말려 올라간다](https://images.hyperbook.com/moojoco-left-arm-mirror-fix-after-2026-08-12.png)

- **렌더링 아티팩트**: 음수 스케일은 삼각형 와인딩을 뒤집어 조명이 깨질 수 있다고 알려져 있는데(반전된 법선), 실측 결과 왼팔 조명이 오른팔과 동일하게 정상 렌더링됐다 — 최신 Three.js가 음수 판별식 행렬을 자동 보정하는 것으로 보인다. 별도 조치 불필요.
- 콘솔 에러 없음, `npx tsc --noEmit`/`npm run build` 통과.

## 3. 남은 것

- 왼손목/손가락 지오메트리는 여전히 없음(왼손은 여전히 관절 없는 박스) — 이건 별개의 "왼팔 2단계" 기능 추가 과제이지 이번 버그와 무관.
- 다리(`createLeg(xSide)`)는 원래부터 문제없었으므로 손대지 않음.
"""

payload = {
    "slug": "2026-08-12-moojoco-left-arm-mirror-fix",
    "title": "왼팔 팔꿈치 비대칭 버그 수정 완료",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-12-moojoco-left-arm-elbow-asymmetry-bug]]에서 발견한 왼팔/오른팔 팔꿈치 굽힘 방향 비대칭을 "
        "수정했다. dual_openarm.urdf처럼 관절별 axis를 손으로 반전하는 대신, fingershake의 도형 기반(키랄성 "
        "없는) 지오메트리 특성을 살려 왼팔 서브트리 전체를 scale.set(-1,1,1)인 부모 그룹으로 감싸는 표준 Three.js "
        "거울 기법을 적용했다 — RobotScene.tsx의 회전 적용 코드는 한 줄도 바꾸지 않았고, 오른팔과 완전히 같은 "
        "부호·공식을 그대로 쓴다. 기존에 손으로 반전해뒀던 leftShoulderYaw/Roll 기본값도 이중 반전을 피하기 "
        "위해 오른팔과 동일값으로 되돌렸다. 실측 결과 기본 포즈는 회귀 없이 유지됐고, 양팔 Elbow Flexion=120°에서 "
        "이제 대칭적으로 정상 동작한다(이전엔 왼팔만 바깥/아래로 꺾였음). 음수 스케일의 조명 반전 우려도 실측상 "
        "문제없었다."
    ),
    "tags": ["handshake-robot", "bug", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: 왼팔 거울 래퍼 구현·실측 검증, 버그 해소 확인",
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
