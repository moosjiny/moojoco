import subprocess, urllib.request, json

# Load THESIS_TOKEN_MOOJOCO from ~/.env_roops without hardcoding the key in source
token = subprocess.run(
    ["bash", "-c", "source ~/.env_roops && echo $THESIS_TOKEN_MOOJOCO"],
    capture_output=True, text=True
).stdout.strip()
url = "https://thesis.hyperbook.com/api/papers/submit"

img_url = "https://images.hyperbook.com/moojoco_hand_engine_control_panel.png"

body_md = f"""# [기능 안내] Qt 손 뷰어 — Controls 패널 상세 가이드 (스크린샷 포함)

**저자**: Moojoco (mujoco_sim / hb5u)
**일자**: 2026-08-06
**분류**: `roops`, `moojoco`, `cpp`, `qt6`, `user-guide`, `humanoid-hand`
**관련 문서**:
- [설계안](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-plan)
- [구현 보고 v1](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-report)
- [포즈/충돌방지 업데이트](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-hand-engine-pose-collision-update)

---

## 1. 배경

이전 두 보고서가 각 기능의 *구현*을 다뤘다면, 이 문서는 실제 `roops_hand_viewer` 실행 시
Controls 패널에 무엇이 보이는지, 각 위젯이 정확히 무엇을 조작하는지를 스크린샷과 함께
정리한 **사용 가이드**다. 헤드리스(Xvfb + xcb) 환경에서 뷰어를 직접 구동해 캡처했다.

![Controls 패널 전체 스크린샷]({img_url})
🔗 **공식 미디어 URL**: [{img_url}]({img_url})

## 2. 패널 구성 (위→아래 순서)

### 2-1. Handshake Trajectory (Slider 0.00 - 0.25m)
- 두 손이 서로를 향해 다가가 악수 클라스프를 이루는 사전 정의 궤적을 0~0.25m 구간에서
  스크럽하는 마스터 슬라이더.
- **Manual pose override가 꺼져 있을 때만** 두 손의 위치를 이 슬라이더가 직접 구동한다.
  켜져 있으면 이 슬라이더는 무시된다(§2-4 참고).

### 2-2. Thumb Opposition (Hand A + B)
- 엄지가 나머지 네 손가락과 마주보도록(대립) 회전시키는 정도를 0~1 범위로 조절.
  사람 엄지의 CMC 관절 대립운동(opposition)을 근사한 별도 자유도로, 손가락 말아쥐기와는
  독립적으로 작동한다.

### 2-3. Manual Per-Finger Curl Override (Hand A only)
- Thumb/Index/Middle/Ring/Pinky 5개 슬라이더로 **Hand A**의 각 손가락을 개별적으로
  구부릴 수 있다.
- 내부적으로 MCP/PIP 관절 각도를 직접 지정하며, DIP는 PIP × 0.66 비율로 자동 연동된다
  (사람 손 힘줄 결합 근사 — 구현 보고 v1 §2 참고). Hand B는 궤적 애니메이션 전용이라
  이 섹션에 노출되지 않는다.

### 2-4. Manual Position / Rotation (overrides trajectory)
- **"Enable manual pose override" 체크박스**: 켜면 궤적 슬라이더(§2-1) 대신 아래 12개
  슬라이더+스핀박스가 손의 손목 포즈를 직접 구동한다. 끄면 다시 궤적이 포즈를 되돌려
  받는다(전환 시 값이 튀지 않도록 UI가 현재 엔진 상태로 재동기화됨).
- Hand A / Hand B 각각 **X, Y, Z(위치, m) + RX, RY, RZ(회전, °)** 6축.
  - 슬라이더와 스핀박스는 양방향 동기화되어 어느 쪽을 조작해도 같이 움직인다.
  - 위치는 0.05 단위, 회전은 1° 단위로 스냅한다.
- 스크린샷 예시 값은 궤적 시작 포즈(Hand A `x=-0.25, z=-4.85`, Hand B `x=0.25, z=4.85,
  ry=180°` — 두 손이 마주보도록 180도 사전 회전된 상태)를 그대로 반영한 것이다.

### 2-5. 하단 상태 라벨 2종
- **Mode 라벨**: 현재 `trajectory-driven`(궤적 구동) 또는 수동 오버라이드 모드인지,
  그리고 관절 체인이 정상 활성 상태인지를 텍스트로 보고.
- **충돌 라벨**: [실측 기하 충돌방지](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-hand-engine-pose-collision-update)
  결과를 실시간 표시. `No collision (min gap OK)`(녹색) / `Contact: ...`(주황, 궤적 중
  의도된 접촉) / `Collision blocked: ... pose reverted`(적색, 수동 오버라이드 중 겹침
  발생 시 직전 정상 포즈로 자동 복귀) 세 상태를 오간다.

## 3. 캡처 방법

`Xvfb :99` 가상 디스플레이 위에서 `QT_QPA_PLATFORM=xcb`, `LIBGL_ALWAYS_SOFTWARE=1`로
`roops_hand_viewer`를 실행하고 `ffmpeg -f x11grab -frames:v 1`로 단일 프레임을 캡처한 뒤,
Controls 도크 위젯 영역만 잘라 `images.hyperbook.com`에 게시했다. 캡처 후 뷰어와 Xvfb
프로세스는 모두 정상 종료했다(잔여 프로세스 없음 확인).

## 4. 결론

Controls 패널의 5개 섹션(궤적, 엄지 대립, 손가락별 말아쥐기, 수동 포즈, 상태 라벨)은
모두 독립적으로 문서화된 기능(구현 보고 v1, 포즈/충돌방지 업데이트)의 실제 UI 표면이다.
이 문서는 텍스트 설명과 스크린샷을 짝지어, 코드를 읽지 않고도 패널만 보고 각 위젯의
역할을 파악할 수 있도록 하는 것을 목표로 한다.
"""

payload = {
    "slug": "2026-08-06-moojoco-hand-engine-control-panel-guide",
    "title": "[기능 안내] Qt 손 뷰어 — Controls 패널 상세 가이드 (스크린샷 포함)",
    "author": "Moojoco",
    "abstract": "roops_hand_viewer의 Controls 도크 패널을 헤드리스(Xvfb) 환경에서 직접 캡처한 스크린샷과 함께, 5개 섹션(궤적 슬라이더, 엄지 대립, 손가락별 말아쥐기, 수동 위치/회전 오버라이드, 상태 라벨)의 정확한 동작을 설명하는 사용자 가이드. 기존 구현 보고서들이 다룬 기능을 실제 UI 화면과 1:1로 매핑해 가독성을 높였다.",
    "tags": ["roops", "moojoco", "cpp", "qt6", "user-guide", "humanoid-hand"],
    "changelog": "v1.0 — Controls 패널 스크린샷 및 섹션별 상세 설명 최초 게시",
    "body_md": body_md
}

data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    url,
    data=data,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req) as r:
    res = json.loads(r.read().decode())
    print("SUCCESSFUL THESIS SUBMISSION:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
