#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 접촉 동역학 3단계 — 옵션 A/B 비교 분석 (결정 전 기록)

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-contact-dynamics-plan]]에서 3단계(진짜 강체 동역학)를 옵션 A(클라이언트 JS 물리엔진)/옵션 B(MuJoCo 백엔드 연동) 두 갈래로 남기고 "아키텍처 결정이 필요해 사령관 판단을 기다린다"고 보류했었다. 사령관 지시 — "3단계 옵션 A/B 중 뭐가 나을지 정리해줘. 이걸 thesis에 먼저 기록해줘." **이 문서는 비교 분석과 권고만 다룬다 — 아직 어느 쪽도 착수하지 않았다.**
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `moojoco`, `plan`, `decision`

---

## 0. 비교표

| 항목 | A. 클라이언트 JS 물리엔진 (rapier3d / cannon-es) | B. MuJoCo 백엔드 연동 |
|---|---|---|
| 정확도 | 범용 게임 물리엔진 수준 — 접촉·마찰은 실제로 풀리지만 로보틱스급 정밀도는 아님 | MuJoCo 솔버 — 접촉·마찰·강체 동역학에 특화, 훨씬 정확 |
| 초기 비용 | npm install 하나로 시작 가능, 백엔드 불필요, 기존 React 앱 안에서 완결 | Python/MuJoCo 서버 신설 + WebSocket 스트리밍 + 21개 슬라이더↔액추에이터 매핑 필요 — 아키텍처 자체가 확장됨(정적 사이트 → 서버 방식) |
| 튜닝 비용 | 관절 20여 개의 질량·관성·마찰계수 + PD 게인 튜닝 필요. 게인이 안 맞으면 로봇이 발작하듯 떨리거나 발산하는 게 흔한 실패 패턴 — 별도의 반복 튜닝 작업 | MJCF 모델만 정확히 만들면 튜닝 부담이 상대적으로 적음(솔버 자체가 이미 검증돼 있음) |
| 재사용성 | 이 `fingershake-robot-main` 토이 프로젝트 전용 — 튜닝 결과가 `dual_arms` 본업에 재사용되지 않음 | `dual_arms`의 실제 MuJoCo 작업(EGL GPU 렌더링, mj_step 동역학)과 같은 축 — 여기서 얻는 경험(MJCF 모델링, 액추에이터 매핑, 실시간 스트리밍)이 본업에 직결 |
| 사령관 실제 임무와의 정합성 | 무관 | hb5u CLAUDE.md에 이미 "다음 단계 후보 1: actuator 토크 제어(mj_step 기반 동역학)"로 명시돼 있음 — 사실상 Moojoco 본업의 연장 |

## 1. 권고

**B(MuJoCo 백엔드)를 추천한다.** 근거는 정확도가 아니라 "투입한 노력이 어디에 재사용되는가"다 — A를 골라 20개 관절을 튜닝하면 그 결과는 이 handshake 토이 안에서만 쓰이고 끝나지만, B를 고르면 그 과정(MJCF 모델링·액추에이터 매핑·실시간 스트리밍)이 hb5u의 실제 본업인 `dual_arms` MuJoCo 작업과 직접 겹친다. 두 물리 근사(Three.js 쪽 fake, MuJoCo 쪽 real)를 따로 유지·보수하는 비용도 피할 수 있다.

다만 B는 아키텍처가 확실히 커진다 — 정적 사이트에서 서버 방식으로 배포 구조 자체가 바뀌고, 지금 당장 눈에 보이는 결과를 원한다면 A가 훨씬 빠르다. 이 트레이드오프는 정확도·재사용성 대 속도·단순성의 문제이지, 어느 한쪽이 명백히 우월한 것은 아니다.

## 2. 결정 상태

이 문서 작성 시점까지 **어느 옵션도 착수하지 않았다.** 사령관 승인 후 실제 작업이 시작되면 각 옵션에 맞는 계획(A라면 rapier3d/cannon-es 도입 계획, B라면 MJCF 모델·스트리밍 프로토콜 설계 계획)을 별도 thesis로 남기고, 지금까지의 관례대로 계획→구현→실측→배포 순서를 따른다.
"""

payload = {
    "slug": "2026-08-12-moojoco-stage3-option-comparison",
    "title": "접촉 동역학 3단계 — 옵션 A/B 비교 분석 (결정 전 기록)",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-contact-dynamics-plan]]에서 보류했던 3단계(진짜 강체 동역학) 옵션 A(클라이언트 "
        "JS 물리엔진, rapier3d/cannon-es)와 옵션 B(MuJoCo 백엔드 연동)를 정확도·초기비용·튜닝비용·재사용성· "
        "사령관 실제 임무와의 정합성 다섯 축으로 비교했다. B를 권고했다 — 정확도 자체보다, B에 투입하는 노력"
        "(MJCF 모델링, 액추에이터 매핑, 실시간 스트리밍)이 hb5u의 실제 본업인 dual_arms MuJoCo 작업과 직접 "
        "겹친다는 점이 근거다. 다만 B는 정적 사이트를 서버 방식으로 바꿔야 해 아키텍처 스코프가 A보다 확실히 "
        "크다는 트레이드오프도 함께 남겼다. 이 문서 작성 시점까지 어느 옵션도 착수하지 않았다."
    ),
    "tags": ["handshake-robot", "physics", "moojoco", "plan", "decision"],
    "changelog": "v1.0 — 최초 제출: 옵션 A/B 비교 분석 및 B 권고 (결정 전 기록, 미착수)",
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
