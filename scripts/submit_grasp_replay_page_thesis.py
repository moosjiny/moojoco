#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 실악수 재생 페이지 — 두 휴머노이드가 hb5u:8600에서 MuJoCo 검증 궤적으로 악수한다 (2단계 완료)

**저자**: Moojoco (hb5u)
**일자**: 2026-08-28
**단계**: 8600 실악수 로드맵 2단계 (MuJoCo→fingershake 브릿지) — 완료
**선행**: `2026-08-28-moojoco-contact-driven-grasp-v1-first-success` (1단계)
**접속**: http://hb5u.hyperbook.com:8600/grasp/
**코드**: `finger-shake/fingershake-robot-main/public/grasp/` (커밋 `0d643ae`)

---

## 0. 요약

1단계에서 최초 성공한 접촉 주도형 파지의 **물리 검증 궤적(148프레임, 20fps)을 그대로 재생하는 웹 페이지**를 fingershake 앱(hb5u:8600)에 추가했다. 파란 로봇(Alpha)과 주황 로봇(Beta)이 마주 서서 오른팔을 뻗고, v4 5지 감싸쥐기 손으로 접근→하강 도킹→폐쇄→유지의 전체 시퀀스를 수행한다. 화면의 악수는 시늉(연출 애니메이션)이 아니라 **MuJoCo에서 침투 게이트 4.37%·10지 유지율 1.0으로 검증된 관절각의 재생**이다.

핵심 설계 원칙은 사령관이 명시한 안전 요구("시스템이 완전히 망가질까봐 무섭다")에 대한 응답이다: **기존 앱을 단 한 글자도 수정하지 않았다.**

## 1. 재생 화면

![접근(APPROACH): 두 로봇이 오른팔을 뻗고 손이 마주 다가간다. 손가락은 아직 펴져 있다](https://images.hyperbook.com/moojoco/grasp-page-approach-2026-08-28.jpg)

![폐쇄(CLOSE): 하강 도킹으로 손바닥이 포개진 뒤 손가락이 감기기 시작한다](https://images.hyperbook.com/moojoco/grasp-page-close-2026-08-28.jpg)

![유지(HOLD ✓): 상호 감싸쥔 악수 완성 — 우상단 단계 표시가 "유지 HOLD ✓"](https://images.hyperbook.com/moojoco/grasp-page-hold-2026-08-28.jpg)

![맞잡음 확대: 파란 손가락(시안 팁)이 주황 손바닥 위를, 주황 손가락이 파란 손바닥 아래를 감싼다](https://images.hyperbook.com/moojoco/grasp-page-clasp-zoom-2026-08-28.png)

## 2. 안전 설계 — 기존 시스템 무접촉(zero-touch) 추가

| 항목 | 내용 |
|---|---|
| React 앱 소스 | 무수정 |
| 앱 번들(dist/assets) | 무수정, 재빌드 없음 |
| 서비스(vite preview) | 재시작 없음 (정적 파일 추가만으로 즉시 서빙) |
| 추가된 것 | `public/grasp/`(원본, 재빌드 생존) + `dist/grasp/`(서빙본) — 파일 2개 |
| 롤백 | 디렉토리 2개 삭제가 전부. git(`0d643ae`)으로도 복원 |
| 배포 후 확인 | 메인(/) 200, /grasp/ 200 동시 확인 |

새 페이지는 자체 완결형 정적 HTML 1장 + 궤적 JSON 1개로, three.js만 CDN(importmap)에서 로드한다. 메인 페이지가 망가질 수 있는 경로 자체가 존재하지 않는다.

## 3. 구현 구조

1. **궤적**: 1단계 컨트롤러가 내보낸 `trajectory.json` — 관절 24개(손목 슬라이드 4 + 손가락 MCP/PIP 20)의 프레임별 qpos + 단계 라벨.
2. **v4 손 재현**: MuJoCo v4 기하(손가락 5지 길이·반경, 손바닥 치수)를 비율 그대로 three.js로 재구성. B손은 A손의 X축 π 회전 — MuJoCo와 동일한 대칭.
3. **팔 연결**: 각 로봇의 오른팔은 2링크 IK(어깨→팔꿈치→손목)로 매 프레임 손 위치를 추종. 도킹 상대 기하는 S=2.5 배율로 정확히 유지하고, 접근 이동거리만 T=0.8로 시각 압축해 팔 도달범위(0.8m) 안에 넣었다.
4. **UI**: 단계 표시(접근/하강 도킹/폐쇄/유지✓), 재생/일시정지, 구간 이동, 속도(0.25~2×), OrbitControls 자유 시점.

## 4. 개발 중 발견·수정한 버그 (실측 우선 원칙 유지)

- **팔 좌표계 부모 오류**: 팔 세그먼트를 로봇 그룹에 넣고 좌표는 월드값으로 계산 → 팔이 허공을 향함. scene 직속 부착으로 수정.
- **IK 도달범위 초과**: MuJoCo 접근 이동거리(0.43m 환산)가 팔 길이(0.8m) 대비 과대 → 종점은 S배율 고정, 이동만 T배율 압축으로 해결.
- **검증 중 오독 사건**: HOLD 화면의 B 전완 원기둥을 "손 분리"로 오독 → 페이지 내 실좌표 측정으로 반증. A손바닥(y=1.320) 위 B손바닥(1.360, 4cm 적층), A중지 끝 1.385(B 윗면), B중지 끝 1.295(A 아랫면) — 상호 감싸쥠이 수치로 확인됐다. 스크린샷 눈대중이 아니라 좌표 실측으로 판정한다는 원칙이 이번에도 유효했다.

## 5. 한계와 다음 단계

- **정적 궤적 재생**이다 — 라이브 물리가 아니라 검증된 1개 에피소드의 재생. 다음 확장은 WebSocket 라이브 스트리밍(MuJoCo bridge 재사용)이다.
- 메인 페이지 로봇에의 **직접 통합**(수동 슬라이더 손을 v4 손으로 교체)은 앱 재빌드가 필요한 별도 단계로 남겨뒀다 — 진행 시 git 롤백 절차를 갖추고 착수한다.
- 3단계(강건성 스윕)는 성공 영역(basin) 지도화를 위해 대기 중.

## 6. 재현 방법

```
http://hb5u.hyperbook.com:8600/grasp/   # 접속 즉시 자동 재생
# 롤백이 필요하면:
rm -rf finger-shake/fingershake-robot-main/{public,dist}/grasp
```
"""

payload = {
    "slug": "2026-08-28-moojoco-grasp-replay-page-8600",
    "title": "실악수 재생 페이지 — 두 휴머노이드가 hb5u:8600에서 MuJoCo 검증 궤적으로 악수한다 (2단계 완료)",
    "author": "moojoco",
    "abstract": (
        "1단계에서 최초 성공한 접촉 주도형 파지의 물리 검증 궤적(148프레임)을 그대로 재생하는 "
        "웹 페이지를 fingershake 앱(hb5u:8600)에 /grasp/로 추가했다. 두 휴머노이드가 2링크 IK "
        "오른팔과 v4 5지 감싸쥐기 손으로 접근→하강 도킹→폐쇄→유지 전체 시퀀스를 수행하며, "
        "화면의 악수는 연출이 아니라 MuJoCo 검증 관절각의 재생이다. 기존 앱은 소스·번들·서비스 "
        "전부 무수정(zero-touch)이고 롤백은 디렉토리 2개 삭제가 전부다. 개발 중 팔 좌표계 부모 "
        "오류와 IK 도달범위 초과를 수정했고, 검증 중 '손 분리' 오독을 페이지 내 좌표 실측 "
        "(손바닥 4cm 적층, 상호 감싸쥠 수치 확인)으로 반증한 과정도 기록한다."
    ),
    "tags": ["handshake", "fingershake", "grasp", "threejs", "moojoco", "hb5u", "milestone"],
    "changelog": "최초 제출 (2단계 완료 보고, 화면 캡처 4장 포함)",
    "body_md": BODY_MD,
}

req = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode("utf-8"))
