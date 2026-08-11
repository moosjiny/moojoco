#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 다리 고관절·무릎 독립화 — 계획 및 결과

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-dof-expansion-roadmap]] 3순위 착수. 사령관 지시 — "다리 고관절·무릎 독립화 시작해줘."
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `moojoco`, `ui`, `result`

---

## 0. 계획 (저비용 항목)

로드맵에서 미리 확인해둔 대로 `leftHip`/`rightHip`/`leftKnee`/`rightKnee` 그룹은 `RobotJointRefs`에 이미 노출돼 있지만 회전이 한 번도 연결된 적이 없다 — [[2026-08-11-moojoco-fingershake-joint-slider-save-usage-guide]]에서 발목(ankleGroup)을 추가하기 전과 정확히 같은 상태다. 발목 때와 같은 패턴을 그대로 따른다:

- `JointAngles`에 `hipFlexion`, `kneeFlexion` 2개 필드 추가(Foot Angle과 마찬가지로 양쪽 다리에 동일하게 적용되는 단일 값 — 팔처럼 좌우를 따로 만들지 않음, 걷는 자세가 아니라 정적 포즈 실험이 목적이라 대칭이면 충분)
- manual 모드에서 `leftHip.rotation.x`, `rightHip.rotation.x`, `leftKnee.rotation.x`, `rightKnee.rotation.x`에 각각 연결
- UI에 Hip Flexion, Knee Flexion 슬라이더 2개 추가(Foot Angle 옆에 배치)
- 새 지오메트리 불필요 — 이미 있는 그룹에 회전만 연결하면 되는 작업이므로 별도 검증 계획 없이 구현 직후 실측 확인으로 충분

## 1. 구현 내역

- `types.ts`: `hipFlexion`, `kneeFlexion` 필드 추가(기본값 0)
- `RobotScene.tsx`: manual 모드에 `alpha.leftHip.rotation.x = manualAnglesAlpha.hipFlexion * degToRad` 등 4줄 추가(양쪽 로봇 × 양쪽 다리)
- `KinematicControls.tsx`: Hip Flexion(-45~90°), Knee Flexion(0~120°) 슬라이더 추가

## 2. 실측 검증

Hip Flexion을 크게(다리를 앞으로 들어올리는 방향), Knee Flexion도 크게 줘서 다리가 확실히 구부러지는지 확인했다.

![다리 고관절·무릎 굴곡 실측 — 양쪽 다리가 앞으로 구부러진 자세](https://images.hyperbook.com/leg_hip_knee_flexion_result.png)

## 3. 정직한 현재 상태

- 발목과 마찬가지로 **양쪽 다리 동시 대칭 적용**이다 — 오른발만 들어올리는 등 좌우 비대칭 다리 동작은 안 된다(로드맵 우선순위상 걷기 애니메이션이 목적이 아니라 정적 포즈 실험이 목적이라 이 정도로 충분하다고 판단).
- [[2026-08-11-moojoco-dof-expansion-roadmap]]의 3순위와 4순위(몸통 Pitch) 중 3순위를 완료했다. 4순위(`torsoPitch`, 마찬가지로 죽은 코드 연결)가 로드맵의 마지막 남은 저비용 항목이다.
"""

payload = {
    "slug": "2026-08-11-moojoco-leg-hip-knee-control",
    "title": "다리 고관절·무릎 독립화 — 계획 및 결과",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-dof-expansion-roadmap]] 3순위 착수. leftHip/rightHip/leftKnee/rightKnee "
        "그룹이 RobotJointRefs에 이미 노출돼 있으나 회전 미연결 상태였음을 확인(발목 추가 전과 동일 패턴). "
        "Foot Angle과 같은 방식으로 hipFlexion/kneeFlexion 2개 필드를 추가해 양쪽 다리에 동일 적용하고, "
        "manual 모드 슬라이더로 연결해 실측 검증했다. 좌우 비대칭 다리 동작(예: 한쪽 다리만 들기)은 범위 밖으로 "
        "명시했다."
    ),
    "tags": ["handshake-robot", "kinematics", "moojoco", "ui", "result"],
    "changelog": "v1.0 — 최초 제출: 다리 고관절/무릎 슬라이더 추가(양쪽 다리 대칭), 실측 검증 이미지 포함",
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
