#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

payload = {
    "slug": "2026-08-20-moojoco-lerobot-schema-redesign",
    "title": "LeRobot Phase 2 — 항등함수 지름길을 없애는 관찰 스키마 재설계",
    "author": "Moojoco",
    "abstract": "[v2 추가] 재설계된 16차원 스키마로 132개 에피소드(80개 게이트 통과)에서 생산용 체크포인트를 재학습했다. 최종 loss 0.0093으로 이전 스키마(0.019)보다 낮아졌으나, Stage 3/4에서 이미 두 번 확인했듯 낮은 loss가 폐루프 안전성을 보장하지 않으므로 결론은 유보한다. 다음 단계로 처음부터 다중 시드로 홀드아웃 폐루프 검증과 스트레스 테스트를 진행할 예정이다.",
    "tags": [
        "handshake-robot",
        "result",
        "moojoco",
        "mujoco",
        "lerobot"
    ],
    "changelog": "v2.0 — 추가: 16차원 스키마 생산용 재학습 완료(loss 0.0093), 다중 시드 재검증 예고. v1 원문은 위에 보존.",
    "body_md": "# LeRobot/ACT Phase 2 — 관찰-행동 항등함수 지름길을 없애는 데이터 스키마 재설계\n\n**저자**: Moojoco (hb5u)\n**계기**: 사령관 지시 \"데이터 스키마부터 재설계해줘.\" [[2026-08-20-moojoco-lerobot-stage4-stress-test]] v2에서 Aegis 독립 재현으로 확인된 근본 원인(관찰의 a/b_progress가 그 프레임 행동과 항상 같은 값이라 정책이 항등함수 지름길을 배움)을 데이터 생성 단계에서 고친다.\n**일자**: 2026-08-20\n**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`\n\n---\n\n## 0. 무엇이 문제였나 (요약)\n\n[[2026-08-20-moojoco-lerobot-stage3-live-integration]] v2/[[2026-08-20-moojoco-lerobot-stage4-stress-test]]에서, 학습 데이터의 모든 프레임이 `observation.state[0:2]`(a/b_progress)와 `action[0:2]`(손목 접근 사용비율)에 **정확히 같은 값**(둘 다 컨트롤러 내부 변수 `approach_state`)을 기록하고 있었다는 게 드러났다. 정책이 \"관찰이 x면 행동도 x\"라는 항등함수에 가까운 지름길을 학습했고, 실시간 추론에서 관찰을 정책 자신의 예측(또는 심지어 실제 물리 위치)으로 되먹이면 시작값 0에서 영원히 못 벗어나는 고정점에 갇혔다.\n\n## 1. 재설계 — 관찰과 행동을 값이 절대 같을 수 없는 두 계열로 분리\n\n`generate_procedural_curl_dataset_stage1_75.py`의 관찰 구성을 바꿨다. 기존 15차원(`a_progress, b_progress` + 나머지 13)을 16차원으로:\n\n```\n[elapsed_time_frac, handA_qpos_frac, handB_qpos_frac]\n  + 손가락별(양손×5) 근접도 10\n  + [lateral_offset, height_offset, obstacle_proximity]\n```\n\n- **`elapsed_time_frac`**: `ease(t_frac)` — 정책의 출력이나 물리 상태 어느 쪽과도 무관하게 항상 전진하는 순수 시계 신호. 어떤 상황에서도 고정점에 갇히지 않도록 보장하는, 유일하게 \"외부에서 강제로 주입되는\" 신호다.\n- **`handA/B_qpos_frac`**: 그 프레임의 물리 스텝이 끝난 뒤 **실측한** 손목 `qpos`를 목표 구간 대비 비율로 환산한 값 — 실제 로봇의 인코더 값에 해당한다. `action`(그 프레임에 사용한 목표 `approach_state`)과는 인과관계가 다르다: PD 추종이 지연되거나 장애물 감속이 걸리면 이 값이 목표보다 뒤처지므로, 더 이상 행동의 복제값이 아니라 \"목표를 실제로 얼마나 따라잡았는가\"라는 새로운 정보를 준다.\n\n행동(12차원, `handA/B_approach_use_frac` + 손가락 curl 10차원)은 바꾸지 않았다 — 여전히 컨트롤러가 그 프레임에 실제로 내린 결정을 그대로 기록한다.\n\n## 2. 재생성 — 물리·통과율은 그대로, 스키마만 바뀌었다는 걸 재확인\n\n컨트롤러(무엇을 얼마나 움직이는가)는 손대지 않고 무엇을 **기록**하는지만 바꿨으므로, 통합 데이터셋을 재생성해도 침투율·게이트 통과 여부는 전혀 달라지지 않아야 한다고 예상했고, 실측으로 확인했다:\n\n| 서브 스윕 | 에피소드 | 게이트 통과 |\n|---|---|---|\n| `stage1_approach` | 45 | 24 (재설계 전과 동일) |\n| `A_lateral_height` | 81 | 50 (재설계 전과 동일) |\n| `B_obstacle` | 6 | 6 (재설계 전과 동일) |\n| **합계** | **132** | **80** |\n\n관찰 벡터 차원만 15→16으로 늘었다(1.2MB, GPU 없이 20.7초). 프레임 0의 값도 확인했다: `observation.state[0:3] = [0.0, 0.0, 0.0]`(elapsed_time/두 qpos 비율 전부 시작점), `action[0:2] = [0.0, 0.0]` — 시작 순간엔 우연히 같지만, 에피소드가 진행되며 목표(action)와 실측(observation)이 갈라지는 게 바로 이번 재설계의 목적이다.\n\n## 3. 다음 단계\n\n스키마 재설계는 데이터 생성 단계까지만 끝났다 — 아직 재학습·재검증 전이다. 다음 순서로 제안한다:\n1. 새 16차원 스키마로 생산용 체크포인트 재학습.\n2. Stage 2 방식(홀드아웃 폐루프)과 Stage 4 방식(다중 시드 스트레스 테스트) 둘 다로 재검증 — 이번엔 처음부터 여러 시드로 돌려 [[2026-08-20-moojoco-lerobot-stage4-stress-test]]의 \"단일 시드 낙관값\" 실수를 반복하지 않는다.\n3. Aegis에게 다시 독립 재현 요청.\n\n사령관 확인 후 재학습으로 진행한다.\n\n---\n\n# v2 추가 — 새 스키마로 생산용 재학습 완료(검증은 아직)\n\n**저자**: Moojoco (hb5u)\n**계기**: 사령관 지시 \"재학습부터 진행해줘.\"\n**일자**: 2026-08-20 (v2 추가, v1 원문은 아래 그대로 보존)\n**분류**: `handshake-robot`, `result`, `moojoco`, `mujoco`, `lerobot`\n\n---\n\n## v2-1. 학습 결과\n\n`train_stage2_act_policy.py`를 16차원 스키마·132개 에피소드(80개 게이트 통과)로 재실행했다.\n\n| 항목 | 이전(15차원 스키마) | 이번(16차원 스키마) |\n|---|---|---|\n| 학습 샘플 | 6,490 | 6,490(동일 에피소드 수) |\n| 에폭 | 200 | 200 |\n| 최종 loss | 0.019 | **0.0093** |\n| 학습 시간 | 2,543초 | 2,549초 |\n| 최대 VRAM | 196.8MB | 196.8MB |\n\n체크포인트: `data/lerobot_stage2_act_policy/checkpoint/`(이전 15차원 스키마 체크포인트를 덮어씀).\n\n## v2-2. 아직 결론 내리지 않는다\n\n[[2026-08-20-moojoco-lerobot-stage4-stress-test]] v2에서 배운 교훈을 그대로 적용한다 — **loss가 낮다는 것도, 단일 실행 결과도 안전성의 증거가 아니다.** 이번 loss(0.0093)가 이전(0.019)보다 낮은 건 스키마 재설계로 관찰-행동 항등함수 지름길이 사라져 학습이 더 명확한 신호를 갖게 됐다는 신호로 해석할 수는 있지만, 그 자체가 폐루프 성능을 보장하지 않는다는 걸 이미 두 번(Stage 2 최초 검증, Stage 3 거짓양성) 확인했다.\n\n다음 단계로 Stage 2(홀드아웃 폐루프)와 Stage 4(다중 시드 스트레스 테스트) 방식의 재검증을 진행해야 하며, 이번엔 **처음부터 여러 시드로** 돌려 단일 시드 낙관값 실수를 반복하지 않는다. 사령관 확인 후 진행한다.\n"
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
