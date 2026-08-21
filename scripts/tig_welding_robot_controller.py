#!/usr/bin/env python3
"""TIG 용접 로봇 셀 제어 프로그램 (ROOPS 통합 셀 설계).

thesis `2026-08-21-hermes-tig-welding-hf-shielding-research`가 제기한 문제 —
TIG HF 아크 스타터(15~20kV, 수 MHz 펄스)가 인접한 dual_openarm의 CAN-FD
버스(can0/can1, 1M/5Mbps)에 EMI를 유발할 수 있다 — 를 제어 소프트웨어
레벨에서 반영한 용접 셀 컨트롤러다.

설계 원칙(전부 위 thesis의 5단계 완화안에서 그대로 가져옴):
  1. 용접 로봇과 dual_openarm은 물리적으로 분리된 별도 셀 — 이 컨트롤러는
     dual_openarm의 CAN 버스를 "감시"만 하지 직접 구동하지 않는다.
  2. HF 아크 스타트는 최후 수단 — 기본 모드는 Lift-TIG("lift"), HF는
     명시적으로 요청했을 때만("hf") 그리고 EMI 베이스라인이 먼저 확보된
     경우에만 허용한다.
  3. "측정 없이 결론 금지" 원칙에 따라, 아크를 켜기 전/후로 CAN 버스
     오류 카운터(berr-counter, bus-off, restart-ms)를 비교 계측한다
     (EMIHealthMonitor.compare_to_baseline).
  4. 실제 용접 로봇/용접기 하드웨어가 아직 없으므로 HAL(SimulatedWeldingHAL)로
     전체 시퀀스를 지금 실행·검증할 수 있게 하고, 실기 도입 시
     WeldingHAL의 다른 구현체(예: 릴레이 보드 시리얼 인터페이스)로
     교체만 하면 상태머신·안전 인터록은 그대로 재사용된다.

이 파일 하나로 지금 당장 `python3 tig_welding_robot_controller.py` 실행이
가능하다(실물 용접기·can0/can1 없이도 시뮬레이션 HAL로 전체 사이클 동작).
"""
from __future__ import annotations

import abc
import argparse
import dataclasses
import enum
import logging
import re
import subprocess
import time

logger = logging.getLogger("tig_weld_cell")


# ───────────────────────── EMI 헬스 모니터 (thesis 5단계 반영) ─────────────────────────

@dataclasses.dataclass
class CanLinkStats:
    iface: str
    present: bool
    tx_errors: int = 0
    rx_errors: int = 0
    bus_off: bool = False
    restarts: int = 0


class EMIHealthMonitor:
    """dual_openarm의 CAN-FD 버스(can0/can1) 오류 카운터를 감시한다.

    실제 오류 통계는 SocketCAN이 netlink로 노출하므로 `ip -details
    -statistics link show <iface>`를 파싱해서 얻는다(python-can은 이
    통계를 이식성 있게 노출하지 않아, 이 프로젝트의 기존 `check_can.py`처럼
    python-can으로 직접 프레임을 세는 대신 커널 통계를 신뢰한다).
    """

    IFACES = ("can0", "can1")
    _BERR_RE = re.compile(r"berr-counter tx (\d+) rx (\d+)")

    def read_stats(self, iface: str) -> CanLinkStats:
        try:
            out = subprocess.run(
                ["ip", "-details", "-statistics", "link", "show", iface],
                capture_output=True, text=True, timeout=2,
            )
        except FileNotFoundError:
            return CanLinkStats(iface, present=False)

        if out.returncode != 0 or "does not exist" in out.stderr:
            return CanLinkStats(iface, present=False)

        text = out.stdout
        m = self._BERR_RE.search(text)
        tx_err, rx_err = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        bus_off = "BUS-OFF" in text or "bus-off" in text
        restarts_m = re.search(r"restart-ms \d+.*?\n.*?(\d+)\s+\d+\s+\d+\s+\d+\s+\d+", text)
        restarts = int(restarts_m.group(1)) if restarts_m else 0
        return CanLinkStats(iface, present=True, tx_errors=tx_err, rx_errors=rx_err,
                             bus_off=bus_off, restarts=restarts)

    def snapshot(self) -> dict[str, CanLinkStats]:
        return {iface: self.read_stats(iface) for iface in self.IFACES}

    def capture_baseline(self) -> dict[str, CanLinkStats]:
        baseline = self.snapshot()
        for iface, s in baseline.items():
            if s.present:
                logger.info("[EMI] 베이스라인 %s: tx_err=%d rx_err=%d bus_off=%s",
                            iface, s.tx_errors, s.rx_errors, s.bus_off)
            else:
                logger.warning("[EMI] %s 인터페이스 없음 — 이 셀에는 dual_openarm이 "
                                "물리적으로 연결돼 있지 않거나 CAN이 아직 up되지 않음", iface)
        return baseline

    def compare_to_baseline(self, baseline: dict[str, CanLinkStats]) -> bool:
        """용접 중/후 통계를 베이스라인과 비교. 문제 있으면 False."""
        healthy = True
        for iface, base in baseline.items():
            now = self.read_stats(iface)
            if not base.present or not now.present:
                continue
            d_tx = now.tx_errors - base.tx_errors
            d_rx = now.rx_errors - base.rx_errors
            d_restart = now.restarts - base.restarts
            if now.bus_off or d_restart > 0 or d_tx > 0 or d_rx > 0:
                healthy = False
                logger.error("[EMI] %s 저하 감지: Δtx_err=%d Δrx_err=%d bus_off=%s "
                             "Δrestarts=%d — HF 노이즈 유입 의심, thesis 완화안(접지/"
                             "페라이트/배선분리) 재점검 필요", iface, d_tx, d_rx,
                             now.bus_off, d_restart)
            else:
                logger.info("[EMI] %s 정상 (Δtx_err=%d Δrx_err=%d)", iface, d_tx, d_rx)
        return healthy


# ───────────────────────── 안전 인터록 ─────────────────────────

class EStop:
    """하드와이어드 비상정지 스텁.

    실기에서는 CAN/이더넷과 완전히 분리된 하드와이어 릴레이 체인이어야 한다
    (thesis의 EMI 논의와 별개로, 비상정지는 통신 버스에 절대 의존하면 안
    된다는 것은 일반 로봇 안전 원칙). 여기서는 in-memory 플래그로 대체하되,
    인터페이스는 실제 GPIO 폴링으로 그대로 교체 가능하게 분리해둔다.
    """

    def __init__(self) -> None:
        self._tripped = False

    def trip(self) -> None:
        self._tripped = True

    def is_tripped(self) -> bool:
        return self._tripped


# ───────────────────────── 용접 HAL (Hardware Abstraction Layer) ─────────────────────────

class ArcMode(enum.Enum):
    LIFT = "lift"   # Lift-TIG — thesis 권고 기본값, HF 노이즈 없음
    HF = "hf"       # 고주파 논접촉 스타트 — EMI 리스크, 베이스라인 확보 후에만


class WeldingHAL(abc.ABC):
    """용접 로봇/용접기 하드웨어 추상 인터페이스.

    실기 도입 시 이 클래스를 구현하는 새 백엔드(예: 릴레이 보드를 시리얼로
    제어하는 `SerialRelayWeldingHAL`, 실제 6축 용접 로봇 컨트롤러와 통신하는
    `RobotArmWeldingHAL`)만 추가하면 아래 상태머신·안전 로직은 그대로 쓴다.
    """

    @abc.abstractmethod
    def gas_on(self) -> None: ...

    @abc.abstractmethod
    def gas_off(self) -> None: ...

    @abc.abstractmethod
    def arc_start(self, mode: ArcMode) -> bool:
        """아크 점화 시도. 성공하면 True."""

    @abc.abstractmethod
    def arc_stop(self) -> None: ...

    @abc.abstractmethod
    def move_torch_to(self, x: float, y: float, z: float) -> None: ...

    @abc.abstractmethod
    def travel(self, speed_mm_s: float, duration_s: float) -> None:
        """용접선을 따라 지정 속도로 이동(모의/실제 궤적 실행)."""


class SimulatedWeldingHAL(WeldingHAL):
    """실물 없이 전체 시퀀스를 검증하기 위한 시뮬레이션 백엔드."""

    def gas_on(self) -> None:
        logger.info("[HAL-SIM] 실드가스 ON (Ar, 사전 유량 확인)")

    def gas_off(self) -> None:
        logger.info("[HAL-SIM] 실드가스 OFF")

    def arc_start(self, mode: ArcMode) -> bool:
        logger.info("[HAL-SIM] 아크 스타트 시도: mode=%s", mode.value)
        time.sleep(0.05)
        return True

    def arc_stop(self) -> None:
        logger.info("[HAL-SIM] 아크 정지 (크레이터 필 없이 즉시 컷)")

    def move_torch_to(self, x: float, y: float, z: float) -> None:
        logger.info("[HAL-SIM] 토치 이동 → (%.1f, %.1f, %.1f) mm", x, y, z)

    def travel(self, speed_mm_s: float, duration_s: float) -> None:
        logger.info("[HAL-SIM] 용접 진행: %.1f mm/s x %.1fs", speed_mm_s, duration_s)
        time.sleep(min(duration_s, 0.2))  # 데모용 축소 대기


# ───────────────────────── 용접 시퀀스 상태머신 ─────────────────────────

class WeldState(enum.Enum):
    IDLE = "IDLE"
    APPROACH = "APPROACH"
    PREFLOW = "PREFLOW"
    ARC_START = "ARC_START"
    WELDING = "WELDING"
    ARC_STOP = "ARC_STOP"
    POSTFLOW = "POSTFLOW"
    RETRACT = "RETRACT"
    FAULT = "FAULT"
    DONE = "DONE"


@dataclasses.dataclass
class WeldJob:
    start_xyz: tuple[float, float, float]
    end_xyz: tuple[float, float, float]
    travel_speed_mm_s: float = 3.0
    arc_mode: ArcMode = ArcMode.LIFT
    preflow_s: float = 1.0
    postflow_s: float = 3.0  # 텅스텐 산화 방지, TIG 표준 관행


class WeldCellController:
    """용접 셀 상태머신 + EMI 게이팅 + 안전 인터록을 묶은 최상위 컨트롤러."""

    def __init__(self, hal: WeldingHAL, emi: EMIHealthMonitor, estop: EStop) -> None:
        self.hal = hal
        self.emi = emi
        self.estop = estop
        self.state = WeldState.IDLE

    def _check_estop(self) -> None:
        if self.estop.is_tripped():
            self.state = WeldState.FAULT
            raise RuntimeError("비상정지 활성 — 시퀀스 중단")

    def run(self, job: WeldJob) -> bool:
        logger.info("=== 용접 사이클 시작: mode=%s ===", job.arc_mode.value)
        baseline = None
        try:
            self._check_estop()
            self.state = WeldState.APPROACH
            self.hal.move_torch_to(*job.start_xyz)

            self.state = WeldState.PREFLOW
            self.hal.gas_on()
            time.sleep(min(job.preflow_s, 0.1))

            # thesis 4/5단계: HF 모드는 EMI 베이스라인을 먼저 확보한 뒤에만 허용.
            # Lift-TIG는 HF 방사가 없으므로 게이팅 없이 진행(비용효율 최우선 권고).
            if job.arc_mode is ArcMode.HF:
                baseline = self.emi.capture_baseline()
                if not any(s.present for s in baseline.values()):
                    logger.warning("[EMI] can0/can1 미검출 — 이 셀에는 dual_openarm이 "
                                    "물리적으로 없다고 판단, HF 진행은 허용하되 "
                                    "실배치 전 반드시 재계측할 것")

            self._check_estop()
            self.state = WeldState.ARC_START
            if not self.hal.arc_start(job.arc_mode):
                raise RuntimeError("아크 점화 실패")

            self.state = WeldState.WELDING
            dist = sum((a - b) ** 2 for a, b in zip(job.start_xyz, job.end_xyz)) ** 0.5
            duration = dist / job.travel_speed_mm_s if job.travel_speed_mm_s else 0.0
            self.hal.travel(job.travel_speed_mm_s, duration)
            self.hal.move_torch_to(*job.end_xyz)

            self.state = WeldState.ARC_STOP
            self.hal.arc_stop()

            self.state = WeldState.POSTFLOW
            time.sleep(min(job.postflow_s, 0.1))
            self.hal.gas_off()

            if baseline is not None:
                ok = self.emi.compare_to_baseline(baseline)
                if not ok:
                    logger.error("EMI 저하가 감지됐다 — thesis 완화안(접지/페라이트/"
                                 "배선분리/Lift-TIG 전환)을 재점검하고 재배치 전까지 "
                                 "HF 모드 사용을 보류할 것")

            self.state = WeldState.RETRACT
            self.hal.move_torch_to(job.end_xyz[0], job.end_xyz[1], job.end_xyz[2] + 50.0)

            self.state = WeldState.DONE
            logger.info("=== 용접 사이클 완료 ===")
            return True
        except Exception:
            self.state = WeldState.FAULT
            self.hal.arc_stop()
            self.hal.gas_off()
            logger.exception("용접 사이클 중단 (FAULT)")
            return False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(description="ROOPS TIG 용접 셀 컨트롤러 데모")
    parser.add_argument("--mode", choices=["lift", "hf"], default="lift")
    args = parser.parse_args()

    hal = SimulatedWeldingHAL()
    emi = EMIHealthMonitor()
    estop = EStop()
    controller = WeldCellController(hal, emi, estop)

    job = WeldJob(
        start_xyz=(300.0, 0.0, 50.0),
        end_xyz=(300.0, 120.0, 50.0),
        travel_speed_mm_s=3.0,
        arc_mode=ArcMode(args.mode),
    )
    ok = controller.run(job)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
