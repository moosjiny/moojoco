#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 이번 세션 자유도(DOF) 확장 기록과 다음 연구 로드맵

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 — "추가된 자유도에 대해서 thesis에 정리해줘. 앞으로 좀 더 자유도가 필요한것 같아. 이부분에 대해서 계속 연구할수 있도록 계획을 세워줘." ([[2026-08-11-moojoco-tesla-optimus-dof-research]]에서 Tesla Optimus와의 DOF 격차를 확인한 직후)
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `roadmap`, `moojoco`, `ui`

---

## 0. 요약

이번 세션에서 `fingershake-robot-main`의 실제 조작 가능한 관절 자유도(DOF)가 **6개 → 14개**로 두 배 이상 늘었다. 오른팔만 보면 **7 DOF로 Tesla Optimus의 팔 자유도와 동률**을 달성했다. 하지만 손가락(1 vs Tesla 22), 다리(1 vs 6), 왼팔 독립성(거울대칭만 가능, 진짜 독립 제어 불가) 쪽은 여전히 큰 격차가 남아있다. 이 격차를 메우는 4단계 로드맵을 정리한다.

![DOF 확장 기록 및 Tesla 대비 격차, 다음 로드맵](https://images.hyperbook.com/dof_progress_and_roadmap.svg)

---

## 1. 이번 세션에서 추가/활성화된 자유도

| 순서 | 추가 내용 | 이전 상태 | 현재 상태 |
|---|---|---|---|
| 1 | Wrist Roll | 필드는 있으나 회전에 미연결(죽은 코드) | 슬라이더 연결, "엄지 위" 정렬 실험에 사용 |
| 2 | Shoulder Roll | 회전엔 연결돼 있었으나 슬라이더 UI 없음 | 슬라이더 추가로 조작 가능 |
| 3 | Foot Angle(발목) | 관절 자체가 없음(발이 종아리에 고정) | 새 THREE.Group(ankleGroup) 생성 + 슬라이더 |
| 4 | 왼팔 거울 대칭 | 완전 정적(shoulder/elbow 그룹은 있지만 회전 미적용) | 오른팔 슬라이더 값을 Yaw·Roll 부호 반전해 동시 적용 |
| 5 | Wrist Yaw | 없음 | 슬라이더 추가, 손목이 Pitch·Roll·Yaw 3축 완비 |
| (부수) | localStorage 스키마 병합 버그 수정 | 새 필드 추가 시 기존 저장값에 없어 NaN 발생 | `{...DEFAULT_JOINT_ANGLES, ...saved}` 병합으로 하위호환 확보 |

이로써 오른팔 손목이 **1축(Pitch만) → 3축(Pitch·Roll·Yaw)**으로 완비됐고, 오른팔 전체는 **어깨3+팔꿈치1+손목3 = 7 DOF**로 Tesla Optimus의 팔 스펙과 정확히 일치하게 됐다.

## 2. 남은 격차 (Tesla Optimus 대비)

- **손가락**: 우리 1 DOF(Finger Grip 하나로 5손가락 동시 이동) vs Tesla 22 DOF(손가락당 4). **가장 큰 격차 구간**.
- **왼팔**: 우리는 오른팔의 거울 이미지로만 움직임(독립 슬라이더 없음, 손목·손 구조 자체가 없음) vs Tesla는 양팔이 완전히 독립적.
- **다리**: 우리 1 DOF(발목만) vs Tesla 6 DOF(고관절·무릎 포함). 고관절·무릎 지오메트리(`leftHip`, `leftKnee` 등)는 이미 있지만 회전이 연결 안 돼 있다 — 발목과 정확히 같은 상태였던 문제를 아직 안 고친 것.
- **몸통**: `torsoPitch` 필드가 타입에는 있지만 여전히 죽은 코드.

## 3. 연구 로드맵 (우선순위 순)

### 1순위 — 손가락 독립 제어
현재 `Finger Grip` 슬라이더 하나가 5개 손가락(엄지 포함)을 전부 동시에 움직인다. 최소한 **엄지 vs 나머지 4개**를 분리하는 2-DOF 손이라도 만들면, 격차가 가장 큰 구간(22 DOF)에서 의미 있는 진전이 된다. `RobotBuilder.ts`의 `fingerConfigs` 배열이 이미 손가락별로 분리돼 있으므로, `applyClaspGrip` 계열 함수에서 엄지만 별도 gripFactor를 받도록 바꾸는 것으로 시작 가능.

### 2순위 — 왼팔 독립화
지금은 오른팔 값을 그대로 미러링만 한다. 왼팔에 실제 `leftWrist`, `leftFingers` 구조를 오른팔과 동일하게(거울 지오메트리로) 만들고 별도 슬라이더를 붙이면, 예를 들어 "오른손은 악수하고 왼손은 흔든다" 같은 비대칭 동작이 가능해진다. 이번 세션의 좌우 대칭 작업보다 작업량이 크다(새 지오메트리 필요).

### 3순위 — 다리 고관절·무릎
이번에 발목을 추가했던 것과 완전히 같은 패턴 — `leftHip`/`rightHip`/`leftKnee`/`rightKnee` 그룹은 이미 `RobotJointRefs`에 노출돼 있으므로, manual 모드에 회전을 연결하고 슬라이더 2개(Hip, Knee)만 추가하면 된다. 비용 대비 가장 저렴한 다음 작업.

### 4순위 — 몸통 Pitch
`torsoPitch` 필드도 이미 타입에 존재하는 죽은 코드다. 3순위와 마찬가지로 연결 비용은 낮지만, 핸드셰이크 시뮬레이션에서 몸통 앞뒤 숙임이 주는 시각적 임팩트는 상대적으로 작아 4순위로 낮췄다.

## 4. 정직한 참고사항

이 로드맵의 DOF 수치는 모두 "슬라이더로 직접 조작 가능한 값" 기준이다. 지오메트리(3D 형상) 자체는 이미 더 많은 관절을 갖고 있는 경우가 많다(예: 손가락 15관절, 다리 고관절/무릎) — 문제는 그 형상이 애니메이션 로직과 연결이 안 돼 있다는 것뿐이다. 즉 "자유도 부족"의 상당 부분은 새 지오메트리를 만드는 문제가 아니라, **이미 있는 지오메트리를 슬라이더에 연결만 하면 되는** 비교적 저비용 작업이라는 점을 밝혀둔다 — 3·4순위가 특히 그렇다.
"""

payload = {
    "slug": "2026-08-11-moojoco-dof-expansion-roadmap",
    "title": "이번 세션 자유도(DOF) 확장 기록과 다음 연구 로드맵",
    "author": "Moojoco",
    "abstract": (
        "fingershake-robot-main의 조작 가능한 관절 자유도가 이번 세션에서 6개→14개로 두 배 이상 늘었다: "
        "손목 Roll·Yaw 추가(1축→3축), 어깨 Roll 슬라이더 노출, 발목 관절 신규 생성, 왼팔 거울대칭 활성화. "
        "오른팔만 놓고 보면 7 DOF로 Tesla Optimus의 팔 자유도와 동률을 달성했다. 다만 손가락(1 vs 22), 다리 "
        "고관절/무릎(미연결), 왼팔 독립성(거울만 가능) 쪽은 격차가 크게 남아있어, 손가락 독립화→왼팔 "
        "독립화→다리 고관절/무릎→몸통 Pitch 순의 4단계 로드맵을 세웠다. 3·4순위는 이미 존재하는 지오메트리를 "
        "슬라이더에 연결만 하면 되는 저비용 작업임을 명시했다."
    ),
    "tags": ["handshake-robot", "kinematics", "roadmap", "moojoco", "ui"],
    "changelog": "v1.0 — 최초 제출: 이번 세션 DOF 확장 내역 정리, Tesla 대비 격차 시각화, 4단계 연구 로드맵 수립",
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
