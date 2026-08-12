#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 해부학적으로 대칭인 팔 객체 탐색 — dual_arms 프로젝트 안에 이미 정답이 있었다

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-left-arm-elbow-asymmetry-bug]] 기록 직후 사령관 질문 — "객체지향적으로 만들어져다면, 부품의 내부 변수는 대칭구조로 만들어졌어야 해... 그렇게 만들어진 객체가 있는지 확인해줘. 실제 로봇팔이라면 동일하게 진행할 수 있어."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `research`, `moojoco`

---

## 0. 질문의 핵심

사령관의 주장을 정확히 옮기면: 팔이 "어깨-팔꿈치-손목"처럼 해부학적 명칭 구조로 제대로 캡슐화돼 있다면, 왼팔은 오른팔과 **똑같은 정의**를 좌우 반전해서 "붙이기만" 해도 굽힘 방향이 저절로 맞아야 한다. 이게 실제 로봇 팔(하드웨어)이라면 기구학적으로 당연히 성립해야 하는 원칙이다. `fingershake-robot-main`의 `RobotBuilder.ts`가 이 원칙을 안 지켜서 [[2026-08-12-moojoco-left-arm-elbow-asymmetry-bug]] 버그가 난 것 아니냐는 질문이었다.

`dual_arms` 프로젝트 전체를 검색해 실제로 그렇게 만들어진 객체가 있는지 확인했다.

## 1. 찾은 것 — `dual_openarm.urdf` / `dual_openarm_handshake.xml`이 정확히 그 패턴이다

**같은 조인트를 좌우 완전 대칭으로 정의**하고 있다 (URDF 원본 기준):

```
left_joint_2:  origin xyz="-0.0301 0 0.06"   axis="-1 0 0"
right_joint_2: origin xyz=" 0.0301 0 0.06"   axis=" 1 0 0"

left_joint_3:  origin xyz=" 0.0301 0 0.06625"  axis="0 0 1"
right_joint_3: origin xyz="-0.0301 0 0.06625"  axis="0 0 1"
```

관절 7개 전체를 대조한 결과, **origin의 X성분은 관절마다 전부 부호가 반대**(정확한 위치 거울 반전)이고, **axis는 joint_2 하나만 부호가 반대**(joint_1,3,4,5,6,7은 축 자체가 이미 대칭적이라 안 뒤집어도 됨)다. 메시(mesh)도 같은 원칙으로 처리됐다 — `link1/link2/link3`는 원본 그대로, `link11/link21/link31`은 **동일 STL 파일을 scale="-0.001 0.001 0.001"로 X축만 반전**해서 만든 거울 복제본이고, 오른팔이 이 거울 복제 메시를 쓴다.

즉 **같은 관절 각도 값을 좌우 조인트에 그대로 보내면 저절로 거울상으로 움직인다** — 사령관이 말한 정확한 그 성질이다. 실제로 B-4에서 MuJoCo Live를 오른팔에 연동했을 때 별도 보정 없이 바로 잘 동작했던 것도 이 URDF가 이미 올바르게 설계돼 있었기 때문이다(단지 왼팔은 아직 연동을 안 했을 뿐).

## 2. 반례 — "prefix/side 매개변수화"만으로는 부족하다

`urdf/dual_open_manipulator_p.urdf.xacro`에서 또 다른 시도를 발견했다:

```xml
<xacro:macro name="open_manipulator_p" params="prefix parent side">
  ...
  <joint name="${prefix}_base_joint" ...>
    <origin xyz="0 ${side * 0.25} 0.01" rpy="0 0 0"/>
  </joint>
  <joint name="${prefix}_joint2" ...>
    <axis xyz="0 1 0"/>   <!-- 고정값, side 매개변수 미사용 -->
  </joint>
  ...
</xacro:macro>
<xacro:open_manipulator_p prefix="left" side="1"/>
<xacro:open_manipulator_p prefix="right" side="-1"/>
```

`prefix`/`side` 매개변수로 좌우를 인스턴스화하는 구조 자체는 객체지향적으로 깔끔하다 — 그런데 **관절 축(axis)이 전부 고정값이고 `side`를 전혀 참조하지 않는다.** 위치(origin)만 `side`로 평행이동될 뿐, 회전축은 거울 반전되지 않는다. 이 macro를 지금 그대로 썼다면 `RobotBuilder.ts`와 똑같은 버그가 났을 것이다 — **"매개변수화된 구조"가 있다고 저절로 대칭이 되는 게 아니라, 위치뿐 아니라 축(axis)까지 좌우에 맞게 반전해야 진짜로 대칭이 된다**는 걸 보여주는 좋은 반례다.

## 3. `fingershake-robot-main` 자체에서도 부분적 증거 발견

`RobotBuilder.ts`의 다리(leg)는 `createLeg(xSide: number)` 하나의 함수로 양쪽 다리를 만든다(`createLeg(-1)`, `createLeg(1)`) — 매개변수화된 빌더가 이미 존재한다. 다만 다리는 고관절/무릎/발목이 전부 단일 축(pitch)만 쓰기 때문에 애초에 좌우 축 반전이 필요 없는 쉬운 경우였다. 반면 팔은 어깨가 3축(pitch/yaw/roll)인데, `buildBipedalRobot` 안에서 왼팔/오른팔이 **함수 재사용 없이 완전히 따로 하드코딩**돼 있고, 기본값의 Yaw/Roll 부호만 손으로 반대로 넣어 흉내만 냈다(팔꿈치 축은 반전 안 함) — 이게 정확히 지금 버그의 위치다.

## 4. 결론

사령관의 가설이 맞았다. `dual_arms` 프로젝트 안에 이미 "해부학적으로 올바르게 대칭 설계된 팔"이 존재한다 — `dual_openarm.urdf`/`dual_openarm_handshake.xml`이다. 이건 실제 로봇 팔의 기구학 정의이므로, 두 팔이 정확한 거울상이 아니면애초에 하드웨어가 동작하지 않는다(그래서 정확했다). `fingershake-robot-main`의 `RobotBuilder.ts`는 이 정답을 참고하지 않고 시각적 근사만으로 손으로 만들어져서 버그가 났다.

**실용적 함의**: [[2026-08-12-moojoco-left-arm-elbow-asymmetry-bug]]에서 제안했던 `buildDexArm(isRight)` 리팩터링을 할 때, 이 URDF의 관절별 origin/axis 부호 패턴(joint_2만 축 반전, 나머지는 위치만 반전)을 그대로 참고하면 시행착오 없이 정확한 거울 구조를 만들 수 있다. 또는 더 근본적으로는, 왼팔도 오른팔처럼 언젠가 MuJoCo Live로 연동하면(B-5-5 이후 후보) 이 URDF가 이미 정답을 갖고 있으므로 프론트엔드의 손으로 만든 회전 로직 자체가 필요 없어질 수도 있다.
"""

payload = {
    "slug": "2026-08-12-moojoco-anatomical-symmetric-arm-search",
    "title": "해부학적으로 대칭인 팔 객체 탐색",
    "author": "Moojoco",
    "abstract": (
        "왼팔 팔꿈치 비대칭 버그 기록 후, 사령관이 '해부학적으로 대칭 구조로 설계된 팔 객체가 이 프로젝트 안에 "
        "있는지' 검색을 요청했다. dual_arms의 dual_openarm.urdf/dual_openarm_handshake.xml에서 정확히 그런 "
        "설계를 발견했다 — 관절 7개 전체가 origin의 X성분을 좌우 완전히 반전하고, 관절 축(axis)은 joint_2 "
        "하나만 반전(나머지는 원래 대칭적이라 불필요), 메시도 동일 STL을 X축만 반전한 거울 복제본을 쓴다. 같은 "
        "관절 각도 값을 좌우에 그대로 보내면 저절로 거울상으로 움직이는 진짜 대칭 구조다. 반면 "
        "dual_open_manipulator_p.urdf.xacro는 prefix/side 매개변수로 좌우를 인스턴스화하는 깔끔한 구조를 "
        "갖고 있지만 관절 축이 고정값이라 side를 반영하지 않아 위치만 반전되고 축은 안 뒤집힌다 — 매개변수화된 "
        "구조만으로는 부족하고 축까지 반전해야 진짜 대칭이 된다는 반례다. fingershake-robot-main의 "
        "RobotBuilder.ts는 다리(createLeg(xSide))는 매개변수화됐지만 팔은 완전히 하드코딩돼 있어 버그의 "
        "원인이 됐다. 사령관 가설이 맞았고, dual_openarm.urdf가 향후 리팩터링의 정답 참고자료가 될 수 있다."
    ),
    "tags": ["handshake-robot", "research", "moojoco"],
    "changelog": "v1.0 — 최초 제출: 대칭 팔 객체 탐색 결과, dual_openarm.urdf가 올바른 참고 예시임을 확인",
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
