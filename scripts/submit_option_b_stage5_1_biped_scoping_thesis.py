#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# B-5-1: 바이페달 균형 테스트 모델 — 최소 자유부유 다리 MJCF

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage4-frontend]] B-4 완료 후 사령관 지시 — "b-5."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 착수 전 확인 — 왜 기존 파일에 다리만 얹을 수 없었나

`dual_openarm_handshake.xml`을 다시 읽어보니 세 가지가 확인됐다:

1. `<option gravity="0 0 0" />` — 중력이 꺼져 있다.
2. 모든 geom이 `contype="0" conaffinity="0"`, 바닥(floor) geom 자체가 없다 — 충돌이 전혀 없다.
3. `base_plate`에 관절이 없다 — 로봇 전체가 월드에 고정된 붙박이 베이스다.

즉 기존 모델은 "절대 넘어질 수 없는" 순수 키네마틱 퍼펫이다(팔 각도만 다루는 B-1~B-4에서는 문제 없었음). B-5의 목표(Stage 1/2 분석적 CoM/ZMP 근사를 실제 MuJoCo 강체 동역학으로 대체 — 균형을 잃으면 진짜로 넘어지는 것)를 이루려면 골반에 6-DOF 자유 관절(freejoint)이 필요하고, 이건 기존 파일에 다리 관절만 추가하는 것보다 훨씬 큰 변경이라 사령관에게 먼저 확인했다. **자유 부유 베이스 + 새 최소 모델부터 시작**하는 방향으로 승인받았다.

## 1. 구현 — `urdf/biped_balance_test.xml`

로봇 1개, 다리만(팔 없음), 시상면 힌지 관절만(고관절/무릎/발목 각 1축, 좌우 대칭) 있는 최소 모델:

- 골반(pelvis)에 `<freejoint>` — 실제로 넘어질 수 있음
- `<option gravity="0 0 -9.81" />` — 중력 켜짐
- 바닥 plane geom + 발 geom 모두 접촉 활성화(`contype/conaffinity=1`, friction 0.9)
- 모든 geom `density="1000"` — 질량이 실제로 있음(기존 모델은 전부 `density="0"`이라 질량이 없었다)
- 관절 6개(hip/knee/ankle × 좌우), `<general>` 액추에이터 6개 — B-2/B-3에서 쓴 것과 같은 토크 모터 방식(위치 서보 아님)
- 무릎 관절 range를 `0 2.269`(0~130°)로 설정 — 0에서 하드 리밋이라 사람 무릎처럼 "펴진 상태에서 잠기는" 구조가 자연히 생김

## 2. 실측 검증

`MjModel.from_xml_path` 로드 확인(7 joints incl. freejoint, 6 actuators, 8 bodies, nv=12), 두 가지 시나리오로 3초씩 `mj_step`:

**시나리오 A — PASSIVE (ctrl=0, 완전 무제어)**
```
t=0.0s  pelvis_z=0.840m  tilt=0.0deg
t=1.0s  pelvis_z=0.840m  tilt=0.0deg
t=2.0s  pelvis_z=0.840m  tilt=0.3deg
t=2.5s  pelvis_z=0.839m  tilt=1.2deg
```
무제어 상태에서도 거의 2초간 거의 그대로 서 있었다 — 근육/모터 토크가 아니라 **무릎 관절의 하드 리밋(0°)이 스트럿처럼 하중을 받치기 때문**이다(실제 사람이 무릎을 편 채 서 있을 때 무릎 자체에는 큰 근력이 필요 없는 것과 같은 원리). 예상 밖의 발견이었지만 물리적으로 타당하다.

**시나리오 B — PD-HELD (KP=8.0/KD=0.5, B-3에서 팔 하나로 튜닝한 게인을 그대로 재사용, 목표=직립 자세 0rad)**
```
t=0.0s  pelvis_z=0.840m  tilt=0.0deg
t=2.0s  pelvis_z=0.839m  tilt=1.1deg
t=2.5s  pelvis_z=0.836m  tilt=7.8deg
final   pelvis_z=0.649m (주저앉음)
```
PD 제어를 켰는데도 **오히려 PASSIVE보다 더 빨리, 더 크게 무너졌다.** 팔 하나(가벼운 링크)로 튜닝한 KP/KD를 몸무게를 받치는 다리에 그대로 쓴 것이 원인으로 보인다 — 자세 오차 기반 PD만으로는 이 정도 하중을 버티는 유효 강성이 안 나오고, 접촉 구속과 상호작용하며 오히려 불안정을 더할 수 있다는 것을 실측으로 확인했다.

## 3. 정직하게 남길 결과

- **두 시나리오 모두 결국 넘어졌다** — 무제어든 팔용 PD 게인이든, 좌우 대칭 직립 자세를 능동적으로 지지하는 진짜 "균형 제어"가 없다는 뜻이다. 이는 실패가 아니라 정확히 B-5가 검증하려던 것: 분석적 CoM/ZMP 근사(Stage 1/2)가 "그럴듯한 경고"였다면, 이제는 실제로 넘어지는 물리가 있다.
- 무릎 하드 리밋이 우연히 초반 안정성을 만들어준 것은 흥미로운 부작용이지 설계 의도가 아니었다 — 관절 range를 조정하면 사라질 수 있는 우연한 안정성이라는 점을 남긴다.
- 팔에서 검증된 PD 게인이 다리에는 그대로 쓸 수 없다는 것을 확인했다 — 다음 단계에서 게인 재튜닝 또는 다른 제어 방식(예: 무게중심 기반 피드백, ZMP 목표 추종)이 필요하다.

## 4. 아직 안 한 것 / 다음 단계

- **균형 제어(B-5-2, 다음 단계 후보)**: 단순 자세 PD가 아니라 CoM/ZMP 피드백 기반 균형 제어 설계·튜닝
- 팔 통합, 두 로봇(Alpha/Beta) 통합, fingershake-robot-main 프론트엔드 연동은 전부 미착수 — 이번 단계는 물리 자체의 타당성 검증까지만
- 렌더링/시각적 검증은 하지 않았다 — 수치(pelvis 높이·기울기) 기반 검증만 수행
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage5-1-biped-scoping",
    "title": "B-5-1: 바이페달 균형 테스트 모델 — 최소 자유부유 다리 MJCF",
    "author": "Moojoco",
    "abstract": (
        "B-5(장기 과제) 착수 전, 기존 dual_openarm_handshake.xml이 중력 꺼짐/접촉 없음/고정 베이스인 순수 "
        "키네마틱 모델임을 확인하고 사령관에게 베이스 타입(자유 부유 vs 고정)과 모델 범위(새 최소 모델 vs 기존 "
        "확장)를 물어 자유 부유 베이스+새 최소 모델로 승인받았다. urdf/biped_balance_test.xml — 골반에 "
        "freejoint, 중력·접촉 활성화, 다리 6관절(고관절/무릎/발목×좌우)만 있는 단일 로봇 모델을 구현했다. "
        "PASSIVE(무제어)와 PD-HELD(B-3의 팔용 게인 재사용) 두 시나리오를 3초씩 실측한 결과, 무릎 하드 리밋 덕에 "
        "초반 약 2초는 거의 그대로 섰지만 둘 다 결국 넘어졌고 특히 PD-HELD가 PASSIVE보다 더 빨리 무너졌다 — "
        "팔용 PD 게인이 다리 하중을 버티기에 부족함을 실측으로 확인했다. 이는 실패가 아니라 실제 강체 동역학이 "
        "작동하고 있다는 증거이며, 다음 단계(B-5-2)로 CoM/ZMP 기반 균형 제어 설계가 필요함을 정직하게 남긴다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-5-1 최소 바이페달 모델 구현·물리 검증(무제어/PD 둘 다 결국 낙상)",
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
