import React, { useEffect, useRef, useState } from 'react';
import { DEFAULT_JOINT_ANGLES, JointAngles, MujocoBridgeStatus } from '../types';
import { Sliders, RotateCcw, Bot, Save, FolderOpen, Footprints, Scale, Cpu, GripHorizontal } from 'lucide-react';
import { soundEngine } from '../utils/audio';

const MANUAL_POSE_STORAGE_KEY = 'fingershake_manual_pose_v1';
const MANUAL_POSE_BACKUP_KEY = 'fingershake_manual_pose_v1_backup';

// Panel is draggable/resizable (width and, for the slider list, height) since
// the icon row overflowed the old fixed w-80 once enough toggles accumulated.
// Layout persists across reloads.
const PANEL_LAYOUT_STORAGE_KEY = 'fingershake_kinematic_panel_layout_v1';
const PANEL_DEFAULT_WIDTH = 400;
const PANEL_MIN_WIDTH = 280;
const PANEL_MAX_WIDTH = 640;
const PANEL_DEFAULT_TOP = 80; // matches the old top-20 default
// The sliders list is the only part with a bounded, scrollable height — the
// header/tabs/status lines above it are always fully shown. 320px matches
// the old fixed max-h-80.
const SLIDER_AREA_DEFAULT_HEIGHT = 320;
const SLIDER_AREA_MIN_HEIGHT = 150;
const SLIDER_AREA_MAX_HEIGHT = 900;

interface PanelLayout {
  x: number;
  y: number;
  width: number;
  sliderAreaHeight?: number;
}

function loadPanelLayout(): PanelLayout | null {
  try {
    const raw = localStorage.getItem(PANEL_LAYOUT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.x === 'number' && typeof parsed?.y === 'number' && typeof parsed?.width === 'number') {
      return parsed;
    }
  } catch {
    // ignore malformed/blocked storage
  }
  return null;
}

// A slider row with a draggable range plus a directly-editable number box.
// The number box keeps its own local text state and only commits (clamped)
// on blur/Enter, so mid-typing states like "-" or "12" while aiming for
// "-120" aren't fought by a controlled re-render on every keystroke.
interface SliderRowProps {
  sliderKey: keyof JointAngles;
  label: string;
  min: number;
  max: number;
  step?: number;
  format?: 'deg' | 'percent';
  value: number;
  onChange: (key: keyof JointAngles, val: number) => void;
  highlighted: boolean;
  registerRef: (key: keyof JointAngles, el: HTMLDivElement | null) => void;
}

const SliderRow: React.FC<SliderRowProps> = ({
  sliderKey,
  label,
  min,
  max,
  step,
  format = 'deg',
  value,
  onChange,
  highlighted,
  registerRef,
}) => {
  const toDisplay = (v: number) => (format === 'percent' ? Math.round(v * 100) : Math.round(v));
  const fromDisplay = (v: number) => (format === 'percent' ? v / 100 : v);
  const [text, setText] = useState<string>(String(toDisplay(value)));

  useEffect(() => {
    setText(String(toDisplay(value)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, format]);

  const commit = () => {
    const n = Number(text);
    if (Number.isNaN(n)) {
      setText(String(toDisplay(value)));
      return;
    }
    const clampedDisplay = Math.min(toDisplay(max), Math.max(toDisplay(min), n));
    setText(String(clampedDisplay));
    onChange(sliderKey, fromDisplay(clampedDisplay));
  };

  const accent = format === 'percent' ? '#F59E0B' : '#3B82F6';

  return (
    <div
      ref={(el) => registerRef(sliderKey, el)}
      className={`p-1.5 rounded border transition-colors ${
        highlighted ? 'bg-[#132038] border-[#3B82F6] ring-1 ring-[#3B82F6]' : 'bg-[#111113] border-[#1A1A1A]'
      }`}
    >
      <div className="flex justify-between items-center text-[#888] mb-0.5 text-[11px] gap-2">
        <span className="truncate">{label}</span>
        <div className="flex items-center gap-0.5 shrink-0">
          <input
            type="number"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
            }}
            className="w-12 bg-[#0A0A0B] border border-[#222226] rounded px-1 py-0.5 text-right font-mono font-bold text-[11px] focus:outline-none focus:border-[#3B82F6]"
            style={{ color: accent }}
          />
          <span className="text-[#666]">{format === 'percent' ? '%' : '°'}</span>
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(sliderKey, Number(e.target.value))}
        className="w-full rounded h-1 cursor-pointer bg-[#222226]"
        style={{ accentColor: accent }}
      />
    </div>
  );
};

const ARM_SLIDERS: [keyof JointAngles, string, number, number][] = [
  ['shoulderPitch', 'Shoulder Pitch', -120, 30],
  ['shoulderYaw', 'Shoulder Yaw', -60, 60],
  ['shoulderRoll', 'Shoulder Roll', -180, 180],
  ['elbowFlexion', 'Elbow Flexion', 0, 120],
  ['wristPitch', 'Wrist Pitch', -45, 45],
  ['wristRoll', 'Wrist Roll', -180, 180],
  ['wristYaw', 'Wrist Yaw', -90, 90],
];

const CURL_SLIDERS: [keyof JointAngles, string][] = [
  ['thumbCurl', 'Thumb Curl'],
  ['indexCurl', 'Index Curl'],
  ['middleCurl', 'Middle Curl'],
  ['ringCurl', 'Ring Curl'],
  ['pinkyCurl', 'Pinky Curl'],
];

const BODY_SLIDERS: [keyof JointAngles, string, number, number][] = [
  ['bodyYaw', 'Body Yaw', -180, 180],
  ['torsoYaw', 'Torso Yaw', -180, 180],
  ['torsoPitch', 'Torso Pitch', -30, 30],
  ['headPitch', 'Head Pitch', -30, 30],
  ['footPitch', 'Foot Angle', -45, 45],
  ['hipFlexion', 'Hip Flexion', -45, 90],
  ['kneeFlexion', 'Knee Flexion', 0, 120],
];

const LEFT_ARM_SLIDERS: [keyof JointAngles, string, number, number][] = [
  ['leftShoulderPitch', 'Left Shoulder Pitch', -120, 30],
  ['leftShoulderYaw', 'Left Shoulder Yaw', -60, 60],
  ['leftShoulderRoll', 'Left Shoulder Roll', -180, 180],
  ['leftElbowFlexion', 'Left Elbow Flexion', 0, 120],
];

interface KinematicControlsProps {
  anglesAlpha: JointAngles;
  setAnglesAlpha: React.Dispatch<React.SetStateAction<JointAngles>>;
  anglesBeta: JointAngles;
  setAnglesBeta: React.Dispatch<React.SetStateAction<JointAngles>>;
  groundLock: boolean;
  setGroundLock: React.Dispatch<React.SetStateAction<boolean>>;
  showComOverlay: boolean;
  setShowComOverlay: React.Dispatch<React.SetStateAction<boolean>>;
  mujocoLive: boolean;
  setMujocoLive: React.Dispatch<React.SetStateAction<boolean>>;
  mujocoStatus: MujocoBridgeStatus;
  // Set when a joint gizmo is clicked in the 3D view (see RobotScene.tsx
  // onJointSelect) — switches to that robot's tab and highlights/scrolls to
  // the slider(s) that actually drive the clicked joint.
  highlightRobot: 'alpha' | 'beta' | null;
  highlightKeys: (keyof JointAngles)[];
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
  mujocoLive,
  setMujocoLive,
  mujocoStatus,
  highlightRobot,
  highlightKeys,
}) => {
  const [activeTab, setActiveTab] = useState<'alpha' | 'beta'>('alpha');
  const sliderRefs = useRef<Partial<Record<keyof JointAngles, HTMLDivElement>>>({});
  const registerSliderRef = (key: keyof JointAngles, el: HTMLDivElement | null) => {
    if (el) sliderRefs.current[key] = el;
    else delete sliderRefs.current[key];
  };

  // A joint clicked in 3D selects its robot's tab and scrolls its slider(s)
  // into view, so "click the joint, see the slider" works without hunting.
  useEffect(() => {
    if (!highlightRobot || highlightKeys.length === 0) return;
    setActiveTab(highlightRobot);
    const el = sliderRefs.current[highlightKeys[0]];
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlightRobot, highlightKeys]);
  const [saveStatus, setSaveStatus] = useState<string>('');

  const [panelPos, setPanelPos] = useState<{ x: number; y: number }>(() => {
    const saved = loadPanelLayout();
    if (saved) {
      // Position was persisted from whatever window size it was last dragged
      // in — clamp it into the CURRENT window so a saved position from a
      // wider/taller screen doesn't leave the panel off-screen (or leave the
      // resize-handle math with zero/negative room to work with) here.
      return {
        x: Math.min(Math.max(0, saved.x), Math.max(0, window.innerWidth - 40)),
        y: Math.min(Math.max(0, saved.y), Math.max(0, window.innerHeight - 40)),
      };
    }
    return { x: Math.max(8, window.innerWidth - PANEL_DEFAULT_WIDTH - 16), y: PANEL_DEFAULT_TOP };
  });
  const [panelWidth, setPanelWidth] = useState<number>(() => loadPanelLayout()?.width ?? PANEL_DEFAULT_WIDTH);
  const [sliderAreaHeight, setSliderAreaHeight] = useState<number>(
    () => loadPanelLayout()?.sliderAreaHeight ?? SLIDER_AREA_DEFAULT_HEIGHT
  );

  useEffect(() => {
    try {
      localStorage.setItem(
        PANEL_LAYOUT_STORAGE_KEY,
        JSON.stringify({ ...panelPos, width: panelWidth, sliderAreaHeight })
      );
    } catch {
      // ignore blocked storage
    }
  }, [panelPos, panelWidth, sliderAreaHeight]);

  const dragStateRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeStateRef = useRef<{ startX: number; origWidth: number } | null>(null);
  const vResizeStateRef = useRef<{ startY: number; origHeight: number } | null>(null);

  const handlePanelDragMove = (e: MouseEvent) => {
    const d = dragStateRef.current;
    if (!d) return;
    setPanelPos({
      x: Math.min(Math.max(0, d.origX + (e.clientX - d.startX)), window.innerWidth - 40),
      y: Math.min(Math.max(0, d.origY + (e.clientY - d.startY)), window.innerHeight - 40),
    });
  };
  const handlePanelDragEnd = () => {
    dragStateRef.current = null;
    window.removeEventListener('mousemove', handlePanelDragMove);
    window.removeEventListener('mouseup', handlePanelDragEnd);
  };
  const handlePanelDragStart = (e: React.MouseEvent) => {
    dragStateRef.current = { startX: e.clientX, startY: e.clientY, origX: panelPos.x, origY: panelPos.y };
    window.addEventListener('mousemove', handlePanelDragMove);
    window.addEventListener('mouseup', handlePanelDragEnd);
  };

  const handlePanelResizeMove = (e: MouseEvent) => {
    const r = resizeStateRef.current;
    if (!r) return;
    // The available-room cap must never fall below PANEL_MIN_WIDTH itself —
    // otherwise (e.g. panelPos.x close to window.innerWidth) this clamp
    // silently pins the width to a tiny/negative value and the handle
    // appears to do nothing.
    const maxWidth = Math.max(PANEL_MIN_WIDTH, Math.min(PANEL_MAX_WIDTH, window.innerWidth - panelPos.x - 8));
    setPanelWidth(Math.min(Math.max(PANEL_MIN_WIDTH, r.origWidth + (e.clientX - r.startX)), maxWidth));
  };
  const handlePanelResizeEnd = () => {
    resizeStateRef.current = null;
    window.removeEventListener('mousemove', handlePanelResizeMove);
    window.removeEventListener('mouseup', handlePanelResizeEnd);
  };
  const handlePanelResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    resizeStateRef.current = { startX: e.clientX, origWidth: panelWidth };
    window.addEventListener('mousemove', handlePanelResizeMove);
    window.addEventListener('mouseup', handlePanelResizeEnd);
  };

  const handlePanelVResizeMove = (e: MouseEvent) => {
    const r = vResizeStateRef.current;
    if (!r) return;
    // Same fix as the width handle above — never let the cap drop below the
    // minimum itself.
    const maxHeight = Math.max(
      SLIDER_AREA_MIN_HEIGHT,
      Math.min(SLIDER_AREA_MAX_HEIGHT, window.innerHeight - panelPos.y - 160)
    );
    setSliderAreaHeight(
      Math.min(Math.max(SLIDER_AREA_MIN_HEIGHT, r.origHeight + (e.clientY - r.startY)), maxHeight)
    );
  };
  const handlePanelVResizeEnd = () => {
    vResizeStateRef.current = null;
    window.removeEventListener('mousemove', handlePanelVResizeMove);
    window.removeEventListener('mouseup', handlePanelVResizeEnd);
  };
  const handlePanelVResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    vResizeStateRef.current = { startY: e.clientY, origHeight: sliderAreaHeight };
    window.addEventListener('mousemove', handlePanelVResizeMove);
    window.addEventListener('mouseup', handlePanelVResizeEnd);
  };

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
    <div
      className="absolute z-10 bg-[#0F0F10]/95 backdrop-blur-md border border-[#222226] rounded-xl shadow-2xl text-[#E0E0E0] p-3.5 space-y-3 font-sans"
      style={{ left: panelPos.x, top: panelPos.y, width: panelWidth }}
    >
      {/* Resize handle — drag to change panel width */}
      <div
        onMouseDown={handlePanelResizeStart}
        title="드래그해서 패널 폭 조절"
        className="absolute top-0 right-0 h-full w-2 cursor-ew-resize hover:bg-[#3B82F6]/30 rounded-r-xl"
      />

      {/* Resize handle — drag to change the slider list's height */}
      <div
        onMouseDown={handlePanelVResizeStart}
        title="드래그해서 슬라이더 목록 세로 크기 조절"
        className="absolute bottom-0 left-0 w-full h-2 cursor-ns-resize hover:bg-[#3B82F6]/30 rounded-b-xl"
      />

      {/* Title (drag handle — drag to move the panel). min-w-0 + truncate on
          the title lets THIS side shrink first as the panel narrows, so the
          icon row on the right (flex-shrink-0) always stays fully visible
          instead of spilling past the panel/window edge. */}
      <div className="flex items-center justify-between gap-2 pb-2 border-b border-[#222226]">
        <div
          onMouseDown={handlePanelDragStart}
          title="드래그해서 패널 위치 이동"
          className="flex items-center gap-2 cursor-move select-none min-w-0"
        >
          <GripHorizontal className="w-3.5 h-3.5 text-[#555] shrink-0" />
          <Sliders className="w-3.5 h-3.5 text-[#3B82F6] shrink-0" />
          <h3 className="text-[11px] font-bold uppercase tracking-widest text-[#888888] font-mono truncate">
            Kinematic_Joint_Sliders
          </h3>
        </div>
        <div className="flex items-center gap-1 shrink-0">
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
          <button
            onClick={() => {
              setMujocoLive((prev) => !prev);
              soundEngine.playClick(mujocoLive ? 500 : 900);
            }}
            className={`p-1 rounded border transition-colors ${
              mujocoLive
                ? mujocoStatus === 'connected'
                  ? 'bg-[#0F1E2E] border-[#38bdf8] text-[#38bdf8]'
                  : mujocoStatus === 'error'
                  ? 'bg-[#2E0F0F] border-[#f87171] text-[#f87171]'
                  : 'bg-[#2E260F] border-[#facc15] text-[#facc15]'
                : 'bg-[#111113] border-[#222226] text-[#666] hover:text-[#38bdf8]'
            }`}
            title="MuJoCo Live (Alpha 오른팔) — 오른팔 7개 슬라이더를 실제 MuJoCo 물리 브리지(ws://<host>:8765)의 PD 제어 목표로 전송하고, 돌아오는 관절각으로 렌더링을 갱신 (관절 이름 1:1 순서 매핑, 해부학적으로 정확하지 않은 근사)"
          >
            <Cpu className="w-3.5 h-3.5" />
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

      {mujocoLive && (
        <div
          className={`text-[10px] text-center font-mono -mt-1 ${
            mujocoStatus === 'connected'
              ? 'text-[#38bdf8]'
              : mujocoStatus === 'error'
              ? 'text-[#f87171]'
              : 'text-[#facc15]'
          }`}
        >
          🖥️ MuJoCo Live (Alpha 오른팔){' '}
          {mujocoStatus === 'connected'
            ? 'ON — 실제 물리 브리지 연결됨'
            : mujocoStatus === 'error'
            ? '연결 실패 (브리지 서버 확인 필요)'
            : '연결 중...'}
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
      <div
        className="space-y-1 text-xs overflow-y-auto pr-1 font-mono"
        style={{ maxHeight: sliderAreaHeight }}
      >
        {ARM_SLIDERS.map(([key, label, min, max]) => (
          <SliderRow
            key={key}
            sliderKey={key}
            label={label}
            min={min}
            max={max}
            value={activeAngles[key]}
            onChange={handleChange}
            highlighted={highlightRobot === activeTab && highlightKeys.includes(key)}
            registerRef={registerSliderRef}
          />
        ))}

        {CURL_SLIDERS.map(([key, label]) => (
          <SliderRow
            key={key}
            sliderKey={key}
            label={label}
            min={0}
            max={1}
            step={0.05}
            format="percent"
            value={activeAngles[key]}
            onChange={handleChange}
            highlighted={highlightRobot === activeTab && highlightKeys.includes(key)}
            registerRef={registerSliderRef}
          />
        ))}

        {BODY_SLIDERS.map(([key, label, min, max]) => (
          <SliderRow
            key={key}
            sliderKey={key}
            label={label}
            min={min}
            max={max}
            value={activeAngles[key]}
            onChange={handleChange}
            highlighted={highlightRobot === activeTab && highlightKeys.includes(key)}
            registerRef={registerSliderRef}
          />
        ))}

        {/* Left Arm — independent, not mirrored from the right arm above */}
        <div className="pt-1 pb-0.5 text-center text-[10px] uppercase tracking-widest text-[#555] font-mono border-t border-[#1A1A1A]">
          Left Arm (independent)
        </div>

        {LEFT_ARM_SLIDERS.map(([key, label, min, max]) => (
          <SliderRow
            key={key}
            sliderKey={key}
            label={label}
            min={min}
            max={max}
            value={activeAngles[key]}
            onChange={handleChange}
            highlighted={highlightRobot === activeTab && highlightKeys.includes(key)}
            registerRef={registerSliderRef}
          />
        ))}
      </div>
    </div>
  );
};
