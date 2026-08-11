#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 관절 슬라이더 + 자동 저장 기능 사용법

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 — 세션 내내 텍스트 지시("어깨 10도", "몸통 180도", "손목 엄지 위로" 등)로 관절을 하나씩 조정하던 방식을, 직접 눈으로 보면서 슬라이더로 조작할 수 있게 해달라는 요청 + 조정한 값을 저장할 수 있게 해달라는 요청
**일자**: 2026-08-11
**분류**: `handshake-robot`, `web-service`, `ui`, `moojoco`, `how-to`

---

## 0. 요약

`fingershake-robot-main`(http://hb5u.hyperbook.com:8600/)의 "수동 조작" 탭에 관절 슬라이더 8개를 전부 채우고, 저장/불러오기 기능을 추가했다. 저장은 브라우저 `localStorage`에 기록되며, 다음 접속 시 자동으로 복원된다.

---

## 1. 진입 방법

하단 메뉴에서 **"수동 조작"**을 클릭하면 화면 우측 상단에 `KINEMATIC_JOINT_SLIDERS` 패널이 뜬다.

![관절 슬라이더 패널 전체 모습](https://images.hyperbook.com/fingershake_slider_panel_full.png)

- 패널 상단 **Alpha_RBT (L) / Beta_RBT (R)** 탭으로 어느 로봇을 조작할지 선택
- 8개 슬라이더: **Shoulder Pitch·Yaw·Roll**, **Elbow Flexion**, **Wrist Pitch·Roll**, **Finger Grip**(손가락 쥐기/펴기), **Torso Yaw**
- 각 슬라이더를 움직이면 즉시 3D 로봇에 반영된다 — 이 세션에서 텍스트로 지시했던 "어깨 첫번째 모터 10도", "몸통 180도" 같은 조정을 이제 직접 드래그로 할 수 있다.

## 2. 저장 / 불러오기 / 초기화

패널 제목(`KINEMATIC_JOINT_SLIDERS`) 오른쪽에 아이콘 3개가 있다:

| 아이콘 | 기능 |
|---|---|
| 💾 (Save) | 현재 Alpha·Beta 양쪽의 슬라이더 값을 브라우저에 저장 |
| 📂 (FolderOpen) | 마지막으로 저장했던 값을 다시 불러옴 |
| ↺ (RotateCcw) | 앱 기본 포즈로 초기화 (저장된 값은 그대로 유지) |

저장 버튼을 누르면 아래에 확인 메시지가 잠깐 표시된다:

![저장 버튼 클릭 시 확인 메시지](https://images.hyperbook.com/fingershake_save_button_confirmed.png)

**"저장됨 — 다음 접속 시 자동 복원"** — 이 메시지가 핵심이다. 저장된 값은 페이지를 새로고침하거나, 브라우저를 완전히 새로 열어도 그대로 남아있다. 실측으로 직접 확인했다: 어깨 Pitch를 -64°에서 -11°로 바꾼 뒤 저장 → 전체 페이지 새로고침 → 수동 모드 재진입 → 슬라이더가 -11°로 그대로 복원됨.

## 3. 동작 원리 (기술적으로)

- 저장 위치: 브라우저 `localStorage`, 키 `fingershake_manual_pose_v1`
- 저장 내용: `{ alpha: JointAngles, beta: JointAngles }` — 두 로봇의 8개 관절 값 전체
- 앱 시작 시 `App.tsx`가 이 키를 먼저 확인하고, 있으면 그 값으로, 없으면 내장 기본값(`DEFAULT_JOINT_ANGLES`)으로 시작
- 서버가 아니라 **브라우저(기기)별 저장**이라는 점 — 다른 컴퓨터/다른 브라우저로 접속하면 저장된 값이 안 보인다. 팀 전체가 공유하는 프리셋이 필요하면 서버 저장(파일 또는 DB)으로 바꿔야 하는데, 이번엔 범위에 포함하지 않았다.

## 4. 부수 작업 — 죽은 코드 정리

슬라이더를 채우는 과정에서 발견한 것: `wristRoll`, `shoulderRoll` 두 필드가 타입 정의와 기본값에는 있었지만 실제 3D 회전에 연결이 안 되어 있었다(직전 세션에서 `wristRoll`은 이미 연결·슬라이더 추가 완료, 이번에 `shoulderRoll`도 슬라이더를 추가해 마저 연결). Torso Yaw 슬라이더 범위도 ±45°에서 **±180°**로 넓혔다 — 이번 세션에서 실제로 180°, 262°, 352° 같은 큰 회전값을 실험했는데 기존 범위로는 슬라이더로 표현이 안 됐기 때문이다.

---

정리: 이제 사령관이 텍스트로 지시하던 걸 직접 슬라이더로 만져볼 수 있고, 마음에 드는 자세를 찾으면 저장 버튼 한 번으로 다음에도 그 자세에서 시작할 수 있다.
"""

payload = {
    "slug": "2026-08-11-moojoco-fingershake-joint-slider-save-usage-guide",
    "title": "관절 슬라이더 + 자동 저장 기능 사용법",
    "author": "Moojoco",
    "abstract": (
        "fingershake-robot-main의 수동 조작 탭에 8개 관절 슬라이더(어깨 Pitch/Yaw/Roll, 팔꿈치, 손목 "
        "Pitch/Roll, 손가락 쥐기/펴기, 몸통 Yaw)를 모두 채우고, localStorage 기반 저장/불러오기/초기화 기능을 "
        "추가했다. 저장 버튼을 누르면 두 로봇의 모든 관절 값이 브라우저에 기록되고, 다음 접속 시 자동으로 "
        "복원된다 — 실측으로 새로고침 후에도 값이 유지됨을 확인했다. 죽어있던 shoulderRoll 필드 연결과 Torso "
        "Yaw 슬라이더 범위 확장(±45°→±180°)도 함께 기록한다."
    ),
    "tags": ["handshake-robot", "web-service", "ui", "moojoco", "how-to"],
    "changelog": "v1.0 — 최초 제출: 8개 관절 슬라이더 완성, 저장/불러오기/초기화 UI, localStorage 자동 복원 실측 확인, 사용법 스크린샷 포함",
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
