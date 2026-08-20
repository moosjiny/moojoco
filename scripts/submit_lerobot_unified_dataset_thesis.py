#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT Phase 2 — Stage 1/1.5/1.75 데이터셋을 하나의 스키마로 통합 재생성

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-20-moojoco-lerobot-stage1-75-dataset-result]] 이후, Stage 1/1.5(행동 10차원, 손가락만)와 Stage 1.75(행동 12차원, 손목 포함)의 스키마가 달라 Stage 2 학습에 그대로 합칠 수 없다는 문제를 보고했다. 사령관 지시("1.75로 통일해서 재생성해줘")로 진행.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`

---

## 0. 무엇을 했나

`scripts/generate_procedural_curl_dataset_unified.py` — 새 스크립트를 만들지 않고, Stage 1.75의 컨트롤러 코드(`generate_procedural_curl_dataset_stage1_75.py`)를 모듈로 그대로 import해서 재사용했다. Stage 1의 원래 그리드(접근 거리·속도 45가지, 장애물 없음·오프셋 없음)를 Stage 1.75와 완전히 동일한 컨트롤러·스키마(관찰 15차원, 행동 12차원)로 다시 실행하고, 여기에 Stage 1.5/1.75의 두 서브 스윕(좌우/상하 오프셋 25개, 장애물 6개)을 이어붙여 **하나의 디렉터리, 하나의 스키마로 76 에피소드**를 생성했다.

## 1. Stage 1 재생성 — 결과가 바뀌지 않는다는 것부터 수학적으로 예상하고, 실측으로 확인

장애물이 멀리 있고(`obstacle_slow_factor`가 항상 1.0) 오프셋이 0이면, 손목 접근의 점화식 `approach_state += (ease(t) - approach_state) * slow_factor`는 `slow_factor=1.0`일 때 매 스텝 `approach_state = ease(t)`로 정확히 수렴한다 — 즉 Stage 1.75의 새 컨트롤러가 장애물이 없을 때는 Stage 1의 원래("장애물 미인지") 손목 궤적과 수식적으로 동일하다. 재생성 전에 이렇게 예상했고, 실측으로 정확히 들어맞았다: **24/45, Stage 1의 원래 결과와 완전히 동일한 숫자**다. 컨트롤러를 바꿨는데도 결과가 안 바뀌는 걸 직접 확인한 것 자체가 "코드를 통합해도 기존 실험이 깨지지 않는다"는 걸 재현 가능하게 보여준 셈이다.

## 2. 통합 데이터셋 요약

`data/procedural_curl_dataset_unified/` — 76 에피소드, Parquet, 712KB, GPU 미사용 12.07초.

| 서브 스윕 | 에피소드 수 | 게이트 통과 |
|---|---|---|
| `stage1_approach` (접근 거리·속도) | 45 | 24 (Stage 1과 동일) |
| `A_lateral_height` (좌우/상하 오프셋) | 25 | 18 (Stage 1.5/1.75와 동일) |
| `B_obstacle` (장애물) | 6 | 6 (Stage 1.75와 동일) |
| **합계** | **76** | **48** |

- 관찰(15차원): `a_progress`, `b_progress`, 손가락별(양손×5) 근접도 10, `handB_lateral_offset_m`, `handB_height_offset_m`, `obstacle_proximity_m`.
- 행동(12차원): `handA/B_approach_use_frac`(손목, 신규 통일) + 손가락별(양손×5) curl 사용비율 10.

## 3. 다음 단계

세 서브 스윕이 이제 완전히 같은 스키마다. [[2026-08-20-moojoco-lerobot-act-phase2-plan]] v2에서 정한 필터링 방침(성공 궤적만 행동으로 모방학습, 실패 궤적은 관찰만 안전-경계 신호로 재사용)을 그대로 76개 전체에 적용할 수 있다. Stage 2(LeRobot 환경 세팅 + ACT 학습) 착수 준비가 끝났다 — 사령관 확인 후 진행한다.
"""

payload = {
    "slug": "2026-08-20-moojoco-lerobot-unified-dataset-result",
    "title": "LeRobot Phase 2 — Stage 1/1.5/1.75 데이터셋 스키마 통합",
    "author": "Moojoco",
    "abstract": (
        "Stage 1/1.5(행동 10차원, 손가락만)와 Stage 1.75(행동 12차원, 손목 포함) 사이의 스키마 불일치를 "
        "해소하기 위해, Stage 1.75의 장애물 인지형 컨트롤러 코드를 모듈로 재사용해 Stage 1의 원래 그리드를 "
        "동일 스키마(관찰 15차원/행동 12차원)로 재생성하고 세 서브 스윕(접근 거리·속도 45, 좌우/상하 오프셋 25, "
        "장애물 6)을 하나의 디렉터리에 통합했다. 장애물이 없을 때는 새 컨트롤러가 수식적으로 기존 컨트롤러와 "
        "동일하게 수렴한다는 것을 재생성 전에 예상했고, 실측 결과(24/45)가 정확히 Stage 1의 원래 숫자와 "
        "일치함을 확인했다. 76 에피소드, 712KB, GPU 없이 12초 만에 생성했으며 48개가 5% 침투 게이트를 "
        "통과했다. Stage 2 착수를 위한 데이터 준비가 끝났다."
    ),
    "tags": ["handshake-robot", "result", "moojoco", "mujoco", "lerobot"],
    "changelog": "v1.0 — 최초 제출: Stage 1/1.5/1.75를 12차원 행동 스키마로 통합 재생성(76 에피소드), Stage 1 결과 불변 확인",
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
