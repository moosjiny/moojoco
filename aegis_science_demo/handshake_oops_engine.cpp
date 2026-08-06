/**
 * ROOPS (Robot Object-Oriented Programming System - OOPS)
 * C++ High-Performance Sub-Object Modular Architecture for Humanoid Robot Hands
 * Author: Aegis (Google DeepMind Science / ROOPS Infrastructure Hub)
 * Dual C++ & Python High-Performance Engine Implementation
 */

#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <fstream>
#include <memory>
#include <chrono>

namespace ROOPS {

// 3D Vector Math
struct Vector3 {
    double x = 0.0, y = 0.0, z = 0.0;
    Vector3() = default;
    Vector3(double _x, double _y, double _z) : x(_x), y(_y), z(_z) {}
};

struct EulerRotation {
    double rx = 0.0, ry = 0.0, rz = 0.0; // In radians
    EulerRotation() = default;
    EulerRotation(double _rx, double _ry, double _rz) : rx(_rx), ry(_ry), rz(_rz) {}
};

// Sub-Object 1: TCP Frame Axes
class TcpFrameAxes {
private:
    double axisLength;
public:
    explicit TcpFrameAxes(double length = 3.5) : axisLength(length) {}
    void RenderInfo() const {
        std::cout << "  [TcpFrameAxes] RGB Axes active (Length: " << axisLength << "m)\n";
    }
};

// Sub-Object 2: 3D Collision Shield
class CollisionShield {
private:
    std::string colorHex;
    double opacity;
    bool active;
public:
    CollisionShield(std::string hex = "0x34d399", double op = 0.7)
        : colorHex(hex), opacity(op), active(true) {}
    void SetColor(const std::string& hex) { colorHex = hex; }
    std::string GetColor() const { return colorHex; }
};

// Sub-Object 3: Finger Joint Link Sub-Object
class FingerJointLink {
public:
    std::string name;
    double x, z;
    double length;
    double radius;
    double maxAngle;
    double currentCurlAngle;
    CollisionShield shield;

    FingerJointLink(std::string _name, double _x, double _z, double _len, double _r, double _maxAngle)
        : name(_name), x(_x), z(_z), length(_len), radius(_r), maxAngle(_maxAngle), currentCurlAngle(0.0), shield("0x34d399", 0.7) {}

    void SetCurlAngle(double angle) {
        currentCurlAngle = std::min(angle, maxAngle);
    }
};

// Sub-Object 4: Palm Base Sub-Object
class PalmBase {
public:
    double width, height, depth;
    CollisionShield shield;

    PalmBase(double w = 3.6, double h = 1.2, double d = 2.4)
        : width(w), height(h), depth(d), shield("0x34d399", 0.6) {}
};

// Internal Instance State Struct
struct HandInternalState {
    std::string handName;
    Vector3 position;
    EulerRotation rotation;
    uint64_t lastUpdatedTimestamp;
};

// Sub-Object 5: Top-Level RobotHandObject
class RobotHandObject {
private:
    std::string name;
    bool isFacingRotated;
    PalmBase palm;
    TcpFrameAxes tcpAxes;
    std::vector<FingerJointLink> fingers;
    HandInternalState internalState;
    bool isSelected;

public:
    RobotHandObject(std::string _name, bool facingRotated = false)
        : name(_name), isFacingRotated(facingRotated), palm(3.6, 1.2, 2.4), tcpAxes(3.5), isSelected(false) {
        
        // Initial Pose
        internalState.handName = _name;
        internalState.position = facingRotated ? Vector3(0.25, 3.0, 4.0) : Vector3(-0.25, 3.0, -4.0);
        internalState.rotation = facingRotated ? EulerRotation(0.0, M_PI, 0.0) : EulerRotation(0.0, 0.0, 0.0);
        internalState.lastUpdatedTimestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        // 5 Finger Joint Links initialization
        fingers.emplace_back("thumb", -1.6, 1.0, 2.2, 0.35, 1.10);
        fingers.emplace_back("index", -0.8, 1.4, 2.8, 0.32, 1.22);
        fingers.emplace_back("middle", 0.0, 1.5, 3.0, 0.32, 1.25);
        fingers.emplace_back("ring", 0.8, 1.4, 2.7, 0.32, 1.20);
        fingers.emplace_back("pinky", 1.6, 1.2, 2.2, 0.30, 1.15);
    }

    void SetPosition(double x, double y, double z) {
        internalState.position = Vector3(x, y, z);
    }

    void SetRotation(double rx, double ry, double rz) {
        internalState.rotation = EulerRotation(rx, ry, rz);
    }

    void SetFingerCurl(double curlAmount) {
        for (auto& finger : fingers) {
            finger.SetCurlAngle(curlAmount);
        }
    }

    void SetAllShieldColors(const std::string& hex) {
        palm.shield.SetColor(hex);
        for (auto& finger : fingers) {
            finger.shield.SetColor(hex);
        }
    }

    // Export internal state to JSON File for external Python/WebGL linking
    void ExportToExternalJson(const std::string& filepath) const {
        std::ofstream file(filepath);
        if (file.is_open()) {
            file << "{\n";
            file << "  \"handName\": \"" << internalState.handName << "\",\n";
            file << "  \"px\": " << internalState.position.x << ",\n";
            file << "  \"py\": " << internalState.position.y << ",\n";
            file << "  \"pz\": " << internalState.position.z << ",\n";
            file << "  \"rx\": " << internalState.rotation.rx << ",\n";
            file << "  \"ry\": " << internalState.rotation.ry << ",\n";
            file << "  \"rz\": " << internalState.rotation.rz << "\n";
            file << "}\n";
            file.close();
            std::cout << "[ROOPS OOPS C++] Exported " << name << " state to " << filepath << "\n";
        }
    }

    void PrintTelemetry() const {
        std::cout << "[" << name << "] Pos: (" << internalState.position.x << ", " 
                  << internalState.position.y << ", " << internalState.position.z << ") | Rot: ("
                  << internalState.rotation.rx * 180.0 / M_PI << "deg, "
                  << internalState.rotation.ry * 180.0 / M_PI << "deg, "
                  << internalState.rotation.rz * 180.0 / M_PI << "deg) | Shield: "
                  << palm.shield.GetColor() << "\n";
    }
};

} // namespace ROOPS

int main() {
    std::cout << "=========================================================\n";
    std::cout << "  ROOPS OOPS (Object-Oriented C++) Humanoid Hand Engine  \n";
    std::cout << "=========================================================\n";

    ROOPS::RobotHandObject handA("Hand A", false);
    ROOPS::RobotHandObject handB("Hand B", true);

    std::cout << "\n[C++ Engine Init Poses]\n";
    handA.PrintTelemetry();
    handB.PrintTelemetry();

    // Simulate Sequential Phase-Coupled Handshake Trajectory (Phase 1 & Phase 2)
    std::cout << "\n[Simulating Sequential Phase-Coupled Handshake Trajectory in C++]\n";
    for (int step = 0; step <= 5; ++step) {
        double sliderVal = step * 0.05; // 0.00m to 0.25m
        double approachRatio = std::min(sliderVal / 0.185, 1.0);
        double claspRatio = std::max((sliderVal - 0.185) / 0.115, 0.0);

        double baseZ = (1.0 - approachRatio) * 3.5 + 1.35;
        double baseCurl = approachRatio * 0.35 + claspRatio * 0.90;

        handA.SetPosition(-0.25, 3.0, -baseZ);
        handB.SetPosition(0.25, 3.0, baseZ);

        handA.SetFingerCurl(baseCurl);
        handB.SetFingerCurl(baseCurl);

        if (approachRatio >= 1.0) {
            handA.SetAllShieldColors("0x34d399"); // Green shields in Phase 2
            handB.SetAllShieldColors("0x34d399");
        } else {
            handA.SetAllShieldColors("0x38bdf8"); // Cyan / Orange in Phase 1
            handB.SetAllShieldColors("0xf97316");
        }

        std::cout << "\n--- Step " << step << " (Slider: " << sliderVal << "m) ---\n";
        handA.PrintTelemetry();
        handB.PrintTelemetry();
    }

    // Export Linked JSON
    handA.ExportToExternalJson("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handA_cpp.json");
    handB.ExportToExternalJson("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handB_cpp.json");

    std::cout << "\n[ROOPS C++ Engine Execution Completed Successfully 🟢]\n";
    return 0;
}
