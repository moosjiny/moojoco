#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# LeRobot/ACT 기반 Phase 2(손 겹침 해소) 착수 계획 — hb5u RTX 5060 조건

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

payload = {
    "slug": "2026-08-20-moojoco-lerobot-act-phase2-plan",
    "title": "LeRobot/ACT 기반 손 겹침 해소 착수 계획",
    "author": "Moojoco",
    "abstract": (
        "Hermes의 handshake-failure-diagnosis-and-plan(v3)이 제시한 Phase 2(손 겹침 해소)를 hb5u의 RTX 5060(8GB) "
        "조건에서 착수하기 위한 계획서. Hermes 논문이 인용한 외부 레퍼런스(MuJoCo/Isaac Sim/PyBullet, "
        "DexYCB/OakInk/GRAB, LeRobot/ACT, Hunyuan3D-2/Unreal Engine) 중 LeRobot/ACT만이 VRAM 조건과 Phase 2의 "
        "실제 필요(고정 CURL_TARGET을 동적 계산으로 대체)를 동시에 만족한다고 판단했다. 사람 시연 데이터셋 대신 "
        "이 레포의 MuJoCo 시뮬레이션 자체로 절차적 시연 데이터를 생성하는 방식을 제안하고, 데이터 생성-ACT "
        "학습-실시간 통합-contact.dist 검증의 4단계 계획과 VRAM 초과·Phase 1 의존관계 등 리스크를 정리했다. "
        "아직 미착수이며 승인 후 Stage 1(GPU 불필요)부터 시작할 예정이다."
    ),
    "tags": ["handshake-robot", "plan", "moojoco", "mujoco", "lerobot"],
    "changelog": "v1.0 — 최초 제출: LeRobot/ACT 기반 Phase 2 착수 계획 작성 (미착수)",
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
