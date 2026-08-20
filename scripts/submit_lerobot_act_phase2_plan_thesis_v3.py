#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

# v3: GET /api/papers/2026-08-20-moojoco-lerobot-act-phase2-plan 확인 결과
# version "2"가 여전히 is_latest=true였음 — append로 진행. v1/v2 본문은
# 한 글자도 고치지 않고 그대로 재사용.
V2_SECTION_MD = """# v2 추가 — Stage 1 실측 결과 + Stage 1.5 신설(기하 다양성·장애물)

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 "stage 1 을 시작해줘"로 Stage 1을 구현·실행([[2026-08-20-moojoco-lerobot-stage1-dataset-result]])한 뒤, 결과를 "실패 궤적은 걸러내고 학습하자"고 확정하는 과정에서 사령관이 두 가지 질문을 던졌다: "지금은 XY 위치가 안 바뀌는데, 바뀐다면 성공/실패가 달라지지 않을까?"와 "두 로봇 사이에 개울 같은 장애물이 있어서 더 접근 못 하면 어떻게 하지?" 두 질문 모두 지금 데이터셋이 표현하지 못하는 실제 결함을 정확히 짚어, 원래 4단계 계획 사이에 **Stage 1.5**를 신설하기로 했다.
**일자**: 2026-08-20 (v2 추가, 원문은 아래 v1 그대로 보존)
**분류**: `handshake-robot`, `plan`, `moojoco`, `mujoco`, `lerobot`, `revision`

---

## v2-1. Stage 1 실측 요약

`scripts/generate_procedural_curl_dataset.py`로 접근 거리·속도 45가지를 스윕, GPU 없이 4.84초 만에 (관찰 12차원/행동 10차원) Parquet 데이터셋 생성. **45개 중 24개만 5% 침투 게이트 통과** — 기존 사전-감속 제어기가 baseline 기하 하나에만 맞춰져 있었다는 것을 정량 확인했다. 상세: [[2026-08-20-moojoco-lerobot-stage1-dataset-result]].

## v2-2. 필터링 방침 확정

Stage 2 학습은 **성공(24개) 궤적의 행동만 모방학습(BC) 대상으로 쓴다.** 단, 실패(21개) 궤적을 완전히 버리지는 않는다 — 그 관찰(어떤 근접도 조합에서 위험했는지)은 별도로 "위험 경계" 이진 분류기(또는 안전 마진 예측기)의 학습 신호로 재사용한다. 즉 실패 궤적의 *행동*은 정답으로 쓰지 않지만, 그 *관찰*은 여전히 유용하다는 것이 이번 논의의 결론이다.

## v2-3. 사령관 질문 1 — XY 위치가 바뀐다면?

정확한 지적이다. `urdf/amazinghand_5finger_docking.xml`의 `handA/B_approach` 관절은 **Y축(전후) 1-DOF 슬라이드뿐**이라, Stage 1 스윕은 "얼마나 깊이/빨리 다가오는가"만 바꿨을 뿐 "옆으로 어긋나거나 손 높이가 다르게 다가오면"은 물리적으로 표현할 수조차 없었다. 좌우(X)·상하(Z) 오프셋이 생기면 어떤 손가락 쌍이 먼저 접촉하는지가 달라지므로 성공/실패 경계도 당연히 달라진다 — 이건 관찰 차원을 늘리는 문제가 아니라 **MJCF 자체에 자유도를 추가**해야 하는 문제다.

## v2-4. 사령관 질문 2 — 장애물(개울)로 더 접근 못 하면?

이 질문은 Stage 1의 관찰/행동 설계가 애초에 답할 수 없는 다른 층위의 문제라는 걸 드러냈다: 지금 정책은 "손이 이만큼 다가왔을 때 손가락을 얼마나 오므려도 안전한가"만 배우고, "손이 얼마나 다가갈 수 있는가"(`a_end`/`b_end`)는 에피소드마다 내가 고정해서 준 값이다. 장애물로 인한 접근 한계는 손가락 curl 정책의 책임 범위 밖 — 팔/손목이 "여기가 한계"임을 감지해 접근 자체를 멈추는 상위 레벨의 문제다. 다루려면 MJCF에 장애물 geom을 추가하고, `mj_geomDistance`로 손-장애물 거리를 관찰에 포함시켜, 정책이 "더 이상 못 감"을 인지한 상태에서도 그 자리에서 안전하게 손가락만 오므리도록 설계해야 한다.

## v2-5. Stage 1.5 신설 — 개정된 단계 구성

```
Stage 1   (완료) 접근 거리·속도 스윕 — 45 에피소드, 24/45 게이트 통과
Stage 1.5 (신규) 기하 다양성 + 장애물 확장
Stage 2         LeRobot 환경 세팅 + ACT 학습 (성공 궤적 BC + 실패 궤적 안전분류기)
Stage 3         실시간 통합
Stage 4         contact.dist 재검증 (+ 가능하면 Aegis 교차검증)
```

**Stage 1.5 세부 계획**:
1. `amazinghand_5finger_docking.xml`에 `handA/B_approach`와 별개로 X(좌우)·Z(상하) slide 자유도를 추가(최소 한쪽 손 기준 상대 오프셋으로 충분 — 두 손 다 움직일 필요는 없음).
2. 관찰에 `x_offset_progress`, `z_offset_progress` 추가.
3. 두 손 사이에 정적 장애물 geom(박스 또는 캡슐)을 선택적으로 배치하는 실험 변형을 추가하고, 손-장애물 최단거리(`mj_geomDistance`)를 관찰에 포함.
4. 스윕 그리드에 X/Z 오프셋과 장애물 유무·위치를 추가해 Stage 1 대비 더 넓은 조건에서 성공/실패 경계를 재수집.

Stage 1.5는 아직 미착수 — 사령관 승인 후 착수한다.
"""

V1_ORIGINAL_BODY_MD = """# LeRobot/ACT 기반 Phase 2(손 겹침 해소) 착수 계획 — hb5u RTX 5060 조건

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-hermes-handshake-failure-diagnosis-and-plan]](v3)이 제시한 4단계 로드맵 중 **Phase 2(관통 해소)** 는 [[2026-08-19-eros-handshake-agent-division-plan]]에서 이미 Moojoco+Aegis 담당으로 배정돼 있다. 사령관이 "hb5u의 RTX 5060 GPU 조건으로 외부 레퍼런스 중 뭘 해볼 수 있나"고 물어, Hermes 논문이 인용한 외부 자료(MuJoCo/Isaac Sim/PyBullet, DexYCB/OakInk/GRAB, LeRobot/ACT, Hunyuan3D-2/Unreal Engine) 중 **LeRobot/ACT**가 hb5u 조건에 가장 적합하다고 판단해 착수 계획을 정리한다. **아직 미착수 — 계획서만 제출, 구현은 승인 후 진행.**
**일자**: 2026-08-20
**분류**: `handshake-robot`, `plan`, `moojoco`, `mujoco`, `lerobot`

---

## 0. 왜 LeRobot/ACT인가 — 다른 외부 레퍼런스와의 비교

Hermes 논문 §8은 각 외부 자료가 "이 레포에서 직접 실측·재현하지 않은 참고자료"임을 명시하고, 통합 전 재현·측정을 요구한다. hb5u의 하드웨어 조건(RTX 5060, VRAM 8GB, CUDA 13.2)에서 후보를 다시 평가하면:

| 후보 | VRAM 적합성 | Phase 2와의 직접 관련성 |
|---|---|---|
| **LeRobot/ACT** | 소규모 ACT 트랜스포머는 배치사이즈를 줄이면 8GB로 충분 | **직접적** — `CURL_TARGET`을 고정값 대신 학습 기반으로 동적 계산하는 것이 Phase 2의 핵심 제안 |
| Isaac Sim/Isaac Lab | NVIDIA 권장 최소사양 경계선(8GB) — RTX/GPU PhysX를 켜면 불안정 위험 | 간접적 (§8-1의 RL 궤적 적응 사례 참고용) |
| Hunyuan3D-2 | mini 체크포인트면 가능하나 물리 정확성과 무관 | 없음 — 마케팅 목업 전용, 문서가 스스로 "정확성 증거 아님"이라 명시 |
| Unreal Engine | 렌더링 자체는 문제없음 | 없음 — 동일하게 물리 검증 도구 아님 |

**결론**: LeRobot/ACT만이 VRAM 조건과 Phase 2의 실제 필요를 동시에 만족한다. `CLAUDE.md`의 기존 후보("LeRobot 데이터 연동, 10 에피소드 omx_follower")와도 방향이 겹쳐 별도 트랙을 새로 여는 게 아니라 기존 관심사를 Phase 2에 접목하는 것이다.

## 1. 목표

`mujoco_bridge_server.py`(또는 손가락 접촉 검증용 신규 MJCF)에서, 두 손의 `CURL_TARGET`(현재 고정값)을 **두 손 사이의 실제 기하학적 여유공간에 따라 동적으로 예측하는 소규모 정책**으로 대체한다. 성공 기준은 Hermes 논문이 요구한 것과 동일: `contact.dist` 실측 재현 시 침투량이 캡슐 반경의 5% 이내.

## 2. 학습 데이터 — 사람 시연이 아니라 이 레포의 물리 시뮬레이션에서 생성

DexYCB/OakInk/GRAB은 사람 손-사물 상호작용 데이터셋이라 이 프로젝트의 "두 로봇 손 사이 접촉" 시나리오와 형태가 다르다. 대신, **이 레포의 MuJoCo 시뮬레이션 자체를 데이터 생성기로 쓴다**:

1. 두 손의 상대 위치·자세를 다양하게(거리, 각도, 접근 속도) 스윕하며 시뮬레이션 실행.
2. 각 스윕마다 `CURL_TARGET`을 이분탐색/그리드서치로 조정해, `contact.dist`가 안전 범위(캡슐 반경의 5% 이내) 안에 들어가는 **"성공한" 목표각**을 탐색·기록.
3. (두 손 상대 자세, 접근 속도) → (안전한 CURL_TARGET) 쌍을 궤적 데이터셋으로 축적 — 사람 시연 대신 **물리 기반 절차적 시연(procedural demonstration)**.

이 방식은 사람 데이터셋 없이도 착수 가능하고, 학습 대상 자체가 이 레포의 실제 기하학과 정확히 일치한다는 장점이 있다.

## 3. 단계별 계획

- **Stage 1 — 데이터 생성 스크립트** (`scripts/`): 위 2절의 스윕+이분탐색을 자동화, 결과를 LeRobot 호환 포맷(에피소드별 parquet/궤적)으로 저장. GPU 불필요(MuJoCo는 CPU 물리).
- **Stage 2 — LeRobot 환경 세팅 + ACT 학습**: `lerobot` 패키지 설치(venv `dual_arms`), Stage 1 데이터로 소규모 ACT 정책 학습. hb5u RTX 5060에서 배치사이즈/모델 크기를 8GB에 맞게 조정, 학습 시간·VRAM 실측 기록.
- **Stage 3 — 실시간 통합**: 학습된 정책을 `mujoco_bridge_server.py` 또는 프론트엔드에 실시간 추론기로 연결, 슬라이더 대신(또는 슬라이더와 병행) 정책이 `CURL_TARGET`을 예측하도록 배선.
- **Stage 4 — 검증**: Hermes 논문의 검증 게이트 그대로 적용 — `contact.dist` 재측정, 가능하면 Aegis의 독립 재현까지 받아 교차검증.

각 스테이지는 기존 방식대로 소단위 실측 후 thesis 기록, 사령관 확인 후 다음 단계 진행.

## 4. 리스크

- **VRAM 초과**: ACT 모델/배치사이즈가 예상보다 크면 8GB를 넘을 수 있음 — Stage 2에서 가장 먼저 실측해 조기에 확인.
- **절차적 시연의 편향**: 이분탐색으로 찾은 "성공 CURL_TARGET"이 그리드서치 해상도에 따라 편향될 수 있음 — Stage 1 산출물의 커버리지를 별도로 점검.
- **Phase 1(손가락 DOF)과의 의존관계**: 현재 손가락은 1-DOF(`Finger Grip` 단일값)라 `CURL_TARGET`의 의미 자체가 제한적 — Phase 1이 먼저 진행돼 자유도가 늘면 Stage 1 데이터 생성도 그에 맞춰 다시 설계해야 할 수 있음. Phase 1과 순서를 사령관과 조율 필요.

## 5. 다음 단계

계획 승인 시 Stage 1(데이터 생성 스크립트, GPU 불필요)부터 착수. Phase 1(손가락 DOF)이 아직 미착수 상태이므로, 사령관 판단에 따라 Phase 1을 먼저 진행한 뒤 이 계획에 착수하는 순서도 고려 가능하다.
"""

NEW_SECTION_MD = """# v3 추가 — Stage 2 정책 범위를 손목 접근까지 확장, 그리고 그 전에 필요한 재작업

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-20-moojoco-lerobot-stage1-5-dataset-result]]에서 장애물이 있으면 손가락 curl 정책만으로는 절대 해결 안 된다는 게 실측으로 드러난 뒤, "Stage 2 정책 범위를 (a) 손가락 curl만 (b) 손목 접근까지 포함" 중 어느 쪽으로 할지 물었고, 사령관이 "**손목접근까지**"로 답했다.
**일자**: 2026-08-20 (v3 추가, v1/v2 원문은 아래 그대로 보존)
**분류**: `handshake-robot`, `plan`, `moojoco`, `mujoco`, `lerobot`, `revision`

---

## v3-1. 결정과 그 함의

Stage 2 정책의 행동(action) 공간이 지금까지의 "손가락 curl 사용비율 10차원"에서 **손목 접근 목표(handA/B_approach, handB_lateral, handB_height)까지 포함하는 더 큰 공간**으로 확장된다. 관찰(observation)은 이미 Stage 1.5에서 `handB_lateral_offset_m`/`handB_height_offset_m`/`obstacle_proximity_m`을 포함해 15차원으로 확장해뒀으므로 그대로 재사용 가능하다 — 바뀌는 건 행동 쪽이다.

## v3-2. 문제 — 지금까지의 데이터셋은 이 결정에 답할 수 없다

Stage 1/1.5는 손목 접근 목표(`a_end`/`b_end`/`lateral_offset`/`height_offset`)를 에피소드마다 **내가 고정해서 준 스윕 파라미터**로 다뤘다. 정책이 그것까지 예측해야 한다면, 데이터셋에는 "이 상황에서 손목이 어디로/얼마나 빨리 움직여야 안전한가"에 대한 **정답 행동**이 있어야 하는데, 지금까지 그건 애초에 기록조차 하지 않았다(고정 입력이었으니까). 특히 장애물이 있는 경우, 지금 손목 컨트롤러(`kp_wrist`로 고정 목표를 그냥 밀어붙임)는 "정답 행동"이 될 수 없다 — [[2026-08-20-moojoco-lerobot-stage1-5-dataset-result]] §2에서 봤듯 그 컨트롤러 자체가 장애물 앞에서 파국적으로 실패하는 바로 그 대상이다.

## v3-3. 필요한 선행 작업 — 장애물 인지형 손목 접근 "전문가"

Stage 2 학습을 시작하려면, 먼저 **장애물 근접도(`obstacle_proximity_m`)를 실제로 보고 반응하는 손목 접근 컨트롤러**를 새로 만들어야 한다 — 손가락 curl에 이미 있는 "상대 손과의 거리 기반 사전-감속" 패턴을 손목 접근에도 그대로 적용하면 된다: 장애물까지 남은 거리가 `SLOW_START_DIST` 이내로 들어오면 접근 속도를 거리에 비례해 줄이고, 0에 가까워지면 접근을 멈춘다. 이 컨트롤러로 손목+손가락을 함께 구동해 데이터를 다시 생성해야, 비로소 "손목까지 포함한 정답 행동"을 가진 데이터셋이 나온다.

## v3-4. 개정된 단계 구성

```
Stage 1    (완료) 접근 거리·속도 스윕
Stage 1.5  (완료) 좌우/상하 오프셋 + 장애물 관찰 추가
Stage 1.75 (신규) 장애물 인지형 손목 접근 전문가 컨트롤러 설계
                  + 손목·손가락 통합 행동으로 데이터셋 재생성
Stage 2           LeRobot 환경 세팅 + ACT 학습 (확장된 행동 공간)
Stage 3           실시간 통합
Stage 4           contact.dist 재검증
```

Stage 1.75는 아직 미착수 — 착수 여부를 사령관에게 확인한다.
"""

BODY_MD = (
    NEW_SECTION_MD
    + "\n---\n\n"
    + V2_SECTION_MD
    + "\n---\n\n# v1 원문 (아래부터, 참고용으로 보존 — 이후 진행 방향은 위 v2/v3를 따를 것)\n\n"
    + V1_ORIGINAL_BODY_MD
)

payload = {
    "slug": "2026-08-20-moojoco-lerobot-act-phase2-plan",
    "title": "LeRobot/ACT 기반 손 겹침 해소 착수 계획",
    "author": "Moojoco",
    "abstract": (
        "[v3 추가] Stage 1.5에서 장애물이 손가락 curl 정책만으로는 해결 불가능함을 확인한 뒤, 사령관이 Stage 2 "
        "정책 범위를 손목 접근 목표까지 포함하도록 확장하기로 결정했다('손목접근까지'). 이 결정에 따라 기존 "
        "Stage 1/1.5 데이터셋은 손목 접근을 고정 스윕 파라미터로만 다뤘을 뿐 정답 행동으로 기록하지 않았다는 "
        "것이 드러나, Stage 2 착수 전 장애물 근접도 기반으로 스스로 감속·정지하는 손목 접근 '전문가' 컨트롤러를 "
        "새로 설계하고 그것으로 손목+손가락 통합 행동 데이터셋을 재생성하는 Stage 1.75를 신설했다. Stage 1.75는 "
        "아직 미착수이며 착수 여부를 사령관에게 확인한다."
    ),
    "tags": ["handshake-robot", "plan", "moojoco", "mujoco", "lerobot", "revision"],
    "changelog": (
        "v3.0 — 추가: Stage 2 정책 범위를 손목 접근까지 확장하는 사령관 결정 기록, 이에 따라 필요한 "
        "장애물 인지형 손목 접근 전문가 컨트롤러 + 데이터셋 재생성을 Stage 1.75로 신설. "
        "v1/v2 원문은 아래에 그대로 보존."
    ),
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
