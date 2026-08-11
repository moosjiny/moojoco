import React, { useState } from 'react';
import { DEFAULT_JOINT_ANGLES, JointAngles } from '../types';
import { Sliders, RotateCcw, Bot, Save, FolderOpen, Footprints, Scale } from 'lucide-react';
import { soundEngine } from '../utils/audio';

const MANUAL_POSE_STORAGE_KEY = 'fingershake_manual_pose_v1';
const MANUAL_POSE_BACKUP_KEY = 'fingershake_manual_pose_v1_backup';

interface KinematicControlsProps {
  anglesAlpha: JointAngles;
  setAnglesAlpha: React.Dispatch<React.SetStateAction<JointAngles>>;
  anglesBeta: JointAngles;
  setAnglesBeta: React.Dispatch<React.SetStateAction<JointAngles>>;
  groundLock: boolean;
  setGroundLock: React.Dispatch<React.SetStateAction<boolean>>;
  showComOverlay: boolean;
  setShowComOverlay: React.Dispatch<React.SetStateAction<boolean>>;
}

export const KinematicControls: React.FC<KinematicControlsProps> = ({
  anglesAlpha,
  setAnglesAlpha,
  anglesBeta,
  setAnglesBeta,
  groundLock,
  setGroundLock,
  showComOverlay,
  setShowComOverlay,
}) => {
  const [activeTab, setActiveTab] = useState<'alpha' | 'beta'>('alpha');
  const [saveStatus, setSaveStatus] = useState<string>('');

  const activeAngles = activeTab === 'alpha' ? anglesAlpha : anglesBeta;
  const setActiveAngles = activeTab === 'alpha' ? setAnglesAlpha : setAnglesBeta;

  const handleChange = (key: keyof JointAngles, val: number) => {
    setActiveAngles((prev) => ({
      ...prev,
      [key]: val,
    }));
    soundEngine.playClick(600 + val * 2);
  };

  const resetToDefaultHandshake = () => {
    setAnglesAlpha(DEFAULT_JOINT_ANGLES);
    setAnglesBeta(DEFAULT_JOINT_ANGLES);
    soundEngine.playClick(950);
  };

  const savePose = () => {
    try {
      // Back up whatever was previously saved before overwriting it — a save
      // is one click and, until now, irreversible.
      const existing = localStorage.getItem(MANUAL_POSE_STORAGE_KEY);
      if (existing) {
        localStorage.setItem(MANUAL_POSE_BACKUP_KEY, existing);
      }
      localStorage.setItem(
        MANUAL_POSE_STORAGE_KEY,
        JSON.stringify({ alpha: anglesAlpha, beta: anglesBeta })
      );
      setSaveStatus('저장됨 — 다음 접속 시 자동 복원');
    } catch {
      setSaveStatus('저장 실패 (브라우저 저장소 접근 불가)');
    }
    soundEngine.playClick(1100);
    window.setTimeout(() => setSaveStatus(''), 2500);
  };

  const loadSavedPose = () => {
    try {
      const raw = localStorage.getItem(MANUAL_POSE_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.alpha) setAnglesAlpha(parsed.alpha);
        if (parsed.beta) setAnglesBeta(parsed.beta);
        setSaveStatus('저장된 값 불러옴');
      } else {
        setSaveStatus('저장된 값 없음');
      }
    } catch {
      setSaveStatus('불러오기 실패');
    }
    soundEngine.playClick(850);
    window.setTimeout(() => setSaveStatus(''), 2500);
  };

  return (
    <div className="absolute top-20 right-4 z-10 w-80 bg-[#0F0F10]/95 backdrop-blur-md border border-[#222226] rounded-xl shadow-2xl text-[#E0E0E0] p-3.5 space-y-3 font-sans">
      {/* Title */}
      <div className="flex items-center justify-between pb-2 border-b border-[#222226]">
        <div className="flex items-center gap-2">
          <Sliders className="w-3.5 h-3.5 text-[#3B82F6]" />
          <h3 className="text-[11px] font-bold uppercase tracking-widest text-[#888888] font-mono">
            Kinematic_Joint_Sliders
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={savePose}
            className="p-1 rounded bg-[#111113] hover:bg-[#1A1A1D] border border-[#222226] text-[#666] hover:text-[#34d399] transition-colors"
            title="현재 각도 저장 (localStorage)"
          >
            <Save className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={loadSavedPose}
            className="p-1 rounded bg-[#111113] hover:bg-[#1A1A1D] border border-[#222226] text-[#666] hover:text-[#8ab4f8] transition-colors"
            title="저장된 각도 불러오기"
          >
            <FolderOpen className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={resetToDefaultHandshake}
            className="p-1 rounded bg-[#111113] hover:bg-[#1A1A1D] border border-[#222226] text-[#666] hover:text-white transition-colors"
            title="기본 포즈로 리셋"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setGroundLock((prev) => !prev);
              soundEngine.playClick(groundLock ? 500 : 900);
            }}
            className={`p-1 rounded border transition-colors ${
              groundLock
                ? 'bg-[#0F2E1F] border-[#34d399] text-[#34d399]'
                : 'bg-[#111113] border-[#222226] text-[#666] hover:text-[#34d399]'
            }`}
            title="지면 고정 — 고관절/무릎/발목 각도를 바꿔도 발바닥이 항상 바닥(y=0)에 붙도록 로봇 몸통 높이를 자동 보정 (물리엔진의 발 접촉 해석을 근사)"
          >
            <Footprints className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => {
              setShowComOverlay((prev) => !prev);
              soundEngine.playClick(showComOverlay ? 500 : 900);
            }}
            className={`p-1 rounded border transition-colors ${
              showComOverlay
                ? 'bg-[#1E2A0F] border-[#a3e635] text-[#a3e635]'
                : 'bg-[#111113] border-[#222226] text-[#666] hover:text-[#a3e635]'
            }`}
            title="무게중심/지지 다각형/ZMP 표시 — 무게중심(CoM)·지지 다각형에 더해, CoM 가속도로 구한 ZMP(파란/노랑/빨강 고리)와 마찰원뿔 초과 여부(미끄러짐 위험)까지 판정 (Stage 1+2 접촉 동역학 근사)"
          >
            <Scale className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {groundLock && (
        <div className="text-[10px] text-center text-[#34d399] font-mono -mt-1">
          🦶 지면 고정 ON — 다리 각도와 무관하게 발이 바닥에 고정됨
        </div>
      )}

      {showComOverlay && (
        <div className="text-[10px] text-center text-[#a3e635] font-mono -mt-1">
          ⚖️ 무게중심/ZMP 표시 ON — 구슬(CoM) 빨강=정적 불안정, 고리(ZMP) 노랑=미끄러짐 위험/빨강=동적 불안정
        </div>
      )}

      {saveStatus && (
        <div className="text-[10px] text-center text-[#8ab4f8] font-mono -mt-1">{saveStatus}</div>
      )}

      {/* Robot Selection Tabs */}
      <div className="grid grid-cols-2 gap-1 p-1 bg-[#111113] rounded border border-[#222226] text-xs font-mono">
        <button
          onClick={() => {
            setActiveTab('alpha');
            soundEngine.playClick(750);
          }}
          className={`py-1.5 font-bold rounded transition-all flex items-center justify-center gap-1.5 ${
            activeTab === 'alpha'
              ? 'bg-[#1D4ED8] text-white border border-[#3B82F6]'
              : 'text-[#666] hover:text-[#AAA]'
          }`}
        >
          <Bot className="w-3.5 h-3.5 text-[#3B82F6]" /> Alpha_RBT (L)
        </button>
        <button
          onClick={() => {
            setActiveTab('beta');
            soundEngine.playClick(750);
          }}
          className={`py-1.5 font-bold rounded transition-all flex items-center justify-center gap-1.5 ${
            activeTab === 'beta'
              ? 'bg-[#33251A] text-[#F59E0B] border border-[#5E452B]'
              : 'text-[#666] hover:text-[#AAA]'
          }`}
        >
          <Bot className="w-3.5 h-3.5 text-[#F59E0B]" /> Beta_RBT (R)
        </button>
      </div>

      {/* Sliders */}
      <div className="space-y-2 text-xs max-h-80 overflow-y-auto pr-1 font-mono">
        {/* Shoulder Pitch */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Shoulder Pitch</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.shoulderPitch}°</span>
          </div>
          <input
            type="range"
            min="-120"
            max="30"
            value={activeAngles.shoulderPitch}
            onChange={(e) => handleChange('shoulderPitch', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Shoulder Yaw */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Shoulder Yaw</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.shoulderYaw}°</span>
          </div>
          <input
            type="range"
            min="-60"
            max="60"
            value={activeAngles.shoulderYaw}
            onChange={(e) => handleChange('shoulderYaw', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Shoulder Roll */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Shoulder Roll</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.shoulderRoll}°</span>
          </div>
          <input
            type="range"
            min="-180"
            max="180"
            value={activeAngles.shoulderRoll}
            onChange={(e) => handleChange('shoulderRoll', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Elbow Flexion */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Elbow Flexion</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.elbowFlexion}°</span>
          </div>
          <input
            type="range"
            min="0"
            max="120"
            value={activeAngles.elbowFlexion}
            onChange={(e) => handleChange('elbowFlexion', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Wrist Pitch */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Wrist Pitch</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.wristPitch}°</span>
          </div>
          <input
            type="range"
            min="-45"
            max="45"
            value={activeAngles.wristPitch}
            onChange={(e) => handleChange('wristPitch', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Wrist Roll */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Wrist Roll</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.wristRoll}°</span>
          </div>
          <input
            type="range"
            min="-180"
            max="180"
            value={activeAngles.wristRoll}
            onChange={(e) => handleChange('wristRoll', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Wrist Yaw */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Wrist Yaw</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.wristYaw}°</span>
          </div>
          <input
            type="range"
            min="-90"
            max="90"
            value={activeAngles.wristYaw}
            onChange={(e) => handleChange('wristYaw', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Independent Finger Curls */}
        {(
          [
            ['thumbCurl', 'Thumb Curl'],
            ['indexCurl', 'Index Curl'],
            ['middleCurl', 'Middle Curl'],
            ['ringCurl', 'Ring Curl'],
            ['pinkyCurl', 'Pinky Curl'],
          ] as [keyof JointAngles, string][]
        ).map(([key, label]) => (
          <div key={key} className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
            <div className="flex justify-between text-[#888] mb-1 text-[11px]">
              <span>{label}</span>
              <span className="font-mono text-[#F59E0B] font-bold">
                {Math.round(activeAngles[key] * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={activeAngles[key]}
              onChange={(e) => handleChange(key, Number(e.target.value))}
              className="w-full accent-[#F59E0B] bg-[#222226] rounded h-1 cursor-pointer"
            />
          </div>
        ))}

        {/* Torso Yaw */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Torso Yaw</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.torsoYaw}°</span>
          </div>
          <input
            type="range"
            min="-180"
            max="180"
            value={activeAngles.torsoYaw}
            onChange={(e) => handleChange('torsoYaw', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Torso Pitch */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Torso Pitch</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.torsoPitch}°</span>
          </div>
          <input
            type="range"
            min="-30"
            max="30"
            value={activeAngles.torsoPitch}
            onChange={(e) => handleChange('torsoPitch', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Foot Angle (Ankle Pitch, both feet) */}
        <div className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
          <div className="flex justify-between text-[#888] mb-1 text-[11px]">
            <span>Foot Angle</span>
            <span className="font-mono text-[#3B82F6] font-bold">{activeAngles.footPitch}°</span>
          </div>
          <input
            type="range"
            min="-45"
            max="45"
            value={activeAngles.footPitch}
            onChange={(e) => handleChange('footPitch', Number(e.target.value))}
            className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
          />
        </div>

        {/* Hip Flexion & Knee Flexion (both legs, symmetric) */}
        {(
          [
            ['hipFlexion', 'Hip Flexion', -45, 90],
            ['kneeFlexion', 'Knee Flexion', 0, 120],
          ] as [keyof JointAngles, string, number, number][]
        ).map(([key, label, min, max]) => (
          <div key={key} className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
            <div className="flex justify-between text-[#888] mb-1 text-[11px]">
              <span>{label}</span>
              <span className="font-mono text-[#3B82F6] font-bold">{activeAngles[key]}°</span>
            </div>
            <input
              type="range"
              min={min}
              max={max}
              value={activeAngles[key]}
              onChange={(e) => handleChange(key, Number(e.target.value))}
              className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
            />
          </div>
        ))}

        {/* Left Arm — independent, not mirrored from the right arm above */}
        <div className="pt-1 pb-0.5 text-center text-[10px] uppercase tracking-widest text-[#555] font-mono border-t border-[#1A1A1A]">
          Left Arm (independent)
        </div>

        {(
          [
            ['leftShoulderPitch', 'Left Shoulder Pitch', -120, 30],
            ['leftShoulderYaw', 'Left Shoulder Yaw', -60, 60],
            ['leftShoulderRoll', 'Left Shoulder Roll', -180, 180],
            ['leftElbowFlexion', 'Left Elbow Flexion', 0, 120],
          ] as [keyof JointAngles, string, number, number][]
        ).map(([key, label, min, max]) => (
          <div key={key} className="p-2 bg-[#111113] rounded border border-[#1A1A1A]">
            <div className="flex justify-between text-[#888] mb-1 text-[11px]">
              <span>{label}</span>
              <span className="font-mono text-[#3B82F6] font-bold">{activeAngles[key]}°</span>
            </div>
            <input
              type="range"
              min={min}
              max={max}
              value={activeAngles[key]}
              onChange={(e) => handleChange(key, Number(e.target.value))}
              className="w-full accent-[#3B82F6] bg-[#222226] rounded h-1 cursor-pointer"
            />
          </div>
        ))}
      </div>
    </div>
  );
};
