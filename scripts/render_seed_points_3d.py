"""
dual_openarm 양팔 로봇을 MuJoCo EGL 오프스크린으로 렌더링하고,
Vorno POC의 15개 씨앗점을 같은 색상 팔레트로 3D 장면에 오버레이한다.
mujoco_sim.service(라이브 스트림)는 건드리지 않는 별도 프로세스.
씨앗 ID↔색상은 visualize_voronoi_poc.py 팔레트와 동일 — 두 시각화 교차 대조용.
"""
import os
os.environ["MUJOCO_GL"] = "egl"

import numpy as np
import mujoco
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "Noto Sans CJK KR"
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
OUT_PATH = "/home/moos/dev_ws/images/moojoco-seed-points-3d-studio-2026-08-03.png"

SEED_BODIES = (
    [f"left_link{i}" for i in range(1, 8)]
    + [f"right_link{i}" for i in range(1, 8)]
    + ["shoulder_block"]
)

# visualize_voronoi_poc.py와 동일 팔레트 (id 14 shoulder_block = 금색)
_HEX = [
    "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c", "#98df8a",
    "#d62728", "#ff9896", "#9467bd", "#c5b0d5", "#8c564b", "#c49c94",
    "#e377c2", "#f7b6d2", "#ffd700",
]
PALETTE = [to_rgb(h) for h in _HEX]

VIEWS = [
    ("정면 (양팔 전개)", dict(azimuth=0, elevation=-12, distance=2.1, lookat=[0.0, 0.0, 0.45])),
    ("측면 (x축 얇음)", dict(azimuth=90, elevation=-12, distance=2.1, lookat=[0.0, 0.0, 0.45])),
    ("등각 (스튜디오 뷰)", dict(azimuth=135, elevation=-25, distance=2.4, lookat=[0.0, 0.0, 0.45])),
]


def ghost_robot(scene, model, hide_bids):
    """로봇 지오메트리를 반투명 처리(씨앗점이 링크 내부에 있어 불투명이면 안 보임).
    IK 타겟 마커(target_left/right)는 씨앗점과 혼동되므로 완전히 숨긴다."""
    for i in range(scene.ngeom):
        g = scene.geoms[i]
        if g.objtype == mujoco.mjtObj.mjOBJ_GEOM and model.geom_bodyid[g.objid] in hide_bids:
            g.rgba[3] = 0.0
        else:
            g.rgba[3] = 0.3


def add_seed_spheres(scene, seed_pos):
    for sid, pos in enumerate(seed_pos):
        if scene.ngeom >= scene.maxgeom:
            break
        g = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(
            g, mujoco.mjtGeom.mjGEOM_SPHERE,
            size=np.array([0.03, 0, 0]),
            pos=np.asarray(pos, dtype=np.float64),
            mat=np.eye(3).flatten(),
            rgba=np.array([*PALETTE[sid], 1.0], dtype=np.float32),
        )
        scene.ngeom += 1


def main():
    model = mujoco.MjModel.from_xml_path(URDF_PATH)
    # 공유 XML은 건드리지 않고 런타임에만 오프스크린 버퍼 확장
    model.vis.global_.offwidth = 1280
    model.vis.global_.offheight = 1280
    data = mujoco.MjData(model)
    data.qpos[:] = 0.0  # rest pose — 씨앗점 추출 당시와 동일 상태
    mujoco.mj_forward(model, data)

    seed_pos = []
    for name in SEED_BODIES:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        seed_pos.append(data.xpos[bid].copy())

    hide_bids = set()
    for name in ("target_left", "target_right"):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid != -1:
            hide_bids.add(bid)

    renderer = mujoco.Renderer(model, height=880, width=880)
    frames = []
    for title, camcfg in VIEWS:
        cam = mujoco.MjvCamera()
        mujoco.mjv_defaultFreeCamera(model, cam)
        cam.azimuth = camcfg["azimuth"]
        cam.elevation = camcfg["elevation"]
        cam.distance = camcfg["distance"]
        cam.lookat[:] = camcfg["lookat"]
        renderer.update_scene(data, camera=cam)
        ghost_robot(renderer.scene, model, hide_bids)
        add_seed_spheres(renderer.scene, seed_pos)
        frames.append((title, renderer.render().copy()))
    renderer.close()

    fig, axes = plt.subplots(1, 3, figsize=(18, 7.2), facecolor="#0a0c14")
    for ax, (title, img) in zip(axes, frames):
        ax.imshow(img)
        ax.set_title(title, color="#a0c4ff", fontsize=12)
        ax.axis("off")

    legend_elems = [
        plt.Line2D([0], [0], marker="o", color="w", label=name,
                   markerfacecolor=PALETTE[sid], markersize=8, linewidth=0)
        for sid, name in enumerate(SEED_BODIES)
    ]
    fig.legend(handles=legend_elems, loc="lower center", ncol=8, fontsize=8,
               facecolor="#12152a", edgecolor="#2a3050", labelcolor="#ccc",
               bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(
        "dual_openarm 3D 스튜디오 렌더 + 보로노이 씨앗점 15개 오버레이 "
        "(rest pose, MuJoCo EGL — 색상은 파티셔닝 시각화와 동일 팔레트)",
        color="#e0e0e0", fontsize=13, y=0.99,
    )
    fig.savefig(OUT_PATH, dpi=120, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"저장 완료: {OUT_PATH}")
    for sid, (name, pos) in enumerate(zip(SEED_BODIES, seed_pos)):
        print(f"  id={sid:2d} {name:14s} {np.round(pos, 4).tolist()}")


if __name__ == "__main__":
    main()
