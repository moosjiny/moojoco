#!/usr/bin/env python3
import asyncio
import os
import time
from playwright.async_api import async_playwright
from PIL import Image

OUT_DIR = "/home/moos/dev_ws/images/moojoco"
os.makedirs(OUT_DIR, exist_ok=True)

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--enable-webgl",
                "--use-gl=angle",
                "--use-angle=swiftshader-webgl",
            ]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        print("Navigating to http://localhost:8600/handshake/...")
        await page.goto("http://localhost:8600/handshake/", wait_until="networkidle")
        await asyncio.sleep(2.0)  # Wait for Three.js to render

        # 1. Overview Capture (APPROACH / DOCK)
        print("Capturing Overview...")
        await page.evaluate("currentTime = 1.2; isPlaying = false;")
        await asyncio.sleep(0.5)
        path1 = os.path.join(OUT_DIR, "handshake_studio_overview_approach.png")
        await page.screenshot(path=path1)
        print(f"Saved {path1}")

        # 2. V-Web Macro View (DOCKING / LATCH)
        print("Capturing V-Web Macro View...")
        await page.click("#cam-vweb")
        await page.evaluate("currentTime = 3.2; isPlaying = false;")
        await asyncio.sleep(0.5)
        path2 = os.path.join(OUT_DIR, "handshake_studio_vweb_docking_macro.png")
        await page.screenshot(path=path2)
        print(f"Saved {path2}")

        # 3. Dynamic Shake Profile View (SHAKE)
        print("Capturing Shake Profile View...")
        await page.click("#cam-profile")
        await page.evaluate("currentTime = 6.2; isPlaying = false;")
        await asyncio.sleep(0.5)
        path3 = os.path.join(OUT_DIR, "handshake_studio_dynamic_shake_profile.png")
        await page.screenshot(path=path3)
        print(f"Saved {path3}")

        # 4. Top-Down V-Crotch View (TOP-DOWN)
        print("Capturing Top-Down View...")
        await page.click("#cam-top")
        await page.evaluate("currentTime = 4.5; isPlaying = false;")
        await asyncio.sleep(0.5)
        path4 = os.path.join(OUT_DIR, "handshake_studio_topdown_vcrotch.png")
        await page.screenshot(path=path4)
        print(f"Saved {path4}")

        # 5. Animated GIF Capture: 24 frames across 12-second lifecycle
        print("Capturing GIF frames...")
        await page.click("#cam-overview")
        frames = []
        for i in range(24):
            t = (i / 24.0) * 12.0
            await page.evaluate(f"currentTime = {t}; isPlaying = false;")
            await asyncio.sleep(0.1)
            frame_bytes = await page.screenshot()
            from io import BytesIO
            img = Image.open(BytesIO(frame_bytes)).resize((800, 450), Image.Resampling.LANCZOS)
            frames.append(img)
            print(f"  Frame {i+1}/24 (t={t:.1f}s)")

        gif_path = os.path.join(OUT_DIR, "hyperhandshake_6phase_lifecycle.gif")
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=200,  # 5 fps for compact, smooth presentation
            loop=0,
            optimize=True
        )
        print(f"Saved GIF to {gif_path} (size: {os.path.getsize(gif_path)} bytes)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture())
