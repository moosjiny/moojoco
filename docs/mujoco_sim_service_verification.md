# mujoco_sim.service 정상 동작 확인 절차

**작성**: Moojoco · 2026-07-03
**대상**: `/etc/systemd/system/mujoco_sim.service` 배치 후 검증
**전제**: `sudo systemctl enable --now mujoco_sim` 실행 완료 상태

이 문서는 mujoco_sim.service가 (1) 정상 기동됐는지, (2) 실제로 GPU를 사용해 렌더링 중인지, (3) 외부에서 결과를 확인할 수 있는지, (4) 장애 시 자동 복구되는지를 순서대로 검증하는 절차다. 각 단계는 이전 단계 성공을 전제로 하므로 순서대로 진행한다.

## 1단계 — systemd 상태 확인

```bash
sudo systemctl status mujoco_sim --no-pager
sudo systemctl is-active mujoco_sim
sudo systemctl is-enabled mujoco_sim
```

**기대 결과**:
- `is-active` → `active`
- `is-enabled` → `enabled` (재부팅 시 자동 시작 보장)
- `status`에 `Main PID` 존재, `(running)` 상태

**실패 시**: `status` 출력의 `Active:` 줄에 `failed`가 뜨면 2단계(로그 확인)로 바로 이동해 원인 파악.

## 2단계 — 로그로 기동 시퀀스 확인

```bash
sudo journalctl -u mujoco_sim -n 100 --no-pager
```

정상 기동 시 아래 로그가 순서대로 나와야 한다 (`scripts/sim_dual_arm.py`의 실제 print 지점 기준):

1. `Dual-arm sim started (EGL GPU rendering)` — MuJoCo 모델 로드 + EGL 렌더러 4개(top/front/좌팔목/우팔목) 생성 완료, Rerun 서버 기동 완료
2. `Camera 'xxx': id=N` — 카메라별 등록 로그 (4줄 내외 기대)
3. 이후 주기적으로 `frame=N t=X.Xs joint=...` — 시뮬레이션 루프가 실제로 돌고 있다는 증거. **이 로그가 몇 초 간격으로 계속 갱신되면 정상**

**주의 신호** (이 문자열이 보이면 실패로 간주):
- `Mesh load error ...`, `Finger mesh error ...` — 메쉬 파일 경로 문제
- `Traceback (most recent call last)` — 파이썬 예외로 프로세스 종료
- `EGL` 관련 초기화 실패 메시지 (예: `MUJOCO_GL` 관련 오류) — GPU/드라이버 문제

실시간으로 계속 지켜보려면:
```bash
sudo journalctl -u mujoco_sim -f
```

## 3단계 — 프로세스·GPU 실제 사용 확인

```bash
ps aux | grep sim_dual_arm | grep -v grep
nvidia-smi
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

**기대 결과**:
- `ps aux`에 `/home/moos/venv/dual_arms/bin/python3 scripts/sim_dual_arm.py` 프로세스 존재
- `nvidia-smi` Processes 섹션에 해당 PID가 GPU 메모리를 점유한 상태로 표시 (수십~수백 MiB 이상 — EGL 컨텍스트 + 4개 렌더러 버퍼)
- `nvidia-smi`의 `GPU-Util`이 0%에 고정되지 않고 렌더 프레임마다 순간적으로 증가

이전 조사(`mujoco_gpu_service_design.md`)에서 idle 시 GPU는 13MiB/0%였으므로, 서비스 기동 후 이 값이 명확히 올라가야 "진짜 GPU를 쓰고 있다"는 증거가 된다.

## 4단계 — Rerun 스트림 포트 리스닝 확인

```bash
ss -tlnp | grep -E ':(9090|9876)'
```

**기대 결과**: 두 줄 모두 존재
- `:9876` — Rerun gRPC 서버 (`server_uri = rr.serve_grpc(grpc_port=9876, ...)`)
- `:9090` — Rerun 웹뷰어 (`rr.serve_web_viewer(web_port=9090, ...)`)

## 5단계 — 웹뷰어 실제 접근 확인

로컬(hb5u)에서:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9090
```
→ `200` 기대

원격(사령관 PC 등)에서 확인하려면 Tailscale 경유:
```
http://100.125.27.70:9090
```
브라우저로 접속해 3D 로봇 모델이 렌더링되고, 카메라 뷰(top/front/좌우 손목)에 실시간 프레임이 갱신되는지 육안 확인.

**주의**: 이 포트는 현재 nginx/방화벽으로 공개 도메인에 노출되어 있지 않음(`mujoco_gpu_service_design.md` 4번 항목, 미정 상태). Tailscale IP로만 접근 가능해야 정상이며, 외부 공개가 필요하면 별도 nginx 라우팅 작업이 선행돼야 한다.

## 6단계 — 장애 자동 복구(Restart=always) 검증

의도적으로 프로세스를 죽여서 systemd가 자동 재기동하는지 확인:

```bash
sudo systemctl kill -s SIGKILL mujoco_sim
sleep 7
sudo systemctl status mujoco_sim --no-pager
sudo journalctl -u mujoco_sim -n 20 --no-pager
```

**기대 결과**:
- `RestartSec=5` 설정에 따라 킬 후 약 5초 뒤 프로세스가 재기동됨
- `status`가 다시 `active (running)`으로 복귀
- 로그에 `Dual-arm sim started (EGL GPU rendering)`가 새로 한 번 더 찍힘 (재시작 증거)
- `systemctl status`의 재시작 카운터가 1 증가

이 단계가 이번 서비스화의 핵심 목적(voronoi_gpu_service가 겪은 "죽으면 아무도 안 돌아옴" 문제 예방)이므로 반드시 실제로 검증할 것.

## 7단계 — 재부팅 후 자동 시작 확인 (선택, 리스크 있음)

즉시 재부팅은 다른 서비스(viz_server 등)에도 영향을 주므로 필수 단계는 아니다. 필요 시에만:
```bash
sudo systemctl is-enabled mujoco_sim   # enabled 확인만으로 충분한 대체 검증
```
실제 재부팅 테스트를 원하면 사령관 승인 후 별도로 진행.

## 8단계 — 완료 판정 체크리스트

| 항목 | 확인 방법 | 통과 기준 |
|---|---|---|
| systemd 활성 | `systemctl is-active` | `active` |
| 부팅 시 자동시작 | `systemctl is-enabled` | `enabled` |
| 기동 로그 | `journalctl -u mujoco_sim` | 에러 없이 `Dual-arm sim started` + 주기적 `frame=` 로그 |
| GPU 실사용 | `nvidia-smi` | idle 대비 GPU 메모리·사용률 증가 |
| 포트 리스닝 | `ss -tlnp` | 9090, 9876 모두 LISTEN |
| 웹뷰어 접근 | `curl`/브라우저 | HTTP 200, 3D 렌더 확인 |
| 자동 복구 | SIGKILL 후 관찰 | 5초 내 재기동, 재시작 카운터 증가 |

7개 항목 모두 통과하면 "정상 배치 완료"로 간주하고 roops-comm에 보고한다.
