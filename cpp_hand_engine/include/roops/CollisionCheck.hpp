/**
 * ROOPS Humanoid Hand Engine — real geometric collision detection between two hands.
 *
 * Unlike the reference OOPS engine's `CollisionShield` (a cosmetic color/opacity wrapper
 * with no distance math — see handshake_oops_engine.cpp), this approximates every phalanx
 * segment and the palm as a capsule (line segment + radius) and computes the true closest
 * distance between every Hand-A / Hand-B capsule pair each frame.
 */
#pragma once
#include "Math3D.hpp"
#include "HumanHandKinematics.hpp"
#include <string>
#include <vector>
#include <limits>

namespace roops {

struct CapsulePrimitive {
    std::string label;
    Vec3 a, b;     // world-space centerline endpoints
    double radius; // approximated as the average of the segment's base/tip radius
};

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

inline std::vector<CapsulePrimitive> collectCapsules(const HumanoidHandObject& hand) {
    std::vector<CapsulePrimitive> caps;

    // Palm: approximated as a single sphere (degenerate capsule) at the wrist origin,
    // radius bounding the palm box's footprint.
    Vec3 palmCenter = hand.palm.worldTransform.translationPart();
    double palmRadius = 0.5 * std::sqrt(hand.palm.width * hand.palm.width + hand.palm.depth * hand.palm.depth);
    caps.push_back({hand.name + "/palm", palmCenter, palmCenter, palmRadius});

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

// Checks every Hand-A capsule against every Hand-B capsule (cross-hand only — the
// intentional per-finger self-interlocking within one hand is not flagged).
inline CollisionResult checkHandCollision(const HumanoidHandObject& handA, const HumanoidHandObject& handB) {
    CollisionResult result;
    auto capsA = collectCapsules(handA);
    auto capsB = collectCapsules(handB);

    for (const auto& ca : capsA) {
        for (const auto& cb : capsB) {
            double dist = closestPtSegmentSegment(ca.a, ca.b, cb.a, cb.b);
            double penetration = (ca.radius + cb.radius) - dist;
            if (penetration > result.worstPenetration) {
                result.worstPenetration = penetration;
                result.partA = ca.label;
                result.partB = cb.label;
                result.colliding = penetration > 0.0;
            }
        }
    }
    return result;
}

} // namespace roops
