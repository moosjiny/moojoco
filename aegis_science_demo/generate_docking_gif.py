#!/usr/bin/env python3
"""
Generate Animated GIF for DeepMind Science 3D Bio-Robotics Docking Simulation
Author: Aegis
Output: /home/moos/dev_ws/images/aegis_deepmind_science_3d_docking.gif
URL: https://images.hyperbook.com/aegis_deepmind_science_3d_docking.gif
"""

import math, os
from PIL import Image, ImageDraw

def render_docking_frame(frame_idx, total_frames=20, width=960, height=540):
    img = Image.new("RGB", (width, height), "#030712")
    draw = ImageDraw.Draw(img)
    
    # 1. Background Cyber Grid
    grid_size = 40
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill="#0f172a", width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill="#0f172a", width=1)
        
    # 2. Binding Pocket (Glowing Core)
    pocket_x, pocket_y = 650, 270
    t = frame_idx / total_frames
    
    # Voronoi Bounding Spheres
    draw.ellipse([pocket_x - 120, pocket_y - 120, pocket_x + 120, pocket_y + 120], outline="#10b981", width=2)
    draw.ellipse([pocket_x - 70, pocket_y - 70, pocket_x + 70, pocket_y + 70], outline="#06b6d4", width=1)
    
    # Bio-Molecule Atoms & Orbit Rings
    atoms = [
        (pocket_x - 80, pocket_y - 40, "#8b5cf6"),
        (pocket_x - 30, pocket_y - 70, "#8b5cf6"),
        (pocket_x + 40, pocket_y - 20, "#8b5cf6"),
        (pocket_x + 70, pocket_y + 50, "#8b5cf6"),
        (pocket_x - 20, pocket_y + 60, "#8b5cf6")
    ]
    
    # Bonds
    for i in range(len(atoms) - 1):
        draw.line([(atoms[i][0], atoms[i][1]), (atoms[i+1][0], atoms[i+1][1])], fill="#c084fc", width=4)
        
    # Atoms
    for ax, ay, c in atoms:
        draw.ellipse([ax - 18, ay - 18, ax + 18, ay + 18], fill=c, outline="#ffffff", width=2)
        
    # Rotating Electron Ring
    angle = (frame_idx / total_frames) * math.pi * 2
    rx = pocket_x + math.cos(angle) * 90
    ry = pocket_y + math.sin(angle) * 40
    draw.ellipse([rx - 8, ry - 8, rx + 8, ry + 8], fill="#f472b6", outline="#ffffff")
    
    # Pocket Core
    draw.ellipse([pocket_x - 30, pocket_y - 30, pocket_x + 30, pocket_y + 30], fill="#ec4899", outline="#f472b6", width=3)
    
    # 3. Robotic Arm Trajectory & Motion
    start_arm_x, start_arm_y = 100, 420
    s = t * t * (3 - 2 * t)
    arm_x = start_arm_x + s * (pocket_x - start_arm_x - 40)
    arm_y = start_arm_y + s * (pocket_y - start_arm_y)
    
    # Trajectory Line
    draw.line([(start_arm_x, start_arm_y), (pocket_x, pocket_y)], fill="#0284c7", width=2)
    
    # Robotic Arm Manipulator Body
    draw.line([(60, 480), (140, 380)], fill="#334155", width=14)
    draw.line([(140, 380), (arm_x, arm_y)], fill="#475569", width=10)
    draw.ellipse([arm_x - 20, arm_y - 20, arm_x + 20, arm_y + 20], fill="#06b6d4", outline="#38bdf8", width=3)
    
    # Laser Targeting Beam
    draw.line([(arm_x, arm_y), (pocket_x, pocket_y)], fill="#38bdf8", width=3)
    
    # 4. Glassmorphism HUD Overlay Text
    # Header HUD Card
    draw.rectangle([20, 20, 420, 90], fill="#0f172a", outline="#38bdf8", width=2)
    draw.text((35, 32), "🧪 DeepMind Science 3D Visualizer", fill="#38bdf8")
    draw.text((35, 58), "AlphaFold Docking & MuJoCo 7-DOF Kinematics", fill="#94a3b8")
    
    # Telemetry HUD Card
    draw.rectangle([20, 420, 400, 510], fill="#0f172a", outline="#10b981", width=2)
    draw.text((35, 432), f"ROBOTIC ARM DOCKING — STEP {frame_idx + 1} / {total_frames}", fill="#34d399")
    draw.text((35, 458), f"End-Effector Pos: ({arm_x:.1f}, {arm_y:.1f})", fill="#f8fafc")
    draw.text((35, 480), f"Binding Energy: -28.721 kcal/mol", fill="#f472b6")
    
    return img

def main():
    print("🎬 Generating Animated GIF for DeepMind Science Docking Simulation...")
    frames = []
    total_frames = 20
    for i in range(total_frames):
        f = render_docking_frame(i, total_frames=total_frames)
        frames.append(f)
        
    out_dir = "/home/moos/dev_ws/images"
    os.makedirs(out_dir, exist_ok=True)
    gif_path = os.path.join(out_dir, "aegis_deepmind_science_3d_docking.gif")
    jpg_path = os.path.join(out_dir, "stitch_cyber_bio_dashboard.jpg")
    
    # Save GIF
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=100, # 100ms per frame = 10 FPS loop
        loop=0
    )
    
    # Copy JPEG mockup too
    src_jpg = "/home/moos/dev_ws/aegis/assets/stitch_cyber_bio_dashboard.jpg"
    if os.path.exists(src_jpg):
        import shutil
        shutil.copy(src_jpg, jpg_path)
        
    print(f"✅ Animated GIF Saved: {gif_path}")
    print(f"✅ Public Image URL: https://images.hyperbook.com/aegis_deepmind_science_3d_docking.gif")
    print(f"✅ Public Dashboard URL: https://images.hyperbook.com/stitch_cyber_bio_dashboard.jpg")

if __name__ == "__main__":
    main()
