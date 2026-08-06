"""
Renders Before vs After Kinematic Handshake Comparison GIF with TCP Frame Axes (RGB = X/Y/Z).

Before: Parallel Orientation (Palms not facing, TCP axes parallel)
After: 180° Symmetric Facing Orientation (Palms facing, TCP axes anti-parallel, Thumbs aligned)
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
from PIL import Image, ImageDraw, ImageFont

# Build temporary XML with TCP Frame Geoms (RGB axes: Red X, Green Y, Blue Z)
xml_content = """
<mujoco model="amazinghand_tcp_comparison">
  <compiler angle="radian" />
  <option gravity="0 0 -9.81" timestep="0.002" />
  <visual>
    <global offwidth="1280" offheight="800" />
  </visual>

  <default>
    <geom density="600" friction="1.0 0.02 0.001" solref="0.01 1" solimp="0.9 0.95 0.001" />
    <joint damping="0.15" frictionloss="0.01" />
  </default>

  <worldbody>
    <light name="light_top" pos="0 0 1.2" dir="0 0 -1" diffuse="0.9 0.9 0.9" directional="true" />
    <light name="light_side" pos="0.8 -0.6 0.6" dir="-0.8 0.6 -0.4" diffuse="0.6 0.6 0.6" directional="true" />

    <!-- WORLD A: BEFORE (Parallel Orientation) -->
    <body name="handA_before_wrist" pos="-0.12 -0.05 0.05">
      <geom name="A_b_palm" type="box" size="0.024 0.017 0.008" rgba="0.22 0.74 0.97 1" />
      <!-- TCP RGB Axes -->
      <geom name="A_b_tcp_x" type="cylinder" fromto="0 0 0 0.04 0 0" size="0.002" rgba="1 0 0 1" contype="0" conaffinity="0" />
      <geom name="A_b_tcp_y" type="cylinder" fromto="0 0 0 0 0.04 0" size="0.002" rgba="0 1 0 1" contype="0" conaffinity="0" />
      <geom name="A_b_tcp_z" type="cylinder" fromto="0 0 0 0 0 0.04" size="0.002" rgba="0 0 1 1" contype="0" conaffinity="0" />

      <body name="A_b_thumb" pos="-0.026 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.038 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
      <body name="A_b_index" pos="-0.013 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.045 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
      <body name="A_b_middle" pos="0 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.048 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
    </body>

    <body name="handB_before_wrist" pos="-0.12 0.08 0.05">
      <geom name="B_b_palm" type="box" size="0.024 0.017 0.008" rgba="0.98 0.57 0.23 1" />
      <!-- TCP RGB Axes -->
      <geom name="B_b_tcp_x" type="cylinder" fromto="0 0 0 0.04 0 0" size="0.002" rgba="1 0 0 1" contype="0" conaffinity="0" />
      <geom name="B_b_tcp_y" type="cylinder" fromto="0 0 0 0 0.04 0" size="0.002" rgba="0 1 0 1" contype="0" conaffinity="0" />
      <geom name="B_b_tcp_z" type="cylinder" fromto="0 0 0 0 0 0.04" size="0.002" rgba="0 0 1 1" contype="0" conaffinity="0" />

      <body name="B_b_thumb" pos="-0.026 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.038 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
      <body name="B_b_index" pos="-0.013 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.045 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
      <body name="B_b_middle" pos="0 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.048 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
    </body>

    <!-- WORLD B: AFTER (180° Symmetric Facing Right-Hand Orientation - Physical Finger Touch) -->
    <body name="handA_after_wrist" pos="0.12 -0.025 0.05">
      <geom name="A_a_palm" type="box" size="0.024 0.017 0.008" rgba="0.22 0.74 0.97 1" />
      <!-- TCP RGB Axes -->
      <geom name="A_a_tcp_x" type="cylinder" fromto="0 0 0 0.04 0 0" size="0.002" rgba="1 0 0 1" contype="0" conaffinity="0" />
      <geom name="A_a_tcp_y" type="cylinder" fromto="0 0 0 0 0.04 0" size="0.002" rgba="0 1 0 1" contype="0" conaffinity="0" />
      <geom name="A_a_tcp_z" type="cylinder" fromto="0 0 0 0 0 0.04" size="0.002" rgba="0 0 1 1" contype="0" conaffinity="0" />

      <body name="A_a_thumb" pos="-0.026 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.038 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
      <body name="A_a_index" pos="-0.013 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.045 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
      <body name="A_a_middle" pos="0 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.048 0" size="0.006" rgba="0.22 0.74 0.97 1" />
      </body>
    </body>

    <body name="handB_after_wrist" pos="0.12 0.025 0.05" euler="3.14159 0 3.14159">
      <geom name="B_a_palm" type="box" size="0.024 0.017 0.008" rgba="0.98 0.57 0.23 1" />
      <!-- TCP RGB Axes -->
      <geom name="B_a_tcp_x" type="cylinder" fromto="0 0 0 0.04 0 0" size="0.002" rgba="1 0 0 1" contype="0" conaffinity="0" />
      <geom name="B_a_tcp_y" type="cylinder" fromto="0 0 0 0 0.04 0" size="0.002" rgba="0 1 0 1" contype="0" conaffinity="0" />
      <geom name="B_a_tcp_z" type="cylinder" fromto="0 0 0 0 0 0.04" size="0.002" rgba="0 0 1 1" contype="0" conaffinity="0" />

      <body name="B_a_thumb" pos="-0.026 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.038 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
      <body name="B_a_index" pos="-0.013 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.045 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
      <body name="B_a_middle" pos="0 0.017 0">
        <geom type="capsule" fromto="0 0 0 0 0.048 0" size="0.006" rgba="0.98 0.57 0.23 1" />
      </body>
    </body>
  </worldbody>
</mujoco>
"""

model = mujoco.MjModel.from_xml_string(xml_content)
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

renderer = mujoco.Renderer(model, height=800, width=1280)
cam = mujoco.MjvCamera()
mujoco.mjv_defaultFreeCamera(model, cam)
cam.azimuth, cam.elevation, cam.distance = -60, -22, 0.45
cam.lookat[:] = [0.0, 0.0, 0.05]

font_path = "/home/moos/dev_ws/aegis/fonts/NanumGothic-Bold.ttf"
try:
    font_title = ImageFont.truetype(font_path, 22)
    font_sub = ImageFont.truetype(font_path, 18)
except:
    font_title = ImageFont.load_default()
    font_sub = font_title

frames = []
for i in range(40):
    cam.azimuth = -60 + i * 0.5
    renderer.update_scene(data, camera=cam)
    img = Image.fromarray(renderer.render()).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Top Header
    draw.rectangle([0, 0, 1280, 65], fill=(12, 16, 28))
    draw.text((20, 10), "오른손-오른손 악수 키네마틱스 툴좌표계(TCP Axes: Red=X, Green=Y, Blue=Z) 수정 전후 비교", fill=(56, 189, 248), font=font_title)
    draw.text((20, 38), "🔴 수정 전: 동일 방향 배치 (손바닥 미대면)   |   🟢 수정 후: 180° 대칭 마주보기 (손바닥 정면 대치)", fill=(244, 114, 182), font=font_sub)

    # Center Vertical Divider Line
    draw.line([(640, 65), (640, 800)], fill=(56, 189, 248), width=3)

    # Left Panel Badge: BEFORE (수정 전)
    draw.rectangle([40, 715, 590, 775], fill=(185, 28, 28))
    draw.text((55, 730), "🔴 수정 전 (BEFORE: 단순 평행 이격)", fill=(255, 255, 255), font=font_title)

    # Right Panel Badge: AFTER (수정 후)
    draw.rectangle([690, 715, 1240, 775], fill=(21, 128, 61))
    draw.text((705, 730), "🟢 수정 후 (AFTER: 180° 대칭 마주보기)", fill=(255, 255, 255), font=font_title)

    frames.append(img)

out_gif = "/home/moos/dev_ws/images/handshake_tcp_kinematic_before_after.gif"
frames[0].save(out_gif, save_all=True, append_images=frames[1:], duration=100, loop=0)
print("SUCCESSFULLY GENERATED BEFORE/AFTER TCP GIF:", out_gif, "Frames:", len(frames))
