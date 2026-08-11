import React from 'react';
import { X, Brain, Target, Zap, Award, Sparkles } from 'lucide-react';

interface RLPolicyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const RLPolicyModal: React.FC<RLPolicyModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in font-sans">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-[#0F0F12] border border-[#3B1F6A] rounded-2xl shadow-2xl text-zinc-100 p-6 scrollbar-thin">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-white bg-[#1A1825] rounded-lg border border-[#2E2842]"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-5 border-b border-[#29223D] pb-4">
          <div className="p-3 bg-purple-900/40 border border-purple-500/40 rounded-xl text-purple-400">
            <Brain className="w-7 h-7 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-extrabold text-white font-mono uppercase tracking-tight">
                Reinforcement Learning Palm-Contact Policy
              </h2>
              <span className="px-2 py-0.5 text-[10px] font-bold font-mono bg-purple-950 text-purple-300 border border-purple-700 rounded uppercase">
                PPO / SAC Agent
              </span>
            </div>
            <p className="text-xs text-purple-300 font-mono">
              MuJoCo Bipedal Robot Handshake Alignment Markov Decision Process (MDP)
            </p>
          </div>
        </div>

        {/* MDP Definition Grid */}
        <div className="space-y-4 text-xs font-mono">
          {/* Observation & Action Space */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 bg-[#14121E] rounded-xl border border-[#2E2545] space-y-1.5">
              <h3 className="text-[#A855F7] font-bold text-xs uppercase flex items-center gap-1.5">
                <Target className="w-4 h-4" /> Observation Space (S)
              </h3>
              <p className="text-[#AAA] text-[11px] leading-relaxed">
                State Vector s_t in R^28:
              </p>
              <ul className="list-disc list-inside text-[#888] text-[11px] space-y-1">
                <li>Palm relative position e_pos = P_A - P_B in R^3</li>
                <li>Palm normal rotation mismatch e_rot in R^3</li>
                <li>Joint angles q in R^14 & velocities dq/dt in R^14</li>
                <li>Tactile force feedback at 5 finger pads</li>
              </ul>
            </div>

            <div className="p-3 bg-[#14121E] rounded-xl border border-[#2E2545] space-y-1.5">
              <h3 className="text-[#EC4899] font-bold text-xs uppercase flex items-center gap-1.5">
                <Zap className="w-4 h-4" /> Action Space (A)
              </h3>
              <p className="text-[#AAA] text-[11px] leading-relaxed">
                Continuous Joint Torque Commands a_t in [-1, 1]^14:
              </p>
              <ul className="list-disc list-inside text-[#888] text-[11px] space-y-1">
                <li>Tau(shoulder_pitch, yaw, roll) [3 DoF / arm]</li>
                <li>Tau(elbow_flexion) [1 DoF / arm]</li>
                <li>Tau(wrist_pitch, roll) [2 DoF / arm]</li>
                <li>Tau(finger_flexion) [1 DoF / hand]</li>
              </ul>
            </div>
          </div>

          {/* Reward Formulation Code Box */}
          <div className="p-3 bg-[#0A090F] rounded-xl border border-[#2A213D] space-y-2">
            <h3 className="text-emerald-400 font-bold text-xs uppercase flex items-center gap-1.5">
              <Award className="w-4 h-4" /> Policy Reward Function R(s_t, a_t)
            </h3>
            <pre className="p-2.5 bg-[#050408] rounded border border-[#1E182B] text-[11px] text-purple-200 overflow-x-auto">
{`# Multi-Objective Handshake Reward Function
R_total = (
    - 10.0 * ||p_palmA - p_palmB||_2       # 3D Palm Distance Penalty
    -  5.0 * (1.0 - dot(n_palmA, -n_palmB)) # Palm Plane Facing Alignment
    + 150.0 * I(palm_contact <= 2mm)        # Convergence Contact Bonus
    -  0.01 * ||action_torque||_2           # Energy Efficiency Penalty
)`}
            </pre>
          </div>

          {/* Training Stages */}
          <div className="p-3 bg-[#14121E] rounded-xl border border-[#2E2545] space-y-2">
            <h3 className="text-sky-400 font-bold text-xs uppercase flex items-center gap-1.5">
              <Sparkles className="w-4 h-4" /> RL Policy Learning Phases
            </h3>
            <div className="grid grid-cols-3 gap-2 text-[10px]">
              <div className="p-2 bg-[#1A162B] rounded border border-[#30274B]">
                <strong className="text-purple-300 block mb-1">1. Trajectory Reach</strong>
                3D Spatial convergence of right palm toward midpoint.
              </div>
              <div className="p-2 bg-[#1A162B] rounded border border-[#30274B]">
                <strong className="text-purple-300 block mb-1">2. Plane Alignment</strong>
                Palm normal vector rotation so surfaces face back-to-back.
              </div>
              <div className="p-2 bg-[#1A162B] rounded border border-[#30274B]">
                <strong className="text-emerald-300 block mb-1">3. Palm Contact</strong>
                Flush surface touch (&lt;2mm) & DexHand finger clasp.
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="mt-5 text-right border-t border-[#29223D] pt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-mono font-bold text-white bg-[#6D28D9] hover:bg-[#7C3AED] border border-[#8B5CF6] rounded-lg transition-colors uppercase shadow-md shadow-purple-900/30"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
