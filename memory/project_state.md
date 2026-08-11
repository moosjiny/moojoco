# Moojoco 미션 상태 — 2026-08-12

## 이번 세션 완료 작업 (fingershake-robot-main, http://hb5u.hyperbook.com:8600/)

물리엔진 근사 기능 4건을 계획→구현→실측→배포→thesis 순으로 완료:

1. **지면 고정(Ground Lock)** — 고관절/무릎/발목 슬라이더를 굽혀도 발바닥이 항상 바닥(y=0)에 붙도록 순기구학으로 root Y를 보정. commit `a2e8ea0`.
   thesis: https://thesis.hyperbook.com/papers/2026-08-11-moojoco-ground-lock-physics-approximation

2. **접촉 동역학 3단계 계획** — 마찰·ZMP·무게중심 도입 로드맵(1단계 CoM+지지다각형, 2단계 동적 ZMP+마찰원뿔, 3단계 진짜 강체 동역학[옵션A 클라이언트 물리엔진 vs 옵션B MuJoCo 백엔드]).
   thesis: https://thesis.hyperbook.com/papers/2026-08-11-moojoco-contact-dynamics-plan

3. **1단계: CoM + 지지 다각형 + 정적 안정성** — 신체 분절 질량비(머리7/몸통40/팔각8/다리각18.5)로 무게중심 계산, convex hull로 지지 다각형 구성, STABLE/UNSTABLE 판정. commit `dffa97b`.
   thesis: https://thesis.hyperbook.com/papers/2026-08-12-moojoco-com-support-polygon-result

4. **2단계: 동적 ZMP + 마찰원뿔** — CoM을 실경과시간으로 수치미분(EMA 스무딩)해 도립진자 ZMP 공식 적용, 마찰원뿔 비율로 미끄러짐 위험 판정. commit `d54d3b6`.
   thesis: https://thesis.hyperbook.com/papers/2026-08-12-moojoco-dynamic-zmp-friction-result

5. **저장 백업 + 기본 테마 변경** — 저장 버튼이 기존 값을 덮어쓰기 전 백업 키로 이동, 기본 테마 Cyber Blue → Titanium Silver. commit `b011173`.

3단계(진짜 강체 동역학)는 옵션 A(클라이언트 JS 물리엔진)/B(MuJoCo 백엔드 연동) 중 방향 결정 대기 중 — 사령관 판단 필요.

## 이번 세션에서 겪은 실수·교훈

- **뷰포트 폭 차이로 아이콘 오클릭**: 여러 다른 창 크기에서 좌표 클릭을 재사용하다 "저장" 버튼을 실수로 눌러 이상한 테스트 자세를 localStorage에 덮어씀 — 즉시 사령관께 공개하고, 재발 방지로 저장 백업 기능을 추가함.
- **같은 URL로 navigate해도 실제 새로고침이 안 됨**: 세션 내내 재사용한 브라우저 탭 하나가 1·2단계 배포 이후에도 실제로는 새로고침되지 않아 낡은 JS 번들을 계속 실행 중이었음(Scale/CoM 버튼이 아예 없었음). `?cachebust=<timestamp>` 쿼리로 강제 새로고침해 해결. **앞으로 프로덕션 재검증 시 항상 새 탭을 만들거나 cachebust 쿼리를 붙일 것.**
- 사령관이 "지금 자세면 앞으로 쓰러져야 할 것 같다"고 직관적으로 지적한 것이 실측(UNSTABLE -286mm)과 정확히 일치 — 물리 근사 로직이 실제로 타당하게 동작한다는 방증.

## 다음 세션 우선순위

1. 3단계(진짜 강체 동역학) 방향 결정 — 사령관에게 옵션 A/B 재확인
2. (미해결) 사령관이 세션 중 보낸 "029"라는 메시지의 의도 확인 필요 — 맥락 없이 전달됨
3. [[project_fingershake_dof_roadmap]]의 기존 후속 과제도 여전히 유효: 왼팔 손목/손 지오메트리, 손가락 PIP/DIP 독립화, 다리 좌우 비대칭, 자동 악수 모드에 신규 DOF 반영

## 배포 상태
- fingershake_web.service: 실행 중, 최신 코드 배포·재검증 완료 (사령관이 매번 직접 재시작 — 에이전트는 sudo 권한 없음)
