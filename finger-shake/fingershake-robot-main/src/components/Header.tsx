import React, { useState } from 'react';
import {
  Volume2,
  VolumeX,
  Camera,
  Palette,
  Info,
  Bot,
  Layers,
  HelpCircle,
  X,
  Cpu,
  Brain,
} from 'lucide-react';
import { CameraPreset, RobotTheme } from '../types';
import { soundEngine } from '../utils/audio';
import { MujocoCodeModal } from './MujocoCodeModal';
import { RLPolicyModal } from './RLPolicyModal';

interface HeaderProps {
  theme: RobotTheme;
  setTheme: (theme: RobotTheme) => void;
  cameraPreset: CameraPreset;
  setCameraPreset: (preset: CameraPreset) => void;
  isMuted: boolean;
  setIsMuted: (muted: boolean) => void;
  showGrid: boolean;
  setShowGrid: (show: boolean) => void;
  showAxes: boolean;
  setShowAxes: (show: boolean) => void;
  showContactVector: boolean;
  setShowContactVector: (show: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  theme,
  setTheme,
  cameraPreset,
  setCameraPreset,
  isMuted,
  setIsMuted,
  showGrid,
  setShowGrid,
  showAxes,
  setShowAxes,
  showContactVector,
  setShowContactVector,
}) => {
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showMujocoModal, setShowMujocoModal] = useState(false);
  const [showRLModal, setShowRLModal] = useState(false);

  const toggleSound = () => {
    const nextMuted = soundEngine.toggleMute();
    setIsMuted(nextMuted);
    if (!nextMuted) {
      soundEngine.playClick(900);
    }
  };

  return (
    <header className="absolute top-0 left-0 right-0 z-20 flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 bg-[#111113]/90 backdrop-blur-md border-b border-[#222226] text-zinc-100 font-sans">
      {/* Title & Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#1D4ED8] border border-[#3B82F6] shadow-md shadow-blue-500/20 text-white font-bold">
          <Bot className="w-5 h-5 animate-pulse" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold tracking-tight text-white uppercase font-sans">
              SIM_CORE <span className="font-normal text-zinc-500 text-xs lowercase">v2.4.0</span>
            </h1>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#1A332E] text-[#4ADE80] border border-[#2B5E50] font-mono uppercase tracking-wider">
              Sync: Handshake
            </span>
            <span className="hidden sm:inline-block text-[10px] font-bold px-2 py-0.5 rounded bg-[#33251A] text-[#F59E0B] border border-[#5E452B] font-mono uppercase tracking-wider">
              Torque Normal
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 font-mono tracking-tight">
            이족보행 로봇 3D Kinematics & Task-Space Impedance Control
          </p>
        </div>
      </div>

      {/* Control Buttons Group */}
      <div className="flex items-center flex-wrap gap-2 text-xs">
        {/* Camera Preset Selection */}
        <div className="flex items-center gap-1.5 bg-[#0F0F10] px-2.5 py-1.5 rounded-lg border border-[#222226]">
          <Camera className="w-3.5 h-3.5 text-[#3B82F6]" />
          <select
            value={cameraPreset}
            onChange={(e) => {
              setCameraPreset(e.target.value as CameraPreset);
              soundEngine.playClick(750);
            }}
            className="bg-transparent text-xs text-zinc-200 focus:outline-none cursor-pointer pr-1 font-mono"
          >
            <option value="default" className="bg-[#111113] text-white">
              Cam: Default Perspective
            </option>
            <option value="hands" className="bg-[#111113] text-white">
              Cam: Hand_R_Contact
            </option>
            <option value="closeup" className="bg-[#111113] text-white">
              Cam: Dual_Robot_CloseUp
            </option>
            <option value="side" className="bg-[#111113] text-white">
              Cam: Joint_Side_View
            </option>
            <option value="top" className="bg-[#111113] text-white">
              Cam: Top_Down_Overview
            </option>
            <option value="robotA" className="bg-[#111113] text-white">
              Cam: Robot_Alpha_POV
            </option>
            <option value="robotB" className="bg-[#111113] text-white">
              Cam: Robot_Beta_POV
            </option>
          </select>
        </div>

        {/* Theme Selector */}
        <div className="flex items-center gap-1.5 bg-[#0F0F10] px-2.5 py-1.5 rounded-lg border border-[#222226]">
          <Palette className="w-3.5 h-3.5 text-[#F59E0B]" />
          <select
            value={theme}
            onChange={(e) => {
              setTheme(e.target.value as RobotTheme);
              soundEngine.playClick(650);
            }}
            className="bg-transparent text-xs text-zinc-200 focus:outline-none cursor-pointer pr-1 font-mono"
          >
            <option value="cyber" className="bg-[#111113] text-white">
              Theme: Cyber Blue
            </option>
            <option value="stealth" className="bg-[#111113] text-white">
              Theme: Stealth Dark
            </option>
            <option value="titanium" className="bg-[#111113] text-white">
              Theme: Titanium Silver
            </option>
            <option value="industrial" className="bg-[#111113] text-white">
              Theme: Industrial Yellow
            </option>
          </select>
        </div>

        {/* View Overlays Toggles */}
        <div className="flex items-center bg-[#0F0F10] rounded-lg p-1 border border-[#222226] gap-1 text-[11px] font-mono">
          <button
            onClick={() => {
              setShowGrid(!showGrid);
              soundEngine.playClick(700);
            }}
            className={`px-2 py-1 rounded transition-colors ${
              showGrid
                ? 'bg-[#1D4ED8] text-white font-medium border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
            title="바닥 그리드 표시/숨기기"
          >
            <Layers className="w-3 h-3 inline mr-1" />
            Grid
          </button>
          <button
            onClick={() => {
              setShowAxes(!showAxes);
              soundEngine.playClick(700);
            }}
            className={`px-2 py-1 rounded transition-colors ${
              showAxes
                ? 'bg-[#1D4ED8] text-white font-medium border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
            title="관절 좌표축 표시/숨기기"
          >
            Axes
          </button>
          <button
            onClick={() => {
              setShowContactVector(!showContactVector);
              soundEngine.playClick(700);
            }}
            className={`px-2 py-1 rounded transition-colors ${
              showContactVector
                ? 'bg-[#1D4ED8] text-white font-medium border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
            title="접촉 반력 벡터 표시/숨기기"
          >
            Vector
          </button>
        </div>

        {/* RL Policy Inspector Button */}
        <button
          onClick={() => {
            setShowRLModal(true);
            soundEngine.playClick(920);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-purple-950/40 border border-purple-600/40 text-purple-300 font-mono font-bold hover:bg-purple-900/50 transition-all shadow-sm"
          title="Reinforcement Learning Palm Contact Policy & MDP Reward Inspector"
        >
          <Brain className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
          <span className="hidden md:inline text-[11px]">RL Policy</span>
        </button>

        {/* MuJoCo Code Inspector Button */}
        <button
          onClick={() => {
            setShowMujocoModal(true);
            soundEngine.playClick(900);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#10B981]/20 border border-[#10B981]/40 text-[#10B981] font-mono font-bold hover:bg-[#10B981]/30 transition-all shadow-sm"
          title="MuJoCo Task-Space Impedance Python Code & Math Inspector"
        >
          <Cpu className="w-3.5 h-3.5" />
          <span className="hidden md:inline text-[11px]">MuJoCo Code</span>
        </button>

        {/* Mute Audio Button */}
        <button
          onClick={toggleSound}
          className={`p-2 rounded-lg border transition-all ${
            isMuted
              ? 'bg-[#0F0F10] border-[#222226] text-zinc-400 hover:text-zinc-200'
              : 'bg-[#1A332E] border-[#2B5E50] text-[#4ADE80] shadow-sm'
          }`}
          title={isMuted ? '음소거 해제' : '음소거'}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>

        {/* Info Modal Trigger */}
        <button
          onClick={() => {
            setShowInfoModal(true);
            soundEngine.playClick(850);
          }}
          className="p-2 rounded-lg bg-[#0F0F10] border border-[#222226] text-zinc-300 hover:text-white transition-all hover:bg-[#18181B]"
          title="시뮬레이션 정보"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>

      {/* RL Policy Inspector Modal */}
      <RLPolicyModal isOpen={showRLModal} onClose={() => setShowRLModal(false)} />

      {/* MuJoCo Code Inspector Modal */}
      <MujocoCodeModal isOpen={showMujocoModal} onClose={() => setShowMujocoModal(false)} />

      {/* Info Modal */}
      {showInfoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-lg p-6 bg-[#0F0F10] border border-[#222226] rounded-xl shadow-2xl text-zinc-200 font-sans">
            <button
              onClick={() => setShowInfoModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-[#1D4ED8]/20 text-[#3B82F6] rounded-lg border border-[#3B82F6]/30">
                <Info className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-extrabold uppercase tracking-tight text-white font-mono">
                  SIM_CORE Kinematics Engine
                </h3>
                <p className="text-xs text-zinc-400 font-mono">
                  Interactive 3D Bipedal Robot Handshake Simulation
                </p>
              </div>
            </div>

            <div className="space-y-3 text-xs text-zinc-300">
              <p className="leading-relaxed">
                양팔과 두 다리를 가진 두 대의 이족보행 로봇(알파 & 베타)이 오른쪽 손을 맞잡고 상호작용하는 물리 Kinematics를 실시간 계산하여 시각화합니다.
              </p>
              <div className="p-3 bg-[#141416] rounded-lg border border-[#222226] text-xs space-y-2 font-mono">
                <h4 className="font-bold text-[#3B82F6] uppercase flex items-center gap-1.5">
                  <Bot className="w-4 h-4" /> System Capabilities
                </h4>
                <ul className="list-disc list-inside space-y-1 text-zinc-300">
                  <li><b>Hierarchical Joint Kinematics</b>: Shoulder Pitch/Yaw/Roll, Elbow, Wrist & Multi-segment Fingers</li>
                  <li><b>Handshake Dynamics & Impedance Control</b>: Task-Space Impedance Control (MuJoCo compliant spring-damper + gravity compensation)</li>
                  <li><b>Manual Kinematics Solver</b>: Real-time joint degree customization via precision sliders</li>
                  <li><b>Telemetry Monitor</b>: Contact Distance (mm), Grip Force (N), Peak Torque (Nm) & World XYZ</li>
                </ul>
              </div>
              <p className="text-[11px] text-zinc-500 font-mono">
                Navigation: Left Drag (Rotate) | Right Drag (Pan) | Scroll (Zoom)
              </p>
            </div>

            <div className="mt-6 text-right">
              <button
                onClick={() => setShowInfoModal(false)}
                className="px-4 py-2 text-xs font-mono font-bold text-white bg-[#1D4ED8] hover:bg-[#2563EB] border border-[#3B82F6] rounded transition-colors uppercase"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

