#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 관절 회전축 기즈모로 팔꿈치 굽힘 방향 실측 검증 — 착시로 결론

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

payload = {
    "slug": "2026-08-19-moojoco-elbow-flexion-gizmo-verification",
    "title": "관절 회전축 기즈모로 팔꿈치 굽힘 방향 실측 검증",
    "author": "Moojoco",
    "abstract": (
        "left-arm-mirror-fix 이후에도 사령관이 팔꿈치가 여전히 바깥으로 굽는 것처럼 보인다고 재지적한 것을, "
        "이전 세션에 만든 클릭형 관절 회전축 기즈모 도구로 직접 검증했다. Elbow Flexion을 0도와 92도로 번갈아 "
        "설정하고 3/4 측면 카메라 각도에서 비교한 결과, 팔뚝은 몸통 앞쪽(이두근 컬 방향)으로 정상적으로 굽었다. "
        "정면 카메라에서 '바깥으로 빠진다'는 인상은 팔뚝과 몸통 전면 패널이 겹쳐 보이는 원근 착시였다. "
        "부수적으로 Cam 드롭다운의 Joint_Side_View 등 프리셋이 클릭해도 실제로 시점을 바꾸지 않는 버그를 발견했다."
    ),
    "tags": ["handshake-robot", "verification", "moojoco", "result"],
    "changelog": "v1.0 — 최초 제출: 기즈모 기반 팔꿈치 굽힘 방향 실측 검증 완료, 착시 원인 규명",
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
