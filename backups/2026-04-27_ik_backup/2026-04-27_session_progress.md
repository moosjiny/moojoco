# 듀얼암 작업 진행 보고서 (2026-04-27 세션)

본 문서는 OpenArm WowRobo 듀얼암 시뮬레이션의 환경 복구·actuator 정의·실측 그리퍼 메쉬 적용·관절 한계 스위프 시각화 작업을 기록합니다.

---

## 1. 개요

| 단계 | 내용 |
|------|------|
| 1 | 환경 복구 (잘못된 사용자 경로, 빈 venv) |
| 2 | venv 재생성 + requirements 설치 |
| 3 | 실행 가능성 검증 |
| 4 | 관절 자유도(DoF) 분석 |
| 5 | Actuator 사양 조사 (인터넷) |
| 6 | URDF→MJCF 변환 + actuator/tendon/equality 주입 |
| 7 | 그리퍼 실측 메쉬 다운로드 + Rerun 통합 |
| 8 | 관절 한계 순차 스위프 + 충돌 비활성화 |
| 9 | 좌표 정합 오류 4건 수정 |

---

## 2. 환경 정비

### 2.1 하드코딩 경로 일괄 치환
17개 파일이 `/home/addinedu/dev_ws/dual_arms/`를 가리켜 모두 실패. `/home/ghlee/`로 일괄 치환.

```bash
xargs -a /tmp/files_to_fix.txt sed -i 's|/home/addinedu/|/home/ghlee/|g'
```

### 2.2 venv 재생성
- 위치: `/home/ghlee/venv/dual_arms` (사용자 지정)
- Python 3.12 + `requirements.txt` 33개 패키지 설치
- 핵심: mujoco 3.7.0, rerun-sdk 0.31.3, fastapi 0.136.1, trimesh 4.12.0
- `scripts/start_all.sh`, `setup_venv.sh`, `run_dashboard.sh`의 venv 경로 갱신

### 2.3 실행 검증
- Dashboard (port 8000) HTTP 200, WebSocket robot_state 스트리밍 확인
- Rerun Web Viewer (port 9090) HTTP 200, gRPC (port 9876) LISTEN
- 에러 0건

---

## 3. 관절 자유도 (DoF)

| 항목 | 값 |
|------|-----|
| njnt | 14 → **18** (그리퍼 4 추가 후) |
| nq, nv | 14 → **18** |
| 회전 관절 | 좌·우 각 7개 (hinge, 1 DoF) |
| 슬라이드 관절 | 좌·우 각 2개 (finger, 0~44mm) |

회전축 패턴: **Z-X-Z-Y-Z-X-Y** (양팔 동일, joint_2만 좌·우 부호 반대로 부분 거울 대칭).

회전 한계: joint_1/3/5/7 = ±π, joint_2/4/6 = ±π/2.

---

## 4. Actuator 정의 적용

### 4.1 인터넷 조사
- **공식 MJCF**: [reazon-research/openarm-mjcf](https://github.com/reazon-research/openarm-mjcf) (Apache-2.0)
- **공식 한 팔 액추에이터 8개**: ctrlrange 모두 ±10 Nm (joint_2만 ±12 Nm), 그리퍼 ±0.1 N
- **dynamics 기본값**: `damping="0.25" frictionloss="0.02"`

### 4.2 Damiao 모터 매핑 (1차 출처: Foxtech, docs.openarm.dev, Seeed Wiki)

| 관절 | 모델 | 정격 / 피크 토크 | 기어비 |
|------|------|-----------------|--------|
| joint_1, joint_2 | DM-J8009P-2EC | 20 / 40 Nm | 9:1 |
| joint_3, joint_4 | DM-J4340(P)-2EC | 9 / 27 Nm | 40:1 |
| joint_5~7, finger | DM-J4310-2EC V1.1 | 3 / 7 Nm | 10:1 |

→ 기존 URDF의 effort 한계(50/30/20 Nm)는 실제 사양과 어긋남 (특히 손목 약 3배 과대). 공식 MJCF의 보수값(±10/±12)으로 동기화.

### 4.3 핵심 발견: URDF 파서 한계
MuJoCo URDF 파서는 `<mujoco>` 확장 블록의 `<actuator>`, `<tendon>`, `<equality>`를 **무시**한다. URDF에 아무리 써도 nu=0이 됨.

**해결책**: MuJoCo `MjSpec` API로 URDF를 로드해 actuator/tendon/equality를 프로그램적으로 주입한 뒤 MJCF로 직렬화.

→ 재사용 가능한 빌드 스크립트: `scratch/build_mjcf.py`

### 4.4 결과
| 항목 | 값 |
|------|-----|
| nu (actuators) | **16** (좌·우 각 7 + 그리퍼 1씩) |
| ntendon | 2 (좌/우 finger_split, coef 0.5+0.5) |
| neq | 2 (좌/우 finger pair equality, polycoef "0 1") |
| disableflags | **mjDSBL_CONTACT** (충돌 처리 비활성화) |
| 모든 joint dynamics | damping=0.25, frictionloss=0.02 |

검증: `data.ctrl[:] = 1.0` → `qfrc_actuator` 정상 반영, finger pair sync diff < 1e-5 m.

---

## 5. 그리퍼 실측 메쉬 적용

### 5.1 메쉬 다운로드
- 공식 저장소(`reazon-research/openarm-mjcf v1/meshes/visual/gripper/`)에서 두 부분으로 구성된 OBJ 다운로드
- `meshes/gripper/finger_0.obj` (496 KB, 7,052 verts) — 회색 본체
- `meshes/gripper/finger_1.obj` (2.7 MB, 35,428 verts) — 검정 액센트

### 5.2 Rerun 통합
한 손가락당 두 mesh 부분(gray + black) × 좌·우 두 손가락 × 양팔 = **8개 정적 mesh entity**. 비대칭 손가락 쌍을 위해 finger_2에는 Y축 미러 + face winding 반전 적용.

### 5.3 그리퍼 동작 규약
- q=0: **닫힘** (공식 규약 — 초기 우리 URDF는 반대 방향이었음, 수정함)
- q=0.044: 완전 열림 (44mm 한계)
- 두 손가락은 tendon coef 0.5+0.5 + equality polycoef "0 1"로 완전 동기

---

## 6. 관절 한계 스위프 + 충돌 비활성

### 6.1 시뮬 루프 변경
기존: 모든 관절을 sin·sin 곱으로 ±0.1 rad 좁게 흔듦.

신규: **순차 단일 관절 스위프**
- 16개 항목(arm 14 + 그리퍼 2 페어)을 4초씩 한계까지 사인파 왕복
- 한 사이클 64초
- 활성 관절만 움직이고 나머지는 home pose 유지 → 관절별 한계 확인 용이
- Rerun에 `status/sweep` TextDocument 패널로 현재 관절·qpos·range 표시

### 6.2 충돌 비활성화
1. `mj_kinematics`만 사용 (정기구학, 동역학 없음)
2. MJCF에 `option.disableflags |= mjDSBL_CONTACT` 명시 — `mj_step` 전환 시에도 안전

---

## 7. 좌표 정합 오류 수정 4건

세션 중 발견·수정한 정합 오류:

### 7.1 그리퍼 손가락 관절 축 반대
- 증상: q=0.044에서 손가락이 중앙 통과 (서로 겹침)
- 원인: 우리 URDF의 finger_joint1 axis=(0,-1,0)인데 공식은 (0,+1,0). q=0이 닫힘인 공식 규약과 어긋남.
- 수정: 4개 finger_joint 축 부호 모두 반전.

### 7.2 그리퍼 부착 Z 너무 멀음
- 증상: 그리퍼가 link7 끝에서 21mm 떠 있음
- 원인: finger joint origin Z=0.1151 (공식 link7 기준). WowRobo link7는 21mm 짧음.
- 측정: link7 mesh top = local Z +0.0945, finger mesh base = body local Z -0.0044
- 수정: finger joint origin Z 0.1151 → **0.0989** (= 0.0945 + 0.0044)

### 7.3 그리퍼 메쉬 오프셋 부호 오류
- 증상: 그리퍼 메쉬가 link7로부터 약 **1.34m 떨어진 위치**에 그려짐
- 원인: `NF_OFFSET_MM = (0, -50, -673)`을 빼는 코드(`v_raw - offset`) → 결과적으로 +673 더해짐
- 수정: 오프셋을 양수 `(0, +50, +673)`로 바꾸고 그대로 빼기 — STL_OFFSETS와 일관된 규약

### 7.4 shoulder Y 부호 반대 + Z 3mm 부족
- 증상: 좌·우 link1이 pillar 표면에서 약 **36mm 갭**, 위쪽으로 3mm 어긋남
- 원인:
  - shoulder_Y에 `±0.0175`를 사용했지만 부호가 반대. `rpy="±1.5708 0 0"` 회전 때문에 link1 body Y = shoulder_Y ∓ 0.0625로 뒤집혀 적용됨
  - shoulder_Z=0.75인데 base_link.stl pillar top은 0.773
- 측정: pillar top surface Y=[-0.044, +0.044], Z=0.773
- 수정: `shoulder_to_left_arm`을 (0, **+0.0175**, **0.753**), `shoulder_to_right_arm`을 (0, **-0.0175**, 0.753)로
- 결과: link1 body 좌=(0, -0.045, 0.773), 우=(0, +0.045, 0.773) — pillar 표면에 정확히 일치

---

## 8. 변경·생성 파일

| 경로 | 변경 |
|------|------|
| `urdf/dual_openarm.urdf` | effort 한계 갱신, `<dynamics>` 추가, 그리퍼 4 링크/조인트 추가, finger 축 부호 정정, shoulder Y/Z 정정 |
| `urdf/dual_openarm.xml` | **신규** — MjSpec 기반 MJCF (actuator 16, tendon 2, equality 2, contact 비활성) |
| `urdf/dual_openarm.urdf.pre_actuator.bak` | **신규** — actuator 작업 직전 URDF 백업 |
| `meshes/gripper/finger_0.obj` | **신규** — 공식 그리퍼 메쉬 |
| `meshes/gripper/finger_1.obj` | **신규** — 공식 그리퍼 메쉬 |
| `scratch/build_mjcf.py` | **신규** — URDF→MJCF 재빌드 유틸 |
| `scripts/sim_dual_arm.py` | URDF_PATH `.xml`로 변경, finger 메쉬 8개 사전 로깅, 순차 스위프 루프 |
| `scripts/start_all.sh`, `setup_venv.sh`, `run_dashboard.sh` | venv 경로를 `/home/ghlee/venv/dual_arms`로 |
| 17개 파일 (전체) | 사용자 경로 `addinedu` → `ghlee` |

---

## 9. 현재 상태

### 검증 통과
- `python3 -m py_compile sim_dual_arm.py dashboard/main.py` → SYNTAX_OK
- `mujoco.MjModel.from_xml_path(...)` → njnt=18, nu=16, ntendon=2, neq=2, contact 비활성
- `mj_kinematics` 후 link1 body 위치 = pillar 표면 (Y=±0.045, Z=0.773)
- start_all.sh 후 dashboard/Rerun HTTP 200, 에러 로그 없음
- Finger pair sync diff < 1e-5 m (equality + tendon 동작 확인)

### 실행 방법
```bash
bash /home/ghlee/dev_ws/dual_arms/scripts/start_all.sh
# Dashboard: http://localhost:8000
# Rerun:     http://localhost:9090
```

URDF를 수정한 뒤에는 반드시:
```bash
/home/ghlee/venv/dual_arms/bin/python /home/ghlee/dev_ws/dual_arms/scratch/build_mjcf.py
```
로 MJCF를 재빌드해야 actuator/tendon/equality 정의가 반영됩니다.

---

## 10. 다음 단계 후보

1. 시뮬 루프를 actuator 기반 토크 제어(`data.ctrl[:] = ...` + `mj_step`)로 전환
2. URDF의 box 그리퍼 visual을 실측 OBJ mesh 참조로 교체 (MuJoCo viewer 호환성 향상)
3. CAN-FD 하드웨어 인터페이스 연결 + Damiao 모터 드라이버 (`config/dual_arm_config.yaml` 활용)
4. dashboard `main.py`의 mock robot_state를 sim_dual_arm.py 실제 상태와 IPC 연동
5. base_link.stl pillar의 X 비대칭(중심 -10mm) 수동 보정 검토
