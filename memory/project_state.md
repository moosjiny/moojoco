# Moojoco 미션 상태 — 2026-08-20 (세션 종료 시점)

## 이번 세션 완료 작업 요약

이전 세션들(Body Yaw, 관절-슬라이더 연결)에 이어, 이번 세션은 크게 세 갈래로 진행됐다: (1) LeRobot/ACT 기반 Phase 2(손 겹침 해소) Stage 1~4 전체 최초 구현·검증, (2) fingershake 웹앱 UI 버그 수정, (3) 세션 후반 사령관 지적으로 발견한 "손바닥 미접촉" 기하학적 결함과 그 재설계 시도.

### 1. LeRobot/ACT Phase 2 — Stage 1~4 (완료, 다만 최종 결과는 "미해결"로 종료)

- **Stage 1**: 접근 거리·속도 45가지 procedural 데이터 생성(`generate_procedural_curl_dataset.py`), 24/45 게이트 통과.
- **Stage 1.5**: 좌우/상하 오프셋(9×9=81) + 장애물(6) 서브 스윕 추가. 오프셋 축이 비단조적(중간값이 제일 위험)임을 발견.
- **Stage 1.75**: 장애물 인지형 손목 접근 컨트롤러 — 3차 시행착오(비례감속 무효 → 손가락도 장애물 무지 발견 → 관성으로 하드스톱도 부족 → 여유거리 40mm/80mm로 확대) 끝에 장애물 6/6 전부 통과.
- **통합 데이터셋**: Stage1/1.5/1.75를 12차원 행동 스키마로 통일(`generate_procedural_curl_dataset_unified.py`), 132 에피소드/80 게이트 통과.
- **Stage 2**: ACT 정책 학습(lerobot 0.6.1 직접 임포트, 커스텀 학습 루프). **홀드아웃 폐루프 검증**(진짜 검증 — 정책 예측으로 물리 재실행)에서 v1 45%만 통과 확인, 원인(a/b_progress가 그 프레임 행동과 항상 같은 값 — 항등함수 지름길) 규명.
- **Stage 3**: 실시간 정책 통합. **최초 "5/5 통과" 발표가 거짓양성이었음을 자체 발견**(손이 전혀 안 움직이는 퇴화 no-op) — v2로 정정, 진짜 통과율 1/5.
- **Stage 4**: 다중 시드 스트레스 테스트. **Aegis 독립 재현이 REJECTED 판정**(내 단일시드 46% vs Aegis 3시드 평균 32%, -14%p 격차) — 수용하고 정정.
- **스키마 재설계**: 항등함수 지름길 버그를 관찰 스키마 차원에서 근본 수정(elapsed_time_frac + 실측 qpos_frac로 교체, 15→16차원). 재학습 후 다중시드 재검증 58.7%(구 32%에서 대폭 개선, 편차도 24%p→6%p로 안정화). Aegis에게 재검증 요청 발송(응답 대기 중).
- 커밋: e4b0653, 09e303a, a7e7c3f, 7dcaee0, 8deec41, ac7fb97, 0a8bc29, 8f8a064, 90872a5, 81e3b4a, 7775c09, 25beaca, d19c9aa, 2e1c971, d3a51b0.
- thesis(주요): `2026-08-20-moojoco-lerobot-act-phase2-plan`(v3), `-stage1-dataset-result`, `-stage1-5-dataset-result`, `-stage1-75-dataset-result`, `-unified-dataset-result`, `-stage2-holdout-validation`(v2), `-stage3-live-integration`(v2, 거짓양성 정정 포함), `-stage4-stress-test`(v2, Aegis REJECTED 반영), `-schema-redesign`(v3).

### 2. fingershake 웹앱 — 허리/목 관절 클릭 연결 (완료)

사령관 지적: 허리(torso)는 슬라이더는 있었지만 클릭 기즈모 미연결, 목(neck)은 슬라이더 자체가 아예 없었음. `torsoGroup`에 markJoint 추가, `headPitch` 필드 신설(types.ts/RobotScene.tsx/KinematicControls.tsx/RobotBuilder.ts)해 headGroup에도 클릭 기즈모 연결. 브라우저에서 실측 확인(클릭→라벨+슬라이더 하이라이트, 값 입력→머리 실제로 숙여짐). 커밋 `e64ef09`.

### 3. 손바닥 미접촉 기하학 결함 발견 및 v3 재설계 (세션 후반, 핵심 사건)

사령관 지적: "두 로봇의 오른 손 바닥이 서로 맞닿아야 된다... 그 메카니즘에 대해서 자료를 찾아봐." 웹 검색으로 "손바닥 접촉 먼저, 손가락 폐쇄가 그 다음"이 실제 악수/로봇그립 메커니즘임을 확인 후, 지금까지 Stage 1~4 전체가 써온 v2 모델을 실측한 결과 **손바닥이 18.8mm 떨어져 있고 손가락끼리만 허공에서 엇갈려 끼우는 동작**이었음을 발견(`2026-08-20-moojoco-handshake-palm-contact-geometry-flaw`).

- 1관절 손가락은 원리적으로 감싸쥐기 불가능함을 궤적 계산으로 증명 → **2관절(MCP+PIP) 손가락으로 v3 재설계**(`urdf/amazinghand_5finger_docking_v3.xml`, `scripts/generate_amazinghand_v3_mjcf.py`).
- 구현 중 버그 2개 발견·수정: (1) 근위-원위 손가락 세그먼트 자기충돌(캡슐 반경 합만큼 -11.1mm 항상 겹침, `<contact><exclude>`로 해결), (2) 검증 스크립트가 handB_lateral/height 미제어로 발산.
- 물리적으로 안정적인 접근+파지 시퀀스 확인(손바닥 0mm 접촉 순간 발생), 커밋 `afc821c`.
- **curl 튜닝 시도 → 실패**: 손으로 맞추면 트레이드오프(많이 굽히면 손바닥 근접·그립 실패, 적게 굽히면 방향은 맞지만 접근 방해). Stage1 방식으로 curl_scale까지 포함해 90개 넓게 스윕했으나 **90개 전부 손가락-손바닥 접촉 0건**(`2026-08-20-moojoco-handshake-v3-curl-sweep-failure`, 커밋 `581fcc1`).
- **근본 진단**: 이 프로젝트 전체가 써온 "가까워지면 감속"(사전-감속) 패턴은 회피 전략인데, 그립은 의도적 접촉이 필요한 정반대 행동 — 같은 도구를 반대 목적에 재사용한 게 원인. 성공 사례 0개인 데이터로는 모방학습(Stage 2 방식)이 성립 안 함.

## 이번 세션 핵심 교훈

- **"침투 0"은 성공의 필요조건이지 충분조건이 아니다** — Stage 3에서 아무것도 안 해도 침투는 0이라는 거짓양성을 자체 발견했고, v3 curl 스윕에서도 "게이트 통과 5개, 그립 성공 0개"로 같은 패턴이 재현됐다. 앞으로는 게이트 통과 여부와 "실제로 과제를 시도했는가/성공했는가"를 반드시 같이 확인해야 한다.
- **다중 시드 검증이 실제로 중요하다** — 단일 시드 46% 발표가 Aegis의 3시드 평균 32%로 뒤집힌 사건이 실제로 일어났다. 앞으로 통과율을 보고할 때는 항상 여러 시드로.
- **회피 전략과 접근/접촉 전략은 다른 도구다** — 근접도 기반 감속(사전-감속)은 "부딪히지 않기"에는 잘 맞지만 "붙잡기"에는 안 맞는다. 다음에 그립/접촉 계열 컨트롤러를 설계할 때는 이 구분을 먼저 명확히 할 것.
- **측정 대상 자체가 맞는지 항상 재질문할 것** — Hermes 이래 다들 contact.dist만 재측정했지, "애초에 손바닥이 접촉 후보에 포함되는가"는 아무도 안 물었다. 사령관의 실제 악수 감각(손바닥이 맞닿는 느낌)이 이걸 잡아냈다 — 정량 측정도 전제가 틀리면 소용없다는 사례로 기록.

## 다음 세션 우선순위

1. Aegis의 v3 스키마 재검증(58.7%) 재현 결과 확인 — ntfy 응답 대기 중이었음.
2. v3 손 모델 그립 전략 재설계 — 3가지 후보(MCP/PIP 순차 굽힘, 성공 기준 완화, 모방학습 대신 RL) 중 방향 결정 필요.
3. v3가 완성되면 Stage 1~4 파이프라인을 새 20-액추에이터 손가락 스키마로 재구축해야 함(아직 미착수).
4. `Cam: Joint_Side_View` 카메라 프리셋 버그, 왼팔 독립 테스트 슬라이더 과도한 뻗음 — 여전히 미해결로 남음(여러 세션째 이월).

## 배포/git 상태

- `fingershake_web.service`: 실행 중, 이번 세션 수정사항(허리/목 관절) 반영·서빙 중.
- `mujoco_bridge_server.py`(포트 8765), `sim_dual_arm.py`, `viz_server.py`: 전부 상시 실행 중.
- git HEAD: `581fcc1`, clean(`.codex/`, `AGENTS.md`는 사령관 지시로 계속 미추적 유지). 이번 세션 커밋 다수, 전부 push는 안 함(사령관이 명시적으로 요청한 적 없음 — 다음 세션 확인 필요).
- `data/` 아래 대용량 산출물(procedural_curl_dataset*, lerobot_stage2_act_policy*, amazinghand_v3_procedural_dataset)은 전부 gitignore 대상, git에는 스크립트만 커밋됨.

---

## 2026-08-21 세션 — TIG 용접 셀 통합 설계 (신규 트랙)

사령관이 thesis `2026-08-21-hermes-tig-welding-hf-shielding-research`(HF 아크 스타터가 dual_openarm의 CAN-FD를 방해할 수 있다는 EMI 문헌 리뷰)를 근거로 "제어하는 로봇을 설계하고 제어프로그램을 만들고 필요한 하드웨어를 구현단계까지 검토"하라고 지시. "통합 로봇 셀 설계"(용접 수행 로봇 + 그 옆에서 안전해야 하는 dual_openarm)로 범위를 확인한 뒤 진행했다.

- **핵심 결정**: 용접 로봇은 dual_openarm과 물리적으로 분리된 별도 셀(≥15m 이격 또는 패러데이 차폐). dual_openarm 팔을 토치 캐리어로 겸용하는 안은 정밀도·듀티·분리원칙 위배로 기각, 전용 6축 용접 로봇 신규 도입을 기본안으로 채택. 아크 스타트 기본값은 Lift-TIG, HF는 EMI 베이스라인 확보 후에만 허용.
- **제어 프로그램**: `scripts/tig_welding_robot_controller.py` 신규 작성 — `WeldingHAL`(추상)+`SimulatedWeldingHAL`(실기 없이 지금 실행 가능), `EMIHealthMonitor`(`ip -details -statistics link show can0/can1` 파싱으로 berr-counter/bus-off를 용접 전후 비교, thesis의 "측정 없이 결론 금지" 원칙을 코드 인터록화), `WeldCellController`(IDLE→…→WELDING→…→DONE 상태머신, 어느 상태서든 e-stop 시 FAULT). `--mode lift`/`--mode hf` 둘 다 실행해 exit=0 확인(hb5u에는 can0/can1이 실장돼 있지 않아 EMI 모니터가 "미검출"을 정상 보고하는 것도 함께 확인).
- **설계 보고서**를 Artifact로 발행(아키텍처 다이어그램, 용접 로봇 사양, EMI 대책→하드웨어 매핑, 전체 BOM, Phase 0~6 로드맵 포함)하고, 동일 내용을 thesis `2026-08-21-moojoco-tig-welding-cell-integrated-design`로 제출(신규, v1).
- **미해결**: 실물 용접 로봇·용접기·EMI 완화 하드웨어 전부 미조달. Phase 0(시뮬레이션 검증)만 완료, Phase 1(EMI 베이스라인 측정)부터가 다음 단계.

관련 파일: `scripts/tig_welding_robot_controller.py`, `scripts/submit_tig_welding_cell_design_thesis.py`.

---

## 2026-08-21~26 세션 — TIG 응답 대기 폴링 + 팀 운영 잡무

- **TIG 설계 Aegis 응답 대기**: 2026-08-21 알림 이후 `/loop`로 1시간 간격 폴링을 닷새 이상 지속(20회 이상 wakeup, 전부 noop). **최종 상태: 세션 종료 시점까지 Aegis 응답 없음**, 다음 세션에서 필요시 재개.
- **ROOPS 조직개편**: 2026-08-25 사령관이 "Aegis는 더 이상 EC2 담당이 아니다, EROS가 담당"이라고 정정. `CLAUDE.md`의 지휘계통/팀구성/Memory API 관할 표기를 갱신하고 커밋·푸시 완료(`9cd310e`). roops-comm에 Aegis/EROS/Codexy 앞으로 라우팅 정정 공지 발송(이전에 Aegis에게 잘못 요청했던 Codexy Memory API 등록 건 철회).
- **Codexy(신규 팀원) 이미지 배치 지원**: `images.hyperbook.com` 네임스페이스 컨벤션에 따라 `/home/moos/dev_ws/images/codexy/`를 신규 생성. SSH 공개키 authorized_keys 등록 요청은 보안설정 변경이라 거부하고, 대신 Codexy가 ntfy에 직접 첨부한 이미지 파일을 다운로드(사령관 채팅창 명시 승인 받음)→SHA-256 검증→배치하는 방식으로 처리(`pdf_editor_manual_capture_20260825.jpg`). `images.hyperbook.com/codexy/...` 200 OK 확인.
- **`~/dev_ws/house/real-property-main` 조사**: 사령관이 thesis `2026-08-11-moojoco-real-property-ai-platform`(부동산 AI 플랫폼, 저자 Moojoco v3)에 대해 질문. 확인 결과 실제 존재하는 논문이고 디렉토리 내용과도 일치하지만, **이번 세션이나 기억하는 과거 세션 어디에도 작업 기록이 없고 `~/.claude/projects/`에도 해당 경로의 세션 폴더가 없음** — 출처 불명으로 남겨둠. 사령관에게 확인 요청함.
- **Claude Code 자동업데이트로 인한 Remote Control 장애 진단**: 2026-08-26 00:41 UTC에 CLI가 2.1.238→2.1.246으로 자동 업데이트됐으나 기존 실행 중이던 세션들(`claude -c`, PID 47741/112460)은 재시작 전까지 구버전 메모리 상태 유지 — Remote Control 페어링 실패의 원인으로 추정. 사령관이 세션 재시작 후 확인 예정.
- **세션 종료**: 사령관 요청으로 세션을 닫을 준비 중. TIG `/loop`는 재시작 시 유실되므로 종료 전 stop 처리함 — 다음 세션에서 필요시 재가동 필요.

관련 파일: 없음(이번 트랙은 주로 ntfy/thesis/CLAUDE.md 운영 작업).

---

## 2026-08-27~09-10 세션 — 접촉 주도형 파지 v1 최초 성공 → hb5u:8600 실악수 재생 페이지 → Codezy 독립 검토 대응

### 1. 접촉 주도형 파지 v1 최초 성공 (2026-08-27~28)

Gravity의 4D 위상학적 시각화 제안 검토 의견을 thesis로 제출한 뒤, 사령관이 "1단계부터 착수해"라고 지시 — v3 손 모델을 실측(mj_geomDistance)해 반대편 손가락끼리 -5~-6mm 관통이 기하학적으로 불가능함을 확인하고, **손바닥을 4cm 간격으로 적층하는 v4 기하**(`urdf/amazinghand_5finger_docking_v4.xml`)로 재설계했다. `contact_driven_grasp_controller_v1.py`에 APPROACH→DESCEND→CLOSE→HOLD 상태머신과 settle→anchor 2단계 유지 로직(고정 스퀴즈각의 관통-접촉실패 트레이드오프를 해결)을 구현, **10개 손가락 전부 감싸쥐기 성공(침투율 4.37%, 유지 접촉률 1.0)** — 이 프로젝트 최초의 성공한 접촉 주도형 그립이다. thesis 2건 제출(`-4d-dual-gpu-proposal-review`, `-contact-driven-grasp-v1-first-success`), 커밋 `d39d50b`.

### 2. hb5u:8600 실악수 재생 페이지 (2026-08-28)

사령관이 "8600 화면에 붙을 수 있을까? 시스템이 망가질까봐 무섭다"고 안전 요구 — 기존 fingershake React 앱을 **한 글자도 수정하지 않고** `public/grasp/`, `dist/grasp/` 정적 페이지만 추가(zero-touch, 롤백은 디렉토리 2개 삭제). three.js로 v4 손 기하를 재구성하고 2링크 IK 팔로 148프레임 검증 궤적을 재생한다. 개발 중 팔 좌표계 부모 오류·IK 도달범위 초과를 수정했고, "손 분리로 보인다"는 스크린샷 오독을 `window.__dbg` 좌표 실측으로 반증(3D 형상은 측정, 눈대중 금지 원칙 재확인). 커밋 `0d643ae`. 화면 캡처 4장을 포함한 thesis(`-grasp-replay-page-8600`) 제출.

### 3. AGENTS.md 시크릿 정리 (2026-08-28)

`AGENTS.md`에 하드코딩돼 있던 ntfy 토큰·RHMS 키를 `~/.env_roops` 참조로 교체(`$NTFY_TOKEN_MOOJOCO`, `$RHMS_KEY_MOOJOCO`) — 이 정리가 이전에 반복되던 git add 차단(자동모드 분류기)의 실제 원인이었음을 확인. 커밋 `6c64aef`.

### 4. Polaris ROOPS PM 거버넌스 등장 (2026-08-31~09-01)

신규 에이전트 Polaris가 예고 없이 "PM 총괄 관리자"로 등장해 프로젝트 8번째 공인 등록·Tier-2 토큰 발급을 **사령관 확인 없이 일방 통보**. `$AGENT_MASTER_KEY` 요구 curl과 발급된 토큰을 즉시 사용하지 않고 보류, 사령관에게 "이게 실제 지시냐"고 먼저 확인(응답: "응"). 이후 토큰을 `~/.env_roops`(`ROOPS_PROJ_TOKEN_HANDSHAKE`)에 저장, repo_path 오기재 정정 요청 발송(반영 여부 미확인, 다음 세션 확인 필요). 신규 자기권위 선언 에이전트는 항상 사령관 확인 우선이라는 패턴을 메모리에 기록(`project_roops_pm_governance.md`).

### 5. Codezy 독립 검토 대응 (2026-09-09~10)

Codezy가 Playwright 실측(148프레임 전수)으로 `/grasp/` 페이지를 독립 검토 — 손바닥/캡슐 치수 지적은 v4 XML과 소스 대조로 정확함을 확인했고, **촉각 표시 구체가 렌더링 배율(S=2.5) 미적용 상태였던 실제 버그**를 발견해 즉시 수정·배포(커밋 `9316a4a`). 캡슐 겹침 수치는 스케일 환산 시 1단계 침투율(4.37%)과 부합함을 확인. v2(TOTP 열람 제한으로 접근 불가, v3로 대리 확인)의 실사진 캡처가 수정 배포 이전 시점임을 인지하고, 같은 방법론(Chrome+`window.__dbg`)으로 수정 후 상태를 직접 재측정 — **겹침 8.013mm→약 2.49mm 축소, 완전 해소는 아님을 숨기지 않고 보고**. SHAKE/RELEASE/RETREAT 미구현이라는 핵심 한계 지적에는 전적으로 동의, 로드맵에 채택. thesis 2건 제출, 커밋 `22fb6f2`.

### 6. 촉각 점 겹침 완전 제거 (2026-09-10, 같은 세션 후반)

잔여 겹침(~2.49mm)의 근본 원인이 "손바닥 표면 밖으로 튀어나온 3D 구체 형상 자체"임을 재진단 — 반경 조정만으론 원리적으로 0이 될 수 없었다. 마커를 3D 구체에서 **손바닥 표면에 마진(0.0002*S)만큼 안쪽으로 묻힌 평평한 원반(`CircleGeometry`)**으로 교체해, 마커가 정의상 자기 표면을 넘어설 수 없게 만들었다. Chrome 브라우저 확장이 이 세션에서 연결되지 않아 대신 **Playwright를 자동화 스크립트로 직접 실행**해 hb5u:8600 라이브 페이지의 마지막 HOLD 프레임 마커 16개(양손 8개씩) 전부를 재측정 — `anyInsideOpposite: false`, 최소 여유거리 0.4865mm로 **겹침 0을 확인**. 8.013mm→2.49mm→0mm로 단계적 해소 과정을 thesis에 기록해 제출(`2026-09-10-moojoco-tactile-dot-overlap-resolved`), 커밋 `6123f71`. 이후 Codezy에게 결과를 공유하려 했으나 `roops-codezy` 전용 토픽은 이력이 전혀 없어(Vorno 사례와 동일한 함정 회피) `roops-comm`에 `[Moojoco->Codezy]` 프리픽스로 발송.

### 다음 세션 우선순위 (갱신)

1. Polaris에게 요청한 repo_path 정정이 반영됐는지 확인.
2. ~~촉각 점 잔여 겹침 완전 제거~~ — 2026-09-10 완료(겹침 0 실측 확인).
3. 3단계(강건성 스윕): 접근 거리/속도/오프셋을 스윕해 v1 성공의 basin 지도화 — 아직 미착수.
4. SHAKE/RELEASE/RETREAT 단계를 컨트롤러 상태머신에 추가해 완전한 악수 궤적으로 확장.
5. `images.hyperbook.com` 이미지 삽입 방식(hb5u 로컬은 `cp`, 슬러그 폴더 `/home/moos/dev_ws/images/moojoco/`)은 이미 여러 세션에서 실사용 확인됨 — Hermes 가이드(`2026-08-04-hermes-thesis-usage-guide`)와 일치.

관련 파일: `scripts/contact_driven_grasp_controller_v1.py`, `urdf/amazinghand_5finger_docking_v4.xml`, `finger-shake/fingershake-robot-main/public/grasp/index.html`, `scripts/submit_*_thesis.py`(다수), `~/.claude/projects/-home-moos-dev-ws-dual-arms/memory/project_lerobot_handshake_phase2.md`, `project_roops_pm_governance.md`.
