# Graph Report - /home/moos/dev_ws/dual_arms  (2026-07-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 195 nodes · 176 edges · 64 communities (36 shown, 28 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3307a8cc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- viz_server.py
- backup/dashboard/main.py
- DualArmIKNode
- dashboard/main.py
- DualArmInteractiveMarker
- DualArmIKNode
- DualArmInteractiveMarker
- compute_4d
- backup/scripts/setup_can.sh
- 2026-04-27_final_ik_rviz/scripts/setup_can.sh
- 2026-04-27_ik_backup/scripts/setup_can.sh
- scripts/setup_can.sh
- backup/scripts/run_dashboard.sh
- backup/scripts/setup_ports.sh
- backup/scripts/start_all.sh
- 2026-04-27_alignment_fixed/setup_venv.sh
- 2026-04-27_final_ik_rviz/scratch/build_mjcf.py
- 2026-04-27_final_ik_rviz/scripts/launch_rviz_robot.sh
- 2026-04-27_final_ik_rviz/scripts/run_dashboard.sh
- 2026-04-27_final_ik_rviz/scripts/setup_ports.sh
- 2026-04-27_final_ik_rviz/scripts/setup_venv.sh
- 2026-04-27_final_ik_rviz/scripts/start_all.sh
- 2026-04-27_final_ik_rviz/scripts/teleop_left.sh
- 2026-04-27_ik_backup/scratch/build_mjcf.py
- 2026-04-27_ik_backup/scripts/run_dashboard.sh
- 2026-04-27_ik_backup/scripts/setup_ports.sh
- 2026-04-27_ik_backup/scripts/setup_venv.sh
- 2026-04-27_ik_backup/scripts/start_all.sh
- scratch/build_mjcf.py
- scripts/launch_rviz_robot.sh
- scripts/run_dashboard.sh
- scripts/setup_ports.sh
- scripts/setup_venv.sh
- scripts/start_all.sh
- start_full_sim.sh
- scripts/teleop_left.sh

## God Nodes (most connected - your core abstractions)
1. `layout()` - 11 edges
2. `DualArmIKNode` - 8 edges
3. `DualArmInteractiveMarker` - 8 edges
4. `DualArmIKNode` - 8 edges
5. `force_layout_3d()` - 7 edges
6. `DualArmInteractiveMarker` - 6 edges
7. `compute_4d()` - 4 edges
8. `get_resource()` - 4 edges
9. `resource_status()` - 4 edges
10. `_heartbeat_loop()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `layout()` --calls--> `compute_4d()`  [EXTRACTED]
  scripts/viz_server.py → scripts/viz4d/layout.py

## Import Cycles
- None detected.

## Communities (64 total, 28 thin omitted)

### Community 0 - "viz_server.py"
Cohesion: 0.13
Nodes (26): _corr_conn(), fetch_papers(), force_layout_3d(), _force_layout_binary(), _force_layout_cpu(), _force_layout_gpu(), _get_redis(), get_resource() (+18 more)

### Community 1 - "backup/dashboard/main.py"
Cohesion: 0.28
Nodes (8): get_dashboard(), lifespan(), FastAPI, Request, WebSocket, Background task to update robot state.     In the future, this will interface wi, update_robot_data(), websocket_endpoint()

### Community 2 - "DualArmIKNode"
Cohesion: 0.25
Nodes (3): DualArmIKNode, Node, run_ros2_ik()

### Community 3 - "dashboard/main.py"
Cohesion: 0.28
Nodes (8): get_dashboard(), lifespan(), FastAPI, Request, WebSocket, Background task to update robot state.     In the future, this will interface wi, update_robot_data(), websocket_endpoint()

### Community 4 - "DualArmInteractiveMarker"
Cohesion: 0.28
Nodes (3): DualArmInteractiveMarker, main(), Node

### Community 5 - "DualArmIKNode"
Cohesion: 0.25
Nodes (3): DualArmIKNode, Node, run_ros2_ik()

### Community 6 - "DualArmInteractiveMarker"
Cohesion: 0.38
Nodes (3): DualArmInteractiveMarker, main(), Node

### Community 7 - "compute_4d"
Cohesion: 0.50
Nodes (3): compute_4d(), viz4d/layout.py — 4차원 매핑 계산  두 3D 그래프의 1:1 매핑으로 4차원 구조를 도출한다.   - papers: 각 논문의, Args:         papers: thesis API papers list         force_layout_fn: force_layo

## Knowledge Gaps
- **21 isolated node(s):** `run_dashboard.sh script`, `setup_ports.sh script`, `start_all.sh script`, `setup_venv.sh script`, `launch_rviz_robot.sh script` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compute_4d()` connect `compute_4d` to `viz_server.py`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Why does `layout()` connect `viz_server.py` to `compute_4d`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `layout()` (e.g. with `force_layout_3d()` and `_layout_keywords()`) actually correct?**
  _`layout()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `run_dashboard.sh script`, `setup_ports.sh script`, `start_all.sh script` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `viz_server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12688172043010754 - nodes in this community are weakly interconnected._