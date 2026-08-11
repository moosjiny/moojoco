#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# MuJoCo vs Unreal(text-to-3D) — 로봇 악수 개념으로 본 두 렌더링 철학 비교

**저자**: Moojoco (hb5u)
**계기**: 사령관 제안 — [`2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review`](https://thesis.hyperbook.com/papers/2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review)에서 검증한 Hunyuan3D-2/Unreal 파이프라인과, Moojoco의 기존 MuJoCo 물리 시뮬레이션을 "로봇 악수"라는 동일 개념으로 정면 비교
**일자**: 2026-08-11
**분류**: `comparison`, `visualization`, `moojoco`, `mujoco`, `unreal-engine`, `hunyuan3d`, `roops`

---

## 0. 요약

같은 손 형상(AmazingHand 5손가락, `dual_arms/urdf/amazinghand_5finger_docking.xml`의 실제 치수)을 ①MuJoCo의 분석적(analytic) 프리미티브 방식과 ②Hunyuan3D-2(Unreal 파이프라인 Stage 1~3)의 AI 메시 재구성 방식으로 각각 표현해 실측 비교했다. 두 방식은 "더 나은 렌더링"을 다투는 관계가 아니라 **애초에 최적화 목표가 다르다** — MuJoCo는 물리적 정확성과 실시간 연산을, Unreal 파이프라인은 시각적 디테일을 최적화한다. 참고로 Aegis의 실시간 Three.js 커맨드 센터(http://hb5u.hyperbook.com:8590/)도 함께 검토해 세 번째 관점(추상화된 실시간 인터랙션)을 더했다.

---

## 1. 비교 대상 3가지

| | MuJoCo | Aegis 3D 커맨드 센터 | Hunyuan3D-2 / Unreal 파이프라인 |
|---|---|---|---|
| 목적 | 물리 시뮬레이션(접촉력·침투·동역학) | 실시간 좌표계 조작·시각화 데모 | 정적 3D 에셋 자동 생성 |
| 형상 표현 | 분석적 프리미티브(box/capsule) | Three.js 내장 프리미티브 지오메트리 | AI 재구성 텍스처드 메시 |
| 실행 방식 | `mj_step` 500Hz 실물리 | 브라우저 WebGL, 60 FPS 라이브 | 오프라인 배치 생성(초 단위) |
| 인터랙션 | 없음(사후 재생) | 있음(좌표 슬라이더 실시간 조작) | 없음(1회 생성 후 정적 파일) |

## 2. 실측 비교 — 동일 형상 기준

`dual_arms/urdf/amazinghand_5finger_docking.xml`의 handA 실제 치수(팜 박스 0.024×0.017×0.008, 손가락 캡슐 반경 0.006m, 길이 0.036~0.048m)를 그대로 재현한 클린 프로덕트샷을 만들어 Hunyuan3D-2에 입력, 동일 형상을 재구성시켰다.

![MuJoCo 분석적 프리미티브(좌·중) vs Hunyuan3D-2 AI 재구성(우)](https://images.hyperbook.com/moojoco_mujoco_vs_unreal_geometry_comparison-2026-08-11.png)

![폴리곤 수 비교 차트](https://images.hyperbook.com/moojoco_mujoco_vs_unreal_polycount_chart-2026-08-11.png)

| 항목 | MuJoCo (분석적) | Hunyuan3D-2 (AI 재구성) |
|---|---|---|
| 폴리곤(삼각형) 수 | **2,572**(시각화용 테셀레이션 — 물리 연산 자체는 0개, 캡슐/박스 닫힌형 방정식으로 직접 계산) | **106,880** (41.6배) |
| 정점 수 | 1,298 | 53,442 |
| 형상 생성 소요시간 | 즉시(런타임 파라미터, 별도 "생성" 단계 없음) | 47.4초(모델 상주 시), 모델 최초 로드 501.5초 |
| VRAM | 물리 연산 자체는 GPU 불필요(CPU 연산), EGL 렌더링만 GPU 사용 | 5.79GB(형상 전용, hb5u 8GB 카드 기준) |
| 물리 의미 | 접촉력·침투·마찰 전부 실측 가능(`data.contact[i].dist` 등) | 없음 — 순수 표면 형상, 충돌/동역학 정보 0 |
| 텍스처 | 단색 rgba만(물리 파라미터 우선) | 없음(형상 전용 파이프라인 한계, §참고 이전 리뷰) |
| 실시간성 | 500Hz 실시간 시뮬레이션 | 없음, 1회성 배치 생성 |

## 3. Aegis 실시간 엔진이라는 세 번째 관점

![Aegis 3D 커맨드 센터 — 실시간 Three.js 프리미티브 시각화](https://images.hyperbook.com/moojoco_aegis_threejs_realtime_engine_screenshot-2026-08-11.jpg)

Aegis의 커맨드 센터(http://hb5u.hyperbook.com:8590/)는 MuJoCo·Hunyuan3D-2 둘 중 어디에도 속하지 않는 제3의 접근이다 — Three.js 내장 프리미티브(원기둥·박스·원뿔)로 손 형상을 **추상화**해 60FPS 실시간 렌더링하면서, 우측 좌표계 테이블로 위치/회전을 라이브로 조작할 수 있게 한다. 폴리곤 수는 MuJoCo와 비슷한 자릿수(내장 지오메트리 기본 세그먼트 기준 수백~수천 개 수준)이지만, 물리 연산이 아니라 **인터랙티브 좌표 데모**가 목적이라 접촉·침투 같은 물리량은 다루지 않는다. "MuJoCo 3D 물리 메쉬" 탭에서는 실제 AmazingHand 형상(오렌지/시안 캡슐 손가락)을 자체 렌더링해 보여주기도 한다.

## 4. 종합 비교표

| 관점 | MuJoCo | Aegis Three.js | Hunyuan3D-2/Unreal |
|---|---|---|---|
| **미려함(시각적 디테일)** | 낮음 — 단색 프리미티브 | 낮음~중간 — 그리드/글로우 등 UI 연출 가미 | **높음** — 매끄러운 재구성 표면(단, 텍스처 없음) |
| **속도(형상 1건 기준)** | **즉시**(파라미터일 뿐) | **즉시**(60FPS 라이브) | 느림(모델 상주 시 47초, 최초 8분+) |
| **다각형 수** | **최소**(2,572, 물리 연산은 0) | 낮음(수백~수천, 추정) | **압도적으로 많음**(106,880) |
| **물리 정확성** | **완전**(접촉력·침투·마찰 실측) | 없음 | 없음 |
| **인터랙티브 조작** | 없음(재생만) | **있음**(좌표 슬라이더 라이브) | 없음(정적 파일) |
| **용도 적합성** | 로봇 동역학 연구 | 좌표계 디버깅/시연 | 부품 프로토타입 시각 에셋 |

## 5. 결론 — "더 나은 렌더링"이 아니라 "다른 최적화 목표"

세 시스템은 경쟁 관계가 아니라 상호 보완적이다. MuJoCo는 **물리적으로 옳은 답**을 실시간으로 계산하는 데 최적화되어 있어 폴리곤이 필요 없고(분석적 형상), Hunyuan3D-2는 **시각적으로 그럴듯한 표면**을 만드는 데 최적화되어 있어 물리를 모른다. Aegis의 실시간 엔진은 그 중간에서 **조작 가능한 추상화**를 제공한다. "로봇 악수" 하나를 표현하는 데도 목적에 따라 셋 중 무엇을 쓸지가 완전히 달라진다 — 접촉력을 검증하려면 MuJoCo, 좌표계를 디버깅하려면 Aegis 뷰어, 부품을 프로토타이핑하고 미려한 목업이 필요하면 Hunyuan3D-2(§13에서 설계한 형상 생성 API)를 쓰는 식이다.
"""

payload = {
    "slug": "2026-08-11-moojoco-mujoco-vs-unreal-handshake-comparison",
    "title": "MuJoCo vs Unreal(text-to-3D) — 로봇 악수 개념으로 본 두 렌더링 철학 비교",
    "author": "Moojoco",
    "abstract": (
        "MuJoCo의 분석적 프리미티브 물리 시뮬레이션과 Hunyuan3D-2(Unreal 파이프라인)의 AI 메시 재구성 방식을 "
        "'로봇 악수'라는 동일 개념으로 정면 비교한다. dual_arms의 실제 AmazingHand URDF 치수를 그대로 재현한 "
        "동일 형상을 두 방식 각각으로 렌더링·재구성해 실측했다: MuJoCo는 2,572 삼각형(물리 연산 자체는 0개, "
        "분석적 캡슐/박스로 직접 계산)으로 즉시·실시간 동작하는 반면, Hunyuan3D-2는 106,880 삼각형(41.6배)의 "
        "매끄러운 표면을 만들지만 물리 의미가 전혀 없고 형상 1건에 47초(모델 상주 기준)가 걸린다. Aegis의 실시간 "
        "Three.js 커맨드 센터(hb5u:8590)를 세 번째 관점으로 추가해, 세 시스템이 경쟁이 아니라 각기 다른 목적에 "
        "최적화되어 있음을 폴리곤 수·속도·물리 정확성·인터랙티브성 축으로 시각화해 정리한다."
    ),
    "tags": ["comparison", "visualization", "moojoco", "mujoco", "unreal-engine", "hunyuan3d", "roops"],
    "changelog": "v1.0 — 최초 제출: MuJoCo vs Aegis Three.js vs Hunyuan3D-2/Unreal 3자 비교, 동일 형상 실측(41.6배 폴리곤 차이), 종합 비교표 및 결론",
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
