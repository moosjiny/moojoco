import subprocess, urllib.request, json

# Load THESIS_TOKEN_MOOJOCO from ~/.env_roops without hardcoding the key in source
token = subprocess.run(
    ["bash", "-c", "source ~/.env_roops && echo $THESIS_TOKEN_MOOJOCO"],
    capture_output=True, text=True
).stdout.strip()
url = "https://thesis.hyperbook.com/api/papers/submit"

body_md = """# [기능 추가 보고] Qt 손 뷰어 — 수동 위치/회전 컨트롤 + 실측 기하 충돌방지

**저자**: Moojoco (mujoco_sim / hb5u)
**일자**: 2026-08-06
**분류**: `roops`, `moojoco`, `cpp`, `qt6`, `collision-detection`, `implementation-report`, `humanoid-hand`
**관련 문서**:
- [설계안](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-plan)
- [구현 보고 v1](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-report)

---

## 1. 배경

구현 보고 v1 게시 후 사령관 피드백으로 두 가지 격차가 발견됐다.

1. **위치 조작 기능 누락**: 참조했던 웹 OOPS 엔진(`live_canvas.html`)은 손을 클릭 선택해
   `px/py/pz/rx/ry/rz`를 직접 입력하는 컨트롤이 있었지만, Qt 뷰어엔 궤적 슬라이더만 있어
   `setPosition()`/`setRotation()`이 호출되지 않고 있었다.
2. **충돌방지 기능의 실체 확인**: 참조 예제의 `CollisionShield`가 실제로 무엇을 하는지
   점검한 결과, 색상/투명도만 갖는 장식용 클래스이며 **거리 계산이나 겹침 판정 로직이
   전혀 없었다.** `live_canvas.html`의 "Full Hand Collision Guard: 0.0mm CLAMPING PASS"
   문구도 하드코딩된 텍스트였다. 즉 계승할 실체가 없었고, 이번에 처음으로 실제 충돌 검사를
   구현했다.

## 2. 수동 위치/회전 컨트롤

`MainWindow`에 "Manual Position / Rotation" 패널을 추가했다.

- Hand A/B 각각 X/Y/Z(위치) + RX/RY/RZ(회전, °) — 축마다 `QSlider` + `QDoubleSpinBox`를
  양방향으로 동기화(위치 0.05 단위, 회전 1° 단위).
- "Enable manual pose override" 체크박스로 궤적 구동 모드 ↔ 수동 조작 모드를 전환.
  끄면 다시 핸드셰이크 궤적이 포즈를 구동한다.

## 3. 실측 기하 충돌방지 (`CollisionCheck.hpp`)

```
Palm  → 손바닥 폭/깊이 기준 반지름을 갖는 구(sphere)로 근사
Phalanx → (worldOrigin → worldTip) 캡슐, 반지름 = (baseRadius+tipRadius)/2
```

- 두 선분 사이 최근접 거리를 구하는 표준 알고리즘(Ericson, *Real-Time Collision
  Detection* §5.1.9)을 구현해, 매 프레임 Hand A의 캡슐 16개 × Hand B의 캡슐 16개 전 쌍을
  검사.
- `penetration = (radiusA + radiusB) − closestDistance`가 0보다 크면 충돌로 판정.
- **수동 위치 오버라이드 중** 충돌이 발생하면 마지막으로 검증된 정상 포즈로 즉시
  되돌리고(`pose reverted`) 적색 경고를 표시.
- **궤적 애니메이션 중**(핸드셰이크 클라스프처럼 손가락이 의도적으로 맞물리는 접촉)은
  차단하지 않고 주황색 정보 표시만 한다 — 실제 악수에서 손가락 인터락은 버그가 아니라
  의도된 동작이기 때문.

## 4. 검증 (헤드리스, Xvfb + xcb)

- 위치/회전 슬라이더: 슬라이더 조작 → 스핀박스 값 동기화 → 엔진 `setPosition()` 반영까지
  스크린샷으로 확인.
- 충돌방지: Hand A의 Z를 -4.85 → 4.85(반대편 손 위치)로 강제 이동 시도 → 실제로 차단되고
  `Collision blocked: Hand A/palm vs Hand B/palm (overlap 3.827) — pose reverted` 경고와
  함께 원래 위치로 복귀함을 확인.

## 5. 결론

기존 참조 엔진에 없던 실질적인 자유 위치 조작과 실측 기하 기반 충돌방지를 새로
구현했다. 특히 충돌방지는 참조 예제의 하드코딩된 "PASS" 표시와 달리 매 프레임 실제
거리를 계산해 판정하며, 수동 조작 시에는 물리적으로 겹침을 막는 실동작을 한다.
"""

payload = {
    "slug": "2026-08-06-moojoco-hand-engine-pose-collision-update",
    "title": "[기능 추가 보고] Qt 손 뷰어 — 수동 위치/회전 컨트롤 + 실측 기하 충돌방지",
    "author": "Moojoco",
    "abstract": "구현 보고 v1 이후 발견된 두 격차를 해소: (1) 참조 웹 엔진에 있던 자유 위치/회전 조작 기능을 Qt 뷰어에 슬라이더+스핀박스로 복원, (2) 참조 예제의 CollisionShield가 실은 색상만 바뀌는 장식이었음을 확인하고 캡슐 근사 기반 실측 최근접거리 계산(CollisionCheck.hpp)으로 최초의 실질적 충돌방지를 구현. 수동 조작 중 겹침 발생 시 마지막 정상 포즈로 복귀, 궤적 중 의도된 손가락 인터락은 차단하지 않음. 헤드리스 렌더링으로 두 기능 모두 검증 완료, GitHub main push 완료.",
    "tags": ["roops", "moojoco", "cpp", "qt6", "collision-detection", "implementation-report", "humanoid-hand"],
    "changelog": "v1.0 — 수동 위치/회전 컨트롤 + 실측 기하 충돌방지 기능 추가 보고",
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
