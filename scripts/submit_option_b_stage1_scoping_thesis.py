#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B(MuJoCo 백엔드) 착수 — B-1: 기존 인프라 조사 및 세부 단계 계획

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-stage3-option-comparison]]에서 옵션 B를 권고, 사령관이 "B로 시작해줘"라고 승인. 다만 "지금 토큰이 많이 남지 않아서 단계별로 나눠서 thesis에 남기면서 진행해야 한다"는 제약이 있어, 옵션 B 자체를 더 잘게 쪼갠다.
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `plan`

---

## 0. 이 문서의 범위

옵션 B를 통째로 계획하지 않는다. 첫 단계(B-1)는 **구현이 아니라 조사** — 이 머신(hb5u)에 이미 있는 MuJoCo 인프라를 확인해, 이후 단계(B-2 이후)의 비용을 실측 근거로 재산정한다. [[2026-08-12-moojoco-stage3-option-comparison]]에서 "MJCF 모델을 새로 설계해야 한다"고 가정했던 부분이 실제로는 상당 부분 이미 존재한다는 것을 이번 조사로 확인했다 — 원래 비교표의 "초기 비용" 항목을 하향 정정해야 한다.

## 1. 조사 결과

- **`mujoco_sim.service`가 이미 실행 중**이다 (`systemctl is-active` → active). `/home/moos/dev_ws/dual_arms/scripts/sim_dual_arm.py`를 구동하며, MuJoCo EGL GPU 렌더링 + Rerun 스트리밍을 수행한다.
- **MuJoCo 3.7.0**이 `/home/moos/venv/dual_arms`에 이미 설치돼 있다.
- **`urdf/dual_openarm_handshake.xml` — 두 로봇이 악수하는 시나리오의 MJCF 모델이 이미 존재한다.** `body`/`joint` 태그를 grep해 확인한 결과, 42개 관절·48개 바디로 구성돼 있으나 **`hip`/`knee`/`ankle`/`leg`/`torso`/`pelvis` 키워드가 전혀 없다** — 즉 다리·몸통이 없는, **고정 베이스(`base_plate`+`central_pillar`) 위에 양팔+손가락(`left_link1~7`, `left_finger_1~2`)만 있는 구조**다. `r2_` 접두사로 두 번째 로봇이 미러링돼 있어 정확히 `fingershake-robot-main`의 양팔+손가락 부분과 대응된다.
- `sim_dual_arm.py`(223줄)를 훑어보니 **외부에 상태를 노출하는 인터페이스가 없다** — `rerun`으로 시각화만 하고, 소켓/HTTP/WebSocket 서버 코드는 전혀 없다. 즉 "스트리밍 브리지"는 기존 코드에서 재사용할 수 없고 새로 만들어야 한다.

## 2. 결론 — 원래 비교표 정정

[[2026-08-12-moojoco-stage3-option-comparison]]에서 옵션 B의 "초기 비용"을 "Python/MuJoCo 서버 신설 + MJCF 모델링"으로 뭉뚱그렸는데, 실제로는:

- **팔·손 부분(어깨/팔꿈치/손목/손가락)**: MJCF 모델이 이미 있다 — 이 부분의 "MJCF 모델링" 비용은 사실상 0에 가깝다. `fingershake-robot-main`의 현재 수동 슬라이더(Shoulder Pitch/Yaw/Roll, Elbow, Wrist, 손가락 5개 Curl)를 `dual_openarm_handshake.xml`의 액추에이터에 매핑하는 작업만 남는다.
- **다리·몸통 부분(고관절/무릎/발목/몸통 Yaw·Pitch, 그리고 그 위에 얹은 1·2단계 CoM/ZMP 근사)**: 대응하는 MJCF가 전혀 없다. 이 부분을 MuJoCo로 대체하려면 별도의 바이페달 모델을 새로 설계해야 하며, 이는 원래 예상대로 비용이 크다.
- **스트리밍 브리지**: 기존 코드 재사용 불가, 신규 작성 필요 — 원래 예상과 동일.

즉 옵션 B는 "전부 새로 만들기"가 아니라 **"팔·손은 거의 공짜로 가능, 다리·몸통은 원래 예상대로 비쌈"**이라는 비대칭적인 그림이다.

## 3. 재조정된 세부 단계 (B-1 ~ B-5)

1. **B-1 (본 문서, 완료)** — 기존 인프라 조사·비용 재산정.
2. **B-2 — 최소 스트리밍 브리지**: `dual_openarm_handshake.xml`을 `mj_step`으로 구동하며 관절 각도를 WebSocket(또는 폴링 HTTP)으로 노출하는 작은 Python 서버 하나. `sim_dual_arm.py`와 별개로 작게 시작(렌더링·Rerun 없이 순수 물리 스텝 + 상태 노출만).
3. **B-3 — 프론트엔드 팔 연동**: `fingershake-robot-main`에 "MuJoCo Live (Arms)" 모드를 추가해, 스트리밍된 팔/손 관절 상태를 기존 `rightShoulder`/`rightElbow`/`rightWrist`/`rightFingers` 그룹에 적용. 다리·몸통은 건드리지 않고 기존 manual FK + 1·2단계 CoM/ZMP 근사를 그대로 유지.
4. **B-4 — 실측 검증·배포**: 슬라이더로 목표 각도를 주고 MuJoCo가 실제로 접촉·마찰을 반영해 손 자세를 계산하는 것을 스크린샷으로 확인.
5. **B-5 (장기, 별도 승인 필요) — 바이페달 다리 MJCF 신설**: 다리·몸통까지 MuJoCo로 대체하려면 이 단계에서 새 모델을 설계한다. 지금 당장은 범위에 넣지 않는다.

**다음 단계**: 사령관 승인을 받으면 B-2(스트리밍 브리지)부터 별도 thesis로 계획→구현을 이어간다.
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage1-scoping",
    "title": "옵션 B(MuJoCo 백엔드) 착수 — B-1: 기존 인프라 조사 및 세부 단계 계획",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-12-moojoco-stage3-option-comparison]]에서 권고한 옵션 B(MuJoCo 백엔드 연동) 착수를 위해, "
        "구현 전 hb5u에 이미 존재하는 MuJoCo 인프라를 먼저 조사했다. mujoco_sim.service가 이미 실행 중이고, "
        "MuJoCo 3.7.0이 설치돼 있으며, 특히 두 로봇이 악수하는 고정 베이스 양팔+손가락 MJCF 모델"
        "(dual_openarm_handshake.xml)이 이미 존재한다는 것을 확인했다 — 다만 다리/몸통(hip/knee/ankle/torso) "
        "은 전혀 없어 fingershake-robot-main의 1·2단계 CoM/ZMP 작업과는 대응되지 않는다. sim_dual_arm.py에는 "
        "외부 상태 노출 인터페이스가 없어 스트리밍 브리지는 신규 작성이 필요함도 확인했다. 이를 바탕으로 원래 "
        "비교표의 '초기 비용' 항목을 정정하고, 팔/손 먼저(B-2~B-4) 진행 후 다리는 별도 승인 하에 장기 과제"
        "(B-5)로 미루는 세부 단계 계획을 세웠다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "plan"],
    "changelog": "v1.0 — 최초 제출: 옵션 B 착수, B-1(인프라 조사) 완료 및 B-2~B-5 세부 계획",
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
