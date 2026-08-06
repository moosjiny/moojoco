/**
 * ROOPS Humanoid Hand Engine v2 - headless CLI demo
 * Replays the same sequential handshake trajectory as handshake_oops_engine.cpp,
 * but every finger now moves through a real MCP/PIP/DIP (or CMC/MCP/IP) chain
 * instead of one lumped curl angle.
 */
#include "roops/HumanHandKinematics.hpp"
#include <iostream>
#include <algorithm>

int main() {
    std::cout << "=========================================================\n";
    std::cout << "  ROOPS Humanoid Hand Engine v2 (Anatomical Finger Joints)  \n";
    std::cout << "=========================================================\n";

    roops::HumanoidHandObject handA("Hand A", false);
    roops::HumanoidHandObject handB("Hand B", true);

    for (int step = 0; step <= 5; ++step) {
        double sliderVal = step * 0.05;
        double approachRatio = std::min(sliderVal / 0.185, 1.0);
        double claspRatio = std::max((sliderVal - 0.185) / 0.115, 0.0);

        double baseZ = (1.0 - approachRatio) * 3.5 + 1.35;
        double baseCurl = approachRatio * 0.35 + claspRatio * 0.90;
        double opposition = claspRatio; // thumb opposes into the grip during the clasp phase

        handA.setPosition(-0.25, 3.0, -baseZ);
        handB.setPosition(0.25, 3.0, baseZ);

        handA.setGraspCurl(baseCurl);
        handB.setGraspCurl(baseCurl);
        handA.setThumbOpposition(opposition);
        handB.setThumbOpposition(opposition);

        handA.computeForwardKinematics();
        handB.computeForwardKinematics();

        std::cout << "\n--- Step " << step << " (Slider: " << sliderVal << "m, curl: " << baseCurl << ") ---\n";
        for (const auto* h : {&handA, &handB}) {
            std::cout << "[" << h->name << "]\n";
            for (const auto& f : h->fingers) {
                std::cout << "  " << f.name << ": ";
                for (const auto& seg : f.segments) {
                    std::cout << seg.joint.name << "=" << (seg.joint.angle * 180.0 / M_PI) << "deg ";
                }
                std::cout << "\n";
            }
        }
    }

    handA.exportToExternalJson("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handA_cpp_v2.json");
    handB.exportToExternalJson("/home/moos/dev_ws/dual_arms/aegis_science_demo/tcp_handB_cpp_v2.json");

    std::cout << "\n[ROOPS Humanoid Hand Engine v2 Execution Completed Successfully]\n";
    return 0;
}
