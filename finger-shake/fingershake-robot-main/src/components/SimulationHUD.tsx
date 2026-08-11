import React from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Gauge,
  Zap,
  Award,
  AlertTriangle,
  Sliders,
  Hand,
  Cpu,
  Brain,
} from 'lucide-react';
import { HandshakeMode } from '../types';
import { soundEngine } from '../utils/audio';

interface SimulationHUDProps {
  mode: HandshakeMode;
  setMode: (mode: HandshakeMode) => void;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  speed: number;
  setSpeed: (speed: number) => void;
}

export const SimulationHUD: React.FC<SimulationHUDProps> = ({
  mode,
  setMode,
  isPlaying,
  setIsPlaying,
  speed,
  setSpeed,
}) => {
  const modes: { id: HandshakeMode; label: string; icon: React.ReactNode; desc: string }[] = [
    {
      id: 'standard',
      label: '표준 악수',
      icon: <Hand className="w-4 h-4 text-blue-400" />,
      desc: '자연스러운 주파수 및 상체 체중 이동',
    },
    {
      id: 'impedance',
      label: 'MuJoCo 임피던스 제어',
      icon: <Cpu className="w-4 h-4 text-emerald-400" />,
      desc: 'Task-Space Impedance Control (유연성 제어 + 중력 보상)',
    },
    {
      id: 'rl_agent',
      label: 'RL 손바닥 자율 탐색',
      icon: <Brain className="w-4 h-4 text-purple-400" />,
      desc: '강화학습(PPO/SAC Policy)을 통해 손바닥 맞닿음 실시간 자율 추종',
    },
    {
      id: 'energetic',
      label: '강렬한 악수',
      icon: <Zap className="w-4 h-4 text-amber-400" />,
      desc: '높은 케이던스 및 가슴 파워 발광',
    },
    {
      id: 'diplomatic',
      label: '외교적 악수',
      icon: <Award className="w-4 h-4 text-sky-400" />,
      desc: '절제된 정중함 및 고개의 정중한 응시',
    },
    {
      id: 'highfive',
      label: '하이파이브',
      icon: <Hand className="w-4 h-4 text-cyan-400" />,
      desc: '손 들어올려 손바닥을 부딪히는 동작',
    },
    {
      id: 'manual',
      label: '수동 조작',
      icon: <Sliders className="w-4 h-4 text-purple-400" />,
      desc: '각 관절 각도 개별 슬라이더 수동 제어',
    },
  ];

  return (
    <div className="absolute bottom-4 left-4 right-4 z-20 flex flex-col md:flex-row items-center justify-between gap-3 p-3 bg-[#0F0F10]/95 backdrop-blur-md border border-[#222226] rounded-xl shadow-2xl text-[#E0E0E0]">
      {/* Mode Selector Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto max-w-full pb-1 md:pb-0 scrollbar-none font-mono">
        {modes.map((m) => {
          const isActive = mode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => {
                setMode(m.id);
                soundEngine.playClick(800);
              }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-bold whitespace-nowrap transition-all border ${
                isActive
                  ? 'bg-[#1D4ED8] border-[#3B82F6] text-white shadow-md shadow-blue-900/30'
                  : 'bg-[#111113] border-[#222226] text-[#666] hover:text-[#AAA] hover:bg-[#1A1A1D]'
              }`}
              title={m.desc}
            >
              {m.icon}
              {m.label}
            </button>
          );
        })}
      </div>

      {/* Playback Controls & Speed */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Play / Pause Toggle */}
        <button
          onClick={() => {
            setIsPlaying(!isPlaying);
            soundEngine.playClick(isPlaying ? 500 : 900);
          }}
          className={`flex items-center justify-center w-9 h-9 rounded-full font-bold transition-all shadow-md ${
            isPlaying
              ? 'bg-[#1D4ED8] hover:bg-[#2563EB] text-white border border-[#3B82F6]'
              : 'bg-[#33251A] hover:bg-[#453222] text-[#F59E0B] border border-[#5E452B]'
          }`}
          title={isPlaying ? '일시정지' : '시뮬레이션 재생'}
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>

        {/* Speed Controls */}
        <div className="flex items-center gap-1 bg-[#111113] px-2 py-1 rounded border border-[#222226] text-xs font-mono">
          <Gauge className="w-3.5 h-3.5 text-[#3B82F6]" />
          <span className="text-[#666] text-[11px] font-bold">RATE:</span>
          {[0.25, 0.5, 1.0, 2.0].map((s) => (
            <button
              key={s}
              onClick={() => {
                setSpeed(s);
                soundEngine.playClick(700 + s * 100);
              }}
              className={`px-1.5 py-0.5 rounded font-mono font-bold text-xs transition-all ${
                speed === s
                  ? 'bg-[#1D4ED8] text-white'
                  : 'text-[#666] hover:text-[#AAA]'
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
