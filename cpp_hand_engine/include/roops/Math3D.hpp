/**
 * ROOPS Humanoid Hand Engine - minimal 3D math (column-major, OpenGL-compatible)
 */
#pragma once
#include <cmath>
#include <array>

namespace roops {

struct Vec3 {
    double x = 0.0, y = 0.0, z = 0.0;
    Vec3() = default;
    Vec3(double _x, double _y, double _z) : x(_x), y(_y), z(_z) {}

    Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    Vec3 operator*(double s) const { return {x * s, y * s, z * s}; }
};

// 4x4 matrix, column-major storage: m[col*4 + row]
struct Mat4 {
    std::array<double, 16> m{};

    static Mat4 identity() {
        Mat4 r;
        r.m = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
        return r;
    }

    static Mat4 translation(const Vec3& t) {
        Mat4 r = identity();
        r.m[12] = t.x; r.m[13] = t.y; r.m[14] = t.z;
        return r;
    }

    // Right-handed rotation about the X axis, angle in radians
    static Mat4 rotationX(double a) {
        Mat4 r = identity();
        double c = std::cos(a), s = std::sin(a);
        r.m[5] = c;  r.m[6] = s;
        r.m[9] = -s; r.m[10] = c;
        return r;
    }

    static Mat4 rotationY(double a) {
        Mat4 r = identity();
        double c = std::cos(a), s = std::sin(a);
        r.m[0] = c;  r.m[2] = -s;
        r.m[8] = s;  r.m[10] = c;
        return r;
    }

    static Mat4 rotationZ(double a) {
        Mat4 r = identity();
        double c = std::cos(a), s = std::sin(a);
        r.m[0] = c;  r.m[1] = s;
        r.m[4] = -s; r.m[5] = c;
        return r;
    }

    static Mat4 scale(double sx, double sy, double sz) {
        Mat4 r = identity();
        r.m[0] = sx; r.m[5] = sy; r.m[10] = sz;
        return r;
    }

    Mat4 operator*(const Mat4& o) const {
        Mat4 r;
        for (int col = 0; col < 4; ++col) {
            for (int row = 0; row < 4; ++row) {
                double sum = 0.0;
                for (int k = 0; k < 4; ++k)
                    sum += m[k * 4 + row] * o.m[col * 4 + k];
                r.m[col * 4 + row] = sum;
            }
        }
        return r;
    }

    Vec3 transformPoint(const Vec3& p) const {
        double x = m[0]*p.x + m[4]*p.y + m[8]*p.z + m[12];
        double y = m[1]*p.x + m[5]*p.y + m[9]*p.z + m[13];
        double z = m[2]*p.x + m[6]*p.y + m[10]*p.z + m[14];
        return {x, y, z};
    }

    Vec3 translationPart() const { return {m[12], m[13], m[14]}; }

    static Mat4 perspective(double fovYRadians, double aspect, double zNear, double zFar) {
        Mat4 r{};
        double f = 1.0 / std::tan(fovYRadians / 2.0);
        r.m[0] = f / aspect;
        r.m[5] = f;
        r.m[10] = (zFar + zNear) / (zNear - zFar);
        r.m[11] = -1.0;
        r.m[14] = (2 * zFar * zNear) / (zNear - zFar);
        return r;
    }

    static Mat4 lookAt(const Vec3& eye, const Vec3& center, const Vec3& up) {
        Vec3 f = center - eye;
        double fl = std::sqrt(f.x*f.x + f.y*f.y + f.z*f.z);
        f = {f.x/fl, f.y/fl, f.z/fl};

        Vec3 s{f.y*up.z - f.z*up.y, f.z*up.x - f.x*up.z, f.x*up.y - f.y*up.x};
        double sl = std::sqrt(s.x*s.x + s.y*s.y + s.z*s.z);
        s = {s.x/sl, s.y/sl, s.z/sl};

        Vec3 u{s.y*f.z - s.z*f.y, s.z*f.x - s.x*f.z, s.x*f.y - s.y*f.x};

        Mat4 r = identity();
        r.m[0]=s.x; r.m[4]=s.y; r.m[8]=s.z;
        r.m[1]=u.x; r.m[5]=u.y; r.m[9]=u.z;
        r.m[2]=-f.x; r.m[6]=-f.y; r.m[10]=-f.z;
        r.m[12] = -(s.x*eye.x + s.y*eye.y + s.z*eye.z);
        r.m[13] = -(u.x*eye.x + u.y*eye.y + u.z*eye.z);
        r.m[14] = f.x*eye.x + f.y*eye.y + f.z*eye.z;
        return r;
    }
};

inline double clampd(double v, double lo, double hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

} // namespace roops
