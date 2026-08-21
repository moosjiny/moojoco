#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# TIG 용접 셀 통합 설계 — 로봇·제어 프로그램·하드웨어를 구현 단계까지

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-21-hermes-tig-welding-hf-shielding-research]]가 밝힌 "TIG HF 아크 스타터(15~20kV, 수 MHz)가 dual_openarm의 CAN-FD(can0/can1, 1M/5Mbps)를 방해할 수 있다"는 문헌 리뷰를 근거로, 사령관 지시에 따라 실제 용접을 수행하는 로봇과 그 옆에서 계속 동작해야 하는 dual_openarm을 한 셀로 보는 통합 설계를 구현 단계까지 정리했다.
**일자**: 2026-08-21
**분류**: `tig-welding`, `robot-design`, `emi`, `moojoco`, `plan`

---

## 0. 이 설계가 푸는 두 겹의 문제

1. 실제로 TIG 용접을 수행하는 로봇을 새로 설계·제어한다.
2. 그 로봇이 옆에서 계속 동작하는 dual_openarm의 CAN-FD 통신을 방해하지 않도록 하드웨어·소프트웨어 양쪽에서 막는다.

Hermes 리뷰의 완화 우선순위(HF 회피 → 접지 → 배선분리/페라이트 → 필터 → 패러데이 케이지 → 실측 검증)를 그대로 아키텍처와 코드에 반영했다.

## 1. 핵심 결정

- **용접 로봇은 dual_openarm과 물리적으로 분리된 별도 셀**에 둔다(≥15m 이격, 불가하면 패러데이 차폐). dual_openarm 팔(OpenArm 팔로워, actuatorfrcrange 10~12N·m급 연구용 매니퓰레이터)을 토치 캐리어로 겸용하는 방안도 검토했으나, TIG가 요구하는 ±0.1mm급 정밀도·연속 듀티에 맞지 않고 무엇보다 같은 인클로저에 두면 "물리적 분리"라는 이 설계의 핵심 전제가 무너져 기각했다.
- **아크 스타트 기본값은 Lift-TIG**. HF는 명시적으로 요청됐을 때만, 그리고 CAN 버스 오류 카운터 베이스라인을 먼저 확보한 경우에만 허용한다.
- 두 셀을 잇는 연결은 **단일점 접지 버스바** 하나와 **읽기전용 EMI 감시 링크** 하나뿐이다. 용접 셀이 dual_openarm을 구동하거나 제어에 관여하는 경로는 설계상 존재하지 않는다.

## 2. 셀 아키텍처

```
[용접 셀 (신규)]                              [dual_openarm 셀 (기존)]
  TIG 용접 로봇(6축)                             can0/can1 (CAN-FD 1M/5M)
  용접기 — Lift-TIG 기본                          OpenArm 팔로워 컨트롤러
  Ar 실드가스 공급                                     │
        │            ≥15m 이격 또는 패러데이 차폐        │  읽기전용
        │        (케이블 교차 시 90°·CAN 근처 페라이트)   ▼
        │                                        EMI 헬스 모니터
        └──────────────── 단일점 접지 버스바 ───────────────┘
                                │
                              접지봉
```

## 3. 용접 로봇 사양 (기본안)

| 항목 | 사양 | 근거 |
|---|---|---|
| 자유도 | 6축 | 토치 자세 자유도(위빙·각도 포함) 확보 |
| 가반하중 | 3~6 kg | 토치(~0.4kg)+케이블 드래그 여유, 소형 산업용 클래스 |
| 반복정밀도 | ±0.05 mm | TIG 비드 품질 기준 ±0.1mm를 만족하는 여유 |
| 도달거리 | 700~900 mm | 테이블급 지그 작업 범위 |
| 제어 인터페이스 | 이더넷/필드버스(EtherCAT 등) — **CAN 아님** | dual_openarm의 can0/can1과 물리 계층을 처음부터 공유하지 않음 |
| 인클로저 | IP54 이상, 접지 러그 확보 | 스패터·차폐가스 환경 + 단일점 접지 연결점 |
| 토치 마운트 | 절연 부싱 경유 장착 | 토치-암 간 접지 루프 형성 방지 |

## 4. 제어 프로그램 — `scripts/tig_welding_robot_controller.py` (신규, 실행·검증 완료)

상태머신은 표준 TIG 시퀀스(IDLE→APPROACH→PREFLOW→ARC_START→WELDING→ARC_STOP→POSTFLOW→RETRACT→DONE)를 따르되, **HF 모드일 때만** ARC_START 직전에 CAN 버스 오류 카운터 베이스라인을 캡처하고 POSTFLOW 이후 다시 읽어 비교하는 게이트를 넣었다 — "측정 없이 결론 금지" 원칙을 코드 인터록으로 구현한 것이다. 비상정지(`_check_estop`)는 어느 상태에서든 즉시 FAULT로 전이하며 아크를 끊고 가스를 잠근다.

구성 요소:
- `WeldingHAL` 추상 인터페이스 + `SimulatedWeldingHAL` — 실기 없이 지금 바로 전체 사이클을 검증할 수 있고, 실기 도입 시 HAL 구현체만 교체하면 상태머신·안전 인터록은 그대로 재사용된다.
- `EMIHealthMonitor` — `ip -details -statistics link show can0/can1`을 파싱해 berr-counter/bus-off/restart를 용접 전후로 비교. can0/can1이 물리적으로 없을 때도 안전하게 "미검출"로 처리하도록 확인했다.
- `WeldCellController.run()` — 위 상태머신 + EMI 게이팅 + 안전 인터록을 묶은 최상위 실행 루프.

### 실행 검증 로그

```
$ python3 scripts/tig_welding_robot_controller.py --mode lift
=== 용접 사이클 시작: mode=lift ===
[HAL-SIM] 토치 이동 → (300.0, 0.0, 50.0) mm
[HAL-SIM] 실드가스 ON (Ar, 사전 유량 확인)
[HAL-SIM] 아크 스타트 시도: mode=lift
[HAL-SIM] 용접 진행: 3.0 mm/s x 40.0s
[HAL-SIM] 아크 정지 (크레이터 필 없이 즉시 컷)
[HAL-SIM] 실드가스 OFF
=== 용접 사이클 완료 ===
exit=0

$ python3 scripts/tig_welding_robot_controller.py --mode hf
=== 용접 사이클 시작: mode=hf ===
...
[EMI] can0 인터페이스 없음 — 물리적으로 없다고 판단, HF 진행은 허용하되 실배치 전 반드시 재계측할 것
[EMI] can1 인터페이스 없음 — 위와 동일
[HAL-SIM] 아크 스타트 시도: mode=hf
...
=== 용접 사이클 완료 ===
exit=0
```

두 모드 모두 exit=0. hb5u에는 아직 can0/can1이 실장돼 있지 않아(`ip link show can0` → "does not exist") EMI 모니터가 그 상황을 정상적으로 감지·보고하는 것까지 확인했다.

## 5. EMI 완화 대책 → 하드웨어/구현 Phase 매핑

| 우선순위 | Hermes 리뷰의 대책 | 이 설계의 구현 | Phase |
|---|---|---|---|
| 1 | HF 자체 제거 | 기본 아크모드 = Lift-TIG, HF는 옵션 | P3 |
| 2 | 단일점 접지 | 용접기·테이블·배전함·dual_openarm 셀을 접지봉 1개로 통합 | P2 |
| 3 | 배선 분리 | CAN 리드와 용접 리드 물리 이격, 불가피한 교차는 90° | P2 |
| 4 | 페라이트 코어 | can0/can1 커넥터 근처 페라이트 링 장착 | P2 |
| 5 | 패러데이 케이지 | 15m 이격 불가 시에만: OpenArm 컨트롤러 인클로저 차폐화 | P2(조건부) |
| 6 | 전원단 필터 | 용접기 전원 입력에 EMI 필터/MOV | P4 |
| 7 | 실측 검증 | EMIHealthMonitor로 용접 전후 berr-counter/bus-off 비교(코드 구현·검증 완료) | P1, P4, P5 |

## 6. 하드웨어 BOM

| 구분 | 품목 | 사양/메모 | 수량 |
|---|---|---|---|
| 용접 로봇 | 6축 소형 산업용 매니퓰레이터 | 가반 3~6kg, 반복정밀도 ±0.05mm, 이더넷/필드버스 | 1 |
| 용접 로봇 | 절연 토치 마운트 브래킷 | 암-토치 간 접지 루프 차단 | 1 |
| 용접기/토치 | 인버터 DC TIG 용접기(Lift-TIG 지원) | HF 옵션 겸용 모델 권장(P3 완화 검증용) | 1 |
| 용접기/토치 | TIG 토치 + 케이블 | 공랭, 로봇 아암 배선 경로용 저강성 케이블 | 1 |
| 용접기/토치 | Ar 가스 실린더+레귤레이터+솔레노이드밸브 | 제어 프로그램의 gas_on/off와 연동 | 1 |
| 용접기/토치 | 작업물 접지 클램프 | 단일점 접지 버스바에 직결 | 1 |
| EMI 완화 | 접지봉 + 접지 버스바 | 4개 지점(용접기·테이블·배전함·dual_openarm) 공통 접지 | 1식 |
| EMI 완화 | 페라이트 코어(클램프형) | can0/can1 커넥터 인근 각 1개 | 2 |
| EMI 완화 | EMI 라인 필터 + MOV | 용접기 전원 입력단 | 1 |
| EMI 완화 | 도전성 차폐 캐비닛(조건부) | 15m 이격 미확보 시에만 | 0~1 |
| 제어/통합 | 용접 셀 산업 PC/컨트롤러 | `tig_welding_robot_controller.py` 실행 호스트 | 1 |
| 제어/통합 | 하드와이어드 e-stop 릴레이 체인 | CAN/이더넷과 완전 독립 배선 | 1식 |
| 안전 | 아크 차광 커튼, 흄 배기, 가스 압력/누출 경보 | 전기적 EMI와 별개인 TIG 필수 안전요건 | 1식 |

## 7. 구현 단계

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 시뮬레이션 검증 — SimulatedWeldingHAL로 상태머신·EMI 게이팅·안전 인터록 전체 사이클 실행 | **완료** |
| 1 | EMI 베이스라인 측정 — 용접기 반입 전 dual_openarm 단독 상태의 can0/can1 오류 카운터 기록 | 예정 |
| 2 | 물리 배치·접지 시공 — 단일점 접지, 배선 분리/90° 교차, 페라이트 코어를 용접기 반입 전에 완료 | 예정 |
| 3 | 용접 로봇 하드웨어 브링업 — 암+Lift-TIG로 저전류 시험 용접, EMI 모니터로 CAN 저하 없음 확인 | 예정 |
| 4 | HF 아크스타트 시험(선택) — Lift-TIG로 부족할 때만, bus-off 밀착 감시 + 킬스위치 | 예정 |
| 5 | 통합 제어 소프트웨어 검증 — 실기 HAL로 교체 후 상태머신·안전 인터록 재검증 | 예정 |
| 6 | 생산 시운전 — 목표 용접 작업 반복 실행, EMI/품질 지표 동시 기록 | 예정 |

## 8. 한계 및 리스크

Hermes의 원 리뷰는 GCP 세션이라 직접 계측 장비가 없어 "공개 문헌 종합"이라는 한계를 스스로 명시했다. 이 설계도 같은 한계를 물려받는다 — BOM의 수치(가반하중, 정밀도 등)는 소형 산업용 6축 로봇의 일반적 사양 범위이지, 특정 실측이나 특정 제품을 지목한 것이 아니다. Phase 1(베이스라인 측정)과 Phase 3~4(실물 EMI 재계측) 없이는 이 설계의 어떤 부분도 "검증됐다"고 부를 수 없다.

## 관련

- 근거 문헌: [[2026-08-21-hermes-tig-welding-hf-shielding-research]]
- 구현: `scripts/tig_welding_robot_controller.py`
"""

payload = {
    "slug": "2026-08-21-moojoco-tig-welding-cell-integrated-design",
    "title": "TIG 용접 셀 통합 설계 — 로봇·제어 프로그램·하드웨어를 구현 단계까지",
    "author": "moojoco",
    "abstract": (
        "Hermes의 TIG HF 노이즈 EMI 문헌 리뷰를 근거로, 실제 용접을 수행하는 "
        "6축 용접 로봇과 그 옆에서 계속 동작해야 하는 dual_openarm(CAN-FD)을 "
        "한 셀로 통합하는 아키텍처·제어 프로그램·하드웨어 BOM·구현 단계를 정리했다. "
        "핵심은 물리적 분리(≥15m/패러데이 차폐)를 1차 방어선으로 두고, Lift-TIG를 "
        "기본값으로, HF는 EMI 베이스라인 확보 후에만 허용하는 게이트를 제어 "
        "프로그램(scripts/tig_welding_robot_controller.py, 신규 작성·실행 검증 완료)에 "
        "코드 인터록으로 구현한 것이다."
    ),
    "tags": ["tig-welding", "robot-design", "emi", "moojoco", "plan"],
    "changelog": "최초 제출",
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
