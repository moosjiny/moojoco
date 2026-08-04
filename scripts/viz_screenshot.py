#!/usr/bin/env python3
"""thesis-3d 각 탭 스크린샷 — EROS 시각 확인용

사용법:
  python3 viz_screenshot.py            # 현재 호스트에서 촬영
  python3 viz_screenshot.py --send     # 촬영 후 EC2 thesis-web assets에 복사 (hb5u 전용)
"""
import sys
import socket
from pathlib import Path
from playwright.sync_api import sync_playwright

URL    = "https://ers.hyperbook.com/viz/thesis-3d"
OUT    = Path("/tmp/viz_tabs")
TABS   = [
    ("network",  "#btn-network"),
    ("keywords", "#btn-keywords"),
    ("synapse",  "#btn-synapse"),
]
WAIT_MS  = 4000
HOST     = socket.gethostname()
EC2_DEST = "ec2-user@ec2.hyperbook.com:/home/ec2-user/hyperbook/services/thesis-web/assets/viz/"

def shoot(send=False):
    OUT.mkdir(exist_ok=True)
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print(f"[{HOST}] → {URL} 로딩 중...")
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(WAIT_MS)

        for tab_name, btn_sel in TABS:
            print(f"[{HOST}] → {tab_name} 탭...")
            page.click(btn_sel)
            page.wait_for_timeout(WAIT_MS)
            path = OUT / f"{HOST}_viz_{tab_name}.png"
            page.screenshot(path=str(path))
            print(f"   저장: {path}")
            files.append(path)

        # synapse → keywords 전환 시나리오
        print(f"[{HOST}] → synapse → keywords 전환...")
        page.click("#btn-synapse")
        page.wait_for_timeout(2000)
        page.click("#btn-keywords")
        page.wait_for_timeout(WAIT_MS)
        path = OUT / f"{HOST}_viz_keywords_after_synapse.png"
        page.screenshot(path=str(path))
        print(f"   저장: {path}")
        files.append(path)

        browser.close()

    if send:
        import subprocess
        print(f"[{HOST}] → EC2 전송 중...")
        for f in files:
            subprocess.run(["scp", str(f), EC2_DEST], check=True)
            print(f"   전송: {f.name}")

    print(f"[{HOST}] 완료. {len(files)}장")
    return files

if __name__ == "__main__":
    shoot(send="--send" in sys.argv)
