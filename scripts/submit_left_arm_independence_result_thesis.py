#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 왼팔 독립화(1단계) 구현 결과

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-left-arm-independence-plan]] 1단계(어깨·팔꿈치) 구현 완료 보고
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `moojoco`, `ui`, `result`

---

## 0. 요약

계획대로 왼팔의 미러링 로직을 걷어내고 `leftShoulderPitch/Yaw/Roll`, `leftElbowFlexion` 4개 독립 필드로 교체했다. manual 모드에서 오른팔은 그대로 두고 왼팔만 극단값(어깨 Pitch +30°, 팔꿈치 0°)으로 바꿔, 오른팔은 여전히 악수하듯 뻗은 자세를 유지하면서 왼팔만 완전히 다른 각도로 내려가는 것을 실측 확인했다.

![오른팔은 악수 자세 유지, 왼팔만 독립적으로 다른 각도로 전환됨](https://images.hyperbook.com/left_arm_independence_result.png)

## 1. 변경 내역

- `types.ts`: `JointAngles`에 `leftShoulderPitch/Yaw/Roll`, `leftElbowFlexion` 4개 필드 추가(기본값은 이전 미러링 결과와 시각적으로 동일하도록 오른팔 기본값의 Yaw·Roll 부호만 반전)
- `RobotScene.tsx`: manual 모드에서 `alpha.leftShoulder.rotation.x = -manualAnglesAlpha.shoulderYaw * degToRad` 등 미러링 수식을 제거하고, 새 필드를 직접 대입하는 코드로 교체
- `KinematicControls.tsx`: "LEFT ARM (INDEPENDENT)" 구분선과 함께 4개 슬라이더 추가

## 2. 실측 검증

오른팔은 손대지 않고, Alpha 로봇의 왼팔만 Left Shoulder Pitch를 최댓값(30°)으로, Left Elbow Flexion을 최솟값(0°)으로 바꿨다. 결과: 오른팔은 여전히 중앙(상대 로봇)을 향해 뻗은 상태를 유지했고, 왼팔만 몸통 옆으로 곧게 내려간 완전히 다른 자세를 취했다 — 더 이상 오른팔을 따라 미러링되지 않음을 시각적으로 확인했다.

## 3. 정직한 현재 상태 (2단계 미착수)

계획서에 명시했던 대로, 이번 1단계는 **어깨·팔꿈치만** 독립화했다. 왼손 자체는 여전히 관절 없는 단순 박스라 손목 방향이나 손가락은 조작할 수 없다. 2단계(손목·손 지오메트리 신설, `buildDexArm` 리팩터링)는 작업량이 커서 이번 세션에서는 진행하지 않았고, 별도 계획으로 이어갈 예정이다.

## 4. 다음 단계

[[2026-08-11-moojoco-dof-expansion-roadmap]]의 3순위(다리 고관절·무릎)로 넘어가거나, 왼팔 2단계(손목·손 지오메트리)를 별도 세션에서 착수할 수 있다.
"""

payload = {
    "slug": "2026-08-11-moojoco-left-arm-independence-result",
    "title": "왼팔 독립화(1단계) 구현 결과",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-left-arm-independence-plan]]의 1단계 계획대로 왼팔의 오른팔 미러링 로직을 "
        "제거하고 leftShoulderPitch/Yaw/Roll, leftElbowFlexion 4개 독립 슬라이더로 교체했다. 오른팔은 손대지 "
        "않고 왼팔만 극단값(어깨 Pitch 30°, 팔꿈치 0°)으로 바꿔, 오른팔이 악수 자세를 유지하는 동안 왼팔만 "
        "완전히 다른 각도로 전환되는 것을 실측 확인했다. 손목·손 지오메트리 신설(2단계)은 작업량이 커 이번 "
        "세션 범위에서 제외했음을 정직하게 기록했다."
    ),
    "tags": ["handshake-robot", "kinematics", "moojoco", "ui", "result"],
    "changelog": "v1.0 — 최초 제출: 왼팔 독립화 1단계(어깨/팔꿈치) 구현 완료, 실측 검증, 2단계 범위 미포함 명시",
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
