import React, { useState } from 'react';
import { TelemetryData } from '../types';
import {
  Activity,
  ShieldCheck,
  Cpu,
  Move,
  ChevronDown,
  ChevronUp,
  Brain,
  Target,
  Scale,
  Waves,
  TriangleAlert,
} from 'lucide-react';

interface TelemetryPanelProps {
  data: TelemetryData;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({ data }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="absolute top-20 left-4 z-10 w-72 bg-[#0F0F10]/95 backdrop-blur-md border border-[#222226] rounded-xl shadow-2xl text-zinc-100 overflow-hidden font-sans">
      {/* Panel Title Bar */}
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center justify-between px-3.5 py-2.5 bg-[#111113] cursor-pointer border-b border-[#222226] hover:bg-[#1A1A1D] transition-colors"
      >
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[#3B82F6] animate-pulse" />
          <span className="text-[11px] font-bold tracking-widest uppercase text-[#888888] font-mono">
            Telemetry_Feedback
          </span>
        </div>
        <button className="text-[#666] hover:text-white">
          {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {!isCollapsed && (
        <div className="p-3 space-y-2.5 text-xs">
          {/* Main Stat Grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
              <span className="text-[10px] text-[#666666] uppercase font-mono font-bold block mb-0.5">
                Hand Contact
              </span>
              <div className="text-sm font-bold font-mono text-[#3B82F6]">
                {data.contactDistance}{' '}
                <span className="text-[10px] font-normal text-[#666]">mm</span>
              </div>
            </div>

            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
              <span className="text-[10px] text-[#666666] uppercase font-mono font-bold block mb-0.5">
                Grip Force
              </span>
              <div className="text-sm font-bold font-mono text-[#F59E0B]">
                {data.gripForce}{' '}
                <span className="text-[10px] font-normal text-[#666]">N</span>
              </div>
            </div>

            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
              <span className="text-[10px] text-[#666666] uppercase font-mono font-bold block mb-0.5">
                Joint Torque
              </span>
              <div className="text-sm font-bold font-mono text-[#4ADE80]">
                {data.jointTorquePeak}{' '}
                <span className="text-[10px] font-normal text-[#666]">Nm</span>
              </div>
            </div>

            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
              <span className="text-[10px] text-[#666666] uppercase font-mono font-bold block mb-0.5">
                Sync Balance
              </span>
              <div className="text-sm font-bold font-mono text-[#60A5FA]">
                {data.syncRatio}{' '}
                <span className="text-[10px] font-normal text-[#666]">%</span>
              </div>
            </div>
          </div>

          {/* RL Policy Stats Block */}
          {data.rlEpisode !== undefined && (
            <div className="p-2 bg-[#14121E] border border-[#3B1F6A] rounded space-y-1 font-mono">
              <div className="flex items-center justify-between text-[11px] text-[#A855F7] font-bold">
                <span className="flex items-center gap-1">
                  <Brain className="w-3.5 h-3.5 animate-pulse" /> RL PPO Policy Agent
                </span>
                <span className="text-purple-300">EP #{data.rlEpisode}</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-zinc-300">
                <span>Reward: <strong className="text-emerald-400">+{data.rlReward}</strong></span>
                <span>Error: <strong className="text-amber-300">{data.palmAlignmentError}mm</strong></span>
              </div>
              <div className="text-[10px] text-purple-200 bg-[#251347] px-1.5 py-0.5 rounded border border-[#4C1D95] text-center font-bold">
                {data.rlPolicyStatus}
              </div>
            </div>
          )}

          {/* World Coordinates & Impedance Status */}
          <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A] space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-[#666] flex items-center gap-1">
                <Move className="w-3 h-3 text-[#3B82F6]" /> Target_XYZ
              </span>
              <span className="text-[#AAA] font-bold">
                [{data.rightHandX}, {data.rightHandY}, {data.rightHandZ}]
              </span>
            </div>

            {data.stiffnessKx !== undefined && (
              <div className="pt-1 border-t border-[#1F1F22] flex items-center justify-between text-[10px] font-mono">
                <span className="text-[#10B981] flex items-center gap-1">
                  <Cpu className="w-3 h-3" /> Impedance Kx / Dx
                </span>
                <span className="text-emerald-400 font-bold">
                  {data.stiffnessKx} N/m | {data.dampingDx} Ns/m
                </span>
              </div>
            )}
          </div>

          {/* Static Stability (Stage 1 contact-dynamics: CoM vs support polygon) */}
          {data.comStabilityAlpha !== undefined && (
            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A] space-y-1 font-mono">
              <div className="flex items-center gap-1 text-[10px] text-[#666] uppercase font-bold">
                <Scale className="w-3 h-3 text-[#a3e635]" /> Static Balance (CoM vs Support Polygon)
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#888]">Alpha</span>
                <span
                  className={`font-bold ${
                    data.comStabilityAlpha === 'STABLE' ? 'text-[#34d399]' : 'text-[#f87171]'
                  }`}
                >
                  {data.comStabilityAlpha} ({data.comMarginAlphaMm}mm)
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#888]">Beta</span>
                <span
                  className={`font-bold ${
                    data.comStabilityBeta === 'STABLE' ? 'text-[#34d399]' : 'text-[#f87171]'
                  }`}
                >
                  {data.comStabilityBeta} ({data.comMarginBetaMm}mm)
                </span>
              </div>
            </div>
          )}

          {/* Dynamic ZMP + Friction Cone (Stage 2 contact-dynamics) */}
          {data.zmpStabilityAlpha !== undefined && (
            <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A] space-y-1 font-mono">
              <div className="flex items-center gap-1 text-[10px] text-[#666] uppercase font-bold">
                <Waves className="w-3 h-3 text-[#38bdf8]" /> Dynamic ZMP (CoM Accel)
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#888] flex items-center gap-1">
                  Alpha
                  {data.slipRiskAlpha && <TriangleAlert className="w-3 h-3 text-[#f59e0b]" />}
                </span>
                <span
                  className={`font-bold ${
                    data.zmpStabilityAlpha === 'STABLE' ? 'text-[#38bdf8]' : 'text-[#f87171]'
                  }`}
                >
                  {data.zmpStabilityAlpha} ({data.zmpMarginAlphaMm}mm)
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#888] flex items-center gap-1">
                  Beta
                  {data.slipRiskBeta && <TriangleAlert className="w-3 h-3 text-[#f59e0b]" />}
                </span>
                <span
                  className={`font-bold ${
                    data.zmpStabilityBeta === 'STABLE' ? 'text-[#38bdf8]' : 'text-[#f87171]'
                  }`}
                >
                  {data.zmpStabilityBeta} ({data.zmpMarginBetaMm}mm)
                </span>
              </div>
            </div>
          )}

          {/* Engine Status & FPS */}
          <div className="flex items-center justify-between pt-1 border-t border-[#1A1A1A] text-[10px] font-mono text-[#666]">
            <span className="flex items-center gap-1 text-[#4ADE80]">
              <ShieldCheck className="w-3 h-3" /> SOLVER_ACTIVE
            </span>
            <span className="text-[#888]">{data.fps} FPS</span>
          </div>
        </div>
      )}
    </div>
  );
};
