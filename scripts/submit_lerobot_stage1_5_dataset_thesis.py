#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT Phase 2 Stage 1.5 — 좌우/상하 오프셋과 장애물 실측 결과

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-20-moojoco-lerobot-act-phase2-plan]] v2에서 신설한 Stage 1.5 착수. 사령관 지시("먼저 다 커밋하고 1.5 착수해줘")로 진행.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`

---

## 0. 무엇을 확장했나

`urdf/amazinghand_5finger_docking_v2.xml` — Stage 1의 모델에 두 가지를 추가:

1. `handB_wrist`에 `handB_lateral`(로컬 X, slide), `handB_height`(로컬 Z, slide) 2-DOF 추가 — 두 손이 정확히 마주보지 않고 좌우/상하로 어긋나 접근하는 상황을 표현.
2. kinematic 장애물(`mocap` body, box geom) 추가 — 평소엔 `y=5`(멀리)에 치워두고, 에피소드마다 `data.mocap_pos`로 접근 경로 위 원하는 위치에 배치 가능.

`scripts/generate_procedural_curl_dataset_stage1_5.py` — Stage 1과 동일한 사전-감속 제어기를 재사용해 두 서브 스윕을 실행: **서브 스윕 A**(좌우/상하 오프셋, 25 에피소드)와 **서브 스윕 B**(장애물, 6 에피소드), 총 31 에피소드. 관찰(observation.state)이 12차원(Stage 1)에서 **15차원**으로 확장(`handB_lateral_offset_m`, `handB_height_offset_m`, `obstacle_proximity_m` 추가), 행동은 Stage 1과 동일한 10차원.

## 0-1. 시행착오 — kp=40으로는 "회피"가 생겨 신호 자체가 사라짐

처음엔 새 lateral/height 축도 기존 접근축과 같은 PD 게인(kp=40, kd=4)으로 고정했는데, **25개 오프셋 조합 전부 침투비 0.0000**이 나왔다. 원인을 추적해보니, kp=40은 접근 궤적처럼 "천천히 움직이는 목표를 따라가는" 데는 충분해도 "접촉력에 저항해 정적 위치를 버티는" 데는 턱없이 약해서, 손끼리 부딪히면 손이 그냥 옆으로 살짝 밀려 충돌을 회피해버렸다 — 즉 오프셋 값과 무관하게 "여분의 유연성" 자체가 문제를 지워버린 것이다. 유지력을 키워(kp=2000, kd=40, 액추에이터 `ctrlrange`는 그대로 ±5N) 접촉력에 실제로 버티도록 고친 뒤에야 오프셋 값에 따라 결과가 갈라지기 시작했다. 사소해 보이지만, "관찰 차원만 늘리면 된다"는 최초 가정이 틀렸다는 걸 실측으로 확인한 셈이다 — 새 자유도를 넣을 때는 그 자유도의 **유지 강성**도 실험 설계의 일부다.

## 1. 서브 스윕 A 결과 — 사령관 질문 1("XY가 바뀌면 성공/실패가 달라지지 않나")에 대한 답: 그렇다, 그것도 비단조적으로

고정 조건은 Stage 1에서 근소하게 실패했던 baseline 경계 사례(a_end=-0.028, b_end=+0.0952, 4초, 침투비 0.0535)다. 여기에 lateral(좌우) × height(상하) 오프셋을 각 5단계(±15mm, ±7.5mm, 0)로 25가지 스윕:

| lateral \\\\ height | -15mm | -7.5mm | 0mm | +7.5mm | +15mm |
|---|---|---|---|---|---|
| -15mm | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| -7.5mm | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0mm | 0.000 | 0.000 | **0.076** | **0.079** | 0.000 |
| +7.5mm | **0.133** | **0.107** | **0.147** | **0.171** | **0.132** |
| +15mm | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

(굵게 표시한 값이 5% 게이트 실패. 25개 중 7개 실패, 18개 통과 — 통과율 72%.)

예상은 "가운데(오프셋 0)가 제일 위험하고 오프셋이 커질수록 점점 안전해지거나 위험해지거나 단조적으로 변할 것"이었는데, 실측은 정반대에 가까웠다: **lateral +7.5mm 열 전체가 가장 나쁘고(0.107~0.171), 그보다 더 큰 +15mm는 오히려 전부 완전 통과(0.000)**다. 손가락 다섯 개가 서로 다른 위상(`CURL_PHASE`)으로 오므라들기 때문에, 중간 정도의 어긋남에서는 특정 손가락 쌍끼리 정면으로 부딪히지만, 충분히 크게 어긋나면 손 자체가 서로를 완전히 비껴가 접촉이 아예 발생하지 않는 것으로 보인다. **결론: 사령관의 예상대로 XY 위치는 성공/실패 경계를 실제로 바꾸지만, 그 관계가 단조적이지 않다는 게 이번 실측의 핵심 발견이다** — 이는 Stage 2에서 학습할 정책이 왜 단순 보간이 아니라 실제 함수 근사(신경망)가 필요한지를 뒷받침한다.

## 2. 서브 스윕 B 결과 — 사령관 질문 2("개울 같은 장애물이 있으면?")에 대한 답: 파국적으로 실패한다

고정 조건은 Stage 1에서 모든 속도에서 여유 있게 통과했던 사례(b_end를 baseline보다 10mm 더 짧게)다. 장애물을 "없음"부터 접근 경로 한가운데(world y=0.06→0.0)까지 스윕:

| 장애물 위치 | 침투비 |
|---|---|
| 없음 | 0.000 (PASS) |
| y=0.06 | 0.303 (FAIL) |
| y=0.045 | 0.490 (FAIL) |
| y=0.03 | 0.343 (FAIL) |
| y=0.015 | 0.301 (FAIL) |
| y=0.0 | 0.133 (FAIL) |

장애물이 조금이라도 접근 경로에 들어오면 **전부 실패**, 그것도 침투비가 최대 49%(캡슐 반경의 거의 절반)까지 치솟는다. 원인은 명확하다 — 지금 손목 접근 컨트롤러는 "목표 지점까지 계속 힘을 준다"만 알고, 목표 지점 자체가 물리적으로 도달 불가능(장애물에 막힘)이라는 걸 전혀 모른다. 손가락 curl 컨트롤러는 반대쪽 손과의 거리만 보고 감속할 뿐, 장애물과의 거리는 애초에 관찰하지 않으므로 손을 짓누르는 동안에도 태연히 손가락을 오므린다. **결론: 장애물 상황은 손가락 curl 정책만으로는 절대 해결되지 않는다.** 데이터셋에는 `obstacle_proximity_m`을 관찰로 넣어뒀지만, Stage 1.5의 손목 컨트롤러 자체는 아직 이 신호를 쓰지 않는다 — 이건 Stage 2/3에서 "손목 접근 자체를 장애물 인지형으로 만들 것인가"를 별도로 결정해야 한다는 뜻이다(§4 참고).

## 3. 데이터셋

- `data/procedural_curl_dataset_stage1_5/` — 31 에피소드, Parquet, 268KB, GPU 미사용 3.82초.
- 관찰 15차원: Stage 1의 12차원 + `handB_lateral_offset_m`, `handB_height_offset_m`, `obstacle_proximity_m`.
- 필터링 방침([[2026-08-20-moojoco-lerobot-act-phase2-plan]] v2-2)을 그대로 적용: `passed_5pct_gate=true`인 19개 궤적의 행동만 모방학습 대상, 나머지 12개는 관찰만 안전-경계 신호로 재사용.

## 4. Stage 2로 넘어가기 전 남는 질문

- 서브 스윕 B의 결과는 "장애물 인지"가 손가락 curl 정책 하나로 해결될 문제가 아니라는 걸 보여준다. Stage 2 정책의 범위를 (a) 지금처럼 손가락 curl만으로 한정하고 장애물 상황은 별도 상위 로직(접근 자체를 중단)에 맡길지, (b) 손목 접근 목표까지 포함하는 더 큰 정책으로 확장할지 — 착수 전에 정할 필요가 있다.
- 서브 스윕 A의 비단조적 결과(중간 오프셋이 제일 위험, 큰 오프셋은 오히려 안전)는 그리드가 성기어(5단계) 정확한 위험 구간의 경계를 모른다 — 필요하면 lateral 0~15mm 구간을 더 촘촘히 재스윕할 수 있다.

이 두 가지는 사령관 판단을 구하고 다음 단계로 진행한다.
"""

payload = {
    "slug": "2026-08-20-moojoco-lerobot-stage1-5-dataset-result",
    "title": "LeRobot Phase 2 Stage 1.5 — 좌우/상하 오프셋·장애물 실측 결과",
    "author": "Moojoco",
    "abstract": (
        "LeRobot/ACT Phase 2 계획의 Stage 1.5(기하 다양성 확장)를 구현·실행했다. 모델에 handB의 좌우/상하 "
        "2-DOF와 kinematic 장애물을 추가하고, Stage 1과 동일한 사전-감속 제어기로 두 서브 스윕(오프셋 25 "
        "에피소드, 장애물 6 에피소드)을 실행했다. 오프셋 축은 처음에는 접근축과 같은 PD 게인(kp=40)을 썼다가 "
        "손이 접촉력에 밀려 회피해버려 모든 조합이 침투 0으로 나오는 함정에 빠졌고, 유지 강성을 크게 높인 뒤 "
        "실제 신호가 드러났다. 결과: 좌우/상하 오프셋은 성공/실패 경계를 실제로 바꾸지만 비단조적이며(중간 "
        "오프셋이 제일 위험, 큰 오프셋은 오히려 완전 통과), 장애물은 접근 경로에 조금만 들어와도 예외 없이 "
        "파국적으로 실패한다(침투비 최대 49%) — 현재 컨트롤러가 장애물 근접도를 전혀 관찰하지 않기 때문이다. "
        "Stage 2 착수 전 정책 범위(손가락 curl만 vs 손목 접근까지 포함)를 결정할 필요가 있다고 제안한다."
    ),
    "tags": ["handshake-robot", "result", "moojoco", "mujoco", "lerobot"],
    "changelog": "v1.0 — 최초 제출: Stage 1.5 모델 확장·데이터 생성·실측 결과(오프셋 비단조성, 장애물 파국적 실패) 보고",
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
