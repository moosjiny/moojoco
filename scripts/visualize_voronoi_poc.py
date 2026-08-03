"""
Vorno의 3D 보로노이 파티셔닝 결과(dual_openarm_voronoi_result.json)를 정적 이미지로 시각화.
mujoco_sim.service(라이브 Rerun 스트림)는 건드리지 않는 별도 스크립트.
"""
import json
import zlib
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "Noto Sans CJK KR"
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

RESULT_PATH = "/home/moos/dev_ws/aistudio/scratch/dual_openarm_voronoi_result.json"
OUT_PATH = "/home/moos/dev_ws/images/vorno-moojoco-voronoi-poc-2026-08-03.png"

BBOX_MIN = np.array([-0.0369, -0.6492, -0.0585])
BBOX_MAX = np.array([0.0443, 0.6492, 0.883])

# 15개 씨앗 ID용 구분 색상. tab20의 회색이 마지막(shoulder_block, 최대 영역)에
# 걸려 '빈 공간'처럼 오해될 수 있어 마지막만 금색으로 교체.
from matplotlib.colors import to_rgb
_HEX = [
    "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c", "#98df8a",
    "#d62728", "#ff9896", "#9467bd", "#c5b0d5", "#8c564b", "#c49c94",
    "#e377c2", "#f7b6d2", "#ffd700",
]
PALETTE = [to_rgb(h) for h in _HEX]


def voxel_center(ix, iy, iz, res=64):
    frac = (np.array([ix, iy, iz]) + 0.5) / res
    return BBOX_MIN + frac * (BBOX_MAX - BBOX_MIN)


def main():
    with open(RESULT_PATH) as f:
        d = json.load(f)
    arr = np.frombuffer(
        zlib.decompress(base64.b64decode(d["voxel_data"])), dtype=np.uint8
    ).reshape(64, 64, 64)  # [z, y, x] 순서 (검증 완료됨)
    mapping = d["seeds_mapping"]
    res = 64

    fig = plt.figure(figsize=(16, 9), facecolor="#0a0c14")

    # ── 좌: 3D 복셀 블록 렌더링 (산점도 대신 — 로봇이 x축으로 매우 얇아서
    #    산점도로는 점들이 뭉개져 잘 안 보임. ax.voxels로 실제 블록 표시) ──
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    ax3d.set_facecolor("#0a0c14")
    step = 4  # 64^3 -> 16^3 서브샘플링(렌더링 부하·가독성)
    ids_sub = arr[::step, ::step, ::step]  # [z,y,x] 순서 유지
    filled = np.ones_like(ids_sub, dtype=bool)
    facecolors = np.empty(ids_sub.shape + (4,))
    for sid in range(15):
        facecolors[ids_sub == sid] = (*PALETTE[sid], 0.9)
    # voxels()는 (x,y,z) 순서를 기대하므로 축 전치
    ax3d.voxels(filled.transpose(2, 1, 0), facecolors=facecolors.transpose(2, 1, 0, 3),
                edgecolor="#0a0c14", linewidth=0.15)

    # 실제 물리 치수 비율 반영 (로봇이 x축으로 얇음을 그대로 드러냄)
    extent = BBOX_MAX - BBOX_MIN
    ax3d.set_box_aspect(extent)
    ax3d.set_title("3D 보로노이 복셀 블록 (서브샘플, 16³)", color="#a0c4ff", fontsize=11)
    ax3d.set_xlabel("x", color="#888"); ax3d.set_ylabel("y", color="#888")
    ax3d.set_zlabel("z", color="#888")
    ax3d.set_xticks([]); ax3d.tick_params(colors="#666")
    ax3d.view_init(elev=16, azim=-70)

    # ── 우: 세 단면(슬라이스) ────────────────────────────────
    mid = res // 2
    slices = [
        ("XY 단면 (z=중앙)", arr[mid, :, :], "x", "y"),
        ("XZ 단면 (y=중앙)", arr[:, mid, :], "x", "z"),
        ("YZ 단면 (x=중앙)", arr[:, :, mid], "y", "z"),
    ]
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(PALETTE)

    gs = fig.add_gridspec(3, 4, left=0.55, right=0.98, top=0.92, bottom=0.08, hspace=0.5)
    for i, (title, sl, xl, yl) in enumerate(slices):
        ax = fig.add_subplot(gs[i, :])
        ax.imshow(sl, cmap=cmap, vmin=0, vmax=14, origin="lower")
        ax.set_title(title, color="#a0c4ff", fontsize=10)
        ax.set_xlabel(xl, color="#888"); ax.set_ylabel(yl, color="#888")
        ax.tick_params(colors="#666")
        ax.set_facecolor("#0a0c14")

    # 범례
    legend_elems = [
        plt.Line2D([0], [0], marker="o", color="w", label=name,
                    markerfacecolor=PALETTE[int(sid)], markersize=7, linewidth=0)
        for sid, name in mapping.items()
    ]
    fig.legend(handles=legend_elems, loc="lower center", ncol=8, fontsize=7,
               facecolor="#12152a", edgecolor="#2a3050", labelcolor="#ccc",
               bbox_to_anchor=(0.5, -0.02))

    fig.suptitle("dual_openarm × Vorno 3D 보로노이 파티셔닝 POC (rest pose, 15 seeds, 64³ voxels)",
                 color="#e0e0e0", fontsize=13, y=0.98)

    fig.savefig(OUT_PATH, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
