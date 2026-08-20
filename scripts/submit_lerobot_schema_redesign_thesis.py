#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT Phase 2 — 관찰-행동 항등함수 지름길을 없애는 데이터 스키마 재설계

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 "데이터 스키마부터 재설계해줘." [[2026-08-20-moojoco-lerobot-stage4-stress-test]] v2에서 Aegis 독립 재현으로 확인된 근본 원인(관찰의 a/b_progress가 그 프레임 행동과 항상 같은 값이라 정책이 항등함수 지름길을 배움)을 데이터 생성 단계에서 고친다.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`

---

## 0. 무엇이 문제였나 (요약)

[[2026-08-20-moojoco-lerobot-stage3-live-integration]] v2/[[2026-08-20-moojoco-lerobot-stage4-stress-test]]에서, 학습 데이터의 모든 프레임이 `observation.state[0:2]`(a/b_progress)와 `action[0:2]`(손목 접근 사용비율)에 **정확히 같은 값**(둘 다 컨트롤러 내부 변수 `approach_state`)을 기록하고 있었다는 게 드러났다. 정책이 "관찰이 x면 행동도 x"라는 항등함수에 가까운 지름길을 학습했고, 실시간 추론에서 관찰을 정책 자신의 예측(또는 심지어 실제 물리 위치)으로 되먹이면 시작값 0에서 영원히 못 벗어나는 고정점에 갇혔다.

## 1. 재설계 — 관찰과 행동을 값이 절대 같을 수 없는 두 계열로 분리

`generate_procedural_curl_dataset_stage1_75.py`의 관찰 구성을 바꿨다. 기존 15차원(`a_progress, b_progress` + 나머지 13)을 16차원으로:

```
[elapsed_time_frac, handA_qpos_frac, handB_qpos_frac]
  + 손가락별(양손×5) 근접도 10
  + [lateral_offset, height_offset, obstacle_proximity]
```

- **`elapsed_time_frac`**: `ease(t_frac)` — 정책의 출력이나 물리 상태 어느 쪽과도 무관하게 항상 전진하는 순수 시계 신호. 어떤 상황에서도 고정점에 갇히지 않도록 보장하는, 유일하게 "외부에서 강제로 주입되는" 신호다.
- **`handA/B_qpos_frac`**: 그 프레임의 물리 스텝이 끝난 뒤 **실측한** 손목 `qpos`를 목표 구간 대비 비율로 환산한 값 — 실제 로봇의 인코더 값에 해당한다. `action`(그 프레임에 사용한 목표 `approach_state`)과는 인과관계가 다르다: PD 추종이 지연되거나 장애물 감속이 걸리면 이 값이 목표보다 뒤처지므로, 더 이상 행동의 복제값이 아니라 "목표를 실제로 얼마나 따라잡았는가"라는 새로운 정보를 준다.

행동(12차원, `handA/B_approach_use_frac` + 손가락 curl 10차원)은 바꾸지 않았다 — 여전히 컨트롤러가 그 프레임에 실제로 내린 결정을 그대로 기록한다.

## 2. 재생성 — 물리·통과율은 그대로, 스키마만 바뀌었다는 걸 재확인

컨트롤러(무엇을 얼마나 움직이는가)는 손대지 않고 무엇을 **기록**하는지만 바꿨으므로, 통합 데이터셋을 재생성해도 침투율·게이트 통과 여부는 전혀 달라지지 않아야 한다고 예상했고, 실측으로 확인했다:

| 서브 스윕 | 에피소드 | 게이트 통과 |
|---|---|---|
| `stage1_approach` | 45 | 24 (재설계 전과 동일) |
| `A_lateral_height` | 81 | 50 (재설계 전과 동일) |
| `B_obstacle` | 6 | 6 (재설계 전과 동일) |
| **합계** | **132** | **80** |

관찰 벡터 차원만 15→16으로 늘었다(1.2MB, GPU 없이 20.7초). 프레임 0의 값도 확인했다: `observation.state[0:3] = [0.0, 0.0, 0.0]`(elapsed_time/두 qpos 비율 전부 시작점), `action[0:2] = [0.0, 0.0]` — 시작 순간엔 우연히 같지만, 에피소드가 진행되며 목표(action)와 실측(observation)이 갈라지는 게 바로 이번 재설계의 목적이다.

## 3. 다음 단계

스키마 재설계는 데이터 생성 단계까지만 끝났다 — 아직 재학습·재검증 전이다. 다음 순서로 제안한다:
1. 새 16차원 스키마로 생산용 체크포인트 재학습.
2. Stage 2 방식(홀드아웃 폐루프)과 Stage 4 방식(다중 시드 스트레스 테스트) 둘 다로 재검증 — 이번엔 처음부터 여러 시드로 돌려 [[2026-08-20-moojoco-lerobot-stage4-stress-test]]의 "단일 시드 낙관값" 실수를 반복하지 않는다.
3. Aegis에게 다시 독립 재현 요청.

사령관 확인 후 재학습으로 진행한다.
"""

payload = {
    "slug": "2026-08-20-moojoco-lerobot-schema-redesign",
    "title": "LeRobot Phase 2 — 항등함수 지름길을 없애는 관찰 스키마 재설계",
    "author": "Moojoco",
    "abstract": (
        "Stage 4 스트레스 테스트에서 발견되고 Aegis 독립 재현으로 확인된 근본 원인 — 학습 데이터의 모든 "
        "프레임에서 관찰(a/b_progress)이 그 프레임 행동과 정확히 같은 값이라 정책이 항등함수 지름길을 "
        "학습한 문제 — 을 데이터 스키마 차원에서 고쳤다. 관찰을 정책 출력과 무관하게 항상 전진하는 시계 "
        "신호와, 행동과 인과관계가 다른 실측 qpos 기반 위치 비율 두 가지로 재설계해 관찰과 행동이 더 이상 "
        "같은 값일 수 없게 만들었다. 컨트롤러 자체는 바꾸지 않았으므로 재생성한 132개 에피소드의 물리·게이트 "
        "통과율(80/132)이 재설계 전과 완전히 동일함을 확인해 스키마만 바뀌었다는 걸 검증했다. 재학습·재검증은 "
        "다음 단계로 남겨뒀다."
    ),
    "tags": ["handshake-robot", "result", "moojoco", "mujoco", "lerobot"],
    "changelog": "v1.0 — 최초 제출: 관찰 스키마 16차원 재설계(항등함수 지름길 제거), 데이터 재생성 및 물리 불변성 확인",
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
