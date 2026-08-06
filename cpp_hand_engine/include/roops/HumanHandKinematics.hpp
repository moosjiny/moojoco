/**
 * ROOPS Humanoid Hand Engine v2 — Anatomically-jointed finger kinematics
 * Author: Moojoco (mujoco_sim / hb5u)
 *
 * Supersedes the single-curl FingerJointLink model in handshake_oops_engine.cpp.
 * Each finger is now a real kinematic chain:
 *   - Index/Middle/Ring/Pinky: MCP(flex+abduct) -> proximal -> PIP(flex) -> middle -> DIP(flex) -> distal
 *   - Thumb:                   CMC(flex+oppose) -> metacarpal -> MCP(flex) -> proximal -> IP(flex) -> distal
 * DIP is mechanically coupled to PIP (tenodesis-style underactuation ratio), matching how
 * most real human grasps and most underactuated robot hands actually move.
 */
#pragma once
#include "Math3D.hpp"
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <chrono>

namespace roops {

// A single rotational DOF with an anatomical range of motion.
struct RevoluteJoint {
    std::string name;
    double angle = 0.0;      // radians, current value
    double minAngle = 0.0;
    double maxAngle = 0.0;
    char axis = 'X';         // 'X' = flexion/extension, 'Y' = abduction/adduction

    RevoluteJoint() = default;
    RevoluteJoint(std::string n, double lo, double hi, char ax = 'X')
        : name(std::move(n)), minAngle(lo), maxAngle(hi), axis(ax) {}

    void setAngle(double a) { angle = clampd(a, minAngle, maxAngle); }
    Mat4 localRotation() const {
        return axis == 'Y' ? Mat4::rotationY(angle) : Mat4::rotationX(angle);
    }
};

// One rigid bone (metacarpal/proximal/middle/distal phalanx), tapered capsule geometry.
struct PhalanxSegment {
    std::string name;
    double length = 1.0;
    double baseRadius = 0.3;
    double tipRadius = 0.25;
    RevoluteJoint joint;              // primary flexion joint at the base of this segment
    RevoluteJoint secondaryJoint;     // optional abduction/opposition joint (MCP, CMC only); maxAngle=0 => unused
    Mat4 worldOrigin = Mat4::identity();  // world transform at the segment base (post-joint rotation)
    Mat4 worldTip = Mat4::identity();     // world transform at the segment tip

    PhalanxSegment(std::string n, double len, double baseR, double tipR)
        : name(std::move(n)), length(len), baseRadius(baseR), tipRadius(tipR) {}
};

// Anatomical parameters for one finger, expressed as a serial chain of segments.
class Finger {
public:
    std::string name;
    bool isThumb = false;
    std::vector<PhalanxSegment> segments;   // 3 bones for every finger (incl. thumb metacarpal)
    Vec3 attachOffset;                      // position on the palm, palm-local frame
    double attachSpreadDeg = 0.0;           // static yaw of the finger base relative to palm +Z
    double dipToPipCoupling = 0.66;         // underactuation ratio: DIP angle = ratio * PIP angle

    Finger(std::string n, bool thumb, Vec3 offset, double spreadDeg)
        : name(std::move(n)), isThumb(thumb), attachOffset(offset), attachSpreadDeg(spreadDeg) {}

    // 0.0 = fully open, 1.0 = fully closed fist — drives every joint within its own
    // anatomical ROM rather than one shared angle, so the segments curl like a real finger.
    void setGraspCurl(double t) {
        t = clampd(t, 0.0, 1.0);
        if (isThumb) {
            // metacarpal: CMC flexion only (opposition set separately via setThumbOpposition)
            segments[0].joint.setAngle(t * segments[0].joint.maxAngle * 0.6);
            // proximal: MCP
            segments[1].joint.setAngle(t * segments[1].joint.maxAngle);
            // distal: IP
            segments[2].joint.setAngle(t * segments[2].joint.maxAngle);
        } else {
            // proximal: MCP flexion
            segments[0].joint.setAngle(t * segments[0].joint.maxAngle);
            // middle: PIP flexion (drives DIP via coupling)
            double pip = t * segments[1].joint.maxAngle;
            segments[1].joint.setAngle(pip);
            // distal: DIP, mechanically coupled to PIP (underactuated tendon-style coupling)
            segments[2].joint.setAngle(pip * dipToPipCoupling);
        }
    }

    // Thumb-only: palmar abduction / opposition, independent of grasp curl.
    void setThumbOpposition(double t) {
        if (!isThumb || segments.empty()) return;
        t = clampd(t, 0.0, 1.0);
        segments[0].secondaryJoint.setAngle(t * segments[0].secondaryJoint.maxAngle);
    }

    // Direct fine-grained control, e.g. for per-joint sliders in the Qt viewer.
    void setJointAngle(size_t segmentIndex, double angleRad) {
        if (segmentIndex < segments.size()) segments[segmentIndex].joint.setAngle(angleRad);
    }

    // Walk the chain: attach -> spread -> [joint rotate, extend by length] per segment.
    void computeForwardKinematics(const Mat4& palmWorld) {
        Mat4 frame = palmWorld
                   * Mat4::translation(attachOffset)
                   * Mat4::rotationY(attachSpreadDeg * M_PI / 180.0);

        for (auto& seg : segments) {
            Mat4 rot = seg.joint.localRotation();
            if (seg.secondaryJoint.maxAngle != 0.0) rot = seg.secondaryJoint.localRotation() * rot;
            frame = frame * rot;
            seg.worldOrigin = frame;
            frame = frame * Mat4::translation(Vec3(0, 0, seg.length));
            seg.worldTip = frame;
        }
    }
};

class Palm {
public:
    double width = 3.6, height = 1.2, depth = 2.4;
    Mat4 worldTransform = Mat4::identity();
};

// Wrist pose (position + Euler rotation), same external contract as the original
// RobotHandObject: SetPosition / SetRotation still work exactly as before.
class HumanoidHandObject {
public:
    std::string name;
    bool isFacingRotated = false;
    Palm palm;
    std::vector<Finger> fingers; // thumb, index, middle, ring, pinky

    Vec3 position;
    Vec3 rotation; // rx, ry, rz (radians)

    HumanoidHandObject(std::string handName, bool facingRotated)
        : name(std::move(handName)), isFacingRotated(facingRotated) {
        position = facingRotated ? Vec3(0.25, 3.0, 4.0) : Vec3(-0.25, 3.0, -4.0);
        rotation = facingRotated ? Vec3(0.0, M_PI, 0.0) : Vec3(0.0, 0.0, 0.0);
        buildAnatomy();
    }

    void setPosition(double x, double y, double z) { position = Vec3(x, y, z); }
    void setRotation(double rx, double ry, double rz) { rotation = Vec3(rx, ry, rz); }

    // Applies to all five fingers at once (replaces the old single-value SetFingerCurl,
    // but now every finger curls through its own anatomically-correct joint chain).
    void setGraspCurl(double t) {
        for (auto& f : fingers) f.setGraspCurl(t);
    }

    void setThumbOpposition(double t) {
        fingers[0].setThumbOpposition(t);
    }

    void computeForwardKinematics() {
        Mat4 wrist = Mat4::translation(position)
                   * Mat4::rotationZ(rotation.z)
                   * Mat4::rotationY(rotation.y)
                   * Mat4::rotationX(rotation.x);
        palm.worldTransform = wrist;
        for (auto& f : fingers) f.computeForwardKinematics(wrist);
    }

    void exportToExternalJson(const std::string& filepath) const {
        std::ofstream file(filepath);
        if (!file.is_open()) return;
        auto ts = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        file << "{\n";
        file << "  \"handName\": \"" << name << "\",\n";
        file << "  \"px\": " << position.x << ", \"py\": " << position.y << ", \"pz\": " << position.z << ",\n";
        file << "  \"rx\": " << rotation.x << ", \"ry\": " << rotation.y << ", \"rz\": " << rotation.z << ",\n";
        file << "  \"lastUpdated\": " << ts << ",\n";
        file << "  \"fingers\": [\n";
        for (size_t fi = 0; fi < fingers.size(); ++fi) {
            const auto& f = fingers[fi];
            file << "    { \"name\": \"" << f.name << "\", \"isThumb\": " << (f.isThumb ? "true" : "false") << ", \"segments\": [\n";
            for (size_t si = 0; si < f.segments.size(); ++si) {
                const auto& s = f.segments[si];
                Vec3 tip = s.worldTip.translationPart();
                file << "      { \"name\": \"" << s.name << "\", \"jointAngleDeg\": " << (s.joint.angle * 180.0 / M_PI)
                     << ", \"tip\": [" << tip.x << ", " << tip.y << ", " << tip.z << "] }";
                file << (si + 1 < f.segments.size() ? ",\n" : "\n");
            }
            file << "    ] }";
            file << (fi + 1 < fingers.size() ? ",\n" : "\n");
        }
        file << "  ]\n";
        file << "}\n";
    }

private:
    void buildAnatomy() {
        // spread (x), forward offset (z) mirrors the original layout in handshake_oops_engine.cpp
        fingers.emplace_back(makeThumb(Vec3(-1.6, 0.0, 1.0)));
        fingers.emplace_back(makeFinger("index",  Vec3(-0.8, 0.0, 1.4), 2.8, 0.32, -8.0, 100.0, 110.0, 90.0));
        fingers.emplace_back(makeFinger("middle", Vec3( 0.0, 0.0, 1.5), 3.0, 0.32,  0.0, 100.0, 110.0, 90.0));
        fingers.emplace_back(makeFinger("ring",   Vec3( 0.8, 0.0, 1.4), 2.7, 0.32,  8.0,  95.0, 105.0, 85.0));
        fingers.emplace_back(makeFinger("pinky",  Vec3( 1.6, 0.0, 1.2), 2.2, 0.30, 14.0,  90.0, 100.0, 80.0));
    }

    static Finger makeFinger(const std::string& n, Vec3 offset, double totalLength, double baseRadius,
                              double spreadDeg, double mcpMaxDeg, double pipMaxDeg, double dipMaxDeg) {
        Finger f(n, false, offset, spreadDeg);
        // Anatomical phalanx length ratio (proximal:middle:distal ~ 0.50:0.29:0.21)
        double lp = totalLength * 0.50, lm = totalLength * 0.29, ld = totalLength * 0.21;

        PhalanxSegment prox(n + "_proximal", lp, baseRadius, baseRadius * 0.85);
        prox.joint = RevoluteJoint(n + "_MCP", -8.0 * M_PI / 180.0, mcpMaxDeg * M_PI / 180.0, 'X');
        prox.secondaryJoint = RevoluteJoint(n + "_MCP_abduct", -15.0 * M_PI / 180.0, 15.0 * M_PI / 180.0, 'Y');

        PhalanxSegment mid(n + "_middle", lm, baseRadius * 0.85, baseRadius * 0.72);
        mid.joint = RevoluteJoint(n + "_PIP", 0.0, pipMaxDeg * M_PI / 180.0, 'X');

        PhalanxSegment dist(n + "_distal", ld, baseRadius * 0.72, baseRadius * 0.55);
        dist.joint = RevoluteJoint(n + "_DIP", 0.0, dipMaxDeg * M_PI / 180.0, 'X');

        f.segments = {prox, mid, dist};
        f.dipToPipCoupling = 0.66; // real-finger tendon coupling approximation
        return f;
    }

    static Finger makeThumb(Vec3 offset) {
        Finger f("thumb", true, offset, -35.0); // thumb sits rotated away from the finger plane
        PhalanxSegment mc("thumb_metacarpal", 0.9, 0.38, 0.34);
        mc.joint = RevoluteJoint("thumb_CMC_flex", 0.0, 45.0 * M_PI / 180.0, 'X');
        mc.secondaryJoint = RevoluteJoint("thumb_CMC_oppose", 0.0, 40.0 * M_PI / 180.0, 'Y');

        PhalanxSegment prox("thumb_proximal", 1.0, 0.34, 0.29);
        prox.joint = RevoluteJoint("thumb_MCP", 0.0, 55.0 * M_PI / 180.0, 'X');

        PhalanxSegment dist("thumb_distal", 0.7, 0.29, 0.23);
        dist.joint = RevoluteJoint("thumb_IP", 0.0, 80.0 * M_PI / 180.0, 'X');

        f.segments = {mc, prox, dist};
        return f;
    }
};

} // namespace roops
