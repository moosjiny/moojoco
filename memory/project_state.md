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
