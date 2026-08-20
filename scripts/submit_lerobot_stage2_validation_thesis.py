#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT Phase 2 Stage 2 검증 — 홀드아웃 폐루프 재실행, 5/11 통과

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 "먼저 검증해줘. 그리고 검증보고서를 thesis에 제출해줘." 직전 학습([[2026-08-20-moojoco-lerobot-unified-dataset-result]] 데이터로 200에폭 학습, loss 0.030)은 48개 게이트-통과 궤적 **전부**로 학습해 "봤던 궤적을 얼마나 잘 재현하는가"만 보여줬을 뿐, 처음 보는 조건에서 안전한지는 증명하지 않았다.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`, `verification`

---

## 0. 검증 방법

Hermes의 검증 게이트("screenshot/loss 수치는 증거 아님, `contact.dist` 실측 재현 요구")를 이 정책에도 그대로 적용했다.

1. 게이트 통과 48개 에피소드를 세 서브 스윕(접근/오프셋/장애물)에서 각각 5개마다 1개씩 층화 추출해 **11개를 완전히 학습에서 제외**하고, 나머지 37개로만 재학습(150에폭).
2. 홀드아웃 11개에 대해 두 가지를 측정:
   - **오프라인 L1**: 정답 관찰이 주어졌을 때 예측 행동과 실제 행동의 차이.
   - **폐루프 시뮬레이터 재실행**(진짜 검증): 매 제어 프레임마다 현재 물리 상태에서 관찰을 새로 조립해 정책에 넣고, 예측된 행동(손목 접근 진행률 + 손가락 curl 사용비율)을 그대로 목표값 삼아 PD 제어로 MuJoCo 물리를 다시 진행시켜 `contact.dist`를 재측정했다. 전문가 컨트롤러(사전-감속 수식)를 정책 예측으로 완전히 대체한 것이다.

## 1. 알려진 데이터 설계 결함 (검증 중 발견, 정직하게 기록)

학습 데이터의 관찰 15차원 중 `a_progress`/`b_progress` 두 차원은 실제로는 "손이 얼마나 왔는가"가 아니라 **단순 시간 신호** `ease(t_frac)`을 양쪽에 그대로 복제한 값이었다(`generate_procedural_curl_dataset_stage1_75.py`의 설계 실수). 장애물 감속이 걸려 실제 손목 위치가 시간 신호보다 뒤처질 때도 정책은 "시간이 얼마나 지났는지"만 볼 뿐 "손이 실제로 어디 있는지"는 보지 못한다. 이번 폐루프 평가는 학습 분포와의 일관성을 위해 추론 때도 동일하게 `ease(t_frac)`을 그대로 사용했다 — 즉 이 결함을 고치지 않고 그대로 둔 채 측정했으며, 아래 결과 해석에 영향을 준다(§4 참고).

## 2. 결과 — 서브 스윕별로 극명하게 갈렸다

| 서브 스윕 | 홀드아웃 수 | 폐루프 게이트 통과 | 비고 |
|---|---|---|---|
| `stage1_approach`(접근 거리·속도) | 5 | **4/5** | 대부분 전문가와 동일하게 침투 0 재현 |
| `A_lateral_height`(좌우/상하 오프셋) | 4 | **0/4** | 전부 실패(침투비 0.08~0.12) |
| `B_obstacle`(장애물) | 2 | **1/2** | |
| **합계** | **11** | **5/11 (45%)** | |

- 오프라인 L1 행동 오차: **0.393**(행동값 범위 0~1 기준으로 상당히 크다 — 청크 예측이 꽤 부정확하다는 뜻).
- 학습 loss는 0.036까지 정상적으로 수렴했는데도(발산·과적합 징후 없음) 홀드아웃 폐루프에서는 절반 넘게 실패했다 — **loss가 낮다고 안전을 보장하지 않는다**는 걸 이번 검증이 직접 보여준다.

### 왜 서브 스윕마다 이렇게 다른가

`stage1_approach`(45개 중 24개 통과, 학습에 20개 사용)는 상대적으로 데이터가 많고 성공/실패 경계가 [[2026-08-20-moojoco-lerobot-stage1-5-dataset-result]]에서 확인했듯 비교적 단순(접근 깊이·속도에 대해 매끄럽게 변함)해서 정책이 잘 일반화했다. 반면 `A_lateral_height`는 같은 논문에서 **비단조적**(중간 오프셋이 제일 위험, 큰 오프셋은 오히려 안전)이라고 이미 밝혀진 함수인데, 학습에 쓴 예시가 14개뿐이라 이 비단조성을 배우기엔 턱없이 부족했던 것으로 보인다 — 홀드아웃 4개 전부 실패한 것이 이를 뒷받침한다.

## 3. 산출물

- 검증용 재학습 체크포인트: `data/lerobot_stage2_act_policy_holdout/checkpoint/`(홀드아웃 11개 제외하고 학습 — Stage 3에 그대로 쓰지 않는다, §4 참고).
- 원본 학습 체크포인트(48개 전부 사용): `data/lerobot_stage2_act_policy/checkpoint/`.
- 검증 리포트: `data/lerobot_stage2_act_policy_holdout/validation_report.json`(에피소드별 전문가 vs 정책 침투비 전부 포함).

## 4. 결론 및 다음 단계 제안

**현재 정책을 그대로 Stage 3(실시간 통합)에 넘기면 안 된다** — 좌우/상하 오프셋이 조금이라도 있는 상황에서 절반 이상 실패하는 정책을 실제 배치할 순 없다. 원인으로 보이는 두 가지를 다음 단계에서 먼저 손봐야 한다고 제안한다:

1. `a_progress`/`b_progress` 관찰 결함 수정 — 시간 신호 대신 실제 손목 진행률(`approach_state`)을 관찰에 넣어 정책이 자기 위치를 실제로 알 수 있게 한다.
2. `A_lateral_height` 데이터 부족 — 이 축의 스윕 해상도를 높이거나(현재 5×5=25개), 비단조 경계 근방을 더 촘촘히 재수집해야 한다.

두 가지를 반영해 데이터를 다시 만들고(Stage 1.5 재실행에 해당) 재학습하는 걸 다음 단계로 제안한다. 사령관 판단을 구한다.
"""

payload = {
    "slug": "2026-08-20-moojoco-lerobot-stage2-holdout-validation",
    "title": "LeRobot Phase 2 Stage 2 검증 — 홀드아웃 폐루프 재실행 결과",
    "author": "Moojoco",
    "abstract": (
        "48개 게이트-통과 궤적 전부로 학습한 ACT 정책은 loss 0.030까지 수렴했지만, 이는 학습에 쓴 궤적을 "
        "얼마나 잘 재현하는지만 보여줄 뿐이었다. 세 서브 스윕에서 층화 추출한 11개 에피소드를 완전히 "
        "학습에서 제외하고 37개로 재학습한 뒤, 홀드아웃에 대해 학습된 정책의 예측 행동으로 MuJoCo 물리를 "
        "다시 실행하는 폐루프 검증을 수행했다. 결과: 접근 거리·속도 서브 스윕은 5개 중 4개가 전문가와 동일하게 "
        "침투 0을 재현했지만, 좌우/상하 오프셋 서브 스윕은 4개 전부 실패(침투비 0.08~0.12)했다 — 이 축이 "
        "이미 비단조적(중간 오프셋이 가장 위험)이라고 밝혀진 함수인데 학습 데이터가 14개뿐이라 일반화에 "
        "실패한 것으로 보인다. 전체 홀드아웃 통과율은 5/11(45%)이며, 학습 loss가 정상적으로 수렴했음에도 "
        "절반 넘게 실패해 loss만으로는 안전성을 보장할 수 없음을 확인했다. 현재 정책을 그대로 Stage 3에 "
        "넘기지 말 것과, 관찰 설계 결함 수정 및 오프셋 데이터 보강을 먼저 할 것을 제안한다."
    ),
    "tags": ["handshake-robot", "result", "moojoco", "mujoco", "lerobot", "verification"],
    "changelog": "v1.0 — 최초 제출: 홀드아웃 폐루프 검증(5/11 통과), 관찰 설계 결함 발견, 다음 단계 제안",
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
