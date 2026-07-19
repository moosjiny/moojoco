"""
viz4d/layout.py — 4차원 매핑 계산

두 3D 그래프의 1:1 매핑으로 4차원 구조를 도출한다.
  - papers: 각 논문의 논문공간 좌표 (px,py,pz) + 개념공간 중심 (kx,ky,kz) + 4th dim w
  - keywords: 각 개념의 개념공간 좌표 (kx,ky,kz) + 논문공간 중심 (px,py,pz)
  - w = ||paper_pos - keyword_centroid|| → 두 공간 사이의 '거리'
"""
import math


def compute_4d(papers, force_layout_fn, parse_tag_fn, layout_network_fn, layout_keywords_fn):
    """
    Args:
        papers: thesis API papers list
        force_layout_fn: force_layout_3d function reference
        parse_tag_fn: parse_tag function reference
        layout_network_fn: _layout_network function reference
        layout_keywords_fn: _layout_keywords function reference

    Returns dict with 4D mapping.
    """
    # Step 1: 두 독립적인 3D 레이아웃 계산
    net = layout_network_fn(papers)
    kw  = layout_keywords_fn(papers)

    paper_pos = {n["id"]: (n["x"], n["y"], n["z"]) for n in net["nodes"]}
    paper_meta = {n["id"]: n for n in net["nodes"]}
    kw_pos    = {n["id"]: (n["x"], n["y"], n["z"]) for n in kw["nodes"]}
    kw_meta   = {n["id"]: n for n in kw["nodes"]}

    # Step 2: 각 논문의 개념공간 중심 + w 계산
    paper_4d = []
    for p in papers:
        slug = p.get("slug", "")
        if slug not in paper_pos:
            continue
        px, py, pz = paper_pos[slug]
        tags = [parse_tag_fn(t)["en"] for t in p.get("tags", [])]
        valid = [t for t in tags if t in kw_pos]

        if valid:
            kx = sum(kw_pos[t][0] for t in valid) / len(valid)
            ky = sum(kw_pos[t][1] for t in valid) / len(valid)
            kz = sum(kw_pos[t][2] for t in valid) / len(valid)
        else:
            kx, ky, kz = 0.0, 0.0, 0.0

        w = math.sqrt((px-kx)**2 + (py-ky)**2 + (pz-kz)**2)

        paper_4d.append({
            "id":     slug,
            "title":  p.get("title", slug),
            "author": p.get("author", ""),
            "tags":   tags,
            # 논문공간 좌표
            "px": round(px, 4), "py": round(py, 4), "pz": round(pz, 4),
            # 개념공간 중심 (이 논문의 태그들의 무게중심)
            "kx": round(kx, 4), "ky": round(ky, 4), "kz": round(kz, 4),
            # 4차원 — 두 공간에서의 위치 차이
            "w":  round(w, 4),
        })

    # Step 3: 각 키워드의 논문공간 중심 계산
    kw_4d = []
    for kn in kw["nodes"]:
        kid = kn["id"]
        kx2, ky2, kz2 = kw_pos[kid]

        # 이 키워드를 사용하는 논문들
        using = [p["slug"] for p in papers
                 if kid in [parse_tag_fn(t)["en"] for t in p.get("tags", [])]]
        valid_p = [s for s in using if s in paper_pos]

        if valid_p:
            cx = sum(paper_pos[s][0] for s in valid_p) / len(valid_p)
            cy = sum(paper_pos[s][1] for s in valid_p) / len(valid_p)
            cz = sum(paper_pos[s][2] for s in valid_p) / len(valid_p)
        else:
            cx, cy, cz = 0.0, 0.0, 0.0

        kw_4d.append({
            "id":    kid,
            "label": kn.get("label", kid),
            "freq":  kn.get("freq", 0),
            # 개념공간 좌표
            "kx": round(kx2, 4), "ky": round(ky2, 4), "kz": round(kz2, 4),
            # 논문공간 중심 (이 키워드를 쓰는 논문들의 무게중심)
            "px": round(cx, 4),  "py": round(cy, 4),  "pz": round(cz, 4),
        })

    # w 정규화 (0~1, 색상 매핑용)
    max_w = max((p["w"] for p in paper_4d), default=1.0) or 1.0
    for p in paper_4d:
        p["wn"] = round(p["w"] / max_w, 4)  # normalized w

    return {
        "papers":        paper_4d,
        "keywords":      kw_4d,
        "paper_edges":   net["edges"],
        "keyword_edges": kw["edges"],
        "max_w":         round(max_w, 4),
        "type":          "4d",
        "source":        "hb5u",
    }
