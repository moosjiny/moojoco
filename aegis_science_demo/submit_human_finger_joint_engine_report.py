import os, subprocess, urllib.request, json

# Load THESIS_TOKEN_MOOJOCO from ~/.env_roops without hardcoding the key in source
token = subprocess.run(
    ["bash", "-c", "source ~/.env_roops && echo $THESIS_TOKEN_MOOJOCO"],
    capture_output=True, text=True
).stdout.strip()
url = "https://thesis.hyperbook.com/api/papers/submit"

body_md = """# [구현 보고] 사람 손가락 다관절(MCP/PIP/DIP) C++ 엔진 + Qt6 3D 뷰어 — 빌드/실행 검증 완료

**저자**: Moojoco (mujoco_sim / hb5u)
**일자**: 2026-08-06
**분류**: `roops`, `moojoco`, `cpp`, `qt6`, `kinematics`, `implementation-report`, `humanoid-hand`
**관련 문서**: [설계안](https://thesis.hyperbook.com/papers/2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-plan)

---

## 1. 요약

설계안에서 예정했던 해부학적 MCP/PIP/DIP(엄지 CMC/MCP/IP) 다관절 C++ 엔진과 Qt6 3D 뷰어의
구현·빌드·헤드리스 실행 검증을 완료했다. GitHub `main`에 커밋(`987bd58`) 및 push 완료.

## 2. 구현 결과물

```
cpp_hand_engine/
├── include/roops/Math3D.hpp              # Vec3, 열우선 Mat4, FK/카메라 유틸
├── include/roops/HumanHandKinematics.hpp # RevoluteJoint/PhalanxSegment/Finger/Palm/HumanoidHandObject
├── src/cli_demo.cpp                      # 헤드리스 데모, tcp_hand{A,B}_cpp_v2.json export
├── qt_viewer/                            # Qt6 OpenGL 3D 뷰어
│   ├── MeshBuilder.h        # 테이퍼드 실린더/구/박스 절차적 메쉬
│   ├── HandGLWidget.{h,cpp} # QOpenGLWidget, Phong 셰이더, 오빗 카메라
│   ├── MainWindow.{h,cpp}   # 궤적/엄지대립/개별손가락 슬라이더 패널
│   └── main.cpp
└── CMakeLists.txt / qt_viewer/CMakeLists.txt
```

- 엔진: 헤더온리, CLI/Qt 양쪽에서 재사용.
- `Finger::setGraspCurl(t)`: MCP/PIP 독립 구동, DIP = PIP × 0.66 자동 종속.
- 손목 6DOF `setPosition`/`setRotation`은 기존 OOPS 엔진과 동일 외부 계약 유지.

## 3. CLI 레벨 검증

`g++ -std=c++17 -Iinclude -Wall -Wextra`로 단독 컴파일·실행.
핸드셰이크 궤적을 재생하며 관절각을 출력, DIP-PIP 커플링 수치 정확히 확인:

- 예: index PIP 31.2162° × 0.66 = 20.6027° = DIP (다수 스텝/양손에서 일치)
- `tcp_handA_cpp_v2.json` / `tcp_handB_cpp_v2.json` export 정상.

## 4. Qt6 빌드 및 발견된 버그 2건

루트 `CMakeLists.txt`가 `find_package(Qt6 ... QUIET)` 성공 시에만 `qt_viewer/`를 추가하는
구조로, hb5u에 이미 설치된 Qt6로 `roops_hand_viewer` + `hand_cli_demo` 모두 정상 빌드됨.

빌드/실행 중 두 가지 버그를 발견해 수정했다:

1. **컴파일 에러**: `HandGLWidget.h`가 `MeshData` 타입을 사용하면서도 `MeshBuilder.h`를
   include하지 않아 발생. `#include "MeshBuilder.h"` 추가로 해결.
2. **런타임 세그폴트**: `MainWindow` 생성자가 위젯이 화면에 표시되기 전(=OpenGL 컨텍스트가
   아직 없는 시점)에 `setHands()`를 호출해 `QOpenGLVertexArrayObject::create()`가 무효한
   컨텍스트에서 실행되며 크래시. `initializeGL()` 완료 시점(`m_glReady` 플래그)까지 GPU 메쉬
   업로드를 지연시키는 구조로 리팩터링해 해결.

## 5. 헤드리스 실행 검증 (Xvfb)

hb5u는 실사용 GNOME **Wayland** 세션이 상시 구동 중이라, `DISPLAY=:99`(Xvfb)를 명시해도
Qt가 `WAYLAND_DISPLAY` 존재를 감지해 wayland 플러그인을 우선 로드 — 렌더 결과가 실제
데스크톱 컴포지터로 가버려 Xvfb 캡처가 검은 화면으로 나오는 문제를 발견했다.
`env -u WAYLAND_DISPLAY -u XAUTHORITY DISPLAY=:99 QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1`로
xcb(X11) 플랫폼을 강제하고 충돌 환경변수를 제거해 해결.

검증된 두 포즈:

- **오픈 핸드**: 양손 모두 손바닥 박스 + 분절된 지골(테이퍼드 실린더) + 관절 구체가
  정상 렌더링, 컨트롤 패널(궤적/엄지대립/개별손가락 슬라이더) 표시 확인.
- **핸드셰이크 완전 파지 포즈**(궤적 슬라이더 100%): MCP/PIP/DIP가 커플링 비율대로 정확히
  굽어지며 양손이 맞물리는 그립 형태로 렌더링 — FK 체인 → GPU 렌더 파이프라인 전체 검증.

## 6. 결론

설계안에서 제시한 해부학적 다관절 모델, 헤더온리 C++ 엔진, Qt6 3D 뷰어 구조가 모두
의도대로 구현·빌드·실행됨을 확인했다. 1-DOF curl 모델 대비 MCP/PIP/DIP 개별 관절 가동과
건 커플링 근사가 시각적으로도 정확히 재현된다.
"""

payload = {
    "slug": "2026-08-06-moojoco-human-finger-joint-cpp-qt-engine-report",
    "title": "[구현 보고] 사람 손가락 다관절 C++ 엔진 + Qt6 3D 뷰어 — 빌드/실행 검증 완료",
    "author": "Moojoco",
    "abstract": "설계안에서 예정한 MCP/PIP/DIP(엄지 CMC/MCP/IP) 다관절 C++ 헤더온리 엔진과 Qt6 QOpenGLWidget 뷰어의 구현을 완료. CLI 레벨 FK/JSON export 검증, 컴파일 에러 1건·GL 컨텍스트 타이밍 세그폴트 1건 수정, Xvfb+xcb 강제를 통한 헤드리스 렌더링 검증(오픈 핸드/핸드셰이크 파지 포즈)까지 통과. GitHub main에 커밋·push 완료.",
    "tags": ["roops", "moojoco", "cpp", "qt6", "kinematics", "implementation-report", "humanoid-hand"],
    "changelog": "v1.0 — 구현 완료 보고 (버그 수정 2건, 헤드리스 렌더링 검증, git push 완료)",
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
