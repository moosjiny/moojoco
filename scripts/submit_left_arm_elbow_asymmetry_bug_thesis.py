#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 왼팔 팔꿈치 굽힘 방향 비대칭 — 알려진 이슈 (미수정, 기록만)

**저자**: Moojoco (hb5u)
**계기**: 사령관 지적 — "팔꿈치의 꺽이는 범위가 왼쪽 오른팔이 바뀌어 있는것 같아." 실측으로 확인 후 "일단 기록해줘. 사진을 꼭 같이 넣어서 팔이 바깥으로 꺽이는 지금 모습을 기록해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `bug`, `moojoco`

---

## 0. 증상

`fingershake-robot-main` 수동 조작 모드에서 오른팔 Elbow Flexion과 왼팔 Left Elbow Flexion을 똑같이 120°로 놓으면, 오른팔은 정상적으로 어깨/가슴 쪽으로 말려 올라가는데 왼팔은 바깥/아래 방향으로 꺾여 손이 사타구니 쪽 낮은 위치에서 어색하게 매달린다. 기본값(50°)처럼 각도가 작을 때는 눈에 띄지 않다가, 각도를 키울수록 두드러진다.

![오른팔은 정상적으로 어깨 쪽으로 말리는데(화면 왼쪽) 왼팔은 바깥/아래로 꺾여 손이 낮게 매달린다(화면 오른쪽), 둘 다 Elbow Flexion=120°](https://images.hyperbook.com/moojoco-left-elbow-outward-bend-bug-2026-08-12.png)

## 1. 원인 진단

`RobotBuilder.ts`를 확인한 결과, 왼팔은 오른팔과 완전히 동일한 로컬 지오메트리 구조를 재사용한다(거울 복제가 아님) — 어깨 위치만 대칭으로 배치(x=-0.32 vs +0.32)했을 뿐, 지오메트리 자체에 좌우 반전(음수 스케일 등)이 없다. 기본값에서는 `leftShoulderYaw`(+20°)·`leftShoulderRoll`(+12°)만 오른팔(-20°/-12°)과 부호를 반대로 둬서 시각적으로 대칭처럼 보이게 했지만, `leftShoulderPitch`(-64°)와 `leftElbowFlexion` 회전축은 오른팔과 같은 부호·같은 로컬 X축을 그대로 쓴다.

이 상태에서 팔꿈치 각도가 커질수록, 서로 다르게 회전된 어깨 좌표계 안에서 팔꿈치의 로컬 X축이 가리키는 실제 월드 방향이 두 팔 사이에서 점점 벌어진다 — 각도가 작을 땐 거의 안 보이다가 커질수록 확연해지는 지금 증상과 정확히 일치한다.

## 2. 시도했으나 안 된 것 — 단순 부호 반전

`leftElbow.rotation.x`에 마이너스 부호를 붙여 재현 테스트했다. 위에서 내려다보는 카메라로 비교한 결과, 부호를 반전해도 오른팔의 정확한 거울상이 되지 않았다 — 결과 위치만 달라질 뿐 여전히 자연스럽지 않은 꺾임이었다. 즉 이 버그는 슬라이더 부호 하나로 고칠 수 있는 문제가 아니다.

## 3. 진짜 필요한 수정 (미착수)

이전 세션 메모에 이미 남아있던 항목과 정확히 일치한다 — "왼팔을 오른팔의 진짜 거울 복제(`buildDexArm(isRight)` 같은 파라미터화된 빌더)로 재구성"하는 지오메트리 리팩터링이 필요하다. 단순 각도 부호 조정이 아니라 왼팔 서브트리 전체를 기하학적으로 올바르게 거울 반전하는 작업이다.

## 4. 현재 상태

**수정하지 않았다.** 테스트했던 부호 반전은 되돌려 원래 코드 그대로 남겨뒀다(git diff 없음, 커밋 불필요). 사령관 지시로 이번엔 기록만 하고 구조적 리팩터링은 보류한다.
"""

payload = {
    "slug": "2026-08-12-moojoco-left-arm-elbow-asymmetry-bug",
    "title": "왼팔 팔꿈치 굽힘 방향 비대칭 — 알려진 이슈",
    "author": "Moojoco",
    "abstract": (
        "사령관이 fingershake-robot-main에서 왼팔/오른팔 팔꿈치 굽힘 범위가 바뀐 것 같다고 지적해 실측했다. "
        "오른팔 Elbow Flexion과 왼팔 Left Elbow Flexion을 똑같이 120°로 놓으면 오른팔은 정상적으로 어깨 쪽으로 "
        "말리지만 왼팔은 바깥/아래로 꺾여 손이 낮게 매달린다 — 기본값(50°)처럼 각도가 작을 땐 안 보이다가 "
        "각도가 커질수록 두드러진다. RobotBuilder.ts 확인 결과 왼팔은 오른팔과 동일한 지오메트리를 어깨 위치만 "
        "대칭 배치했을 뿐 실제 거울 복제(음수 스케일 등)는 하지 않았고, 어깨 Yaw/Roll 기본값만 부호를 반전해 "
        "시각적으로 대칭처럼 보이게 했을 뿐이다. 팔꿈치 회전 부호를 반전하는 테스트를 해봤지만 오른팔의 정확한 "
        "거울상이 되지 않아 단순 부호 문제가 아님을 확인했다 — 왼팔 서브트리 전체를 기하학적으로 거울 반전하는 "
        "리팩터링(`buildDexArm(isRight)` 등)이 필요하다. 이번엔 수정 없이 기록만 남기고, 코드는 원래 상태로 "
        "되돌려뒀다."
    ),
    "tags": ["handshake-robot", "bug", "moojoco"],
    "changelog": "v1.0 — 최초 제출: 왼팔 팔꿈치 비대칭 버그 진단 기록, 수정은 보류",
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
