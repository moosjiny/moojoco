#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B — 지금 눈으로 확인 가능한 것 vs 아직 안 되는 것

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-long-term-roadmap]] 장기 로드맵 기록 직후, 사령관 질문 — "지금까지 진행한것에서 내가 눈으로 실제 구동되는것을 테스트할만한것은 무엇인가?"
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `status`

---

## 0. 왜 이 기록이 필요한가

B-1부터 B-5-4, 장기 로드맵까지 전부 thesis로 남겼지만, 지금 **당장 브라우저나 화면으로 확인할 수 있는 것**과 **아직 터미널 숫자 출력으로만 검증된 것**이 뒤섞여 있어 사령관이 직접 물어봐야 했다. 다음에 같은 질문이 나오지 않도록 현재 상태를 눈으로 볼 수 있는지 기준으로 정리한다.

## 1. 지금 바로 브라우저에서 테스트 가능 (`http://hb5u.hyperbook.com:8600/`)

`fingershake_web.service`가 상시 켜져 있어 아래는 지금 바로 확인 가능:

- **수동 조작 모드 → 🦶 지면 고정(Ground Lock)**: 고관절/무릎 슬라이더를 움직여도 발이 항상 바닥(y=0)에 붙는 순기구학 보정. [[2026-08-11-moojoco-ground-lock-physics-approximation]]
- **⚖️ 무게중심/ZMP 표시**: Hip Flexion을 90°까지 올리면 STABLE→UNSTABLE로 바뀌고, 리셋 직후 정적으로는 안정인데 동적으로는 잠깐 불안정했다가 회복되는 것까지 볼 수 있다(단, 이건 **분석적 근사**지 실제 MuJoCo 물리가 아니다). [[2026-08-12-moojoco-com-support-polygon-result]], [[2026-08-12-moojoco-dynamic-zmp-friction-result]]
- **KinematicControls 패널 드래그/리사이즈**: 제목줄 드래그로 이동, 우측 테두리 드래그로 폭 조절(280~640px), localStorage에 저장돼 새로고침해도 유지.
- **🖥️ MuJoCo Live 토글(Alpha 오른팔)**: 켜면 오른팔 슬라이더 값이 실제 MuJoCo 백엔드(PD 위치제어)에 목표각으로 전달되고, 돌아오는 실제 물리 결과로 팔이 움직인다. **단, 브리지 서버(`mujoco_bridge_server.py`, 포트 8765)가 항상 켜져 있는 건 아니다** — 각 단계 검증 후 수동으로 종료해왔기 때문에, 지금 이 순간 토글을 켜면 "연결 실패"가 뜰 가능성이 높다. 서버를 다시 띄우면 즉시 확인 가능. [[2026-08-12-moojoco-option-b-stage4-frontend]]

## 2. 아직 눈으로 볼 방법이 없음 — 터미널 숫자로만 검증됨

B-5-1~B-5-4의 바이페달 균형 제어(자유부유 골반, 실제 중력·접촉, 20초 안정 기립, hip strategy로 20N까지 push 회복)는 지금까지 전부 `pitch_deg`/`pelvis_z` 같은 숫자 로그로만 검증했다. `biped_bridge_server.py`(포트 8766)가 WebSocket으로 상태를 스트리밍하긴 하지만, 그걸 받아 그림으로 그려주는 화면이 없다 — 렌더링/시각화가 전혀 연결돼 있지 않다.

같은 dual_arms 프로젝트의 `mujoco_sim.service`가 이미 EGL GPU 렌더링 + Rerun 스트리밍을 쓰고 있어(2026-06-22 이식), 이 인프라를 재사용하면 비교적 빠르게 바이페달 쪽에도 시각화를 붙일 수 있을 것으로 보인다 — 이게 사실상 장기 로드맵 [[2026-08-12-moojoco-option-b-long-term-roadmap]]의 Phase 2 방향과 일치한다.

## 3. 요약표

| 항목 | 눈으로 확인 | 조건 |
|---|---|---|
| 지면 고정 | ✅ 즉시 가능 | 없음 |
| CoM/ZMP 오버레이 (분석적 근사) | ✅ 즉시 가능 | 없음 — 단, 실제 물리 아님 |
| 패널 드래그/리사이즈 | ✅ 즉시 가능 | 없음 |
| MuJoCo Live (Alpha 오른팔, 실제 물리) | ⏳ 조건부 가능 | 브리지 서버(8765) 재시작 필요 |
| 바이페달 균형 제어 (실제 물리) | ❌ 불가 | 시각화 미구현 (Rerun 연동 필요) |

## 4. 다음 액션 후보 (미착수, 사령관 지시 대기)

1. 팔 브리지 서버를 다시 켜서 MuJoCo Live를 즉시 시연
2. 바이페달 쪽에 Rerun 시각화를 새로 붙여 균형 제어를 눈으로 확인 가능하게 만들기(장기 로드맵 Phase 2와 맞물림)
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-visual-testability-status",
    "title": "옵션 B — 지금 눈으로 확인 가능한 것 vs 아직 안 되는 것",
    "author": "Moojoco",
    "abstract": (
        "B-1~B-5-4와 장기 로드맵까지 진행한 시점에서, 사령관이 '눈으로 실제 구동되는 것을 테스트할 만한 것이 "
        "무엇인가'를 물어 현재 상태를 시각적 확인 가능 여부 기준으로 정리했다. fingershake-robot-main "
        "웹앱(지면 고정, CoM/ZMP 분석적 오버레이, 패널 드래그/리사이즈)은 지금 바로 브라우저에서 확인 가능하다. "
        "MuJoCo Live(Alpha 오른팔 실제 물리 연동)는 코드는 배포돼 있지만 브리지 서버가 검증 후 매번 종료돼 지금 "
        "이 순간엔 꺼져 있어 재시작이 필요하다. 반면 B-5-1~B-5-4의 바이페달 균형 제어(20초 안정 기립, hip "
        "strategy로 20N push 회복)는 전부 터미널 숫자 로그로만 검증됐고 시각화가 전혀 연결돼 있지 않아 지금은 "
        "눈으로 볼 방법이 없다 — mujoco_sim.service가 이미 쓰는 EGL+Rerun 인프라를 재사용하면 빠르게 붙일 수 "
        "있을 것으로 보이며, 이는 장기 로드맵 Phase 2와 맞물린다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "status"],
    "changelog": "v1.0 — 최초 제출: 현재 시각적 테스트 가능 여부 현황 정리",
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
