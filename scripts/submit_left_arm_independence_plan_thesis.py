#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 왼팔 독립화 구현 계획

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-dof-expansion-roadmap]]의 2순위 항목 착수. 사령관 지시 — "왼팔 독립화 시작해줘."
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `plan`, `moojoco`, `ui`

---

## 0. 현재 상태 진단

`RobotBuilder.ts`를 확인한 결과, 왼팔의 실제 지오메트리 수준이 오른팔과 크게 다르다:

| 부위 | 오른팔 | 왼팔 |
|---|---|---|
| 어깨(Shoulder) | Group, 3-DOF 회전 가능 | Group, 존재함(3-DOF 가능) |
| 팔꿈치(Elbow) | Group, 1-DOF | Group, 존재함(1-DOF 가능) |
| 손목(Wrist) | FT센서링·palm chassis·back plate 등 별도 Group | **없음** |
| 손(Hand) | 5손가락×MCP/PIP/DIP 관절 체인 | **단순 Box 메시 하나뿐(관절 없음)** |

즉 어깨·팔꿈치는 이미 지오메트리가 있어 [[2026-08-11-moojoco-fingershake-joint-slider-save-usage-guide]] 세션에서 미러링으로 활성화했지만, 손목·손은 애초에 만들어진 적이 없다 — 이건 "슬라이더만 연결하면 되는" 저비용 작업이 아니라 **새 3D 지오메트리를 처음부터 만들어야 하는** 작업이다.

## 1. 단계적 접근

한 번에 손목·손까지 전부 독립화하는 대신, 2단계로 나눈다.

### 1단계(이번 작업) — 어깨·팔꿈치 독립화
지금은 왼팔이 오른팔 슬라이더 값을 그대로 미러링만 한다(`RobotScene.tsx`의 `alpha.leftShoulder.rotation.x = manualAnglesAlpha.shoulderPitch * degToRad` 등). 이걸 **왼팔 전용 슬라이더 4개**(Left Shoulder Pitch/Yaw/Roll, Left Elbow Flexion)로 교체해, 오른팔과 완전히 다른 자세를 취할 수 있게 한다. 기존 지오메트리(leftShoulder, leftElbow 그룹)를 그대로 쓰므로 새 3D 모델링이 필요 없다.

### 2단계(향후, 별도 세션) — 손목·손 지오메트리 신설
오른팔의 손목 조립체(FT센서링, palm chassis, thenar/hypothenar 패드, 촉각 센서, 5손가락×MCP/PIP/DIP)를 왼쪽으로 거울 복제하는 함수로 리팩터링해야 한다. 지금 `RobotBuilder.ts`의 "6. Right Arm" 섹션(약 300줄)이 오른팔 전용으로 하드코딩돼 있어서, `buildDexArm(isRight: boolean)` 형태로 일반화한 뒤 양쪽에서 호출하는 리팩터링이 선행돼야 한다. 작업량이 커서 이번 턴에서는 계획만 밝히고 진행하지 않는다.

## 2. 1단계 구체 변경 계획

### 2-1. 타입 (`types.ts`)
`JointAngles`에 4개 필드 추가:
```ts
leftShoulderPitch: number;
leftShoulderYaw: number;
leftShoulderRoll: number;
leftElbowFlexion: number;
```
기본값은 오른팔과 대칭인 자세가 자연스럽도록, 오른팔 기본값(-64/-20/-12/50)에서 Yaw·Roll만 부호 반전한 값(-64/20/12/50)으로 채운다 — 지금의 미러링 결과와 시각적으로 동일한 초기 자세를 유지하기 위함.

### 2-2. 회전 로직 (`RobotScene.tsx`)
manual 모드에서 아래 미러링 코드:
```ts
alpha.leftShoulder.rotation.x = manualAnglesAlpha.shoulderPitch * degToRad;
alpha.leftShoulder.rotation.y = -manualAnglesAlpha.shoulderYaw * degToRad;
alpha.leftShoulder.rotation.z = -manualAnglesAlpha.shoulderRoll * degToRad;
alpha.leftElbow.rotation.x = manualAnglesAlpha.elbowFlexion * degToRad;
```
를 새 필드를 직접 쓰는 코드로 교체:
```ts
alpha.leftShoulder.rotation.x = manualAnglesAlpha.leftShoulderPitch * degToRad;
alpha.leftShoulder.rotation.y = manualAnglesAlpha.leftShoulderYaw * degToRad;
alpha.leftShoulder.rotation.z = manualAnglesAlpha.leftShoulderRoll * degToRad;
alpha.leftElbow.rotation.x = manualAnglesAlpha.leftElbowFlexion * degToRad;
```

### 2-3. UI (`KinematicControls.tsx`)
"왼팔(Left Arm)" 구획을 오른팔 슬라이더들과 시각적으로 구분되도록 추가(예: 구분선 또는 소제목 텍스트로 "— Left Arm —" 표기). 슬라이더 4개, 범위는 오른팔과 동일하게.

## 3. 검증 계획
1. `tsc --noEmit` 통과 확인
2. 로컬 dev 서버에서 오른팔은 그대로 두고 왼팔만 크게 다른 각도(예: 수평으로 옆으로 뻗기)로 조작해, 두 팔이 서로 다른 자세를 동시에 취하는지 스크린샷으로 확인 — 이게 바로 "미러링이 아니라 독립"이라는 증거
3. 프로덕션 빌드 후 배포

## 4. 정직한 범위 한정
이번 1단계로는 왼손 자체(손목 방향, 손가락)는 여전히 조작 불가능하다 — 왼팔을 아무리 돌려도 손끝에 달린 건 관절 없는 상자 하나다. "왼팔 독립화"라는 제목이 완전한 손 기능까지 포함한다고 오해되지 않도록 이 한계를 명시한다. 2단계(손목·손 지오메트리 신설)는 별도 계획으로 이어간다.
"""

payload = {
    "slug": "2026-08-11-moojoco-left-arm-independence-plan",
    "title": "왼팔 독립화 구현 계획",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-dof-expansion-roadmap]] 2순위 착수. RobotBuilder.ts 조사 결과 왼팔은 어깨·팔꿈치 "
        "지오메트리는 있지만 손목·손은 관절 없는 단순 박스 하나뿐임을 확인했다. 이에 따라 2단계로 나눠, 1단계는 "
        "기존 어깨·팔꿈치 지오메트리를 활용해 오른팔 미러링을 걷어내고 왼팔 전용 슬라이더 4개(Shoulder Pitch/"
        "Yaw/Roll, Elbow Flexion)로 완전 독립화하는 계획을 세웠다. 2단계(손목·손 지오메트리 신설, buildDexArm "
        "리팩터링)는 작업량이 커서 별도 세션 과제로 남기고 이번엔 계획만 명시했다."
    ),
    "tags": ["handshake-robot", "kinematics", "plan", "moojoco", "ui"],
    "changelog": "v1.0 — 최초 제출: 왼팔 독립화 2단계 계획 수립(1단계 어깨/팔꿈치, 2단계 손목/손 지오메트리는 향후 과제)",
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
