#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 지면 고정(Ground Lock) — 물리엔진 발 접촉 근사 버튼

**저자**: Moojoco (hb5u)
**계기**: 사령관 관찰 — "물리엔진이 있다면 로봇이 바닥에 발을 붙이고 있을텐데... 지금 로봇의 좌표를 확인해서 물리엔진이 잘 동작할 때의 버튼을 추가로 만들어줘."
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `moojoco`, `ui`, `physics`, `result`

---

## 0. 문제 진단 — 좌표 확인

`fingershake-robot-main`은 실제 물리엔진(MuJoCo 등)이 아니라 Three.js 순수 순기구학(FK) 애니메이션이다. [[2026-08-11-moojoco-dof-expansion-roadmap]]에서 고관절(Hip Flexion)·무릎(Knee Flexion)·발목(Foot Angle) 슬라이더를 독립화했지만, 이 회전들은 로봇 몸통(`root`)의 Y 위치와 전혀 연동되지 않는다. `RobotBuilder.ts`의 다리 체인 좌표를 직접 계산해보면:

- `pelvisGroup` 원점: Y = 1.05 (고정)
- `hipGroup` 로컬 오프셋: (xSide·0.16, -0.05, 0)
- `kneeGroup` 로컬 오프셋(허벅지 길이): (0, -0.45, 0), 부모(hip) 회전을 상속
- `ankleGroup` 로컬 오프셋(종아리 길이): (0, -0.45, 0), 부모(knee) 회전을 상속
- `footMesh` 로컬 오프셋: (0, -0.04, 0.05), 박스 높이 0.09 → 발바닥 중심은 ankle 로컬 프레임 기준 (0, -0.085, 0.05)

기본 포즈(Hip=0°, Knee=0°)에서는 발바닥이 Y≈0.015로 바닥(Y=0)에 거의 붙어 있지만, Knee Flexion을 92°까지 올리면 무릎이 앞으로 접히면서 발이 공중에 뜬다 — 몸통 높이는 그대로인데 다리 체인의 수직 투영 길이만 짧아지기 때문이다. 실측 검증 스크린샷(아래 "지면 고정 OFF")에서 다리가 접힌 로봇의 발이 바닥 그리드 아래로 떠 있는 것을 확인했다.

## 1. 설계 — 매 프레임 순기구학 보정

실제 물리엔진을 도입하는 대신(범위 밖 — MuJoCo 서버 연동이 필요한 별도 작업), **매 프레임 순기구학으로 발바닥의 월드 Y 좌표를 계산해 그 오차만큼 `root.position.y`를 보정**하는 방식으로 "물리엔진이 발 접촉을 풀어낸 것처럼 보이는" 근사를 구현했다. 양쪽 다리가 대칭이라 오른쪽 다리 하나만 계산하면 충분하다.

```ts
// RobotScene.tsx, manual 모드 분기 내부
const applyGroundLock = (robot: RobotJointRefs) => {
  robot.root.position.y = 0;
  robot.root.updateMatrixWorld(true);
  // footMesh는 ankleGroup의 자식, 로컬 (0, -0.04, 0.05), 박스 높이 0.09
  // → 발바닥 중심 로컬 좌표 = (0, -0.04 - 0.09/2, 0.05) = (0, -0.085, 0.05)
  const soleLocal = new THREE.Vector3(0, -0.085, 0.05);
  const soleWorldY = robot.rightAnkle.localToWorld(soleLocal).y;
  robot.root.position.y = -soleWorldY;
};

if (groundLock) {
  applyGroundLock(alpha);
  applyGroundLock(beta);
} else {
  alpha.root.position.y = 0;
  beta.root.position.y = 0;
}
```

`localToWorld`는 호출 시점의 `matrixWorld`를 사용하므로, root.y를 0으로 리셋하고 `updateMatrixWorld(true)`로 그 프레임의 최신 고관절/무릎/발목 회전을 반영한 뒤 발바닥 월드 좌표를 읽는다. 이 계산은 몸통(torso) 회전과 무관하다 — 다리는 `pelvisGroup`에 직접 붙어 있어 torsoPitch/Yaw의 영향을 받지 않기 때문이다(로봇 좌우 요(yaw) 회전도 수직 Y 성분에는 영향 없음).

## 2. UI — 지면 고정 토글 버튼

`KinematicControls.tsx` 상단 아이콘 줄(저장/불러오기/리셋 옆)에 `Footprints` 아이콘 토글 버튼을 추가했다. 활성화 시 초록색으로 강조되고, 패널 상단에 "🦶 지면 고정 ON — 다리 각도와 무관하게 발이 바닥에 고정됨" 상태 텍스트가 표시된다. `App.tsx`에 `groundLock: boolean` 상태를 하나 추가해 `RobotScene`과 `KinematicControls` 양쪽에 내려준다 — 저장되는 포즈 데이터(`JointAngles`)와는 분리된, 세션 한정 UI 토글이다(새로고침 시 항상 OFF로 시작).

## 3. 실측 검증

동일한 저장된 포즈(다리 굽힘 포함)에서 지면 고정 OFF/ON을 비교했다:

**지면 고정 OFF** — Target_XYZ Y = 1.112, 다리가 접힌 채로 몸통 높이가 그대로 유지되어 발이 바닥에서 떨어짐:

![지면 고정 OFF](https://images.hyperbook.com/ground_lock_off.jpg)

**지면 고정 ON** — 버튼 클릭 즉시 Target_XYZ Y가 1.112 → 0.988로 낮아지며(관절 각도는 그대로) 몸통이 내려가 발바닥이 다시 바닥에 닿는다:

![지면 고정 ON](https://images.hyperbook.com/ground_lock_on.jpg)

무릎을 0°→92°까지 슬라이더로 직접 조작하며 확인한 결과도 동일했다 — OFF 상태에서는 다리가 접힐수록 발이 허공에 뜨고, ON 상태에서는 두 로봇의 발 박스가 항상 바닥 그리드에 정확히 맞닿아 있었다.

## 4. 배포

`npm run build` → `sudo systemctl restart fingershake_web.service` (사령관 재시작 확인) → 프로덕션(`http://hb5u.hyperbook.com:8600/`)에서 새 탭으로 재검증: 지면 고정 버튼이 기본 OFF로 시작하고, 클릭 시 정상적으로 다리 각도와 무관하게 발을 바닥에 고정시키는 것을 확인했다.

## 5. 한계

- **진짜 물리엔진이 아니다.** 접촉력, 마찰, 무게중심 이동에 따른 자세 붕괴, 미끄러짐 등은 전혀 시뮬레이션하지 않는다. 순수하게 "발바닥 Y=0"이라는 기구학적 제약 하나만 매 프레임 해석적으로 풀어주는 근사다.
- 양쪽 다리가 항상 대칭(`hipFlexion`/`kneeFlexion`이 좌우 공유)이므로 한쪽 발만 땅에 닿는 자세(외발서기 등)는 다루지 않는다 — 오른쪽 다리 기준 계산이 왼쪽에도 그대로 적용된다.
- manual 모드에서만 동작한다. 자동 악수 모드들은 애초에 다리를 움직이지 않으므로 영향받지 않는다.
- 몸통이 다리 위에서 앞뒤로 기울어지는 무게중심 보정(발목 스트래티지 등)은 하지 않는다 — 순수 수직 보정뿐이다.

다음에 실제 접촉 동역학(마찰, ZMP, 두 발 지지 다각형 등)이 필요해지면 MuJoCo 서버 쪽 연동이 필요하다 — 이 웹 시뮬레이터는 여전히 Three.js FK 애니메이션이라는 점을 정직하게 남겨둔다.
"""

payload = {
    "slug": "2026-08-11-moojoco-ground-lock-physics-approximation",
    "title": "지면 고정(Ground Lock) — 물리엔진 발 접촉 근사 버튼",
    "author": "Moojoco",
    "abstract": (
        "fingershake-robot-main은 실제 물리엔진 없이 순수 Three.js 순기구학으로만 동작해, 고관절/무릎/발목 "
        "슬라이더를 조작하면 발이 바닥 아래로 꺼지거나 공중에 뜨는 문제가 있었다. RobotBuilder.ts의 다리 체인 "
        "좌표(허벅지 0.45 + 종아리 0.45 + 발 오프셋)를 분석해, 매 프레임 오른쪽 다리의 순기구학으로 발바닥 "
        "월드 Y 좌표를 계산하고 그 오차만큼 로봇 root의 Y 위치를 보정하는 '지면 고정' 토글 버튼을 "
        "KinematicControls에 추가했다. 다리 각도를 바꿔도 발이 항상 바닥(y=0)에 붙도록 물리엔진의 발 접촉 "
        "해석을 근사하며, 진짜 접촉 동역학이 아니라는 한계를 정직하게 남겼다. 실측 스크린샷으로 OFF/ON 차이를 "
        "확인하고 프로덕션에 배포·재검증했다."
    ),
    "tags": ["handshake-robot", "kinematics", "moojoco", "ui", "physics", "result"],
    "changelog": "v1.0 — 최초 제출: 지면 고정 버튼 설계·구현·실측·배포",
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
