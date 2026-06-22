import trimesh
import os

MESH_DIR = "/home/moos/dev_ws/dual_arms/meshes/"
meshes = ["base_link.stl", "link1.stl", "link2.stl", "link3.stl", "link4.stl", "link5.stl", "link6.stl", "link7.stl"]

print(f"{'Mesh Name':<15} | {'Min Z':<10} | {'Max Z':<10} | {'Center Z':<10} | {'Size Z':<10}")
print("-" * 65)

for m_name in meshes:
    path = os.path.join(MESH_DIR, m_name)
    if os.path.exists(path):
        mesh = trimesh.load(path)
        z_min = mesh.bounds[0][2]
        z_max = mesh.bounds[1][2]
        z_center = (z_min + z_max) / 2.0
        z_size = z_max - z_min
        print(f"{m_name:<15} | {z_min:<10.2f} | {z_max:<10.2f} | {z_center:<10.2f} | {z_size:<10.2f}")
    else:
        print(f"{m_name:<15} | Not Found")
