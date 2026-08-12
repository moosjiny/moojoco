import * as THREE from 'three';
import { RobotTheme } from '../types';

export interface RobotJointRefs {
  root: THREE.Group;
  torso: THREE.Group;
  head: THREE.Group;
  leftShoulder: THREE.Group;
  leftElbow: THREE.Group;
  rightShoulder: THREE.Group;
  rightElbow: THREE.Group;
  rightWrist: THREE.Group;
  rightFingers: THREE.Group[];
  leftHip: THREE.Group;
  leftKnee: THREE.Group;
  leftAnkle: THREE.Group;
  rightHip: THREE.Group;
  rightKnee: THREE.Group;
  rightAnkle: THREE.Group;
  handTargetPos: THREE.Vector3;
  rightHandPalmMesh: THREE.Mesh;
  chestLight: THREE.PointLight;
  visorMesh: THREE.Mesh;
  armorMaterials: THREE.MeshStandardMaterial[];
}

export function getThemeColors(theme: RobotTheme, isAlpha: boolean) {
  switch (theme) {
    case 'cyber':
      return {
        main: isAlpha ? 0x1e293b : 0x0f172a, // Metallic slate navy
        armor: isAlpha ? 0x2563eb : 0xd97706, // Neon Blue vs Neon Gold/Amber
        joint: 0x334155, // Dark titanium
        visor: isAlpha ? 0x38bdf8 : 0xf59e0b, // Cyan vs Amber
        chest: isAlpha ? 0x60a5fa : 0xfbbf24,
      };
    case 'stealth':
      return {
        main: 0x111827, // Dark matte obsidian
        armor: isAlpha ? 0x374151 : 0x4b5563,
        joint: 0x1f2937,
        visor: isAlpha ? 0xef4444 : 0x10b981, // Crimson vs Emerald
        chest: isAlpha ? 0xf87171 : 0x34d399,
      };
    case 'titanium':
      return {
        main: 0xe2e8f0, // Brushed platinum
        armor: isAlpha ? 0x94a3b8 : 0xcbd5e1,
        joint: 0x475569,
        visor: isAlpha ? 0x06b6d4 : 0x8b5cf6, // Cyan vs Purple
        chest: isAlpha ? 0x22d3ee : 0xa78bfa,
      };
    case 'industrial':
      return {
        main: isAlpha ? 0xd97706 : 0xca8a04, // Safety Yellow / Orange
        armor: 0x27272a, // Heavy steel
        joint: 0x18181b,
        visor: 0xfacc15,
        chest: 0xfde047,
      };
  }
}

export function buildBipedalRobot(
  id: 'alpha' | 'beta',
  theme: RobotTheme = 'cyber'
): RobotJointRefs {
  const isAlpha = id === 'alpha';
  const colors = getThemeColors(theme, isAlpha);

  const root = new THREE.Group();
  root.name = `robot_${id}`;

  // Materials
  const mainArmorMat = new THREE.MeshStandardMaterial({
    color: colors.main,
    metalness: 0.7,
    roughness: 0.3,
  });

  const accentArmorMat = new THREE.MeshStandardMaterial({
    color: colors.armor,
    metalness: 0.8,
    roughness: 0.2,
  });

  const jointMat = new THREE.MeshStandardMaterial({
    color: colors.joint,
    metalness: 0.9,
    roughness: 0.4,
  });

  const visorMat = new THREE.MeshBasicMaterial({
    color: colors.visor,
  });

  const chestLightMat = new THREE.MeshBasicMaterial({
    color: colors.chest,
  });

  const armorMaterials = [mainArmorMat, accentArmorMat];

  // 1. Pelvis / Hips Group (Origin ~ Y = 1.05)
  const pelvisGroup = new THREE.Group();
  pelvisGroup.position.set(0, 1.05, 0);
  root.add(pelvisGroup);

  const pelvisMesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.38, 0.2, 0.28),
    accentArmorMat
  );
  pelvisMesh.castShadow = true;
  pelvisGroup.add(pelvisMesh);

  // 2. Spine & Torso (Above Pelvis)
  const torsoGroup = new THREE.Group();
  torsoGroup.position.set(0, 0.15, 0);
  pelvisGroup.add(torsoGroup);

  // Chest Armor (Slightly tapered)
  const chestMesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.52, 0.55, 0.36),
    mainArmorMat
  );
  chestMesh.position.y = 0.32;
  chestMesh.castShadow = true;
  torsoGroup.add(chestMesh);

  // Chest Accent Plates
  const chestPlateLeft = new THREE.Mesh(
    new THREE.BoxGeometry(0.2, 0.35, 0.04),
    accentArmorMat
  );
  chestPlateLeft.position.set(-0.13, 0.35, 0.19);
  chestPlateLeft.castShadow = true;
  torsoGroup.add(chestPlateLeft);

  const chestPlateRight = new THREE.Mesh(
    new THREE.BoxGeometry(0.2, 0.35, 0.04),
    accentArmorMat
  );
  chestPlateRight.position.set(0.13, 0.35, 0.19);
  chestPlateRight.castShadow = true;
  torsoGroup.add(chestPlateRight);

  // Chest Reactor Core (Glowing Light)
  const reactorMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.08, 0.08, 0.06, 16),
    chestLightMat
  );
  reactorMesh.rotation.x = Math.PI / 2;
  reactorMesh.position.set(0, 0.35, 0.19);
  torsoGroup.add(reactorMesh);

  const chestLight = new THREE.PointLight(colors.chest, 1.2, 2.5);
  chestLight.position.set(0, 0.35, 0.25);
  torsoGroup.add(chestLight);

  // 3. Head & Neck
  const neckGroup = new THREE.Group();
  neckGroup.position.set(0, 0.62, 0);
  torsoGroup.add(neckGroup);

  const neckMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(0.07, 0.09, 0.1, 12),
    jointMat
  );
  neckMesh.position.y = 0.05;
  neckGroup.add(neckMesh);

  const headGroup = new THREE.Group();
  headGroup.position.set(0, 0.12, 0);
  neckGroup.add(headGroup);

  const headMesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.28, 0.26, 0.28),
    mainArmorMat
  );
  headMesh.position.y = 0.13;
  headMesh.castShadow = true;
  headGroup.add(headMesh);

  // Head Ears / Sensors
  const leftEar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.02, 0.05, 0.12, 8),
    accentArmorMat
  );
  leftEar.rotation.z = Math.PI / 2;
  leftEar.position.set(-0.16, 0.15, 0);
  headGroup.add(leftEar);

  const rightEar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.02, 0.05, 0.12, 8),
    accentArmorMat
  );
  rightEar.rotation.z = -Math.PI / 2;
  rightEar.position.set(0.16, 0.15, 0);
  headGroup.add(rightEar);

  // Visor (Eye Glow)
  const visorMesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.22, 0.07, 0.06),
    visorMat
  );
  visorMesh.position.set(0, 0.15, 0.13);
  headGroup.add(visorMesh);

  // 4. Legs (Left & Right)
  function createLeg(xSide: number) {
    const hipGroup = new THREE.Group();
    hipGroup.position.set(xSide * 0.16, -0.05, 0);

    const hipBall = new THREE.Mesh(
      new THREE.SphereGeometry(0.08, 12, 12),
      jointMat
    );
    hipGroup.add(hipBall);

    const thighMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.09, 0.07, 0.45, 12),
      mainArmorMat
    );
    thighMesh.position.y = -0.225;
    thighMesh.castShadow = true;
    hipGroup.add(thighMesh);

    const kneeGroup = new THREE.Group();
    kneeGroup.position.set(0, -0.45, 0);
    hipGroup.add(kneeGroup);

    const kneeJoint = new THREE.Mesh(
      new THREE.SphereGeometry(0.075, 12, 12),
      jointMat
    );
    kneeGroup.add(kneeJoint);

    const calfMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.07, 0.06, 0.45, 12),
      accentArmorMat
    );
    calfMesh.position.y = -0.225;
    calfMesh.castShadow = true;
    kneeGroup.add(calfMesh);

    // Ankle Joint (allows independent foot pitch rotation)
    const ankleGroup = new THREE.Group();
    ankleGroup.position.set(0, -0.45, 0);
    kneeGroup.add(ankleGroup);

    const ankleJoint = new THREE.Mesh(
      new THREE.SphereGeometry(0.045, 10, 10),
      jointMat
    );
    ankleGroup.add(ankleJoint);

    const footMesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.14, 0.09, 0.28),
      jointMat
    );
    footMesh.position.set(0, -0.04, 0.05);
    footMesh.castShadow = true;
    ankleGroup.add(footMesh);

    return { hipGroup, kneeGroup, ankleGroup };
  }

  const leftLeg = createLeg(-1);
  const rightLeg = createLeg(1);
  pelvisGroup.add(leftLeg.hipGroup);
  pelvisGroup.add(rightLeg.hipGroup);

  // 5. Left Arm (Standard rest posture)
  // Anatomical mirror: the left arm reuses the exact same local geometry and
  // rotation formulas as the right arm (see manualAnglesAlpha.leftShoulder*
  // application in RobotScene.tsx — same sign, no per-axis flipping there).
  // A true mirror image only comes for free if the whole subtree sits inside
  // a negative-X-scale wrapper; without it, yaw/roll rotations diverge from
  // the right arm's as the angle grows even though pitch/elbow look fine
  // near 0 (see thesis 2026-08-12-moojoco-left-arm-elbow-asymmetry-bug).
  const leftArmMirror = new THREE.Group();
  leftArmMirror.position.set(-0.32, 0.5, 0);
  leftArmMirror.scale.set(-1, 1, 1);
  torsoGroup.add(leftArmMirror);

  const leftShoulder = new THREE.Group();
  leftArmMirror.add(leftShoulder);

  const leftShoulderCap = new THREE.Mesh(
    new THREE.SphereGeometry(0.09, 12, 12),
    accentArmorMat
  );
  leftShoulder.add(leftShoulderCap);

  const leftUpperArm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.065, 0.055, 0.38, 12),
    mainArmorMat
  );
  leftUpperArm.position.y = -0.19;
  leftUpperArm.castShadow = true;
  leftShoulder.add(leftUpperArm);

  const leftElbow = new THREE.Group();
  leftElbow.position.set(0, -0.38, 0);
  leftShoulder.add(leftElbow);

  const leftElbowJoint = new THREE.Mesh(
    new THREE.SphereGeometry(0.06, 12, 12),
    jointMat
  );
  leftElbow.add(leftElbowJoint);

  const leftForearm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.055, 0.045, 0.36, 12),
    accentArmorMat
  );
  leftForearm.position.y = -0.18;
  leftForearm.castShadow = true;
  leftElbow.add(leftForearm);

  const leftHand = new THREE.Mesh(
    new THREE.BoxGeometry(0.08, 0.1, 0.05),
    jointMat
  );
  leftHand.position.set(0, -0.4, 0);
  leftElbow.add(leftHand);

  // 6. Right Arm (Fully Articulated Dexterous Handshake Arm - MuJoCo DexHand Architecture)
  const rightShoulder = new THREE.Group();
  rightShoulder.position.set(0.32, 0.5, 0);
  torsoGroup.add(rightShoulder);

  const rightShoulderCap = new THREE.Mesh(
    new THREE.SphereGeometry(0.09, 12, 12),
    accentArmorMat
  );
  rightShoulder.add(rightShoulderCap);

  const rightUpperArm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.065, 0.055, 0.38, 12),
    mainArmorMat
  );
  rightUpperArm.position.y = -0.19;
  rightUpperArm.castShadow = true;
  rightShoulder.add(rightUpperArm);

  const rightElbow = new THREE.Group();
  rightElbow.position.set(0, -0.38, 0);
  rightShoulder.add(rightElbow);

  const rightElbowJoint = new THREE.Mesh(
    new THREE.SphereGeometry(0.06, 12, 12),
    jointMat
  );
  rightElbow.add(rightElbowJoint);

  const rightForearm = new THREE.Mesh(
    new THREE.CylinderGeometry(0.055, 0.045, 0.36, 12),
    accentArmorMat
  );
  rightForearm.position.y = -0.18;
  rightForearm.castShadow = true;
  rightElbow.add(rightForearm);

  // Right Wrist Assembly
  const rightWrist = new THREE.Group();
  rightWrist.position.set(0, -0.36, 0);
  rightElbow.add(rightWrist);

  // High-precision Chrome & Carbon materials for DexHand
  const chromeMat = new THREE.MeshStandardMaterial({
    color: 0xdedede,
    metalness: 0.95,
    roughness: 0.15,
  });

  const carbonMat = new THREE.MeshStandardMaterial({
    color: 0x1f242d,
    metalness: 0.6,
    roughness: 0.4,
  });

  const sensorPadMat = new THREE.MeshStandardMaterial({
    color: colors.visor,
    emissive: colors.visor,
    emissiveIntensity: 0.45,
    roughness: 0.2,
  });

  // Wrist FT-Sensor Ring (Force-Torque Sensor Array)
  const ftSensorBase = new THREE.Mesh(
    new THREE.CylinderGeometry(0.046, 0.046, 0.025, 16),
    jointMat
  );
  ftSensorBase.rotation.x = Math.PI / 2;
  rightWrist.add(ftSensorBase);

  const ftSensorRing = new THREE.Mesh(
    new THREE.CylinderGeometry(0.048, 0.048, 0.008, 16),
    new THREE.MeshBasicMaterial({ color: colors.visor })
  );
  ftSensorRing.rotation.x = Math.PI / 2;
  rightWrist.add(ftSensorRing);

  // Hydraulic / Tendon Micro-Actuator Struts
  const actuatorLeft = new THREE.Mesh(
    new THREE.CylinderGeometry(0.005, 0.005, 0.05, 8),
    chromeMat
  );
  actuatorLeft.position.set(-0.022, -0.025, 0.015);
  rightWrist.add(actuatorLeft);

  const actuatorRight = new THREE.Mesh(
    new THREE.CylinderGeometry(0.005, 0.005, 0.05, 8),
    chromeMat
  );
  actuatorRight.position.set(0.022, -0.025, 0.015);
  rightWrist.add(actuatorRight);

  // Ergonomic Palm Chassis
  const rightHandPalmMesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.082, 0.112, 0.038),
    accentArmorMat
  );
  rightHandPalmMesh.position.set(0, -0.062, 0);
  rightHandPalmMesh.castShadow = true;
  rightWrist.add(rightHandPalmMesh);

  // Dorsal Back Titanium Armor Plate
  const backPlate = new THREE.Mesh(
    new THREE.BoxGeometry(0.076, 0.088, 0.008),
    mainArmorMat
  );
  backPlate.position.set(0, -0.058, -0.021);
  backPlate.castShadow = true;
  rightWrist.add(backPlate);

  // Thenar (Thumb-side) Metacarpal Cushion Pad
  const thenarPad = new THREE.Mesh(
    new THREE.BoxGeometry(0.032, 0.05, 0.012),
    carbonMat
  );
  thenarPad.position.set(-0.022, -0.055, 0.02);
  rightWrist.add(thenarPad);

  // Hypothenar (Pinky-side) Metacarpal Cushion Pad
  const hypothenarPad = new THREE.Mesh(
    new THREE.BoxGeometry(0.028, 0.05, 0.012),
    carbonMat
  );
  hypothenarPad.position.set(0.024, -0.055, 0.02);
  rightWrist.add(hypothenarPad);

  // Palm Center Tactile Sensor Micro-Grid Array
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 2; col++) {
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.0035, 8, 8),
        sensorPadMat
      );
      dot.position.set(-0.012 + col * 0.024, -0.045 - row * 0.018, 0.02);
      rightWrist.add(dot);
    }
  }

  // Multi-segmented 5 Dexterous Digits (MuJoCo DexHand Config)
  const rightFingers: THREE.Group[] = [];

  const fingerConfigs = [
    {
      name: 'thumb',
      x: -0.046,
      y: -0.028,
      z: 0.018,
      rotZ: Math.PI / 3.4,
      rotY: Math.PI / 4.2,
      rotX: -0.22,
      lengths: [0.03, 0.026, 0.02],
      widths: [0.018, 0.016, 0.014],
    },
    {
      name: 'index',
      x: -0.031,
      y: -0.118,
      z: 0.006,
      rotZ: 0.04,
      rotY: 0,
      rotX: 0,
      lengths: [0.038, 0.028, 0.02],
      widths: [0.017, 0.015, 0.013],
    },
    {
      name: 'middle',
      x: -0.01,
      y: -0.122,
      z: 0.006,
      rotZ: 0,
      rotY: 0,
      rotX: 0,
      lengths: [0.042, 0.031, 0.021],
      widths: [0.017, 0.015, 0.013],
    },
    {
      name: 'ring',
      x: 0.011,
      y: -0.118,
      z: 0.006,
      rotZ: -0.03,
      rotY: 0,
      rotX: 0,
      lengths: [0.038, 0.028, 0.02],
      widths: [0.016, 0.014, 0.012],
    },
    {
      name: 'pinky',
      x: 0.031,
      y: -0.11,
      z: 0.006,
      rotZ: -0.08,
      rotY: 0,
      rotX: 0,
      lengths: [0.032, 0.024, 0.018],
      widths: [0.015, 0.013, 0.011],
    },
  ];

  fingerConfigs.forEach((cfg) => {
    // 1. MCP Base Group (Metacarpophalangeal Joint)
    const fBase = new THREE.Group();
    fBase.name = `${cfg.name}_mcp_base`;
    fBase.position.set(cfg.x, cfg.y, cfg.z);
    fBase.rotation.set(cfg.rotX, cfg.rotY, cfg.rotZ);
    rightWrist.add(fBase);

    // MCP Knuckle Pin Cylinder
    const mcpPin = new THREE.Mesh(
      new THREE.CylinderGeometry(0.009, 0.009, cfg.widths[0] + 0.004, 10),
      chromeMat
    );
    mcpPin.rotation.z = Math.PI / 2;
    fBase.add(mcpPin);

    // Proximal Phalanx
    const proxLength = cfg.lengths[0];
    const proxMesh = new THREE.Mesh(
      new THREE.BoxGeometry(cfg.widths[0], proxLength, cfg.widths[0]),
      jointMat
    );
    proxMesh.position.y = -proxLength / 2;
    proxMesh.castShadow = true;
    fBase.add(proxMesh);

    // Dorsal Tendon Cable Along Proximal Phalanx
    const tendon = new THREE.Mesh(
      new THREE.CylinderGeometry(0.0015, 0.0015, proxLength * 0.9, 8),
      chromeMat
    );
    tendon.position.set(0, -proxLength / 2, -cfg.widths[0] / 2 - 0.002);
    fBase.add(tendon);

    // 2. PIP Joint Group (Proximal Interphalangeal)
    const pipGroup = new THREE.Group();
    pipGroup.name = 'pip_joint';
    pipGroup.position.set(0, -proxLength, 0);
    fBase.add(pipGroup);

    // PIP Pin Cylinder
    const pipPin = new THREE.Mesh(
      new THREE.CylinderGeometry(0.0075, 0.0075, cfg.widths[1] + 0.003, 10),
      chromeMat
    );
    pipPin.rotation.z = Math.PI / 2;
    pipGroup.add(pipPin);

    // Middle Phalanx
    const midLength = cfg.lengths[1];
    const midMesh = new THREE.Mesh(
      new THREE.BoxGeometry(cfg.widths[1], midLength, cfg.widths[1]),
      mainArmorMat
    );
    midMesh.position.y = -midLength / 2;
    midMesh.castShadow = true;
    pipGroup.add(midMesh);

    // 3. DIP Joint Group (Distal Interphalangeal)
    const dipGroup = new THREE.Group();
    dipGroup.name = 'dip_joint';
    dipGroup.position.set(0, -midLength, 0);
    pipGroup.add(dipGroup);

    // DIP Pin Cylinder
    const dipPin = new THREE.Mesh(
      new THREE.CylinderGeometry(0.006, 0.006, cfg.widths[2] + 0.002, 10),
      chromeMat
    );
    dipPin.rotation.z = Math.PI / 2;
    dipGroup.add(dipPin);

    // Distal Phalanx (Fingertip)
    const distLength = cfg.lengths[2];
    const distMesh = new THREE.Mesh(
      new THREE.BoxGeometry(cfg.widths[2], distLength, cfg.widths[2]),
      accentArmorMat
    );
    distMesh.position.y = -distLength / 2;
    distMesh.castShadow = true;
    dipGroup.add(distMesh);

    // Tactile Pressure Sensor Pad at Fingertip
    const tipPad = new THREE.Mesh(
      new THREE.BoxGeometry(cfg.widths[2] * 0.85, distLength * 0.6, 0.005),
      sensorPadMat
    );
    tipPad.position.set(0, -distLength * 0.6, cfg.widths[2] / 2 + 0.001);
    dipGroup.add(tipPad);

    rightFingers.push(fBase);
  });

  const handTargetPos = new THREE.Vector3();

  return {
    root,
    torso: torsoGroup,
    head: headGroup,
    leftShoulder,
    leftElbow,
    rightShoulder,
    rightElbow,
    rightWrist,
    rightFingers,
    leftHip: leftLeg.hipGroup,
    leftKnee: leftLeg.kneeGroup,
    leftAnkle: leftLeg.ankleGroup,
    rightHip: rightLeg.hipGroup,
    rightKnee: rightLeg.kneeGroup,
    rightAnkle: rightLeg.ankleGroup,
    handTargetPos,
    rightHandPalmMesh,
    chestLight,
    visorMesh,
    armorMaterials,
  };
}
