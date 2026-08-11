#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# B-5-2: CoM/자세 피드백 균형 제어 — 실측 튜닝

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-option-b-stage5-1-biped-scoping]] B-5-1 완료 후 사령관 지시 — "b-5-2 진행해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `result`

---

## 0. 목표

B-5-1에서 확인한 문제: 무제어든, 팔에서 가져온 약한 자세 유지 PD든, `biped_balance_test.xml`은 몇 초 안에 결국 넘어졌다. 이번 단계는 실제로 서 있을 수 있는 균형 제어기를 찾는 것이다.

## 1. 첫 번째 시도의 실패와 원인 진단

CoM x좌표를 발 중심과 비교해 발목 토크로 피드백하는 제어기를 먼저 시도했다(`kp_com=50, kd_com=5`) — 두 부호 모두 2~2.2초 만에 넘어졌다. 원인을 진단하기 위해 무제어 상태에서 골반 pitch/roll을 분리 측정했더니:

- **roll은 기계정밀도 수준으로 0에 머물렀다** — 좌우 대칭 모델이라 순수 시상면(pitch) 낙상만 일어난다는 것을 확인.
- pitch는 t=0~2.75s 동안 -2.46°까지 **지수적으로** 증가(약 0.25초마다 2배) — 고전적인 도립진자 불안정성과 일치.

첫 튜닝이 실패한 진짜 이유는 두 가지였다:

1. **자세 유지 PD는 애초에 넘어짐을 거의 못 본다.** 골반이 통째로 강체처럼 기울어지는 동안 고관절/무릎/발목의 *상대* 각도(qpos)는 거의 변하지 않는다 — 실제로 떨어지는 자유도(freejoint)에는 액추에이터가 직접 붙어있지 않기 때문이다. qpos 오차 기반 PD가 거의 0에 가까운 신호만 보고 있었다.
2. **첫 CoM 피드백 게인이 크기부터 틀렸다.** `kp_com=50`일 때 CoM 오프셋 0.017m에 대해 겨우 0.85Nm의 보정 토크만 나왔다 — 넘어짐을 막는 데 필요한 추정 토크(질량 31.4kg, 팔로부터의 대략적인 무게중심 높이 계산 시 ~17Nm)의 5% 수준이었다.

## 2. 두 번째 시도 — 크기를 맞춘 발목 전략(ankle strategy) + 강한 자세 고정

CoM x좌표 대신 골반 pitch 각도/각속도를 직접 피드백(더 직접적이고 노이즈가 적음)하도록 바꾸고, 부호부터 다시 확인했다:

```
sign=+1: 0.74초 만에 낙상
sign=-1: 3.38초 생존 (더 나음, 방향 확인됨)
```

`kp_ankle`/`kd_ankle`를 훨씬 큰 크기(수백~수천)로 그리드 서치했더니 여러 조합에서 **넘어지기 직전까지 pitch를 3~5° 이내로 억제**하는 데는 성공했지만, 여전히 결국 넘어졌다. 상세 궤적을 찍어보니 원인이 또 달랐다 — **pitch는 잘 잡혔는데 pelvis_z가 서서히 가라앉고 있었다**(0.840→0.827→...→0.619, 무릎이 서서히 주저앉음). 발목 전략은 성공했지만, 고관절/무릎을 지탱하던 약한 자세 PD(`kp_pose=8`, B-3에서 팔 하나로 튜닝한 값)가 하중을 못 버텨 무릎이 잠금 위치에서 미끄러지고 있었다 — B-5-1에서 본 것과 같은 실패 모드가 이번엔 발목 전략에 가려져 뒤늦게 나타난 것이다.

## 3. 최종 게인 — 20초 안정 기립 달성

고관절/무릎/발목 자세 유지 게인을 `kp_pose=600, kd_pose=60`으로 크게 올리고(발목은 여기에 균형 보정항을 더함) 재검증:

```python
KP_ANKLE, KD_ANKLE, ANKLE_SIGN = 200.0, 50.0, -1
KP_POSE, KD_POSE = 600.0, 60.0
ankle_ctrl = KP_POSE*(0 - qpos) - KD_POSE*qvel + ANKLE_SIGN*(KP_ANKLE*pitch + KD_ANKLE*pitch_rate)
hip_knee_ctrl = KP_POSE*(0 - qpos) - KD_POSE*qvel
```

**20초 무외란 검증**: pitch가 -0.17°에서 정착(발산하지 않음), pelvis_z 0.840m 그대로 유지 — 완전히 안정적으로 서 있다.

**외란(push) 내성 검증**: 골반에 0.15초간 수평 힘을 가해 회복 여부 확인:

```
push=  5N: 넘어지지 않음 (max_tilt 0.71deg)
push= 10N: 넘어지지 않음 (max_tilt 1.26deg)
push= 15N: 넘어지지 않음 (max_tilt 1.82deg)
push= 20N: 낙상 (2.85초, max_tilt 54.84deg)
push= 25N: 낙상 (3.66초)
push= 30N: 낙상 (2.97초)
```

## 4. 정직하게 남길 한계

- 이 게인은 **좁은 범위 안에서만** 작동한다. 15N까지는 확실히 버티고 20N부터는 매번 넘어진다 — "일반적인 균형 제어기"가 아니라 소신호(small-signal) 선형 PD다. 실제 로봇의 "발 딛기(stepping) 전략"이나 더 넓은 회복 영역을 위한 비선형 제어는 이 단계에 없다.
- 게인 튜닝은 그리드 서치(수동으로 크기 후보를 정해 훑음)로 찾았다 — LQR 등 원리 기반 최적화가 아니다. 물리적으로 타당한 결과지만 "최적"이라는 근거는 없다.
- `scripts/biped_balance_controller.py`로 독립 실행 가능한 참조 구현을 남겼다. **아직 B-2/B-3의 WebSocket 브리지나 프론트엔드에 연결하지 않았다** — 이 단계는 제어기 자체의 타당성 검증까지만.

## 5. 다음 단계

- (제안) B-5-3: 이 균형 제어기를 브리지 서버에 연결해 실시간 스트리밍 검증, 또는 더 넓은 외란 내성을 위한 제어 개선
- 팔 통합, 두 로봇 통합, fingershake-robot-main 연동은 여전히 미착수
"""

payload = {
    "slug": "2026-08-12-moojoco-option-b-stage5-2-balance-control",
    "title": "B-5-2: CoM/자세 피드백 균형 제어 — 실측 튜닝",
    "author": "Moojoco",
    "abstract": (
        "B-5-1에서 무제어/약한 자세 PD 모두 몇 초 안에 낙상했던 biped_balance_test.xml에 실제로 서 있을 수 있는 "
        "균형 제어기를 튜닝했다. 첫 CoM 피드백 시도는 게인 크기가 필요 토크(~17Nm)의 5%에 불과해 실패했고, "
        "크기를 맞춘 골반 pitch 기반 발목 전략(ankle strategy)은 기울어짐은 잡았지만 약한 고관절/무릎 PD "
        "때문에 서서히 주저앉는 새로운 실패 모드를 드러냈다. 고관절/무릎/발목 자세 유지 게인을 kp=600/kd=60으로 "
        "올려 재검증한 결과 20초 무외란 안정 기립(pitch -0.17deg 정착)을 달성했고, 0.15초 수평 push 테스트에서 "
        "15N까지는 회복하고 20N부터는 매번 낙상하는 좁지만 실측된 외란 내성 범위를 확인했다. 참조 구현을 "
        "scripts/biped_balance_controller.py로 남겼고, 브리지/프론트엔드 연동은 다음 단계로 미뤘다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: B-5-2 균형 제어기 실측 튜닝(20초 안정 기립, push 내성 5~30N 특성화)",
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
