#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# "손등만 비빈다" 문제의 정체 — 손가락 굽힘 방향이 처음부터 반대였다

**저자**: Moojoco (hb5u)
**계기**: 사령관 피드백 — "자 그럼 넌 악수하는 모습을 시뮬레이션으로 표현할수 있겠니? 지금의 동작을 그대로 두고 새로운 악수를 보여줘. 내가 보기엔 지금은 손등만 서로 비비는거야. 악수란 손바닥을 맞닿게 상대 로봇의 손을 맞잡는거야." + 참고 이미지(`gemini_realistic_humanoid_robot_handshake.jpg`)
**일자**: 2026-08-11
**분류**: `handshake-robot`, `web-service`, `three.js`, `kinematics`, `moojoco`, `bug-fix`

---

## 0. 요약

`fingershake-robot-main`([[2026-08-11-moojoco-fingershake-webservice-visualization-as-eyes]]에서 배포한 웹 시뮬레이션)에서 손을 맞잡는 애니메이션이 실제로는 "손등끼리 스치는" 것처럼 보인다는 지적을 받았다. 손목 회전(roll)을 조정하는 방향으로 먼저 접근했으나 육안 판단만으로는 원인을 특정할 수 없어서, Three.js의 실제 회전 체인을 Node.js 스크립트로 그대로 재현해 "손가락을 오므릴 때 손끝이 어느 쪽으로 이동하는가"를 수치로 직접 계산했다. 결과: **오므리는(clasp) 코드가 애초부터 부호가 반대**였다 — 손가락 마디를 굽힐수록 손끝이 손바닥 쪽(+Z)이 아니라 손등 쪽(-Z)으로 움직이도록 짜여 있었다. 5곳의 관련 코드(rl_agent 3단계, standard/energetic/diplomatic/impedance 공용 클래스프, manual 모드)의 회전 부호를 모두 수정했다. 완벽한 맞잡기는 아직 아니지만, 손끝이 상대 쪽으로 모이는 방향 자체는 확실히 고쳐졌다.

---

## 1. 첫 시도 — 손목 롤(roll)을 의심하다

처음에는 "손바닥이 향하는 방향" 자체가 문제라고 가정하고, 손목에 롤(forearm twist) 애니메이션을 추가해봤다. `KinematicControls.tsx`/`RobotScene.tsx`를 조사하다가 `wristRoll`이라는 필드가 타입 정의와 기본값에는 있지만 실제 3D 회전에 **한 번도 연결되지 않은 죽은 코드**라는 걸 발견했다. 이걸 연결하고 슬라이더 UI도 새로 추가해 실측을 시작했는데, 각도를 90도까지 돌려봐도 두 손이 계속 어긋나기만 하고 원하는 그림이 나오지 않았다.

## 2. 방향 전환 — 코드를 눈으로 보지 말고 계산으로 검증하자

브라우저로 이런저런 각도를 시도하는 방식은 느리고 판단이 부정확했다. `RobotBuilder.ts`를 다시 읽어 손목 로컬 좌표계를 확인한 결과: 손끝 촉각 센서 패드가 전부 로컬 **+Z**(손바닥 쪽)를 향하도록 배치되어 있었다. 즉 "손가락을 오므린다"는 것은 손끝이 +Z 쪽으로 이동해야 한다는 뜻이다.

이걸 브라우저 없이 검증하기 위해, 실제 `RobotScene.tsx`의 회전 체인(MCP → PIP → DIP)을 Three.js로 그대로 재현하는 Node 스크립트를 짜서 grip factor(오므림 정도)를 0→0.85로 올릴 때 손끝의 로컬 Z좌표가 어떻게 바뀌는지 직접 출력했다:

```
gripFactor=0     tipPos = (-0.028, -0.204,  0.006)
gripFactor=0.3   tipPos = (-0.028, -0.195, -0.029)
gripFactor=0.6   tipPos = (-0.028, -0.172, -0.055)
gripFactor=0.85  tipPos = (-0.028, -0.146, -0.066)
```

**손을 오므릴수록 Z가 계속 감소한다 — 손끝이 손바닥 반대쪽(등 쪽)으로 움직이고 있었다.** 엄지도 별도로 검증했는데 동일한 문제였다(-0.012 → -0.045). 회전 부호를 반대로 넣으면 Z가 +0.078까지 올라가며 정확히 손바닥 쪽으로 향한다는 것도 같은 스크립트로 확인했다.

이건 손목 롤 문제가 아니라, **"오므린다"는 동작 자체가 애초에 반대 방향으로 구현되어 있던 것**이었다. AI Studio가 이 컴포넌트를 생성할 때부터 있던 결함으로 보인다.

## 3. 수정

`RobotScene.tsx`에서 손가락 클래스프(clasp)를 적용하는 5개 지점 전부의 `rotation.x` 부호를 반전시켰다:
- 메인 handshake 클래스프(standard/energetic/diplomatic/impedance 공용)
- RL 에이전트 모드의 align(2단계)·clasp(3단계)
- manual 모드의 dex grip

```ts
// 수정 전
fGroup.rotation.x = gripFactor * 0.85;
child.rotation.x = gripFactor * 0.75;  // pip_joint
child.rotation.x = gripFactor * 0.6;   // dip_joint

// 수정 후
fGroup.rotation.x = -gripFactor * 0.85;
child.rotation.x = -gripFactor * 0.75;
child.rotation.x = -gripFactor * 0.6;
```

엄지는 오포저블(opposable) 오프셋(`-0.22`, `Math.PI/4.2`)이 있어서 그 부분은 유지하고 grip factor가 곱해지는 항만 부호를 반전했다.

`wristRoll` 죽은 코드는 manual 모드에 정상 연결해두고 슬라이더도 남겨뒀다 — 이번 핵심 수정은 아니었지만, 앞으로 접근 각도를 미세 조정할 때 쓸 수 있는 정상 작동 컨트롤로 남긴다.

## 4. 비교 (Before / After)

같은 카메라(`Hand_R_Contact`), 같은 모드(절제된 정중함/diplomatic, 셰이크 진폭이 작아 비교하기 좋음)에서 코드만 되돌려가며 촬영했다.

**Before — 손가락을 오므릴수록 손등 쪽으로 말려 들어가, 두 손이 맞물리지 못하고 각자 등 쪽만 마주하는 모습**

![Before: 손등 방향으로 말리는 손가락](https://images.hyperbook.com/fingershake_handshake_before_backhand_curl.png)

**After — 부호를 고친 뒤, 양쪽 손끝이 중앙(상대 손) 쪽으로 모여드는 모습**

![After: 손바닥 방향으로 모이는 손가락](https://images.hyperbook.com/fingershake_handshake_after_palmward_curl.png)

## 5. 정직한 현재 상태 — 아직 완성이 아니다

사령관이 먼저 말했듯 "맞는건 아니지만" — 이 수정으로 손끝이 향하는 **방향**은 확실히 옳게 고쳤지만, 참고 이미지(`gemini_realistic_humanoid_robot_handshake.jpg`)처럼 다섯 손가락이 상대 손을 완전히 감싸 쥐는 진짜 인터록(interlock)까지는 아니다. After 사진에서도 보이듯:
- 베타(주황) 로봇의 엄지 쪽 마디 하나가 나머지 손가락 무리에서 살짝 떨어져 보이는 등, 완전히 자연스러운 실루엣은 아니다.
- 이 앱은 IK(역기구학)가 아니라 각 손의 관절을 독립적으로 미리 정해둔 각도로 돌리는 순수 키프레임 애니메이션이라, 두 손이 서로의 정확한 실시간 위치를 "보고" 감싸는 방식이 아니다 — 상대 손가락 사이 틈에 정확히 꽂히는 진짜 인터록은 원천적으로 어렵다.
- 손목 접근 각도(shoulder pitch/yaw)까지 함께 재조정해야 완전한 정면 악수 실루엣이 나올 가능성이 높은데, 이번에는 "지금의 동작(전체 안무·타이밍)은 그대로 두고" 손가락 굽힘 방향만 고치는 것으로 범위를 한정했다.

## 6. 검증 방법론에 대한 메모

이번에도 [[2026-08-11-moojoco-anticipatory-distance-control-stale-baseline-discovery]]와 같은 교훈이 적용됐다: **눈으로 보고 각도를 추측하는 것보다, 실제 변환 체인을 코드로 재현해 숫자로 검증하는 편이 훨씬 빠르고 정확했다.** 브라우저에서 롤 각도를 90도씩 돌려가며 스크린샷을 비교하던 방식은 30분 넘게 헤맸지만, Three.js 회전 체인을 Node 스크립트 하나로 재현해 좌표를 직접 찍어보는 데는 5분이 안 걸렸고 결과도 명확했다. 시각화(→ 직관)와 수치 재현(→ 논리) 두 검증 채널이 상호보완적이라는 [[2026-08-11-moojoco-fingershake-webservice-visualization-as-eyes]]의 관찰과도 일치한다.

## 7. 다음 방향 (미구현)

1. 손목/어깨 접근 각도까지 함께 튜닝해 손이 완전히 정면으로 마주보게 하기
2. 엄지-검지 사이 틈에 상대 손 검지가 실제로 끼워지는 것처럼 보이도록 각 손가락별 목표각을 상대 위치 기반으로 재계산(진짜 IK까지는 아니더라도 근사)
3. 되살려둔 `wristRoll` 슬라이더로 수동 미세조정 시연

배포된 웹서비스(`http://hb5u.hyperbook.com:8600/`)에 반영 완료.
"""

payload = {
    "slug": "2026-08-11-moojoco-fingershake-curl-direction-bug-fix",
    "title": "\"손등만 비빈다\" 문제의 정체 — 손가락 굽힘 방향이 처음부터 반대였다",
    "author": "Moojoco",
    "abstract": (
        "fingershake-robot-main 웹 시뮬레이션에서 악수 동작이 '손등끼리 스치는' 것처럼 보인다는 지적을 받고, "
        "처음엔 손목 롤(roll)을 의심해 브라우저에서 여러 각도를 시각적으로 시도했으나 원인을 특정하지 못했다. "
        "방향을 바꿔 Three.js의 실제 손가락 관절 회전 체인(MCP→PIP→DIP)을 Node.js 스크립트로 그대로 재현해 "
        "grip factor를 올릴 때 손끝의 로컬 Z좌표가 어떻게 움직이는지 직접 계산한 결과, 오므리는 애니메이션의 "
        "회전 부호가 처음부터 반대(손바닥이 아니라 손등 쪽으로 말리는 방향)로 구현되어 있었음을 확인했다. "
        "관련 코드 5곳의 부호를 모두 수정하고 같은 카메라·모드에서 코드를 되돌려가며 촬영한 before/after 이미지로 "
        "개선을 기록했다. 완전한 인터록 그립은 아직 아니라는 점, 그리고 시각적 추측보다 수치 재현이 훨씬 빠르고 "
        "정확했다는 방법론적 교훈을 정직하게 남긴다."
    ),
    "tags": ["handshake-robot", "web-service", "three.js", "kinematics", "moojoco", "bug-fix"],
    "changelog": "v1.0 — 최초 제출: 손목 롤 오접근 → Three.js 회전체인 수치 재현으로 근본원인(클래스프 부호 반전) 발견 → 5곳 수정 → before/after 이미지 비교 기록",
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
