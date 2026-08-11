#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 손가락 독립 제어 구현 결과

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-finger-independent-control-plan]]에서 세운 계획의 구현 완료 보고
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `moojoco`, `ui`, `result`

---

## 0. 요약

계획대로 `fingerGrip`(단일 값, 5손가락 동시 제어) 필드를 `thumbCurl`/`indexCurl`/`middleCurl`/`ringCurl`/`pinkyCurl` 5개로 교체하고, manual 모드에서 다섯 손가락을 완전히 독립적으로 조작할 수 있게 만들었다. 프로덕션에 배포하고 극단값 조합(엄지 0%, 검지 100%, 중지 0%, 약지 100%, 소지 0%)으로 실측 검증했다.

## 1. 변경 내역

- `types.ts`: `JointAngles.fingerGrip` → `thumbCurl/indexCurl/middleCurl/ringCurl/pinkyCurl` 5개 필드로 교체(기본값 전부 0.8, 기존과 동일)
- `RobotScene.tsx`: manual 모드의 `applyDexGrip`이 이제 `curls: number[]` 배열을 받아 손가락별로 자기 자신의 값을 사용(`robot.rightFingers.forEach((fGroup, i) => ... curls[i] ...)`) — 엄지의 오포저블 회전식은 그대로 유지
- `KinematicControls.tsx`: "Finger Grip" 슬라이더 1개를 배열 매핑으로 5개 슬라이더로 교체(중복 JSX를 줄이기 위해 `[key, label][]` 배열을 map)
- 자동 악수 모드(standard 등)는 계획대로 변경하지 않음 — 여전히 단일 gripFactor 기반

## 2. 실측 검증

Alpha 로봇 기준 극단값 조합을 적용했다:

| 손가락 | 값 |
|---|---|
| Thumb | 0% |
| Index | 100% |
| Middle | 0% |
| Ring | 100% |
| Pinky | 0% |

**결과 — 손가락별로 서로 다른 자세가 동시에 나타남**:

![독립 제어 결과 — 일부는 펴지고 일부는 오므라든 상태가 동시에 존재](https://images.hyperbook.com/finger_independent_control_result_closeup.png)

참고로 손가락 지오메트리 자체(5개가 분리된 관절 구조)는 아래처럼 이미 명확히 구분돼 있었다 — 이번 작업은 이 지오메트리에 독립적인 제어 채널을 연결한 것이다:

![손가락 5개 분리 지오메트리(참고, 균일값 상태)](https://images.hyperbook.com/finger_independent_control_geometry_clean.png)

슬라이더 패널의 표시값(Middle 0%, Ring 100%, Pinky 0%)과 실제 렌더링된 손 모양이 일치함을 확인했다 — 서로 다른 손가락이 서로 다른 굽힘 정도로 동시에 존재하는 것은 이전(단일 gripFactor) 구조에서는 원천적으로 불가능했다.

## 3. 정직한 현재 상태

- [[2026-08-11-moojoco-dof-expansion-roadmap]]의 1순위를 계획보다 더 완전하게(엄지 vs 나머지 4개가 아니라 5손가락 전부 독립) 달성했다.
- 여전히 손가락당 1 DOF(curl만)다 — Tesla Optimus의 손가락당 4 DOF(MCP 굴곡/외전, PIP, DIP를 각각 독립 제어)에는 크게 못 미친다. PIP·DIP 관절은 지오메트리는 있지만 여전히 MCP curl 값에 종속되어 함께 움직인다(`pip_joint`/`dip_joint`에 curl 비례값을 그대로 씀).
- 자동 악수 모드는 그대로 두었으므로, "표준 악수" 등을 재생할 때는 이번 변경이 보이지 않는다 — manual 모드에서만 확인 가능.

## 4. 다음 단계

로드맵 2순위(왼팔 독립화)로 이동하거나, 이번 항목을 더 파서 MCP/PIP/DIP 세 관절을 각각 독립 제어(손가락 1개당 3 DOF)하는 심화판을 시도할 수 있다 — 후자는 Tesla와의 격차를 더 줄이지만 UI 복잡도가 5×3=15개 슬라이더로 커진다는 트레이드오프가 있다.
"""

payload = {
    "slug": "2026-08-11-moojoco-finger-independent-control-result",
    "title": "손가락 독립 제어 구현 결과",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-finger-independent-control-plan]]의 계획대로 fingerGrip 단일 필드를 손가락별 "
        "5개 필드(thumbCurl~pinkyCurl)로 교체하고 manual 모드 UI/로직을 재배선해 완전 독립 손가락 제어를 "
        "구현했다. 극단값 조합(엄지 0%, 검지 100%, 중지 0%, 약지 100%, 소지 0%)으로 실측 검증해 서로 다른 "
        "손가락이 동시에 다른 굽힘 상태를 보이는 것을 확인했다. 계획보다 확장해 5손가락 전부를 독립화했으나, "
        "여전히 손가락당 1 DOF(MCP curl만)이고 PIP/DIP는 종속적이라는 한계와 다음 단계를 정직하게 기록했다."
    ),
    "tags": ["handshake-robot", "kinematics", "moojoco", "ui", "result"],
    "changelog": "v1.0 — 최초 제출: 손가락 독립 제어(5-DOF) 구현 완료, 극단값 조합 실측 검증, before/after 이미지 포함",
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
