#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 손가락 독립 제어 구현 계획

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-dof-expansion-roadmap]]의 1순위 항목("손가락 독립 제어") 착수. 사령관 지시 — "손가락 독립 제어부터 시작해줘. 단 thesis에 계획을 세운후 시작해줘."
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `plan`, `moojoco`, `ui`

---

## 0. 현재 상태 진단

`fingershake-robot-main`의 손 지오메트리(`RobotBuilder.ts`)는 이미 손가락별로 완전히 분리돼 있다 — `fingerConfigs` 배열에 thumb/index/middle/ring/pinky 5개가 각자의 MCP/PIP/DIP 관절 체인을 갖는다. 문제는 애니메이션 쪽이다: manual 모드의 `applyDexGrip` 함수(`RobotScene.tsx`)가 **단 하나의 `gripFactor` 값**(`manualAnglesAlpha.fingerGrip`)을 5개 손가락 전부에 동시 적용한다. 즉 지오메트리는 5-DOF급인데 실제 제어는 1-DOF다.

## 1. 목표

`Finger Grip` 슬라이더 1개를 **손가락별 5개 슬라이더**(Thumb / Index / Middle / Ring / Pinky Curl)로 교체해, manual 모드에서 다섯 손가락을 완전히 독립적으로 오므리고 펼 수 있게 한다. [[2026-08-11-moojoco-dof-expansion-roadmap]]이 제안한 최소 기준("엄지 vs 나머지 4개")보다 더 나아가 완전 독립(5-DOF)을 목표로 잡는다 — 지오메트리가 이미 그렇게 분리돼 있어서 추가 비용이 크지 않기 때문이다.

**범위 한정**: 이번 작업은 manual 모드(수동 조작 탭)에만 적용한다. standard/energetic/diplomatic/impedance/rl_agent 등 자동 악수 모드는 지금처럼 단일 `gripFactor` 기반 클래스프 로직을 그대로 유지한다 — 자동 모드까지 손가락별로 나누는 건 이번 로드맵 1순위의 범위를 넘어선다.

## 2. 구체적 변경 계획

### 2-1. 타입 (`types.ts`)
`JointAngles.fingerGrip: number` 필드를 제거하고, 아래 5개로 교체:
```ts
thumbCurl: number;
indexCurl: number;
middleCurl: number;
ringCurl: number;
pinkyCurl: number; // 전부 0~1
```
`DEFAULT_JOINT_ANGLES`도 5개 모두 기존 기본값(0.8)으로 채운다.

### 2-2. 회전 로직 (`RobotScene.tsx`, manual 모드)
기존 `applyDexGrip(robot, gripFactor)`을 `applyDexGrip(robot, curls: number[])`로 바꾼다. 손가락 배열(`robot.rightFingers`)의 인덱스 순서(0=thumb, 1=index, 2=middle, 3=ring, 4=pinky)에 맞춰 각 손가락에 자기 자신의 curl 값을 사용하도록 `forEach`의 `gripFactor`를 `curls[i]`로 치환한다. 엄지의 특수 회전식(`rotation.y` 오포저블 오프셋)은 그대로 유지 — `curls[0]`(엄지 값)만 대입하면 된다.

### 2-3. UI (`KinematicControls.tsx`)
"Finger Grip" 슬라이더 1개를 삭제하고 5개 슬라이더로 교체(0~100%, step 5%). 패널이 이미 스크롤 가능하므로 슬라이더 5개 추가로 인한 레이아웃 문제는 없다.

### 2-4. 저장/불러오기
이미 구현된 localStorage 스키마 병합(`{...DEFAULT_JOINT_ANGLES, ...saved}`) 덕분에, 필드 이름이 `fingerGrip`→`thumbCurl` 등으로 바뀌어도 옛 저장값에는 새 필드가 없어 자동으로 기본값(0.8)이 채워진다 — 별도 마이그레이션 코드가 필요 없다. 다만 옛 저장값에 남아있는 `fingerGrip` 키는 그냥 무시된다(사용되지 않는 채로 localStorage에 남지만 해가 없음).

## 3. 검증 계획

1. `tsc --noEmit`으로 타입 에러 없는지 확인
2. 로컬 dev 서버(포트 8601)에서 각 손가락 슬라이더를 개별로 움직여, 다른 손가락은 그대로인 채 해당 손가락만 오므라드는지 스크린샷으로 확인
3. 예를 들어 엄지만 0%, 나머지 전부 100%로 설정해 "가위" 모양이 나오는지 등 극단값 조합으로 독립성 검증
4. 프로덕션 빌드 후 사령관 확인 요청

## 4. 다음 논문 예고

구현 완료 후 결과(before/after 스크린샷, 검증 로그)를 후속 논문으로 기록한다.
"""

payload = {
    "slug": "2026-08-11-moojoco-finger-independent-control-plan",
    "title": "손가락 독립 제어 구현 계획",
    "author": "Moojoco",
    "abstract": (
        "fingershake-robot-main의 손 지오메트리는 이미 5손가락으로 분리돼 있지만, manual 모드의 애니메이션 "
        "로직은 단일 gripFactor 값 하나로 5손가락을 동시 제어한다(1 DOF). [[2026-08-11-moojoco-dof-expansion-"
        "roadmap]]의 1순위 항목 착수를 위해, fingerGrip 필드를 thumbCurl/indexCurl/middleCurl/ringCurl/"
        "pinkyCurl 5개로 교체하고 각 손가락을 독립 슬라이더로 제어하는 계획을 세웠다. 자동 악수 모드(standard "
        "등)는 범위 밖으로 두고 manual 모드에만 적용하며, 기존 localStorage 스키마 병합 덕분에 별도 마이그레이션 "
        "없이 하위호환된다."
    ),
    "tags": ["handshake-robot", "kinematics", "plan", "moojoco", "ui"],
    "changelog": "v1.0 — 최초 제출: 손가락 독립 제어(5-DOF) 구현 계획 수립, 구현 전 사전 기록",
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
