import React, { useState } from 'react';
import { RobotScene } from './components/RobotScene';
import { Header } from './components/Header';
import { SimulationHUD } from './components/SimulationHUD';
import { TelemetryPanel } from './components/TelemetryPanel';
import { KinematicControls } from './components/KinematicControls';
import { CameraPreset, DEFAULT_JOINT_ANGLES, HandshakeMode, JointAngles, RobotTheme, TelemetryData } from './types';

const MANUAL_POSE_STORAGE_KEY = 'fingershake_manual_pose_v1';

function loadStoredManualPose(): { alpha: JointAngles; beta: JointAngles } | null {
  try {
    const raw = localStorage.getItem(MANUAL_POSE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Merge over the current defaults so poses saved before a new joint was
    // added (e.g. wristYaw) don't leave that field undefined -> NaN rotations.
    if (parsed && parsed.alpha && parsed.beta) {
      return {
        alpha: { ...DEFAULT_JOINT_ANGLES, ...parsed.alpha },
        beta: { ...DEFAULT_JOINT_ANGLES, ...parsed.beta },
      };
    }
  } catch {
    // ignore malformed/blocked storage
  }
  return null;
}

export default function App() {
  const [mode, setMode] = useState<HandshakeMode>('standard');
  const [theme, setTheme] = useState<RobotTheme>('titanium');
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1.0);
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>('default');

  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [showAxes, setShowAxes] = useState<boolean>(false);
  const [showContactVector, setShowContactVector] = useState<boolean>(true);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Initial pose for manual joint slider manipulation — restored from
  // localStorage if a pose was previously saved, otherwise the built-in default.
  const [manualAnglesAlpha, setManualAnglesAlpha] = useState<JointAngles>(
    () => loadStoredManualPose()?.alpha ?? DEFAULT_JOINT_ANGLES
  );

  const [manualAnglesBeta, setManualAnglesBeta] = useState<JointAngles>(
    () => loadStoredManualPose()?.beta ?? DEFAULT_JOINT_ANGLES
  );

  // Ground Lock — approximates a physics engine's foot-contact solve by vertically
  // correcting the root height so the feet stay planted on the floor as hip/knee/
  // ankle sliders change (manual mode only; see RobotScene.tsx applyGroundLock).
  const [groundLock, setGroundLock] = useState<boolean>(false);

  // Balance overlay — Stage 1 of the contact-dynamics plan (see thesis
  // 2026-08-11-moojoco-contact-dynamics-plan): shows the mass-weighted center
  // of mass and support polygon, and whether the pose is statically stable.
  const [showComOverlay, setShowComOverlay] = useState<boolean>(false);

  const [telemetry, setTelemetry] = useState<TelemetryData>({
    contactDistance: 12,
    gripForce: 65,
    rightHandX: 0,
    rightHandY: 1.25,
    rightHandZ: 0,
    jointTorquePeak: 45,
    syncRatio: 99.2,
    fps: 60,
  });

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-slate-950 select-none font-sans">
      {/* Top Navigation & Settings Bar */}
      <Header
        theme={theme}
        setTheme={setTheme}
        cameraPreset={cameraPreset}
        setCameraPreset={setCameraPreset}
        isMuted={isMuted}
        setIsMuted={setIsMuted}
        showGrid={showGrid}
        setShowGrid={setShowGrid}
        showAxes={showAxes}
        setShowAxes={setShowAxes}
        showContactVector={showContactVector}
        setShowContactVector={setShowContactVector}
      />

      {/* Main 3D Canvas Scene */}
      <main className="w-full h-full">
        <RobotScene
          mode={mode}
          theme={theme}
          isPlaying={isPlaying}
          speed={speed}
          cameraPreset={cameraPreset}
          showGrid={showGrid}
          showAxes={showAxes}
          showContactVector={showContactVector}
          showJointAngles={mode === 'manual'}
          manualAnglesAlpha={manualAnglesAlpha}
          manualAnglesBeta={manualAnglesBeta}
          groundLock={groundLock}
          showComOverlay={showComOverlay}
          onTelemetryUpdate={setTelemetry}
        />
      </main>

      {/* Telemetry Stats Panel Overlay */}
      <TelemetryPanel data={telemetry} />

      {/* Manual Kinematic Joint Controls (When in Manual Mode) */}
      {mode === 'manual' && (
        <KinematicControls
          anglesAlpha={manualAnglesAlpha}
          setAnglesAlpha={setManualAnglesAlpha}
          anglesBeta={manualAnglesBeta}
          setAnglesBeta={setManualAnglesBeta}
          groundLock={groundLock}
          setGroundLock={setGroundLock}
          showComOverlay={showComOverlay}
          setShowComOverlay={setShowComOverlay}
        />
      )}

      {/* Bottom Simulation HUD Controls */}
      <SimulationHUD
        mode={mode}
        setMode={setMode}
        isPlaying={isPlaying}
        setIsPlaying={setIsPlaying}
        speed={speed}
        setSpeed={setSpeed}
      />
    </div>
  );
}
