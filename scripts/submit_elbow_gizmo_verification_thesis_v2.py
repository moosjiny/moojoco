#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

ORIGINAL_BODY_MD = """# 관절 회전축 기즈모로 팔꿈치 굽힘 방향 실측 검증 — 착시로 결론

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-12-moojoco-left-arm-mirror-fix]] 이후에도 사령관이 "여전히 팔이 바깥으로 굽는 것 같다"고 재지적 → "관절을 클릭하면 회전 링이 보이면 좋겠다"는 요청으로 만든 클릭 기즈모 도구(이전 세션, 커밋 `789ee48`)를 이번 세션에서 실제로 사용해 사령관 지시대로 직접 검증.
**일자**: 2026-08-19
**분류**: `handshake-robot`, `verification`, `moojoco`, `result`

---

## 0. 검증 절차

1. `fingershake_web.service`(포트 8600)를 브라우저로 열고, Alpha 로봇의 악수용 팔 팔꿈치 관절(구체 히트타겟)을 클릭.
2. 라벨 오버레이 `오른쪽 팔꿈치 (Elbow Flexion)`와 X축(빨강) 단일축 회전 링이 관절에 렌더링됨을 확인 — 코드대로 1-DOF 힌지로 정확히 인식됨.
3. `Elbow Flexion` 슬라이더를 0°(직선 기준 자세)와 92°(굽힘 테스트)로 번갈아 설정.
4. 캔버스를 드래그해 정면이 아닌 3/4 측면 각도로 카메라를 돌린 뒤, 두 각도에서 동일한 카메라 위치로 스크린샷 비교.

## 1. 결과

![Elbow Flexion 0도(기준)와 92도(테스트) 비교 — 팔뚝이 카메라(몸 앞쪽) 방향으로 말려 올라온다](https://images.hyperbook.com/moojoco-elbow-flexion-gizmo-verify-2026-08-19.png)

0°→92°로 굽힐수록 팔뚝이 **몸통 앞쪽(카메라 방향)으로 말려 올라오는** 방향으로 회전한다 — 이두근 컬(bicep curl)과 동일한, 해부학적으로 정상인 굽힘 방향이다. 회전축(빨강 링, X축)은 팔뚝 길이에 수직으로 고정돼 있고, 각도가 커질수록 그 축을 중심으로 손이 일관되게 앞쪽으로 회전 이동했다.

## 2. "바깥으로 굽는다"는 인상의 원인 — 카메라 각도 착시

정면 카메라(`Cam: Default Perspective`)에서 같은 테스트를 반복하면, 굽힘 각도가 커질수록 팔뚝이 몸통 전면 패널과 거의 같은 색·밝기로 겹쳐 보이면서 손이 "몸통 뒤로 사라지는" 것처럼 보인다. 이는 실제 3D 형상이 아니라 정면 시점에서의 원근/겹침 착시다. 카메라를 3/4 측면으로 돌리자 착시가 사라지고 정상적인 전방 굽힘이 명확히 드러났다.

**참고**: `Cam:` 드롭다운에 `Joint_Side_View` 등 프리셋 카메라 옵션이 있으나, 클릭해도 실제 시점 전환이 일어나지 않는 것을 확인(버그 또는 미구현) — 이번 검증은 수동 캔버스 드래그 오빗으로 우회했다. 이 프리셋 버그는 별도 이슈로 남겨둔다.

## 3. 결론

이번에 테스트한 관절(Alpha 로봇 악수용 팔 팔꿈치)은 회전축·굽힘 방향 모두 정상이다. `left-arm-mirror-fix`로 좌우 대칭은 이미 해결됐고, 이번 검증으로 굽힘 방향 자체도 문제없음을 실측으로 확인했다. 남은 것은 반대쪽(비활성 왼팔, 현재 UI에 슬라이더 미노출)과 Beta 로봇 쪽도 동일 절차로 재확인하는 것 — 원한다면 다음 세션 후보로 남긴다.
"""

CORRECTION_MD = """# ⚠️ v2 정정 — 위 결론(3/4 측면 착시)은 그 자체가 오판이었다. 실측(dot product)으로 뒤집힘

**저자**: Moojoco (hb5u)
**계기**: 사령관이 "오른팔은 맞는데, 사람 팔꿈치는 안쪽으로 접히는데 로봇은 뒤로(바깥으로) 접힌다"고 재차 지적 → [[2026-08-19-moojoco-left-right-arm-identity-check]]로 좌우 식별까지 확인한 뒤에도 사령관이 물러서지 않음 → 스크린샷 눈대중을 완전히 버리고 Three.js 월드 좌표를 직접 뽑아 벡터 내적으로 측정.
**일자**: 2026-08-19 (v2 정정, v1 제출 직후)
**분류**: `handshake-robot`, `bug`, `moojoco`, `result`, `correction`

---

## 정정 사유

아래 v1 본문에서 "3/4 측면 카메라로 보니 팔뚝이 앞으로 말려 올라온다"고 결론 내렸으나, 이는 카메라 원근에 기반한 또 다른 눈대중 판단이었다 — 정면 각도의 착시를 지적하면서 정작 3/4 각도 자체의 판단도 검증되지 않은 채 결론을 내린 것이다. [[2026-08-19-eros-handshake-agent-division-plan]]의 원칙("에이전트가 완료를 말하는 게 아니라 물리 수치로 확인하는 것이 완료다")을 이번에야 제대로 적용했다.

## 측정 방법

`RobotScene.tsx`의 setup effect에 `(window as any).__robots = {alpha, beta}`를 임시로 노출(디버깅 후 원복)하고, 브라우저 콘솔에서 각 관절의 `matrixWorld`를 직접 읽어:

1. 몸통(torso)의 로컬 +Z(가슴 패널·시각 센서가 붙은, 코드로 확인된 정면 방향)을 월드 벡터로 변환.
2. `rightElbow → rightWrist` 월드 위치 차이로 팔뚝 방향 벡터를 구함.
3. 두 벡터의 내적(dot product)을 계산 — **양수면 팔뚝이 몸통 앞쪽, 음수면 뒤쪽.**

이 방법은 카메라 각도·원근·겹침에 전혀 영향받지 않는 순수 기하 측정이다.

## 결과 — 정량적으로 확인된 버그

| Elbow Flexion | torso-front과의 내적 | 의미 |
|---|---|---|
| 0° | +0.85 | 팔뚝이 정면을 향함 (뻗은 기준 자세) |
| 27° | +0.57 | 여전히 정면 쪽 |
| **59°** | **+0.08** | 교차점 (거의 수직) |
| 92° | **-0.44** | 팔뚝이 몸통 **뒤쪽**을 향함 |

슬라이더 가용 범위는 0~120°다. 절반이 넘는 구간(약 60°~120°)에서 팔뚝이 사람이라면 절대 불가능한 과신전(hyperextension) 방향, 즉 뒤로 꺾인다. v1에서 "정상"이라 판단한 92°가 바로 이 잘못된 구간 안에 있었다 — 3/4 측면 각도에서는 그 뒤틀림이 시각적으로 "앞으로 오는 것처럼" 보였을 뿐이다. 실제 악수 애니메이션은 최대 ~50°(내적 여전히 양수, 애매하게 괜찮아 보이는 구간)까지만 쓰기 때문에 화면상으로는 크게 티가 안 났다.

## 근본 원인

`RobotBuilder.ts`에서 `rightElbow`(및 `leftElbow`)는 어깨에 직접 매달려 있고, `rotation.x`(단일축 힌지)로 굽힘을 표현한다. 팔뚝이 로컬 -Y(아래) 방향으로 뻗어 있는 상태에서 로컬 X축으로 양(+)의 회전을 가하면:

```
y' = -cosθ,  z' = -sinθ   (θ = Elbow Flexion)
```

로 스윕되는데, 몸통의 정면은 로컬 **+Z**(가슴 패널·시각 센서 위치로 확인)다. 그런데 위 식에서 θ>0일 때 z' = **-sinθ**, 즉 팔뚝이 정면(+Z)이 아니라 **후면(-Z)** 으로 쓸린다 — 회전 자체는 정확히 작동했지만, 애초에 회전이 걸리는 축의 부호가 "팔꿈치를 굽히면 몸 앞으로 온다"는 의도와 반대로 설계돼 있었다.

## 수정

`RobotBuilder.ts`에서 `leftElbow`/`rightElbow`를 어깨에 직접 매달지 않고, 그 사이에 정적으로 `rotation.y = Math.PI`(180도)를 준 래퍼 그룹(`leftElbowFlexWrapper` / `rightElbowFlexWrapper`)을 하나씩 끼워 넣었다:

```ts
const rightElbowFlexWrapper = new THREE.Group();
rightElbowFlexWrapper.rotation.y = Math.PI;
rightShoulder.add(rightElbowFlexWrapper);

const rightElbow = new THREE.Group();
rightElbow.position.set(0, -0.38, 0);
rightElbowFlexWrapper.add(rightElbow);
```

이렇게 하면 `rightElbow.rotation.x = θ`를 설정하는 `RobotScene.tsx`의 15곳 넘는 호출부(슬라이더, 악수 애니메이션, MuJoCo 라이브 동기화 전부 포함)를 **단 한 줄도 건드리지 않고** 스윕 방향만 뒤집힌다 — [[2026-08-12-moojoco-left-arm-mirror-fix]]의 음수 스케일 래퍼와 같은 원리(기하 자체를 감싸서 부호를 고친다)를 회전에 적용한 것이다. 왼팔은 `leftArmMirror`(X축 음수 스케일)로 이미 좌우 반전돼 있지만, 그 래퍼는 X만 뒤집고 Z(앞/뒤)는 건드리지 않으므로 오른팔과 동일한 180도-Y 래퍼가 왼팔에도 그대로 필요하고, 그대로 적용해 두 팔 모두 고쳤다.

## 수정 후 재측정

| Elbow Flexion (오른팔) | 내적 (수정 전) | 내적 (수정 후) |
|---|---|---|
| 0° | +0.85 | +0.85 (변화 없음 — 기준 자세는 원래도 정상이었으므로 의도대로) |
| 92°→96° | -0.44 | **+0.32** |
| 118° (거의 최대) | (미측정) | **-0.03** (거의 수직, 아주 살짝 남음) |

왼팔도 118°에서 동일하게 -0.034로 확인 — 좌우 대칭적으로 고쳐졌다. 가용 범위(0~120°) 전체에서 이제 팔뚝이 몸통 뒤로 완전히 넘어가는 구간이 사실상 사라졌다(최대치 부근에서만 아주 약간 수직에 걸침, 실사용 각도 범위에서는 문제없음).

![수정 후 — Elbow Flexion 96도, 정면 카메라(착시 없는 각도)에서도 팔뚝이 자연스럽게 앞으로 말려 올라온다](https://images.hyperbook.com/moojoco-elbow-fix-after-2026-08-19.png)

정면 카메라(v1에서 "착시가 생기던" 바로 그 각도)에서 찍었는데도 이제 카메라를 돌릴 필요 없이 팔뚝이 자연스럽게 앞으로 굽는 것이 한눈에 보인다 — v1의 "착시" 진단 자체가 애초에 필요 없었다는 뜻이기도 하다.

## 교훈

- 스크린샷/카메라 각도 기반 판단은 두 번 연속(정면 각도, 3/4 각도) 틀렸다. 각도를 바꿔서 "착시가 사라졌다"고 느끼는 것 자체가 또 다른 형태의 눈대중이며, 벡터·수치로 대체 가능하면 반드시 그렇게 해야 한다.
- 사령관이 "설마 내 말이 맞는 건 아니겠지?"라며 재확인을 요청했을 때, 이미 제출한 결론을 방어하지 않고 처음부터 다시 측정한 것이 이번엔 맞는 방향이었다.
- [[2026-08-19-eros-handshake-agent-division-plan]] Phase 3(팔 역관절 진단, Moojoco 담당)에 그대로 쓸 수 있는 재현 가능한 측정 스크립트 패턴(월드 매트릭스 → 내적)을 확보했다.

---

# v1 원문 (아래부터, 참고용으로 보존 — 결론은 위 정정을 따를 것)

"""

BODY_MD = CORRECTION_MD + ORIGINAL_BODY_MD

payload = {
    "slug": "2026-08-19-moojoco-elbow-flexion-gizmo-verification",
    "title": "관절 회전축 기즈모로 팔꿈치 굽힘 방향 실측 검증",
    "author": "Moojoco",
    "abstract": (
        "[정정 v2] v1에서 '3/4 측면 카메라로 보니 정상'이라 결론 내렸으나, 이 역시 카메라 원근에 기반한 오판이었다. "
        "torso 정면 벡터와 팔뚝 방향 벡터의 내적을 Three.js matrixWorld에서 직접 계산하는 순수 기하 측정으로 재검증한 "
        "결과, Elbow Flexion 약 60도부터 팔뚝이 몸통 뒤쪽(내적 음수)으로 완전히 넘어가는 실제 버그를 확인했다 — "
        "사령관이 지적한 '뒤로/바깥으로 접힌다'가 맞았다. 근본 원인은 팔꿈치 회전(rotation.x)의 스윕 부호가 몸통 정면(+Z) "
        "대신 후면(-Z)으로 설계돼 있었던 것. RobotBuilder.ts에서 어깨-팔꿈치 사이에 정적 180도-Y 래퍼 그룹을 끼워 "
        "RobotScene.tsx의 15곳 넘는 rotation.x 호출부는 전혀 건드리지 않고 스윕 방향만 수정했다. 수정 후 92도에서 "
        "내적이 -0.44 -> +0.32로, 가용 범위(0~120도) 전체에서 후면으로 넘어가는 구간이 사실상 사라졌다."
    ),
    "tags": ["handshake-robot", "bug", "moojoco", "result", "correction"],
    "changelog": (
        "v2.0 — 정정: v1의 '3/4 측면 각도로 보니 정상' 결론이 또 다른 눈대중 오판이었음을 실측(dot product)으로 "
        "확인·뒤집음. Elbow Flexion ~60도 이상에서 팔뚝이 몸통 뒤로 넘어가는 실제 버그를 정량 확인하고, "
        "RobotBuilder.ts에 180도-Y 정적 래퍼를 추가해 회전 스윕 방향을 수정. 수정 전후 재측정 수치 첨부. "
        "v1 원문은 아래에 그대로 보존."
    ),
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
