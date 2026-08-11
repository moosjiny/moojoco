#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 옵션 B — B-3: 제어 채널 + PD 위치제어 레이어 (프론트엔드 연동 전 필수 발견)

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage2-bridge]] B-2 완료 후 사령관 지시 — "이어가."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 원래 계획과 달라진 점

[[2026-08-12-moojoco-option-b-stage1-scoping]]에서 B-3을 "프론트엔드 팔 연동"으로 잡았었다. 실제로 착수해보니, 프론트엔드를 연결하기 전에 막힌 문제가 하나 있었다 — **그래서 이번 단계는 프론트엔드 연동이 아니라 그 전에 반드시 풀어야 했던 제어 레이어 문제로 범위가 바뀌었다.** 프론트엔드 연동은 다음 단계(B-4)로 미룬다. 토큰이 한정적이라는 사령관 제약에 맞춰, 이번에도 작은 단위로 끊는다.

## 1. 발견 — 액추에이터가 위치 서보가 아니라 정속 토크 모터였다

`dual_openarm_handshake.xml`의 `<general>` 액추에이터에는 `gaintype`/`biastype`가 명시돼 있지 않다. MuJoCo는 이 경우 기본값(`gaintype="fixed"`, `biastype="none"`)을 쓰는데, 이는 **`ctrl` 값을 그대로 힘(토크)으로 적용하는 정속 모터**를 의미한다 — "목표 각도"가 아니다.

실측으로 확인했다:
```
ctrl=+0.05 -> 3초 후 right_joint_1 = 3.1401 rad (179.9°, 관절 한계 -3.14~3.14 rad에 거의 도달)
ctrl=+0.20 -> 3초 후에도 동일하게 관절 한계에 도달
```
작은 `ctrl` 값조차 지속적인 토크로 작용해 결국 관절이 기계적 한계까지 밀려 거기서 멈춘다. `ctrl`을 "각도"처럼 다루면 프론트엔드 슬라이더를 아무리 세밀하게 조작해도 팔이 순식간에 관절 한계까지 튕겨나가는, 전혀 쓸 수 없는 데모가 됐을 것이다.

## 2. 해결 — 브리지 서버에 자체 PD 위치제어 루프 추가

MJCF 파일(다른 에이전트/프로젝트가 공유해 쓸 수 있는 모델)을 직접 수정하는 대신, **`mujoco_bridge_server.py` 안에서 매 스텝 PD 제어를 계산**하도록 했다:

```python
KP = 8.0
KD = 0.5
# 매 프레임:
error = target - data.qpos[qpos_adr]
ctrl = KP * error - KD * data.qvel[dof_adr]
data.ctrl[idx] = clip(ctrl, *ctrlrange)
```

새 메시지 타입 `{"target": {actuator_name: angle_rad, ...}}`로 지속적인 목표각을 설정하면 매 프레임 이 PD식으로 `ctrl`을 재계산한다. 기존의 `{"ctrl": {...}}`(순간 힘, raw)도 저수준 테스트용으로 남겨뒀다.

## 3. 실측 검증

목표각을 0°, 30°, -45°, 90°로 차례로 보내고 각각 3초(180프레임) 안정화를 기다렸다:

```
target=  +0deg -> settled=  +0.0deg
target= +30deg -> settled= +30.9deg
target= -45deg -> settled= -47.1deg
target= +90deg -> settled= +93.3deg
```

목표각 근처(오차 1~3°, 비례제어의 전형적인 정상상태 오차)로 정확히 안정화되는 것을 확인했다 — 더 이상 관절 한계로 튕겨나가지 않는다.

## 4. 아직 안 한 것

- **프론트엔드 연동은 하지 않았다.** 이 단계는 백엔드 제어 레이어만 검증했다.
- KP=8.0/KD=0.5는 `right_joint_1` 하나로만 튜닝한 값이다 — 관절마다 관성·마찰이 달라 다른 관절도 같은 게인으로 잘 작동하는지는 확인 전이다.
- 서버는 검증 후 다시 종료했다 — 아직 상시 서비스 아님.

## 5. 다음 단계 (B-4)

`fingershake-robot-main`에 "MuJoCo Live (Arms)" 모드 추가: WebSocket 연결, 오른팔 슬라이더 7개(Shoulder Pitch/Yaw/Roll, Elbow, Wrist Pitch/Roll/Yaw) 값을 `right_joint1_ctrl..7`의 `target`으로 전송(관절 이름 1:1 순서 매핑 — 해부학적으로 정확하지 않은 근사임을 명시할 것), 돌아오는 qpos를 화면에 반영. 다른 관절들의 게인도 이 단계에서 함께 확인.
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage3-pd-control",
    "title": "옵션 B — B-3: 제어 채널 + PD 위치제어 레이어",
    "author": "Moojoco",
    "abstract": (
        "B-2 브리지의 제어 채널을 붙이기 전, dual_openarm_handshake.xml의 <general> 액추에이터가 gaintype/"
        "biastype 미지정으로 정속 토크 모터로 동작해 작은 ctrl 값도 관절을 기계적 한계까지 밀어붙인다는 것을 "
        "실측으로 발견했다(ctrl=0.05만으로도 3초 내 관절이 179.9°까지 도달). MJCF 모델을 수정하는 대신 브리지 "
        "서버 안에 KP=8.0/KD=0.5 PD 위치제어 루프를 추가해, {\"target\": {actuator: angle_rad}} 메시지로 지속 "
        "목표각을 설정하면 매 프레임 ctrl을 재계산하도록 했다. 0°/30°/-45°/90° 목표각 테스트에서 모두 오차 "
        "1~3° 이내로 안정화되는 것을 확인했다. 프론트엔드 연동은 하지 않았고, 다음 단계(B-4)로 미뤘다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-3 제어 채널+PD 위치제어 레이어 구현·실측, 프론트엔드 연동은 B-4로 이관",
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
