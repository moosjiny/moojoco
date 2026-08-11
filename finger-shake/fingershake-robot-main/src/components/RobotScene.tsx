import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { buildBipedalRobot, RobotJointRefs, getThemeColors } from './RobotBuilder';
import { CameraPreset, HandshakeMode, JointAngles, RobotTheme, TelemetryData } from '../types';
import { soundEngine } from '../utils/audio';

interface RobotSceneProps {
  mode: HandshakeMode;
  theme: RobotTheme;
  isPlaying: boolean;
  speed: number;
  cameraPreset: CameraPreset;
  showGrid: boolean;
  showAxes: boolean;
  showContactVector: boolean;
  showJointAngles: boolean;
  manualAnglesAlpha: JointAngles;
  manualAnglesBeta: JointAngles;
  onTelemetryUpdate: (data: TelemetryData) => void;
}

export const RobotScene: React.FC<RobotSceneProps> = ({
  mode,
  theme,
  isPlaying,
  speed,
  cameraPreset,
  showGrid,
  showAxes,
  showContactVector,
  showJointAngles,
  manualAnglesAlpha,
  manualAnglesBeta,
  onTelemetryUpdate,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

  const robotAlphaRef = useRef<RobotJointRefs | null>(null);
  const robotBetaRef = useRef<RobotJointRefs | null>(null);

  const contactVectorRef = useRef<THREE.ArrowHelper | null>(null);
  const axesHelpersRef = useRef<THREE.Group | null>(null);
  const particlesRef = useRef<THREE.Points | null>(null);
  const particleGeoRef = useRef<THREE.BufferGeometry | null>(null);

  const timeRef = useRef<number>(0);
  const frameIdRef = useRef<number>(0);
  const lastClaspSoundRef = useRef<number>(0);
  const rlEpisodeRef = useRef<number>(1);
  const rlLastPhaseRef = useRef<string>('seeking');

  // Initialize Three.js Scene
  useEffect(() => {
    if (!containerRef.current) return;

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0b); // Elegant dark obsidian
    scene.fog = new THREE.FogExp2(0x0a0a0b, 0.08);
    sceneRef.current = scene;

    // 2. Camera setup
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 1.8, 3.8);
    cameraRef.current = camera;

    // 3. Renderer setup
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 + 0.02; // Prevents camera going under floor
    controls.minDistance = 0.8;
    controls.maxDistance = 12;
    controls.target.set(0, 1.25, 0); // Center at handshake position
    controls.update();
    controlsRef.current = controls;

    // 5. Lighting Setup
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const mainSpot = new THREE.SpotLight(0xffffff, 2.5);
    mainSpot.position.set(3, 6, 4);
    mainSpot.angle = Math.PI / 4;
    mainSpot.penumbra = 0.5;
    mainSpot.castShadow = true;
    mainSpot.shadow.mapSize.width = 1024;
    mainSpot.shadow.mapSize.height = 1024;
    mainSpot.shadow.bias = -0.0001;
    scene.add(mainSpot);

    const rimLight1 = new THREE.DirectionalLight(0x38bdf8, 1.2); // Cyan rim light
    rimLight1.position.set(-5, 4, -4);
    scene.add(rimLight1);

    const rimLight2 = new THREE.DirectionalLight(0xf43f5e, 0.8); // Coral rim light
    rimLight2.position.set(5, 3, -4);
    scene.add(rimLight2);

    // 6. Floor Grid & Shadow Plane
    const floorGeo = new THREE.PlaneGeometry(20, 20);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0f0f10,
      roughness: 0.3,
      metalness: 0.7,
    });
    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.receiveShadow = true;
    scene.add(floorMesh);

    const grid = new THREE.GridHelper(20, 40, 0x3b82f6, 0x222226);
    grid.position.y = 0.001;
    grid.name = 'grid_helper';
    scene.add(grid);

    // 7. Spark Particle System
    const particleCount = 60;
    const pPositions = new Float32Array(particleCount * 3);
    const pVelocities: THREE.Vector3[] = [];

    for (let i = 0; i < particleCount; i++) {
      pPositions[i * 3] = 0;
      pPositions[i * 3 + 1] = 1.25;
      pPositions[i * 3 + 2] = 0;
      pVelocities.push(
        new THREE.Vector3(
          (Math.random() - 0.5) * 0.02,
          Math.random() * 0.03,
          (Math.random() - 0.5) * 0.02
        )
      );
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    particleGeoRef.current = pGeo;

    const pMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.035,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
    });

    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);
    particlesRef.current = particles;

    // 8. Contact Vector Arrow Helper
    const dir = new THREE.Vector3(0, -1, 0);
    const origin = new THREE.Vector3(0, 1.25, 0);
    const arrow = new THREE.ArrowHelper(dir, origin, 0.25, 0xf59e0b, 0.08, 0.04);
    arrow.visible = showContactVector;
    scene.add(arrow);
    contactVectorRef.current = arrow;

    // 9. Joint Axes Group
    const axesGroup = new THREE.Group();
    const axisA = new THREE.AxesHelper(0.2);
    axisA.name = 'axis_a';
    const axisB = new THREE.AxesHelper(0.2);
    axisB.name = 'axis_b';
    axesGroup.add(axisA);
    axesGroup.add(axisB);
    axesGroup.visible = showAxes;
    scene.add(axesGroup);
    axesHelpersRef.current = axesGroup;

    // 10. Instantiate Robots Alpha and Beta
    const robotAlpha = buildBipedalRobot('alpha', theme);
    const robotBeta = buildBipedalRobot('beta', theme);

    // Initial positioning facing each other at handshake distance
    // Robot Alpha on Left (-X), Robot Beta on Right (+X)
    robotAlpha.root.position.set(-0.54, 0, 0.08);
    robotAlpha.root.rotation.y = Math.PI / 2 - 0.16;

    robotBeta.root.position.set(0.54, 0, -0.08);
    robotBeta.root.rotation.y = -Math.PI / 2 - 0.16;

    scene.add(robotAlpha.root);
    scene.add(robotBeta.root);

    robotAlphaRef.current = robotAlpha;
    robotBetaRef.current = robotBeta;

    // Handle Resize
    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(containerRef.current);

    return () => {
      if (frameIdRef.current) cancelAnimationFrame(frameIdRef.current);
      resizeObserver.disconnect();
      if (rendererRef.current && rendererRef.current.domElement) {
        rendererRef.current.domElement.remove();
      }
    };
  }, []);

  // Update theme colors when changed
  useEffect(() => {
    if (!robotAlphaRef.current || !robotBetaRef.current) return;
    const colorsAlpha = getThemeColors(theme, true);
    const colorsBeta = getThemeColors(theme, false);

    robotAlphaRef.current.armorMaterials[0].color.setHex(colorsAlpha.main);
    robotAlphaRef.current.armorMaterials[1].color.setHex(colorsAlpha.armor);
    robotAlphaRef.current.chestLight.color.setHex(colorsAlpha.chest);
    robotAlphaRef.current.visorMesh.material = new THREE.MeshBasicMaterial({ color: colorsAlpha.visor });

    robotBetaRef.current.armorMaterials[0].color.setHex(colorsBeta.main);
    robotBetaRef.current.armorMaterials[1].color.setHex(colorsBeta.armor);
    robotBetaRef.current.chestLight.color.setHex(colorsBeta.chest);
    robotBetaRef.current.visorMesh.material = new THREE.MeshBasicMaterial({ color: colorsBeta.visor });
  }, [theme]);

  // Toggle Grid
  useEffect(() => {
    if (!sceneRef.current) return;
    const grid = sceneRef.current.getObjectByName('grid_helper');
    if (grid) grid.visible = showGrid;
  }, [showGrid]);

  // Toggle Axes & Contact Vector
  useEffect(() => {
    if (axesHelpersRef.current) axesHelpersRef.current.visible = showAxes;
    if (contactVectorRef.current) contactVectorRef.current.visible = showContactVector;
  }, [showAxes, showContactVector]);

  // Smooth Camera Preset Transition
  useEffect(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const cam = cameraRef.current;
    const target = controlsRef.current.target;

    switch (cameraPreset) {
      case 'default':
        cam.position.set(0, 1.8, 3.8);
        target.set(0, 1.25, 0);
        break;
      case 'hands':
        cam.position.set(0, 1.35, 1.2);
        target.set(0, 1.22, 0);
        break;
      case 'side':
        cam.position.set(0, 1.4, 4.2);
        cam.position.applyAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 2);
        target.set(0, 1.2, 0);
        break;
      case 'top':
        cam.position.set(0, 4.5, 0.01);
        target.set(0, 1.2, 0);
        break;
      case 'robotA':
        cam.position.set(-1.8, 1.7, 1.8);
        target.set(-0.5, 1.3, 0);
        break;
      case 'robotB':
        cam.position.set(1.8, 1.7, 1.8);
        target.set(0.5, 1.3, 0);
        break;
      case 'closeup':
        // Both robots' upper bodies + hand/finger joints visible together
        cam.position.set(0, 1.55, 2.1);
        target.set(0, 1.24, 0);
        break;
    }
    controlsRef.current.update();
  }, [cameraPreset]);

  // Animation Loop & Physics Simulation
  useEffect(() => {
    let fpsCounter = 0;
    let fpsLastTime = performance.now();
    let currentFps = 60;

    const renderLoop = () => {
      frameIdRef.current = requestAnimationFrame(renderLoop);

      // FPS Calculation
      fpsCounter++;
      const now = performance.now();
      if (now - fpsLastTime >= 1000) {
        currentFps = Math.round((fpsCounter * 1000) / (now - fpsLastTime));
        fpsCounter = 0;
        fpsLastTime = now;
      }

      if (isPlaying) {
        timeRef.current += 0.016 * speed;
      }

      const t = timeRef.current;
      const alpha = robotAlphaRef.current;
      const beta = robotBetaRef.current;

      if (alpha && beta) {
        let shakeOffset = 0;
        let gripValue = 0.8;
        let torque = 42;

        let rlEpisodeVal: number | undefined = undefined;
        let rlRewardVal: number | undefined = undefined;
        let rlStatusVal: string | undefined = undefined;
        let palmErrorVal: number | undefined = undefined;

        if (mode === 'rl_agent') {
          // Reinforcement Learning Auto-Seeking & Palm Contact Policy
          const cycleDuration = 9.0;
          const epCycle = t % cycleDuration;
          const currentEp = Math.floor(t / cycleDuration) + 1;
          rlEpisodeRef.current = currentEp;
          rlEpisodeVal = currentEp;

          // 1. Phase 1: 3D Spatial Trajectory Reaching (0 <= epCycle < 3.5s)
          if (epCycle < 3.5) {
            const progress = epCycle / 3.5;
            const easeP = Math.sin((progress * Math.PI) / 2);
            const noise = Math.sin(t * 18) * 0.02 * (1 - easeP);

            // Reaching from neutral down (-0.3) to extended pitch (-1.12)
            alpha.rightShoulder.rotation.x = THREE.MathUtils.lerp(-0.3, -1.12, easeP) + noise;
            alpha.rightShoulder.rotation.y = THREE.MathUtils.lerp(-0.1, -0.34, easeP);
            alpha.rightElbow.rotation.x = THREE.MathUtils.lerp(0.3, 0.88, easeP);
            alpha.rightWrist.rotation.x = THREE.MathUtils.lerp(0.0, 0.15, easeP);

            beta.rightShoulder.rotation.x = THREE.MathUtils.lerp(-0.3, -1.12, easeP) - noise;
            beta.rightShoulder.rotation.y = THREE.MathUtils.lerp(-0.1, -0.34, easeP);
            beta.rightElbow.rotation.x = THREE.MathUtils.lerp(0.3, 0.88, easeP);
            beta.rightWrist.rotation.x = THREE.MathUtils.lerp(0.0, 0.15, easeP);

            // Open hands during reach
            const applyReachGrip = (robot: RobotJointRefs) => {
              robot.rightFingers.forEach((fGroup) => (fGroup.rotation.x = 0.1));
            };
            applyReachGrip(alpha);
            applyReachGrip(beta);

            rlStatusVal = '1/3 PPO Policy: 3D Palm Coordinates Seeking...';
            rlRewardVal = Math.round(progress * 65);
            palmErrorVal = Math.round((1 - progress) * 160 + 15);
            torque = 45 + Math.round(noise * 100);
            soundEngine.updateServoSound(0.5, speed);
          }
          // 2. Phase 2: Palm Plane Normal Vector Alignment (3.5 <= epCycle < 6.0s)
          else if (epCycle < 6.0) {
            const progress = (epCycle - 3.5) / 2.5;
            const easeP = Math.sin((progress * Math.PI) / 2);

            alpha.rightShoulder.rotation.x = -1.12;
            alpha.rightShoulder.rotation.y = -0.34;
            alpha.rightElbow.rotation.x = 0.88;
            alpha.rightWrist.rotation.x = THREE.MathUtils.lerp(0.15, 0.18, easeP);

            beta.rightShoulder.rotation.x = -1.12;
            beta.rightShoulder.rotation.y = -0.34;
            beta.rightElbow.rotation.x = 0.88;
            beta.rightWrist.rotation.x = THREE.MathUtils.lerp(0.15, 0.18, easeP);

            // Align fingers towards palm enclosure
            const applyAlignGrip = (robot: RobotJointRefs, factor: number) => {
              robot.rightFingers.forEach((fGroup) => {
                fGroup.rotation.x = -factor * 0.4;
              });
            };
            applyAlignGrip(alpha, easeP);
            applyAlignGrip(beta, easeP);

            rlStatusVal = '2/3 Aligning Palm Planes & Surface Angles...';
            rlRewardVal = Math.round(65 + progress * 45);
            palmErrorVal = Math.round((1 - progress) * 15 + 2);
            torque = 35;
            soundEngine.updateServoSound(0.3, speed);
          }
          // 3. Phase 3: Palm Contact Converged & Clasp (6.0 <= epCycle < 9.0s)
          else {
            const handshakeTime = epCycle - 6.0;
            shakeOffset = Math.sin(handshakeTime * 4.5) * 0.06;

            alpha.rightShoulder.rotation.x = -1.12 + shakeOffset;
            alpha.rightElbow.rotation.x = 0.88 - shakeOffset * 0.4;
            beta.rightShoulder.rotation.x = -1.12 + shakeOffset;
            beta.rightElbow.rotation.x = 0.88 - shakeOffset * 0.4;

            // Clasp DexHand digits firmly around aligned palms
            // (rotation.x sign is negated for the curl to wrap toward the palm/partner
            // side of the hand instead of the dorsal/back side — see standard-mode fix below)
            const applyClaspGrip = (robot: RobotJointRefs) => {
              robot.rightFingers.forEach((fGroup, i) => {
                const isThumb = i === 0;
                if (isThumb) {
                  fGroup.rotation.x = -0.72;
                  fGroup.rotation.y = Math.PI / 4.2 - 0.35;
                } else {
                  fGroup.rotation.x = -0.85;
                }
                fGroup.traverse((child) => {
                  if (child.name === 'pip_joint') child.rotation.x = -0.75;
                  if (child.name === 'dip_joint') child.rotation.x = -0.6;
                });
              });
            };
            applyClaspGrip(alpha);
            applyClaspGrip(beta);

            if (performance.now() - lastClaspSoundRef.current > 1200) {
              soundEngine.playClaspChime();
              lastClaspSoundRef.current = performance.now();
            }

            rlStatusVal = '3/3 PALM CONTACT CONVERGED! (+150 Reward)';
            rlRewardVal = 150;
            palmErrorVal = 1; // 1mm precision contact
            torque = 52;
            gripValue = 0.95;
            soundEngine.updateServoSound(0.4, speed);
          }
        } else if (mode === 'manual') {
          // Manual sliders mode
          const degToRad = Math.PI / 180;
          alpha.rightShoulder.rotation.x = manualAnglesAlpha.shoulderPitch * degToRad;
          alpha.rightShoulder.rotation.y = manualAnglesAlpha.shoulderYaw * degToRad;
          alpha.rightShoulder.rotation.z = manualAnglesAlpha.shoulderRoll * degToRad;
          alpha.rightElbow.rotation.x = manualAnglesAlpha.elbowFlexion * degToRad;
          alpha.rightWrist.rotation.x = manualAnglesAlpha.wristPitch * degToRad;
          alpha.rightWrist.rotation.z = manualAnglesAlpha.wristRoll * degToRad;
          alpha.rightWrist.rotation.y = manualAnglesAlpha.wristYaw * degToRad;
          alpha.torso.rotation.y = manualAnglesAlpha.torsoYaw * degToRad;
          alpha.leftAnkle.rotation.x = manualAnglesAlpha.footPitch * degToRad;
          alpha.rightAnkle.rotation.x = manualAnglesAlpha.footPitch * degToRad;
          // Left arm — independent sliders, no longer mirrored from the right arm
          alpha.leftShoulder.rotation.x = manualAnglesAlpha.leftShoulderPitch * degToRad;
          alpha.leftShoulder.rotation.y = manualAnglesAlpha.leftShoulderYaw * degToRad;
          alpha.leftShoulder.rotation.z = manualAnglesAlpha.leftShoulderRoll * degToRad;
          alpha.leftElbow.rotation.x = manualAnglesAlpha.leftElbowFlexion * degToRad;

          beta.rightShoulder.rotation.x = manualAnglesBeta.shoulderPitch * degToRad;
          beta.rightShoulder.rotation.y = manualAnglesBeta.shoulderYaw * degToRad;
          beta.rightShoulder.rotation.z = manualAnglesBeta.shoulderRoll * degToRad;
          beta.rightElbow.rotation.x = manualAnglesBeta.elbowFlexion * degToRad;
          beta.rightWrist.rotation.x = manualAnglesBeta.wristPitch * degToRad;
          beta.rightWrist.rotation.z = manualAnglesBeta.wristRoll * degToRad;
          beta.rightWrist.rotation.y = manualAnglesBeta.wristYaw * degToRad;
          beta.torso.rotation.y = manualAnglesBeta.torsoYaw * degToRad;
          beta.leftAnkle.rotation.x = manualAnglesBeta.footPitch * degToRad;
          beta.rightAnkle.rotation.x = manualAnglesBeta.footPitch * degToRad;
          beta.leftShoulder.rotation.x = manualAnglesBeta.leftShoulderPitch * degToRad;
          beta.leftShoulder.rotation.y = manualAnglesBeta.leftShoulderYaw * degToRad;
          beta.leftShoulder.rotation.z = manualAnglesBeta.leftShoulderRoll * degToRad;
          beta.leftElbow.rotation.x = manualAnglesBeta.leftElbowFlexion * degToRad;

          // Independent finger clasping in Manual mode — each finger gets its own curl
          // value (thumb, index, middle, ring, pinky, matching rightFingers order) instead
          // of a single shared gripFactor. (rotation.x sign negated on the curl term so
          // curling wraps the fingertips toward the palm/partner side, not the dorsal side)
          const applyDexGrip = (robot: RobotJointRefs, curls: number[]) => {
            robot.rightFingers.forEach((fGroup, i) => {
              const isThumb = i === 0;
              const curl = curls[i];
              if (isThumb) {
                fGroup.rotation.x = -0.22 - curl * 0.45;
                fGroup.rotation.y = Math.PI / 4.2 - curl * 0.35;
              } else {
                fGroup.rotation.x = -curl * 0.85;
              }

              fGroup.traverse((child) => {
                if (child.name === 'pip_joint') {
                  child.rotation.x = -curl * 0.75;
                } else if (child.name === 'dip_joint') {
                  child.rotation.x = -curl * 0.6;
                }
              });
            });
          };

          applyDexGrip(alpha, [
            manualAnglesAlpha.thumbCurl,
            manualAnglesAlpha.indexCurl,
            manualAnglesAlpha.middleCurl,
            manualAnglesAlpha.ringCurl,
            manualAnglesAlpha.pinkyCurl,
          ]);
          applyDexGrip(beta, [
            manualAnglesBeta.thumbCurl,
            manualAnglesBeta.indexCurl,
            manualAnglesBeta.middleCurl,
            manualAnglesBeta.ringCurl,
            manualAnglesBeta.pinkyCurl,
          ]);
        } else if (mode === 'highfive') {
          // High-five gesture: Step back, raise hand up, clap, then return
          const cycle = (Math.sin(t * 2.5) + 1) / 2; // 0 to 1
          const isClapping = cycle > 0.85;

          // Arms reach high
          alpha.rightShoulder.rotation.x = THREE.MathUtils.lerp(-1.1, -2.4, cycle);
          alpha.rightShoulder.rotation.y = THREE.MathUtils.lerp(-0.35, -0.1, cycle);
          alpha.rightElbow.rotation.x = THREE.MathUtils.lerp(0.9, 0.3, cycle);

          beta.rightShoulder.rotation.x = THREE.MathUtils.lerp(-1.1, -2.4, cycle);
          beta.rightShoulder.rotation.y = THREE.MathUtils.lerp(-0.35, -0.1, cycle);
          beta.rightElbow.rotation.x = THREE.MathUtils.lerp(0.9, 0.3, cycle);

          // Open flat hand for highfive
          const applyDexGrip = (robot: RobotJointRefs, gripFactor: number) => {
            robot.rightFingers.forEach((fGroup, i) => {
              const isThumb = i === 0;
              if (isThumb) {
                fGroup.rotation.x = -0.1;
                fGroup.rotation.y = Math.PI / 4.2;
              } else {
                fGroup.rotation.x = gripFactor * 0.2;
              }

              fGroup.traverse((child) => {
                if (child.name === 'pip_joint') {
                  child.rotation.x = gripFactor * 0.1;
                } else if (child.name === 'dip_joint') {
                  child.rotation.x = gripFactor * 0.1;
                }
              });
            });
          };
          applyDexGrip(alpha, 0.1);
          applyDexGrip(beta, 0.1);

          if (isClapping && performance.now() - lastClaspSoundRef.current > 400) {
            soundEngine.playClaspChime();
            lastClaspSoundRef.current = performance.now();
          }
        } else {
          // Handshake animation modes
          let shakeFreq = 5.0;
          let shakeAmp = 0.08;
          let stiffnessKx: number | undefined = undefined;
          let dampingDx: number | undefined = undefined;

          if (mode === 'impedance') {
            // Task-Space Impedance Control mode (Compliant spring-damper + gravity compensation)
            shakeFreq = 3.2;
            shakeAmp = 0.06;
            torque = 28; // Low torque due to impedance yielding
            gripValue = 0.85;
            stiffnessKx = 150;
            dampingDx = 20;
            soundEngine.updateServoSound(0.3, speed);
          } else if (mode === 'energetic') {
            shakeFreq = 9.0;
            shakeAmp = 0.15;
            torque = 78;
            gripValue = 0.95;
            soundEngine.updateServoSound(0.8, speed);
          } else if (mode === 'diplomatic') {
            shakeFreq = 2.5;
            shakeAmp = 0.04;
            torque = 32;
            gripValue = 0.7;
            soundEngine.updateServoSound(0.2, speed);
          } else if (mode === 'glitch') {
            shakeFreq = 24.0;
            shakeAmp = 0.12;
            torque = 110;
            soundEngine.playSparkGlitch();
          } else {
            // Standard
            soundEngine.updateServoSound(0.4, speed);
          }

          shakeOffset = Math.sin(t * shakeFreq) * shakeAmp;

          // Extended hand pose with shake
          // Right shoulder (1st motor in the arm chain) pitch nudged +10°, then +45° more per 사령관 request (total +55°)
          const basePitch = -1.12 + THREE.MathUtils.degToRad(55);
          // In impedance mode, spring-damper compliance adds soft damped lag
          const complianceLag = mode === 'impedance' ? Math.cos(t * shakeFreq) * 0.02 : 0;

          alpha.rightShoulder.rotation.x = basePitch + shakeOffset + complianceLag;
          alpha.rightShoulder.rotation.y = -0.34;
          alpha.rightElbow.rotation.x = 0.88 - shakeOffset * 0.4;
          alpha.rightWrist.rotation.x = 0.15 + shakeOffset * 0.2;
          // Wrist roll swept numerically to point the thumb (local -X) as close to
          // world +Y (up) as this arm chain allows — best found at 265° (0.639 of max 1.0)
          alpha.rightWrist.rotation.z = THREE.MathUtils.degToRad(265);

          beta.rightShoulder.rotation.x = basePitch + shakeOffset - complianceLag;
          beta.rightShoulder.rotation.y = -0.34;
          beta.rightElbow.rotation.x = 0.88 - shakeOffset * 0.4;
          beta.rightWrist.rotation.x = 0.15 + shakeOffset * 0.2;
          beta.rightWrist.rotation.z = THREE.MathUtils.degToRad(265);

          // Torso breathing & weight transfer response
          alpha.torso.rotation.z = shakeOffset * 0.12;
          beta.torso.rotation.z = -shakeOffset * 0.12;
          // Torso yaw re-solved to prioritize PALM-FACING alignment over hand distance
          // (262° minimized distance to ~138mm but palm normals pointed away from the
          // partner, alignment score -0.425/1.0; 352° maximizes facing to 0.639/1.0,
          // at the cost of distance growing to ~1360mm under the current +55° shoulder pitch)
          alpha.torso.rotation.y = THREE.MathUtils.degToRad(352);
          beta.torso.rotation.y = THREE.MathUtils.degToRad(352);
          alpha.head.rotation.x = Math.sin(t * shakeFreq * 0.5) * 0.04;
          beta.head.rotation.x = Math.sin(t * shakeFreq * 0.5) * 0.04;

          // Clasped DexHand fingers
          // (rotation.x sign negated on the gripFactor term so curling wraps the
          // fingertips toward the palm/partner side, not the dorsal/back side —
          // verified analytically: positive curl moved the fingertip from z=+0.006
          // to z=-0.066 relative to the wrist, i.e. toward the back of the hand)
          const applyClaspGrip = (robot: RobotJointRefs, gripFactor: number) => {
            robot.rightFingers.forEach((fGroup, i) => {
              const isThumb = i === 0;
              if (isThumb) {
                fGroup.rotation.x = -0.22 - gripFactor * 0.5;
                fGroup.rotation.y = Math.PI / 4.2 - gripFactor * 0.35;
              } else {
                fGroup.rotation.x = -gripFactor * 0.85;
              }

              fGroup.traverse((child) => {
                if (child.name === 'pip_joint') {
                  child.rotation.x = -gripFactor * 0.75;
                } else if (child.name === 'dip_joint') {
                  child.rotation.x = -gripFactor * 0.6;
                }
              });
            });
          };

          applyClaspGrip(alpha, gripValue);
          applyClaspGrip(beta, gripValue);

          // Play periodic clasp chime on hand peak contact
          if (Math.abs(shakeOffset) > shakeAmp * 0.9 && performance.now() - lastClaspSoundRef.current > 350) {
            soundEngine.playClaspChime();
            lastClaspSoundRef.current = performance.now();
          }
        }

        // Calculate Hand World Positions for Telemetry
        alpha.rightHandPalmMesh.getWorldPosition(alpha.handTargetPos);
        const betaPalmPos = new THREE.Vector3();
        beta.rightHandPalmMesh.getWorldPosition(betaPalmPos);

        const contactDistMM = Math.round(alpha.handTargetPos.distanceTo(betaPalmPos) * 1000);
        const contactCenter = alpha.handTargetPos.clone().add(betaPalmPos).multiplyScalar(0.5);

        // Update Axes Helpers
        if (axesHelpersRef.current) {
          const axisA = axesHelpersRef.current.getObjectByName('axis_a');
          const axisB = axesHelpersRef.current.getObjectByName('axis_b');
          if (axisA) axisA.position.copy(alpha.handTargetPos);
          if (axisB) axisB.position.copy(betaPalmPos);
        }

        // Update Contact Arrow
        if (contactVectorRef.current) {
          contactVectorRef.current.position.copy(contactCenter);
          contactVectorRef.current.setLength(0.2 + Math.abs(shakeOffset) * 0.5);
        }

        // Animate Particles at hand contact
        if (particlesRef.current && particleGeoRef.current) {
          const posAttr = particleGeoRef.current.getAttribute('position') as THREE.BufferAttribute;
          const posArr = posAttr.array as Float32Array;

          for (let i = 0; i < posArr.length / 3; i++) {
            posArr[i * 3 + 1] -= 0.002 * (mode === 'glitch' ? 3 : 1);
            if (posArr[i * 3 + 1] < contactCenter.y - 0.2) {
              posArr[i * 3] = contactCenter.x + (Math.random() - 0.5) * 0.15;
              posArr[i * 3 + 1] = contactCenter.y + (Math.random() - 0.5) * 0.08;
              posArr[i * 3 + 2] = contactCenter.z + (Math.random() - 0.5) * 0.15;
            }
          }
          posAttr.needsUpdate = true;
        }

        // Emit Telemetry Data
        onTelemetryUpdate({
          contactDistance: contactDistMM,
          gripForce: Math.round(50 + gripValue * 60 + Math.abs(shakeOffset) * 120),
          rightHandX: Number(contactCenter.x.toFixed(3)),
          rightHandY: Number(contactCenter.y.toFixed(3)),
          rightHandZ: Number(contactCenter.z.toFixed(3)),
          jointTorquePeak: Math.round(torque + Math.abs(shakeOffset) * 35),
          syncRatio: Math.round(98.5 + Math.sin(t * 2) * 1.2),
          fps: currentFps,
          stiffnessKx: mode === 'impedance' ? 150 : undefined,
          dampingDx: mode === 'impedance' ? 20 : undefined,
          rlEpisode: rlEpisodeVal,
          rlReward: rlRewardVal,
          rlPolicyStatus: rlStatusVal,
          palmAlignmentError: palmErrorVal,
        });
      }

      if (controlsRef.current) controlsRef.current.update();
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    };

    renderLoop();

    return () => {
      if (frameIdRef.current) cancelAnimationFrame(frameIdRef.current);
    };
  }, [isPlaying, speed, mode, manualAnglesAlpha, manualAnglesBeta]);

  return (
    <div className="relative w-full h-full min-h-[400px] overflow-hidden bg-slate-950">
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
    </div>
  );
};
