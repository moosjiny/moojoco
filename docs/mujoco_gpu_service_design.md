# MuJoCo GPU 서비스 분리 설계 (초안)

**작성**: Moojoco · 2026-07-03
**계기**: Aegis→Haru voronoi_gpu_service(:8892) 장애 보고 대응 중, 사령관이 hb5u 전체의 GPU 서비스 구조를 점검하고 Moojoco 쪽도 동일 패턴으로 분리할 필요가 있는지 검토 지시.

## 1. 현황 조사 결과

### 1.1 voronoi_gpu_service (:8892) — Haru 소유, Moojoco와 무관
- 위치: `/home/moos/dev_ws/ConnectAI-LAB-Template/voronoi_gpu_service.py`
- cupy(CUDA)로 실제 GPU 연산(Voronoi JFA)을 수행하는 stateless API: `POST /api/voronoi` → PNG
- systemd 유닛 없음 — 수동 기동 방식이라 재부팅/장애 시 자동 복구 안 됨 (이번 장애의 원인으로 추정)
- **dual_arms 저장소와 코드/의존성 공유 없음**

### 1.2 viz_server.py (:8891) — Moojoco 소유, 현재 GPU 연산 없음
- `pynvml`로 GPU 사용률을 **모니터링만** 함 (`/health` 엔드포인트, resource_status 판단용)
- 3D 논문 네트워크 그래프 렌더링은 **브라우저 클라이언트 사이드** (Three.js/WebGL) — 서버 GPU 미사용
- 즉, thesis-3d 뷰어 자체는 분리할 "GPU 처리"를 현재 갖고 있지 않음 (최초 가정과 다름 — 아래 1.3 참고)

### 1.3 sim_dual_arm.py — 실제 GPU 컴퓨트 보유, 현재 서비스화 안 됨
- `scripts/sim_dual_arm.py`: MuJoCo 물리 시뮬레이션 + **EGL GPU 렌더링**(`MUJOCO_GL=egl`, 4채널 카메라: top/front/좌우 손목) + Rerun 스트리밍(gRPC :9876, 웹뷰어 :9090)
- 현재 systemd 미등록, ps 확인 결과 **미실행 상태** — 필요 시 수동 실행하는 스크립트
- voronoi_gpu_service와 달리 **stateless 요청-응답이 아니라 연속 시뮬레이션 루프 + 스트리밍** 구조라 API 형태가 다름

**결론**: hb5u에서 분리가 필요한 실제 GPU 서비스는 viz_server가 아니라 **sim_dual_arm.py**. viz_server(웹/썸네일 UI)는 이미 GPU 연산과 분리되어 있음.

## 2. 목표 아키텍처

```
[웹/UI 레이어]              [GPU 컴퓨트 레이어]
viz_server.py (:8891)       mujoco_sim_service (:9090/9876, 신설)
 - 논문 네트워크 뷰어         - MuJoCo 물리 + EGL 렌더 + Rerun 스트림
 - GPU 모니터링만            - systemd 관리, 독립 재기동
 - (voronoi 무관)            - 외부 에이전트가 API/스트림으로 구독

ConnectAI-LAB-Template       (참고: 동일 패턴 선례)
voronoi_gpu_service (:8892)
 - cupy 기반 stateless API
 - Haru 소유, systemd 부재 → 이번 장애 원인
```

## 3. 제안

1. **sim_dual_arm.py → systemd 서비스화**
   - 유닛명(가칭): `mujoco_sim.service`, `WorkingDirectory=/home/moos/dev_ws/dual_arms`
   - `Restart=always` — voronoi_gpu_service가 겪은 "수동 기동이라 장애 시 무응답" 문제 예방
   - 기존 viz_server.service와 동일한 systemd 패턴 재사용 (이미 검증된 구성)

2. **API 경계 정리**
   - Rerun 웹뷰어(:9090)는 이미 사실상 "서비스 API" 역할 — 문서화만 하면 외부 에이전트(EROS 등)가 URL로 바로 접근 가능
   - 필요 시 상태 조회용 경량 REST(`GET /health` — sim 실행 여부, 마지막 프레임 시각 등) 추가 검토. voronoi_gpu_service의 `/health` 패턴 참고 가능

3. **viz_server.py는 현행 유지**
   - GPU 연산이 없으므로 추가 분리 불필요. `/health`의 GPU 모니터링 필드는 "이 머신의 GPU 여유율"을 보여주는 용도로 계속 유지(다른 GPU 서비스 기동 판단에 참고 가능)

4. **문서/합의 필요 사항**
   - 포트 확정: 9090/9876 유지 or 별도 프록시 경로로 통일할지 (nginx 라우팅 정책은 Aegis/사령관 결정 필요)
   - mujoco_sim_service를 상시 기동할지, 요청 시에만 기동할지 (물리 시뮬레이션은 GPU를 지속 점유하므로 voronoi처럼 요청 단위 stateless로 만들기 어려움 — 상시 기동 + idle 시 저부하 전략이 현실적)
   - EROS 등 외부 에이전트가 실제로 어떤 데이터/스트림이 필요한지 (카메라 프레임? 조인트 상태? Rerun 뷰 전체?) 요구사항 확인 필요

## 4. 다음 단계 (승인 후 진행)
- [ ] mujoco_sim.service 유닛 파일 작성 및 배치
- [ ] `/health` 경량 엔드포인트 추가 여부 결정
- [ ] nginx 라우팅 (필요 시) — Aegis와 조율
- [ ] EROS/다른 에이전트 요구사항 확인 후 API 형태 확정
