#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# Body Yaw 슬라이더 추가 — 로봇 전체를 강체로 회전시키는 기능

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-19-moojoco-left-right-arm-identity-check]]에서 두 로봇의 `root.rotation.y`를 계산해 "서로 마주보는 구도"라고 결론 냈으나, 사령관이 실제 화면을 보고 "로봇이 서로 마주보고 있지 않다, 비스듬히 서로 오른쪽으로 25도 정도 돌아가 있다"고 지적 — 계산상 마주본다는 결론과 실제 눈으로 보이는 인상이 다르다는 것. 수치 계산만으론 "이 정도 어긋남이 사람 눈에 어떻게 보이는지"까지는 알 수 없으므로, 사령관이 직접 눈으로 보면서 맞는 각도를 찾을 수 있는 도구가 필요하다는 취지로 "로봇 전체를 회전시킬 수 있는 슬라이드바"를 요청받아 구현.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `feature`, `moojoco`, `result`

---

## 0. 기존 Torso Yaw와의 차이

`RobotScene.tsx`에는 이미 `Torso Yaw` 슬라이더가 있었지만, 이건 `torso.rotation.y`만 조작한다 — 몸통(가슴/어깨/팔)만 돌고 다리·발은 원래 방향에 그대로 고정된 채 남는다. 사령관이 요청한 건 **팔·다리·베이스를 포함한 로봇 전체를 하나의 강체로** 돌리는 기능이었다. `RobotBuilder.ts`에서 각 로봇의 최상위 `root` 그룹이 바로 그 전체 강체 단위이므로, 새 슬라이더는 `torso`가 아니라 `root.rotation.y`를 조작한다.

## 1. 구현

두 로봇은 애초에 서로를 향해 고정된 기본 지향 각도로 지어진다(`RobotScene.tsx`):

```ts
const ALPHA_BASE_ROOT_YAW = Math.PI / 2 - 0.16;
const BETA_BASE_ROOT_YAW = -Math.PI / 2 - 0.16;
...
robotAlpha.root.rotation.y = ALPHA_BASE_ROOT_YAW;
robotBeta.root.rotation.y = BETA_BASE_ROOT_YAW;
```

새 슬라이더 값(`bodyYaw`, 도 단위)은 이 고정값을 **대체하지 않고 그 위에 오프셋으로 더해진다**:

```ts
alpha.root.rotation.y = ALPHA_BASE_ROOT_YAW + manualAnglesAlpha.bodyYaw * degToRad;
beta.root.rotation.y = BETA_BASE_ROOT_YAW + manualAnglesBeta.bodyYaw * degToRad;
```

이렇게 하면 슬라이더 0°는 항상 "원래 지어진 자세 그대로"를 의미하고, 사령관이 눈으로 보면서 실제로 맞는 각도(대략 ±25° 근방으로 예상)를 직접 찾아 넣을 수 있다. `types.ts`의 `JointAngles`에 `bodyYaw: number`(기본값 0) 필드를 추가하고, `KinematicControls.tsx`에 `Torso Yaw` 바로 위에 `Body Yaw`(범위 -180°~180°) 슬라이더를 배치했다. Alpha/Beta 각 로봇 탭에서 독립적으로 조절된다.

## 2. 실측 검증

![수정 전 — Body Yaw 0°(기본값), 슬라이더가 새로 노출됨](https://images.hyperbook.com/moojoco-body-yaw-slider-before-2026-08-20.jpg)

![Body Yaw 92°로 설정 — 로봇 전체(팔·다리·베이스 전부)가 강체로 회전, 발 위치까지 함께 이동](https://images.hyperbook.com/moojoco-body-yaw-slider-after-2026-08-20.jpg)

Alpha 로봇의 Body Yaw를 92°까지 돌려보면 몸통뿐 아니라 다리·발까지 전체가 한 덩어리로 회전하는 것이 확인된다 — 기존 Torso Yaw와 달리 다리가 뒤에 남지 않는다. 0°로 되돌리면 원래 자세로 정확히 복귀. `npx tsc --noEmit`, `npm run build` 통과, `dist/` 재빌드 후 8600 포트에 실측 확인.

## 3. 남은 것

- 실제로 "정확히 마주보는" 각도값 자체는 이번엔 찾지 않았다 — 사령관이 슬라이더로 직접 눈으로 보면서 찾도록 도구만 제공하는 것이 이번 요청의 취지.
- 저장/불러오기(포즈 프리셋) 기능이 있다면 `bodyYaw`도 함께 저장되는지는 별도 확인 필요(이번엔 미확인).
"""

payload = {
    "slug": "2026-08-20-moojoco-body-yaw-slider-feature",
    "title": "Body Yaw 슬라이더 추가 — 로봇 전체 강체 회전 기능",
    "author": "Moojoco",
    "abstract": (
        "두 로봇의 root.rotation.y 계산상으론 서로 마주보는 구도였지만, 사령관이 실제 화면에서는 비스듬히 "
        "오른쪽으로 25도가량 돌아가 있는 것처럼 보인다고 지적하며, 눈으로 직접 각도를 맞춰볼 수 있는 슬라이더를 "
        "요청했다. 기존 Torso Yaw는 몸통만 돌고 다리는 고정된 채 남는 한계가 있어, 새로 로봇 전체(팔·다리·베이스)를 "
        "강체로 회전시키는 Body Yaw 슬라이더를 추가했다. RobotBuilder.ts가 각 로봇에 부여하는 고정 기본 지향값 "
        "위에 오프셋으로 더해지는 방식이라 0도는 항상 원래 자세를 의미한다. Alpha/Beta 로봇 탭에서 각각 독립 조절 "
        "가능하며, 92도까지 돌려 팔·다리·발 전체가 한 덩어리로 회전하는 것을 스크린샷으로 확인했다."
    ),
    "tags": ["handshake-robot", "feature", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: Body Yaw 슬라이더 구현·배포·실측 검증",
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
