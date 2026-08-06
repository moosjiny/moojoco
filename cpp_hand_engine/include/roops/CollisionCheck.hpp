/**
 * ROOPS Humanoid Hand Engine — real geometric collision detection between two hands.
 *
 * Unlike the reference OOPS engine's `CollisionShield` (a cosmetic color/opacity wrapper
 * with no distance math — see handshake_oops_engine.cpp), this computes the true closest
 * distance between every finger segment (capsule) and the palm (a proper oriented box,
 * OBB) of Hand A against Hand B each frame.
 *
 * The palm was previously approximated as a chain of parallel capsules (see git history),
 * which is a round-cross-section shape and can never exactly cover a rectangular one: it
 * under-covers the box's corners/edges between the chain's capsule centers, letting a thin
 * finger capsule tunnel through undetected near those regions (a false negative, visible as
 * real mesh interpenetration that the collision guard fails to block). A true OBB removes
 * that whole class of approximation error.
 */
#pragma once
#include "Math3D.hpp"
#include "HumanHandKinematics.hpp"
#include <string>
#include <vector>
#include <limits>
#include <utility>
#include <cmath>

namespace roops {

struct CapsulePrimitive {
    std::string label;
    Vec3 a, b;     // world-space centerline endpoints
    double radius; // approximated as the average of the segment's base/tip radius
};

// Oriented bounding box: world-space center, three orthonormal axes, half-extent along each.
struct OBB {
    std::string label;
    Vec3 center;
    Vec3 axisX, axisY, axisZ; // unit vectors, world space
    Vec3 halfExtents;         // along axisX, axisY, axisZ respectively
};

inline Vec3 cross(const Vec3& a, const Vec3& b) {
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

// Closest distance between two line segments (Ericson, "Real-Time Collision Detection" 5.1.9).
inline double closestPtSegmentSegment(const Vec3& p1, const Vec3& q1, const Vec3& p2, const Vec3& q2) {
    Vec3 d1 = q1 - p1, d2 = q2 - p2, r = p1 - p2;
    double a = d1.dot(d1), e = d2.dot(d2), f = d2.dot(r);
    const double EPS = 1e-9;
    double s, t;

    if (a <= EPS && e <= EPS) {
        return (p1 - p2).length();
    }
    if (a <= EPS) {
        s = 0.0;
        t = clampd(f / e, 0.0, 1.0);
    } else {
        double c = d1.dot(r);
        if (e <= EPS) {
            t = 0.0;
            s = clampd(-c / a, 0.0, 1.0);
        } else {
            double b = d1.dot(d2);
            double denom = a * e - b * b;
            s = (denom != 0.0) ? clampd((b * f - c * e) / denom, 0.0, 1.0) : 0.0;
            t = (b * s + f) / e;
            if (t < 0.0) { t = 0.0; s = clampd(-c / a, 0.0, 1.0); }
            else if (t > 1.0) { t = 1.0; s = clampd((b - c) / a, 0.0, 1.0); }
        }
    }
    Vec3 c1 = p1 + d1 * s;
    Vec3 c2 = p2 + d2 * t;
    return (c1 - c2).length();
}

// Closest distance between a line segment and an OBB, via alternating projection: repeatedly
// project the current segment point onto the box (clamp in the box's local frame — exact,
// since the box is axis-aligned there) and the current box point onto the segment (standard
// point-segment projection). This converges to the true global closest points because both
// shapes are convex (classical alternating-projection result); 20 iterations is far more than
// enough for shapes at this scale (sub-millimeter convergence in practice).
inline double closestPtSegmentOBB(const Vec3& segA, const Vec3& segB, const OBB& box) {
    auto toLocal = [&](const Vec3& p) {
        Vec3 d = p - box.center;
        return Vec3(d.dot(box.axisX), d.dot(box.axisY), d.dot(box.axisZ));
    };
    Vec3 a = toLocal(segA), b = toLocal(segB);
    Vec3 d = b - a;
    double segLenSq = d.dot(d);

    Vec3 p = a + d * 0.5;
    Vec3 onBox = p;
    for (int iter = 0; iter < 20; ++iter) {
        onBox = Vec3(
            clampd(p.x, -box.halfExtents.x, box.halfExtents.x),
            clampd(p.y, -box.halfExtents.y, box.halfExtents.y),
            clampd(p.z, -box.halfExtents.z, box.halfExtents.z));
        if (segLenSq <= 1e-12) { p = a; break; }
        double t = clampd((onBox - a).dot(d) / segLenSq, 0.0, 1.0);
        p = a + d * t;
    }
    Vec3 diff = p - onBox;
    return diff.length();
}

// OBB-vs-OBB overlap via the Separating Axis Theorem (Gottschalk): tests the 3 face normals
// of each box plus the 9 cross products of their edge axes (15 candidate axes total). If any
// axis separates the boxes, they don't overlap. Otherwise the minimum per-axis overlap is
// used as an approximate penetration depth (the same approach used by e.g. Bullet's OBB-OBB
// detector) — not always the exact minimum-translation vector for edge-edge contacts, but
// accurate enough for this diagnostic/guard use case.
inline std::pair<bool, double> overlapOBBOBB(const OBB& A, const OBB& B) {
    Vec3 axesA[3] = {A.axisX, A.axisY, A.axisZ};
    Vec3 axesB[3] = {B.axisX, B.axisY, B.axisZ};
    double halfA[3] = {A.halfExtents.x, A.halfExtents.y, A.halfExtents.z};
    double halfB[3] = {B.halfExtents.x, B.halfExtents.y, B.halfExtents.z};
    Vec3 centerDiff = B.center - A.center;

    double minOverlap = std::numeric_limits<double>::max();
    bool found = false;

    auto testAxis = [&](Vec3 axis) -> bool {
        double len = axis.length();
        if (len < 1e-9) return true; // near-parallel edge pair: degenerate cross product, skip
        axis = axis * (1.0 / len);
        double ra = 0.0, rb = 0.0;
        for (int i = 0; i < 3; ++i) {
            ra += halfA[i] * std::fabs(axesA[i].dot(axis));
            rb += halfB[i] * std::fabs(axesB[i].dot(axis));
        }
        double dist = std::fabs(centerDiff.dot(axis));
        double overlap = ra + rb - dist;
        if (overlap < 0.0) return false; // separating axis found -> boxes don't overlap
        if (overlap < minOverlap) { minOverlap = overlap; found = true; }
        return true;
    };

    for (auto& ax : axesA) if (!testAxis(ax)) return {false, 0.0};
    for (auto& ax : axesB) if (!testAxis(ax)) return {false, 0.0};
    for (auto& a : axesA)
        for (auto& b : axesB)
            if (!testAxis(cross(a, b))) return {false, 0.0};

    return {true, found ? minOverlap : 0.0};
}

inline OBB buildPalmOBB(const HumanoidHandObject& hand) {
    const Mat4& t = hand.palm.worldTransform;
    OBB box;
    box.label = hand.name + "/palm";
    box.center = t.translationPart();
    box.axisX = Vec3(t.m[0], t.m[1], t.m[2]);
    box.axisY = Vec3(t.m[4], t.m[5], t.m[6]);
    box.axisZ = Vec3(t.m[8], t.m[9], t.m[10]);
    box.halfExtents = Vec3(hand.palm.width * 0.5, hand.palm.height * 0.5, hand.palm.depth * 0.5);
    return box;
}

inline std::vector<CapsulePrimitive> collectFingerCapsules(const HumanoidHandObject& hand) {
    std::vector<CapsulePrimitive> caps;
    for (const auto& f : hand.fingers) {
        for (const auto& seg : f.segments) {
            caps.push_back({
                hand.name + "/" + seg.name,
                seg.worldOrigin.translationPart(),
                seg.worldTip.translationPart(),
                0.5 * (seg.baseRadius + seg.tipRadius)
            });
        }
    }
    return caps;
}

struct CollisionResult {
    bool colliding = false;
    double worstPenetration = 0.0; // positive = overlap depth, in scene units
    std::string partA, partB;
};

// Checks every Hand-A part against every Hand-B part (cross-hand only — the intentional
// per-finger self-interlocking within one hand is not flagged): finger-vs-finger as
// capsule-vs-capsule, finger-vs-palm as capsule-vs-OBB, palm-vs-palm as OBB-vs-OBB (SAT).
inline CollisionResult checkHandCollision(const HumanoidHandObject& handA, const HumanoidHandObject& handB) {
    CollisionResult result;

    auto consider = [&](double penetration, const std::string& a, const std::string& b) {
        if (penetration > result.worstPenetration) {
            result.worstPenetration = penetration;
            result.partA = a;
            result.partB = b;
            result.colliding = penetration > 0.0;
        }
    };

    auto capsA = collectFingerCapsules(handA);
    auto capsB = collectFingerCapsules(handB);
    OBB palmA = buildPalmOBB(handA);
    OBB palmB = buildPalmOBB(handB);

    for (const auto& ca : capsA) {
        for (const auto& cb : capsB) {
            double dist = closestPtSegmentSegment(ca.a, ca.b, cb.a, cb.b);
            consider((ca.radius + cb.radius) - dist, ca.label, cb.label);
        }
    }
    for (const auto& ca : capsA) {
        double dist = closestPtSegmentOBB(ca.a, ca.b, palmB);
        consider(ca.radius - dist, ca.label, palmB.label);
    }
    for (const auto& cb : capsB) {
        double dist = closestPtSegmentOBB(cb.a, cb.b, palmA);
        consider(cb.radius - dist, palmA.label, cb.label);
    }
    auto [palmColliding, palmDepth] = overlapOBBOBB(palmA, palmB);
    if (palmColliding) consider(palmDepth, palmA.label, palmB.label);

    return result;
}

} // namespace roops
