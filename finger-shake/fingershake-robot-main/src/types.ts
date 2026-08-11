export type HandshakeMode = 'standard' | 'energetic' | 'diplomatic' | 'impedance' | 'rl_agent' | 'manual' | 'highfive';

export type RobotTheme = 'cyber' | 'stealth' | 'titanium' | 'industrial';

export type CameraPreset = 'default' | 'hands' | 'side' | 'top' | 'robotA' | 'robotB' | 'closeup';

export interface JointAngles {
  shoulderPitch: number; // degrees
  shoulderYaw: number;
  shoulderRoll: number;
  elbowFlexion: number;
  wristPitch: number;
  wristRoll: number;
  wristYaw: number;
  fingerGrip: number; // 0 to 1
  torsoPitch: number;
  torsoYaw: number;
  footPitch: number; // ankle dorsiflexion(+)/plantarflexion(-), degrees, applied to both feet
}

export const DEFAULT_JOINT_ANGLES: JointAngles = {
  shoulderPitch: -64,
  shoulderYaw: -20,
  shoulderRoll: -12,
  elbowFlexion: 50,
  wristPitch: 10,
  wristRoll: 0,
  wristYaw: 0,
  fingerGrip: 0.8,
  torsoPitch: 0,
  torsoYaw: -10,
  footPitch: 0,
};

export interface TelemetryData {
  contactDistance: number; // mm
  gripForce: number; // N
  rightHandX: number;
  rightHandY: number;
  rightHandZ: number;
  jointTorquePeak: number; // Nm
  syncRatio: number; // %
  fps: number;
  stiffnessKx?: number; // N/m (Impedance Control)
  dampingDx?: number; // Ns/m
  complianceOffset?: number; // mm
  rlEpisode?: number;
  rlReward?: number;
  rlPolicyStatus?: string;
  rlLoss?: number;
  palmAlignmentError?: number; // mm
}

export interface RobotConfig {
  id: 'alpha' | 'beta';
  name: string;
  color: number;
  accentColor: number;
  eyeColor: number;
  positionX: number;
  positionZ: number;
  rotationY: number;
}

