#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# Tesla Optimus 관절 자유도(DOF) 조사 — 우리 시뮬레이션과의 격차

**저자**: Moojoco (hb5u)
**계기**: 사령관 지시 — "휴머노이드 로봇중에 테슬라의 경우 로봇의 관절 자유도가 어떻게 되는지 조사해서 thesis에 기록해줘." (직전 세션에서 왼팔을 오른팔과 거울 대칭으로 연결한 직후의 요청)
**일자**: 2026-08-11
**분류**: `handshake-robot`, `kinematics`, `literature-review`, `moojoco`, `tesla-optimus`

---

## 0. 요약

Tesla Optimus의 관절 자유도(DOF)를 조사했다. 전신 28 DOF(Gen 2 body, 14 rotary + 14 linear actuator), 팔 1개당 7 DOF(어깨 3 + 팔꿈치 1 + 손목 3), 손 1개당 22 DOF(Gen 3, 텐던구동, 손가락당 4 DOF + 손목 2 DOF, 액추에이터 25개는 전완에 배치)로 확인됐다. 전신 합계(Gen3 손 포함) 72+ DOF다. 이걸 우리 `fingershake-robot-main`과 비교하면, 팔은 얼추 비슷한 범주(6 vs 7 DOF)지만 손목에 Yaw 축이 없고, 손가락은 지오메트리는 있지만 실제 제어 가능한 자유도가 사실상 1개(Finger Grip 슬라이더 하나가 5개 손가락을 동시에 움직임)뿐이라는 차이가 크다.

![Tesla Optimus vs 우리 시뮬레이션 DOF 비교](https://images.hyperbook.com/tesla_optimus_dof_comparison.svg)

---

## 1. Tesla Optimus 전신 DOF

- **Gen 2 body**: 28 DOF, 14개 rotary actuator(frameless torque motor + harmonic drive reducer + 센서) + 14개 linear actuator(frameless torque motor + planetary roller screw + 센서)
- **팔 1개**: 7 DOF — 어깨 3(rotary), 팔꿈치 1(rotary), 손목 3
- **다리 1개**: 무릎·고관절 신전에 linear actuator, 발목에도 linear actuator 사용 — 보행 중 충격 하중에 강한 planetary roller screw 방식

## 2. Tesla Optimus 손 (Gen 3, 2026년 특허 공개)

Gen 1/2는 손 1개당 11 DOF였는데, Gen 3에서 **22 DOF로 2배 증가**했다. 핵심 설계:
- 손가락 1개당 4 DOF
- 손목(손 자체가 아니라 전완 쪽)에 2 DOF
- **액추에이터 25개를 전부 전완(forearm)으로 옮기고**, 손가락까지는 텐던(힘줄형 케이블) 3가닥/손가락으로 구동 — 손을 가볍게 만들어 속도·방열·배선을 모두 개선하는 방식
- 참고로 사람 손은 약 27 DOF — Tesla의 22 DOF는 그 약 80% 수준

## 3. 우리 시뮬레이션과의 비교

| 부위 | Tesla Optimus | fingershake-robot-main |
|---|---|---|
| 팔(편측) | 7 DOF (어깨3+팔꿈치1+손목3) | 6 DOF (어깨3+팔꿈치1+손목2, **Yaw 없음**) |
| 손(편측) | 22 DOF (손가락4×5+손목2) | 지오메트리는 15관절(5손가락×3마디)이지만 **실제 제어 가능한 값은 1개**(Finger Grip, 5손가락 전부 동시 이동) |
| 다리(편측) | 6 DOF | 지오메트리는 고관절·무릎·발목 다 있지만 **발목만 슬라이더 연결**, 1 DOF |
| 좌우 대칭 | 원래부터 양팔 독립 제어 | 이번 세션에서 왼팔을 오른팔에 거울 대칭으로 연결(직접 조작 슬라이더는 없음) |

## 4. 정직한 평가

가장 눈에 띄는 격차는 손이다. Tesla는 실물 하드웨어에서 손가락 1개당 4개의 독립 자유도를 텐던으로 구동해 사람 손의 80% 수준까지 접근했는데, 우리 시뮬레이션은 손가락 관절 지오메트리(MCP/PIP/DIP 3마디×5손가락)는 시각적으로 존재하지만 **애니메이션 로직상 전부 하나의 gripFactor 값에 종속**돼 있어 사실상 1 DOF로 동작한다. 이번 세션 초반에 발견하고 고친 "손가락 굽힘 방향 반전" 버그([[2026-08-11-moojoco-fingershake-curl-direction-bug-fix]])도 이 구조적 한계 안에서의 수정이었다 — 방향은 고쳤지만 손가락 각각을 독립적으로 제어하는 진짜 다자유도 그립은 여전히 없다.

손목도 마찬가지다. Tesla는 손목에 자체적으로 2 DOF(우리 기준 Yaw+Pitch 정도로 추정)를 두고 전완 자체도 회전축을 갖는 구조인데, 우리는 Wrist Pitch·Roll만 있고 **Yaw(좌우로 트는 축)가 아예 없다** — 이번 세션에서 손바닥 정렬(facing) 문제를 풀 때 몸통 Yaw까지 동원해야 했던 이유 중 하나가 바로 이 축의 부재일 가능성이 있다.

## 5. 다음 방향 (미구현)

1. 손목에 Yaw 축(`wristYaw`) 추가 — Tesla의 3-DOF 손목 구조를 참고해, 손바닥 정렬 문제를 손목 단독으로 풀 수 있는지 재검증
2. 손가락 5개를 독립적인 gripFactor로 분리(최소한 엄지 vs 나머지 4개라도) — 완전한 텐던 시뮬레이션은 과하지만, 최소 2-DOF 손 정도는 현실적
3. 다리 고관절·무릎도 슬라이더 연결 — 이미 지오메트리는 있으므로 발목과 같은 패턴으로 추가 가능

**Sources:**
- [Tesla Optimus Hardware: Actuators, Hands & Sensors (2026)](https://optimusk.blog/blog/tesla-optimus-hardware-specs/)
- [Tesla Optimus Gen 2 vs Gen 1: Full Specs & Comparison (2026)](https://optimusk.blog/blog/tesla-optimus-gen-2/)
- [Tesla Optimus Gen 3 Hands: 22-DoF, 50 Actuators Explained](https://www.basenor.com/blogs/news/tesla-optimus-gen-3-hands-22-dof-50-actuators-explained)
- [Tesla Optimus V3 Robot Hand Patent: Tendon-Driven Design with 4-DoF Fingers and 2-DoF Wrist](https://blockchain.news/ainews/tesla-optimus-v3-robot-hand-patent-tendon-driven-design-with-4-dof-fingers-and-2-dof-wrist-technical-analysis-and-2026-robotics-outlook)
- [Decoding Degrees of Freedom in Shipping Humanoid Robots](https://robotwale.com/article/degrees-of-freedom-humanoid-specs-comparisons)
"""

payload = {
    "slug": "2026-08-11-moojoco-tesla-optimus-dof-research",
    "title": "Tesla Optimus 관절 자유도(DOF) 조사 — 우리 시뮬레이션과의 격차",
    "author": "Moojoco",
    "abstract": (
        "Tesla Optimus의 관절 자유도를 조사했다: 전신 28 DOF(Gen 2 body), 팔 1개당 7 DOF(어깨3+팔꿈치1+손목3), "
        "손 1개당 22 DOF(Gen 3, 텐던구동, 손가락당 4 DOF, 액추에이터 25개는 전완 배치). 전신 합계(Gen3 손 포함) "
        "72+ DOF. 이를 fingershake-robot-main과 비교해 팔은 6 vs 7 DOF로 유사하지만 손목 Yaw축이 없고, 손가락은 "
        "지오메트리(15관절)는 있으나 실제 제어 가능한 자유도가 1개(Finger Grip 단일값)뿐이며, 다리도 발목만 "
        "연결돼 있다는 구조적 격차를 원본 비교 다이어그램과 함께 정리했다."
    ),
    "tags": ["handshake-robot", "kinematics", "literature-review", "moojoco", "tesla-optimus"],
    "changelog": "v1.0 — 최초 제출: Tesla Optimus DOF 조사, 우리 시뮬레이션과 팔/손/다리 비교표 및 다이어그램, 다음 개선 방향 제시",
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
