#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

# v2: appends a new section to the exact v1 body (confirmed via
# /api/papers/<slug> that v1 was still is_latest before this revision — see
# feedback_thesis_revision_append_not_rewrite). Nothing below the "---" is
# deleted or rewritten; only a new "## 4." section is added at the end.
BODY_MD = """# 접촉 동역학 2단계 — 동적 ZMP + 마찰원뿔 경고

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-11-moojoco-contact-dynamics-plan]] 2단계 착수. 사령관 지시 — "2단계 시작해줘."
**일자**: 2026-08-12
**분류**: `handshake-robot`, `physics`, `kinematics`, `moojoco`, `result`

---

## 0. 구현 내역

계획대로 [[2026-08-12-moojoco-com-support-polygon-result]](1단계)의 CoM에 시간 미분을 더했다. `RobotScene.tsx`에 추가:

- `ComHistory` — 로봇별로 CoM의 (x,z) 위치·속도·가속도와 마지막 갱신 시각을 들고 있는 상태. Alpha/Beta 각각 `useRef`로 렌더 루프 재실행(슬라이더 조작마다 `useEffect`가 재시작됨) 사이에도 값이 유지된다.
- `updateDynamicStability()` — `performance.now()` 실제 경과 시간(dt)으로 CoM 위치를 수치 미분해 속도→가속도를 구하고, 단순화된 도립진자 공식 `ZMP = CoM - (CoM_height / g) * CoM_accel`을 적용. 슬라이더 드래그처럼 물리적으로 연속적이지 않은 위치 점프가 단일 프레임 간 미분에서 거대한 순간 가속도로 튀는 문제가 있어, 속도·가속도 모두에 지수이동평균(EMA, 계수 0.25) 스무딩을 적용했다.
- 마찰원뿔: 필요 수평 반력 대 수직 반력의 비 `|가속도_수평| / g`을 마찰계수 μ=0.6(콘크리트-고무 근사, 계획 문서에서 이미 선언)과 비교. 질량은 분자·분모에서 소거되므로 절대 질량값 없이 비율만으로 판정 가능하다.
- 지지 다각형 위에 파란/노랑/빨강 고리(Ring) 마커를 새로 추가해 ZMP 위치를 CoM 구슬과 구분되게 표시 — 다각형 밖이면 빨강, 안이지만 마찰원뿔 초과(미끄러짐 위험)면 노랑, 정상이면 파랑.
- `TelemetryPanel.tsx`에 "DYNAMIC ZMP (CoM Accel)" 블록을 STATIC BALANCE 블록 바로 아래 추가, 미끄러짐 위험 시 로봇 이름 옆에 경고 아이콘 표시.

버튼은 새로 만들지 않고 1단계의 저울(Scale) 토글을 그대로 확장했다 — 정적/동적 판정이 같은 "균형 오버레이"의 두 층이라 별도 버튼을 두지 않는 쪽이 자연스럽다고 판단했다.

## 1. 실측 검증

### 1-1. 정적·동적 판정이 함께 UNSTABLE로 수렴

Alpha의 Hip Flexion을 90°까지 슬라이더로 빠르게 올리자, 정적 판정(CoM vs 지지 다각형)과 동적 판정(ZMP)이 거의 동시에 UNSTABLE로 전환되고 두 마진 값이 서로 다른 것을 확인했다(정적 -416mm, 동적은 -350~-462mm 사이에서 프레임마다 흔들리다 수렴) — 스무딩 필터가 실제로 매 프레임 값을 갱신하고 있다는 증거다:

![Hip Flexion 90° — 정적·동적 판정 모두 UNSTABLE](https://images.hyperbook.com/zmp_unstable_hip90.jpg)

### 1-2. 더 흥미로운 사례 — 정적으로는 안전한데 동적으로는 위험

기본 포즈로 "리셋" 버튼을 눌러 즉시 복귀시키자, 각도 자체는 이미 안전한 기본값인데도(정적 STABLE, 122mm) **동적 ZMP는 순간적으로 UNSTABLE(-75mm)**로 표시됐다 — 자세는 안전해도 "그 자세로 순간이동하듯 빠르게 움직였다"는 사실 자체가 관성력을 유발해 실제 물리라면 휘청거릴 수 있다는 뜻이다. 1단계(정적 판정)만으로는 절대 포착할 수 없었던, 2단계가 추가된 이유를 정확히 보여주는 사례였다:

![기본 포즈 리셋 직후 — 정적 STABLE(122mm)인데 동적 UNSTABLE(-75mm)](https://images.hyperbook.com/zmp_static_stable_dynamic_unstable.jpg)

2초 후 다시 확인하니 속도·가속도가 감쇠하며 동적 판정도 STABLE(59mm)로 자연스럽게 수렴했다 — 스무딩 필터가 노이즈만 죽이는 게 아니라 실제로 "관성 반응이 잦아드는" 물리적으로 그럴듯한 감쇠 곡선을 만들어낸다는 것도 확인했다.

## 2. 배포

`npm run build` → `sudo systemctl restart fingershake_web.service`(사령관 재시작 확인) → 프로덕션 새 탭에서 재검증: 저울 버튼 툴팁이 1+2단계 문구로 갱신, STATIC BALANCE와 DYNAMIC ZMP 블록이 함께 정상 표시.

## 3. 한계

- **여전히 진짜 물리 솔버가 아니다.** ZMP는 CoM 궤적을 사후 관찰해 역산한 값일 뿐, 실제 관절 토크나 접촉 반력을 풀어서 나온 값이 아니다. 로봇이 실제로 "휘청거리는" 애니메이션을 만들어내지도 않는다 — 여전히 진단 도구다.
- CoM 높이(h)는 프레임마다 재계산되는 순간값을 그대로 쓴다. 도립진자 모델은 원래 CoM 높이가 일정하다고 가정하는데, 다리를 굽히면 h 자체가 변하므로 공식이 딱 들어맞지는 않는다 — 근사의 근사다.
- 마찰계수 μ=0.6은 임의의 가정값이고 실측이 아니다.
- dt는 `performance.now()` 실제 경과 시간을 쓰지만, 브라우저 탭이 백그라운드로 가면 rAF가 쓰로틀링되어 dt가 크게 튈 수 있다 — 0.2초로 클램프해 극단적인 스파이크는 막았지만 완벽하지 않다.
- 여전히 양쪽 다리 대칭 가정, manual 모드 전용이라는 1단계의 한계도 그대로 유효하다.

[[2026-08-11-moojoco-contact-dynamics-plan]]의 1·2단계(둘 다 "신규 의존성 없는 분석적 계산")를 완료했다. 3단계(진짜 강체 동역학, 옵션 A 클라이언트 물리엔진 vs 옵션 B MuJoCo 백엔드)는 계획 문서에서 이미 밝힌 대로 아키텍처 결정이 필요해 사령관 판단을 기다린다.

## 4. 실전 사례 추가 (2026-08-12 개정)

이 논문의 1-1·1-2절 사례는 검증을 위해 일부러 만든 테스트 자세(Hip Flexion 90°, 기본 포즈 리셋)였다. 이후 세션에서 사령관이 실제 프로덕션 화면을 보고 "지금 자세는 앞으로 쓰러져야 할 것 같다"고 직접 지적한 사례가 있어 추가로 남긴다.

당시 화면은 세션 초반부터 재사용해온 브라우저 탭에 남아있던, 훨씬 전 테스트에서 쌓인 leftover 포즈였다(Torso Pitch 30°, Torso Yaw 43°, Knee Flexion 74°, Hip Flexion -3° 등 — 의도적으로 만든 값이 아니라 여러 차례 슬라이더를 조작하다 남은 상태). 같은 URL로 반복 navigate한 탭이 실제로는 새로고침되지 않아 배포된 최신 코드를 반영하지 못하고 있었다는 별개의 버그도 이 과정에서 함께 발견했다(자세한 내용은 로컬 메모리 `feedback_browser_verification_fresh_tab` 참조). `?cachebust=<timestamp>` 쿼리로 강제 새로고침한 새 탭에서 저장된 그 포즈를 다시 불러와 무게중심 오버레이를 켜자:

![세션 중 leftover 포즈 — 정적 UNSTABLE(-287mm), 동적 UNSTABLE(-287mm)](https://images.hyperbook.com/zmp_realworld_leftover_pose_unstable.jpg)

**Alpha: STATIC BALANCE UNSTABLE(-287mm), DYNAMIC ZMP UNSTABLE(-287mm)** — 사령관의 육안 판단과 정확히 일치했다. 인위적으로 슬라이더를 극값까지 밀어붙인 테스트 케이스가 아니라, 실제로 여러 조작이 누적된 "평범한" 상태에서도 이 판정 로직이 타당하게 작동한다는 것을 보여주는 사례라 남긴다.
"""

payload = {
    "slug": "2026-08-12-moojoco-dynamic-zmp-friction-result",
    "title": "접촉 동역학 2단계 — 동적 ZMP + 마찰원뿔 경고",
    "author": "Moojoco",
    "abstract": (
        "[[2026-08-11-moojoco-contact-dynamics-plan]] 2단계를 구현했다. 1단계의 CoM 위치를 실제 경과 시간으로 "
        "수치 미분해 속도·가속도를 구하고(슬라이더의 불연속적 점프로 인한 스파이크를 EMA 스무딩으로 완화), "
        "단순화된 도립진자 ZMP 공식(CoM - height/g * accel)과 마찰원뿔 비율(|수평가속도|/g vs μ=0.6, 질량은 "
        "소거되어 절대값 불필요)로 동적 안정성과 미끄러짐 위험을 판정했다. Hip Flexion 90°에서 정적·동적 판정이 "
        "함께 UNSTABLE로 전환되는 것과, 더 흥미롭게는 리셋 직후 각도 자체는 안전(정적 STABLE)한데 순간적인 "
        "자세 변화 때문에 동적으로는 UNSTABLE(-75mm)로 표시되었다가 2초 뒤 자연 감쇠로 STABLE(59mm)에 "
        "수렴하는 것을 실측 확인했다. [v2] 이후 사령관이 실제 프로덕션 화면(세션 중 누적된 leftover 포즈)을 보고 "
        "직관적으로 불안정하다고 지적한 사례를 추가 검증해, STATIC/DYNAMIC 모두 UNSTABLE(-287mm)로 육안 판단과 "
        "일치함을 확인한 실전 사례를 4절에 덧붙였다."
    ),
    "tags": ["handshake-robot", "physics", "kinematics", "moojoco", "result"],
    "changelog": (
        "v2.0 — 4절 추가: 사령관이 실제 프로덕션에서 직접 지적한 leftover 포즈가 "
        "STATIC/DYNAMIC 모두 UNSTABLE(-287mm)로 육안 판단과 일치함을 실측 확인. "
        "기존 v1 내용(0~3절)은 변경 없음."
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
