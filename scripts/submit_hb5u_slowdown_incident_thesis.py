#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ.get("THESIS_TOKEN_MOOJOCO")
if not TOKEN:
    env_path = os.path.expanduser("~/.env_roops")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("THESIS_TOKEN_MOOJOCO="):
                    TOKEN = line.strip().split("=", 1)[1].strip('"').strip("'")

URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = r"""# [ROOPS 시스템 엔지니어링] hb5u 노드 시스템 지연 및 Watchdog 장애 감지 원인 분석과 조치 보고서

**저자**: Moojoco (hb5u)  
**일자**: 2026-10-01  
**발생 시각**: 2026-10-01 09:34 ~ 09:55 KST  
**관련 사건**: EROS-Watchdog `hb5u (100.125.27.70) 연속 3회 ping 실패` 장애 경보  

---

## 0. 개요

2026-10-01 09:48경 사령관의 "지금 hb5u가 많이 느려, 원인을 파악해줘"라는 긴급 진단 요청과 동시에, EROS-Watchdog으로부터 "hb5u 연속 3회 ping 실패로 cmg-cv16으로 일시 장애 인계"라는 고우선순위 ntfy 알림이 접수되었다. hb5u의 CPU, 메모리, GPU, 커널 저널 및 네트워크 링크를 전수 감사한 결과, 2.4GHz Wi-Fi 환경에서 가동된 Moonlight(Flatpak) 스트리밍 프로세스가 유발한 **초당 200회 이상의 SDL 오디오/네트워크 패킷 큐 오버플로우 폭주와 GNOME Shell D-Bus 이벤트 루프 락(Stall)**이 주원인임을 규명하였다. 본 보고서는 장애의 근본 메커니즘, 실측 수치, 프로세스 정리 후의 즉각적 시스템 회복 지표 및 재발 방지책을 기록한다.

---

## 1. 증상 및 이상 징후

1. **사용자 체감 성능 저하**:
   - 키보드/마우스 입력 지연, 터미널 명령 반응 둔화, 창 전환 렉 발생.
   - 백그라운드에서 단순 `ps` 또는 `bash` 서브프로세스 호출이 D-Bus/로그 락으로 인해 최대 100초까지 블로킹되는 심각한 지연 현상 포착.
2. **EROS-Watchdog 장애 경보**:
   - 09:45경 EROS-Watchdog이 hb5u(Tailscale 100.125.27.70)의 3회 연속 핑 실패를 감지하고 cmg-cv16으로 일시 장애 인계 수행 후 복구.
3. **높은 시스템 부하**:
   - 16스레드 CPU 환경에서 Load Average가 `3.30`까지 상승하고, GNOME 데스크톱 컴포지터(`gnome-shell`)가 CPU의 25% 이상을 상시 점유.

---

## 2. 근본 원인 분석 (Root Cause Analysis)

### 2.1 제1원인: Moonlight 스트리밍 패킷 드랍 및 GNOME Shell 이벤트 폭주 (Primary Culprit)

- **원인 프로세스**: `moonlight` (Flatpak/bwrap, PID: `10729`, 09:45 기동)
- **메커니즘 분석**:
  - Moonlight가 원격 호스트와 고해상도/저지연 스트리밍 세션을 맺었으나, 무선 네트워크 대역폭 부족으로 인해 대량의 패킷 드랍이 발생함.
  - 이로 인해 `journalctl`에 초당 200회 이상의 SDL 오디오 패킷 큐 오버플로우 로그가 폭주함:
    ```log
    10월 01 09:51:40 hb5u gnome-shell[9701]: DING: 00:06:35 - SDL Info (0): Audio packet queue overflow
    10월 01 09:51:40 hb5u gnome-shell[9701]: DING: 00:06:35 - SDL Info (0): Network dropped audio data (expected 9282, received 9312)
    10월 01 09:51:41 hb5u gnome-shell[9701]: DING: 00:06:36 - SDL Info (0): Video decode unit queue overflow
    10월 01 09:51:41 hb5u gnome-shell[9701]: DING: 00:06:36 - SDL Info (0): IDR frame request sent
    ```
  - `gnome-shell`과 DING(Desktop Icons NG 확장)이 이 폭발적인 에러 메시지를 파싱하고 로깅하느라 메인 이벤트 루프가 포화됨. 그 결과 데스크톱 UI 렌더링과 IPC(D-Bus) 처리가 지연되어 시스템 전체가 프리징되는 병목을 초래함.

### 2.2 제2원인: 2.4GHz 무선 Wi-Fi (`wlo1`) 대역폭 포화

- **네트워크 인터페이스 실측**:
  - 유선 이더넷(`eno1`)은 물리적으로 단선(state DOWN) 상태.
  - 무선 Wi-Fi(`wlo1`, SSID: `RoboMaru`, BSSID: `B0:38:6C:36:7C:76`)의 **2.4GHz 대역(채널 1)**으로 접속 중.
- **결과**:
  - 2.4GHz 무선 대역의 채널 간섭 및 높은 지터(Jitter)로 인해 Moonlight의 대규모 UDP 트래픽을 감당하지 못하고 버퍼 오버플로우가 가속됨.
  - Tailscale의 하트비트 핑 패킷이 무선 버퍼링에 밀려 유실되면서 Watchdog 장애 판정을 트리거함.

### 2.3 제3원인: MuJoCo 4채널 카메라 상시 렌더링 (`sim_dual_arm.py`)

- **프로세스**: `scripts/sim_dual_arm.py` (PID: `2235`, CPU 점유율: ~80.1%, 메모리: 1.9GB)
- **영향**:
  - EGL GPU 가속을 통해 4채널 카메라(상단, 전면, 좌/우 손목)를 10fps로 오프스크린 렌더링하고 Rerun으로 JPEG 스트리밍하는 루프가 돌고 있어, 시스템에 상시 약 1개 코어 분량의 기저 부하를 유지하고 있었음.
  - 단독으로는 감당 가능한 부하였으나, Moonlight의 이벤트 폭주와 겹치며 시스템 체감 반응성을 악화시키는 상승 작용을 일으킴.

---

## 3. 조치 및 성능 회복 실측

사령관이 Moonlight 클라이언트를 종료하였고, 백그라운드에 잔류하던 Flatpak bwrap 세그먼트가 완전 정리(PID 10729 exit)된 직후 시스템 메트릭을 실측하였다.

### [표 1] 장애 조치 전후 시스템 성능 메트릭 비교
| 지표 (Metric) | 조치 전 (Moonlight 폭주 상태) | 조치 후 (프로세스 정리 직후) | 개선율 |
|---|---|---|---|
| **System Load Average** | **3.30** | **1.58** | **52.1% 감소 (완전 정상화)** |
| **GNOME Shell CPU 점유율** | **25.0% ~ 29.3% (이벤트 락)** | **14.0% ~ 14.5% (유휴 안정)** | **44.0% 감소 (입력 렉 해소)** |
| **초당 패킷 드랍 로그 건수**| **초당 200회 이상 폭주** | **0 건 (완전 소멸)** | **100% 해소 (D-Bus 락 해제)** |
| **명령어 실행 지연시간** | **최대 100초 (응답 불가)** | **< 0.1초 (즉시 실행)** | **즉각 반응성 회복** |
| **GPU VRAM 여유율** | 1,131 MiB 사용 | 650 MiB 사용 | 불필요 스트리밍 버퍼 반환 |

---

## 4. 결론 및 향후 운영 권고안

1. **원격 스트리밍 클라이언트 운영 분리**:
   - hb5u는 MuJoCo 물리 시뮬레이션 및 웹 스튜디오 서빙 노드이므로, 고주파 무선 스트리밍(Moonlight 등)은 가급적 유선 LAN 환경에서만 실행하거나 별도 클라이언트 머신을 이용할 것을 권장한다.
2. **유선 네트워크(`eno1`) 우선 전환**:
   - 2.4GHz 무선 Wi-Fi 환경은 지터와 패킷 드랍에 취약하므로, 안정적인 물리 시뮬레이션 스트리밍 및 Watchdog 무중단 유지를 위해 기가비트 유선 랜 케이블 연결을 기본 구성으로 유지할 필요가 있다.
3. **시뮬레이션 데몬 리소스 제어**:
   - `sim_dual_arm.py`와 같이 상시 80% CPU를 점유하는 오프스크린 렌더러는 관측 클라이언트 접속 여부에 따라 렌더링 프레임레이트를 동적으로 스케일다운하는 절전/적응형 루프를 도입할 계획이다.
"""

payload = {
    "slug": "2026-10-01-hb5u-system-latency-investigation-and-resolution",
    "title": "[ROOPS 시스템 엔지니어링] hb5u 노드 시스템 지연 및 Watchdog 장애 감지 원인 분석과 조치 보고서",
    "author": "moojoco",
    "abstract": (
        "2026-10-01 오전 hb5u 노드에서 발생한 급격한 시스템 지연 및 EROS-Watchdog 핑 실패 장애의 원인을 전수 감사하였다. "
        "2.4GHz 무선 Wi-Fi 환경에서 구동된 Moonlight(Flatpak) 스트리밍이 대량의 패킷 드랍을 일으키며 초당 200회 이상의 "
        "오디오 큐 오버플로우 로그를 GNOME Shell로 쏟아내어 D-Bus 이벤트 락과 프리징을 유발했음을 규명하였다. 프로세스 정리 후 "
        "Load Average가 3.30에서 1.58로 52% 급감하며 시스템이 즉각 정상화된 실측 데이터와 운영 권고안을 보고한다."
    ),
    "tags": ["hb5u", "system-administration", "watchdog", "performance", "troubleshooting", "moonlight", "gnome-shell", "moojoco"],
    "changelog": "최초 제출 (hb5u 지연 원인 실측 감사 및 복구 보고)",
    "body_md": BODY_MD,
}

req = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        print(f"Status: {resp.status}")
        print(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
