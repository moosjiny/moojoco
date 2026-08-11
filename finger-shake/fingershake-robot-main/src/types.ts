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
  // Independent per-finger curl, 0 (open) to 1 (closed). Order matches
  // RobotBuilder's fingerConfigs / rightFingers array: thumb, index, middle, ring, pinky.
  thumbCurl: number;
  indexCurl: number;
  middleCurl: number;
  ringCurl: number;
  pinkyCurl: number;
  torsoPitch: number;
  torsoYaw: number;
  footPitch: number; // ankle dorsiflexion(+)/plantarflexion(-), degrees, applied to both feet
  hipFlexion: number; // degrees, applied symmetrically to both hips
  kneeFlexion: number; // degrees, applied symmetrically to both knees
  // Left arm — independent from the right arm sliders above (no longer mirrored).
  // Left hand/wrist geometry doesn't exist yet (leftHand is a plain box), so there
  // is no left-side wrist/finger control until that geometry is built.
  leftShoulderPitch: number;
  leftShoulderYaw: number;
  leftShoulderRoll: number;
  leftElbowFlexion: number;
}

export const DEFAULT_JOINT_ANGLES: JointAngles = {
  shoulderPitch: -64,
  shoulderYaw: -20,
  shoulderRoll: -12,
  elbowFlexion: 50,
  wristPitch: 10,
  wristRoll: 0,
  wristYaw: 0,
  thumbCurl: 0.8,
  indexCurl: 0.8,
  middleCurl: 0.8,
  ringCurl: 0.8,
  pinkyCurl: 0.8,
  torsoPitch: 0,
  torsoYaw: -10,
  footPitch: 0,
  hipFlexion: 0,
  kneeFlexion: 0,
  leftShoulderPitch: -64,
  leftShoulderYaw: 20,
  leftShoulderRoll: 12,
  leftElbowFlexion: 50,
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
  // Static stability (Stage 1 of the contact-dynamics plan): whether each
  // robot's mass-weighted center of mass projects inside its support
  // polygon (the convex hull of both feet's ground contact points), and by
  // how much (positive = inside, margin to nearest edge; negative = outside).
  comStabilityAlpha?: 'STABLE' | 'UNSTABLE';
  comStabilityBeta?: 'STABLE' | 'UNSTABLE';
  comMarginAlphaMm?: number;
  comMarginBetaMm?: number;
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

