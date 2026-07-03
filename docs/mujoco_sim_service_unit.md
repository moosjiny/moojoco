# mujoco_sim.service 유닛 파일 작성 — 배경, 이유, 계획

**작성**: Moojoco · 2026-07-03
**관련 문서**: [mujoco_gpu_service_design.md](./mujoco_gpu_service_design.md) (2026-07-03, GPU 서비스 분리 설계 초안)
**파일**: `/home/moos/dev_ws/dual_arms/mujoco_sim.service`

## 1. 배경

2026-07-03, Aegis가 roops-comm에 `hb5u:8892 (voronoi_gpu_service)` Connection refused 장애를 보고하며 Haru에게 재기동을 요청했다. Moojoco는 이 보고를 계기로 hb5u 전체의 GPU 서비스 구조를 점검했다.

조사 결과:
- `voronoi_gpu_service.py`(Haru 소유, ConnectAI-LAB-Template)는 cupy 기반 stateless GPU API지만 **systemd 미등록** 상태였고, 이것이 이번 장애(수동 기동 프로세스가 죽은 뒤 아무도 복구하지 못함)의 근본 원인으로 추정됐다.
- Moojoco의 `viz_server.py`(:8891)는 조사 결과 서버 GPU 연산이 전혀 없었다 — 3D 논문 네트워크 렌더링은 브라우저 Three.js/WebGL이 담당하고, 서버는 `pynvml`로 GPU 사용률을 모니터링만 한다.
- 반면 `scripts/sim_dual_arm.py`는 **실제로 GPU를 쓰는** MuJoCo EGL 렌더링(4채널 카메라: top/front/좌팔목/우팔목) + Rerun 스트리밍(gRPC :9876, 웹뷰어 :9090) 스크립트였는데, voronoi_gpu_service와 동일하게 **systemd 미등록, 수동 실행** 상태였다.

즉 hb5u에는 "systemd로 관리되지 않아 장애 시 복구가 안 되는 GPU 프로세스"가 최소 두 개(voronoi_gpu_service, sim_dual_arm.py) 있었고, 이번 장애는 그중 하나가 먼저 드러난 사례였다.

## 2. 이유 — 왜 systemd 서비스화가 필요한가

1. **장애 재발 방지**: voronoi_gpu_service와 동일한 구조적 취약점(수동 기동 → 크래시/재부팅 시 무응답)을 sim_dual_arm.py도 그대로 갖고 있다. `Restart=always`로 자동 복구되게 만들면 동일 유형의 장애를 예방할 수 있다.
2. **운영 일관성**: viz_server.py는 이미 `viz_server.service`(systemd)로 관리되고 있다. sim_dual_arm.py만 예외적으로 스크립트 상태로 남아있는 것은 관리 방식의 비일관성이다.
3. **관측 가능성**: systemd 등록 시 `journalctl -u mujoco_sim`으로 로그를 중앙에서 확인할 수 있어, 원격지(Aegis, EC2)에서도 장애 진단이 쉬워진다.
4. **외부 에이전트 연동의 전제조건**: EROS 등 다른 에이전트가 dual-arm 시뮬레이션의 카메라 스트림/상태를 API나 Rerun 뷰어로 구독하려면, 그 서비스가 상시 가용해야 한다. 수동 스크립트로는 이 전제를 만족할 수 없다.

## 3. 유닛 파일 내용

```ini
[Unit]
Description=Moojoco MuJoCo Dual-Arm Sim (EGL GPU Rendering + Rerun Stream)
After=network.target

[Service]
Type=simple
User=moos
WorkingDirectory=/home/moos/dev_ws/dual_arms
ExecStart=/home/moos/venv/dual_arms/bin/python3 scripts/sim_dual_arm.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

기존 `viz_server.service`와 동일한 패턴(`Type=simple`, `User=moos`, `Restart=always`, `RestartSec=5`)을 재사용해 운영 방식을 통일했다. 차이점:
- `MUJOCO_GL=egl`은 `sim_dual_arm.py` 코드 내부에서 `os.environ`으로 이미 설정하므로 유닛 파일에 별도 `Environment=` 불필요
- Redis 등 viz_server 전용 환경변수는 sim_dual_arm.py에 해당 없음
- `After=nginx.service` 의존성은 제외 — Rerun 웹뷰어(:9090)의 nginx 프록시 여부가 아직 미정이기 때문 (아래 4번 참고)

**현재 상태**: 유닛 파일은 저장소(`/home/moos/dev_ws/dual_arms/mujoco_sim.service`)에 작성만 완료했다. `/etc/systemd/system/`에 배치·`systemctl enable --now`는 아직 진행하지 않았다 — 사령관 검토 후 실행 여부를 결정할 예정이다.

## 4. 계획 (다음 단계)

- [ ] 사령관 검토 승인 후 `/etc/systemd/system/mujoco_sim.service`에 배치, `systemctl daemon-reload && systemctl enable --now mujoco_sim`
- [ ] 기동 확인: `journalctl -u mujoco_sim -f`, GPU 사용률(`nvidia-smi`)로 EGL 렌더링 정상 동작 확인
- [ ] Rerun 웹뷰어(:9090) 외부 노출 여부 결정 — nginx 리버스 프록시 추가할지, Tailscale 내부망으로만 열지 Aegis와 조율
- [ ] 경량 `/health` 엔드포인트 추가 검토 (voronoi_gpu_service, viz_server와 동일하게 상태 조회 가능하도록)
- [ ] EROS 등 외부 에이전트가 실제로 필요로 하는 데이터 형태(카메라 프레임 스냅샷 vs 조인트 상태 vs Rerun 뷰 전체) 확인 후 API 형태 확정

## 5. Moojoco 원래 임무와의 관계

CLAUDE.md에 정의된 Moojoco의 역할은 **"MuJoCo 메인 서버 — Phase 4 음성·멀티툴 워크샵 시뮬레이션 담당"**이다. `sim_dual_arm.py`는 이 임무를 실제로 수행하는 핵심 실행체 — dual-arm 로봇의 물리 시뮬레이션과 카메라 렌더링을 담당하는 바로 그 스크립트다.

지금까지 이 스크립트는 "필요할 때 사람이 켜는 데모용 스크립트"로 존재해왔다. 그런데 다음 미션 후보로 명시된 항목들:
1. actuator 토크 제어 (mj_step 기반 동역학)
2. LeRobot 데이터 연동 (10 에피소드 omx_follower)
3. CAN-FD 하드웨어 연결 (Damiao 모터)
4. IK 제어 (역기구학 양팔 조작)

은 모두 `sim_dual_arm.py`(또는 그 확장)를 **지속적으로, 안정적으로 실행되는 상태**로 전제한다. 예를 들어 CAN-FD 하드웨어 연결이나 LeRobot 데이터 수집은 시뮬레이션이 세션 중간에 죽지 않고 계속 돌아가야 의미가 있고, 외부 에이전트(EROS)가 워크샵 시뮬레이션 상태를 구독하려면 서비스가 상시 가용해야 한다.

즉 이번 systemd 서비스화 작업은 지엽적인 인프라 정리가 아니라, **Moojoco 본연의 임무(워크샵 시뮬레이션)를 데모 스크립트 단계에서 운영 가능한 서비스 단계로 승격시키는 작업**이며, 향후 액추에이터 제어·하드웨어 연동·IK 제어 등 모든 다음 단계 미션의 인프라적 전제조건이 된다.
