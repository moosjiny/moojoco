/**
 * Minimal procedural mesh generator: tapered cylinders (phalanx bones) and
 * UV spheres (joint knuckles) as interleaved position+normal float buffers.
 */
#pragma once
#include <vector>
#include <cmath>

struct MeshData {
    std::vector<float> vertices;        // px,py,pz, nx,ny,nz interleaved
    std::vector<unsigned int> indices;
};

inline MeshData buildTaperedCylinder(double length, double baseRadius, double tipRadius, int segments = 16) {
    MeshData mesh;
    double slope = (baseRadius - tipRadius) / (length > 1e-9 ? length : 1.0);
    for (int i = 0; i <= segments; ++i) {
        double theta = 2.0 * M_PI * i / segments;
        double cx = std::cos(theta), cy = std::sin(theta);
        double nl = std::sqrt(cx*cx + cy*cy + slope*slope);
        float nx = float(cx / nl), ny = float(cy / nl), nz = float(slope / nl);

        mesh.vertices.insert(mesh.vertices.end(), {
            float(cx * baseRadius), float(cy * baseRadius), 0.0f, nx, ny, nz
        });
        mesh.vertices.insert(mesh.vertices.end(), {
            float(cx * tipRadius), float(cy * tipRadius), float(length), nx, ny, nz
        });
    }
    for (int i = 0; i < segments; ++i) {
        unsigned int base0 = i * 2, tip0 = i * 2 + 1, base1 = (i + 1) * 2, tip1 = (i + 1) * 2 + 1;
        mesh.indices.insert(mesh.indices.end(), {base0, tip0, base1, base1, tip0, tip1});
    }
    return mesh;
}

inline MeshData buildSphere(double radius, int rings = 8, int segments = 12) {
    MeshData mesh;
    for (int r = 0; r <= rings; ++r) {
        double phi = M_PI * r / rings;               // 0..pi
        double y = std::cos(phi), ringR = std::sin(phi);
        for (int s = 0; s <= segments; ++s) {
            double theta = 2.0 * M_PI * s / segments;
            double x = ringR * std::cos(theta), z = ringR * std::sin(theta);
            mesh.vertices.insert(mesh.vertices.end(), {
                float(x * radius), float(y * radius), float(z * radius),
                float(x), float(y), float(z)
            });
        }
    }
    int stride = segments + 1;
    for (int r = 0; r < rings; ++r) {
        for (int s = 0; s < segments; ++s) {
            unsigned int a = r * stride + s, b = a + stride;
            mesh.indices.insert(mesh.indices.end(), {a, b, a + 1, a + 1, b, b + 1});
        }
    }
    return mesh;
}

inline MeshData buildBox(double w, double h, double d) {
    float x = float(w / 2.0), y = float(h / 2.0), z = float(d / 2.0);
    MeshData mesh;
    struct Face { float nx, ny, nz; float verts[4][3]; };
    Face faces[6] = {
        {0,0,1,  {{-x,-y,z},{x,-y,z},{x,y,z},{-x,y,z}}},
        {0,0,-1, {{x,-y,-z},{-x,-y,-z},{-x,y,-z},{x,y,-z}}},
        {0,1,0,  {{-x,y,z},{x,y,z},{x,y,-z},{-x,y,-z}}},
        {0,-1,0, {{-x,-y,-z},{x,-y,-z},{x,-y,z},{-x,-y,z}}},
        {1,0,0,  {{x,-y,z},{x,-y,-z},{x,y,-z},{x,y,z}}},
        {-1,0,0, {{-x,-y,-z},{-x,-y,z},{-x,y,z},{-x,y,-z}}},
    };
    for (const auto& f : faces) {
        unsigned int start = mesh.vertices.size() / 6;
        for (auto& v : f.verts)
            mesh.vertices.insert(mesh.vertices.end(), {v[0], v[1], v[2], f.nx, f.ny, f.nz});
        mesh.indices.insert(mesh.indices.end(), {start, start+1, start+2, start, start+2, start+3});
    }
    return mesh;
}
