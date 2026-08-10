/**
 * ROOPS (Robot Object-Oriented Programming System - OOPS)
 * Sub-Object Modular Architecture for Humanoid Robot Hands
 * High-Visibility Mesh Standard & Emissive Phong Materials
 * Author: Aegis
 */

class TcpFrameAxes {
  constructor(size = 5.5) {
    this.group = new THREE.Group();

    // Prominent Axes Helper (Red=X, Green=Y, Blue=Z)
    this.axesHelper = new THREE.AxesHelper(size);
    this.group.add(this.axesHelper);

    // Explicit RGB Arrow Helpers for 100% Visibility
    const origin = new THREE.Vector3(0, 0, 0);
    const arrowX = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), origin, size, 0xff0000, 1.2, 0.6); // Red X
    const arrowY = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), origin, size, 0x00ff00, 1.2, 0.6); // Green Y
    const arrowZ = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), origin, size, 0x0000ff, 1.2, 0.6); // Blue Z

    this.group.add(arrowX);
    this.group.add(arrowY);
    this.group.add(arrowZ);

    this.group.visible = true;
  }

  setVisible(visible) {
    this.group.visible = visible;
  }

  getMesh() {
    return this.group;
  }
}

class CollisionShield {
  constructor(geometry, color = 0x34d399, opacity = 0.6) {
    this.material = new THREE.MeshBasicMaterial({
      color: color,
      wireframe: true,
      transparent: true,
      opacity: opacity
    });
    this.mesh = new THREE.Mesh(geometry, this.material);
  }
  setColor(colorHex) {
    this.material.color.setHex(colorHex);
  }
  getMesh() {
    return this.mesh;
  }
}

class FingerJointLink {
  constructor(name, x, z, len, radius, maxAngle, handColor) {
    this.name = name;
    this.x = x;
    this.z = z;
    this.len = len;
    this.radius = radius;
    this.maxAngle = maxAngle;

    this.group = new THREE.Group();
    this.group.position.set(x, 0, z);

    const fGeo = new THREE.CylinderGeometry(radius, radius * 0.8, len, 16);
    fGeo.translate(0, len / 2, 0);
    
    // HIGH-VISIBILITY EMISSIVE PHONG MATERIAL
    const fMat = new THREE.MeshPhongMaterial({
      color: handColor,
      emissive: handColor,
      emissiveIntensity: 0.35,
      shininess: 80,
      side: THREE.DoubleSide
    });
    this.mesh = new THREE.Mesh(fGeo, fMat);
    this.group.add(this.mesh);

    const fsGeo = new THREE.CylinderGeometry(radius + 0.12, (radius * 0.8) + 0.12, len + 0.15, 12);
    fsGeo.translate(0, len / 2, 0);
    this.shield = new CollisionShield(fsGeo, 0x34d399, 0.6);
    this.group.add(this.shield.getMesh());
  }

  setRotationX(angle) {
    this.group.rotation.x = angle;
  }

  setShieldColor(colorHex) {
    this.shield.setColor(colorHex);
  }

  getGroup() {
    return this.group;
  }
}

class PalmBase {
  constructor(width, height, depth, handColor) {
    this.geometry = new THREE.BoxGeometry(width, height, depth);
    
    // HIGH-VISIBILITY EMISSIVE PHONG MATERIAL
    this.material = new THREE.MeshPhongMaterial({
      color: handColor,
      emissive: handColor,
      emissiveIntensity: 0.35,
      shininess: 90,
      side: THREE.DoubleSide
    });
    this.mesh = new THREE.Mesh(this.geometry, this.material);

    const shieldGeo = new THREE.BoxGeometry(width + 0.3, height + 0.3, depth + 0.3);
    this.shield = new CollisionShield(shieldGeo, 0x34d399, 0.5);
    this.mesh.add(this.shield.getMesh());
  }

  setShieldColor(colorHex) {
    this.shield.setColor(colorHex);
  }

  getMesh() {
    return this.mesh;
  }
}

class RobotHandObject {
  constructor(name, colorHex, isFacingRotated = false) {
    this.name = name;
    this.colorHex = colorHex;
    this.isFacingRotated = isFacingRotated;

    this.group = new THREE.Group();
    this.group.name = name;

    this.internalState = {
      px: isFacingRotated ? 0.10 : -0.10,
      py: 3.0,
      pz: isFacingRotated ? 0.60 : -0.60,
      rx: 0.0,
      ry: isFacingRotated ? Math.PI : 0.0,
      rz: 0.0,
      lastUpdated: Date.now()
    };

    // Sub-Object 1: Palm Base
    this.palm = new PalmBase(3.6, 1.2, 2.4, colorHex);
    this.palm.getMesh().userData = { handName: name };
    this.group.add(this.palm.getMesh());

    // Sub-Object 2: Selection Highlight Wireframe Box
    const selectGeo = new THREE.BoxGeometry(4.4, 2.0, 3.4);
    const selectMat = new THREE.MeshBasicMaterial({ color: 0xfacc15, wireframe: true, visible: false });
    this.selectMesh = new THREE.Mesh(selectGeo, selectMat);
    this.group.add(this.selectMesh);

    // Sub-Object 3: ENHANCED PROMINENT TCP RGB FRAME AXES
    this.tcpAxes = new TcpFrameAxes(5.5);
    this.group.add(this.tcpAxes.getMesh());

    // Sub-Objects 4: 5 Finger Joint Links
    const fingerDefs = [
      { name: "thumb", x: -1.6, z: 1.0, len: 2.2, r: 0.35, maxAngle: 1.10 },
      { name: "index", x: -0.8, z: 1.4, len: 2.8, r: 0.32, maxAngle: 1.22 },
      { name: "middle", x: 0.0, z: 1.5, len: 3.0, r: 0.32, maxAngle: 1.25 },
      { name: "ring", x: 0.8, z: 1.4, len: 2.7, r: 0.32, maxAngle: 1.20 },
      { name: "pinky", x: 1.6, z: 1.2, len: 2.2, r: 0.30, maxAngle: 1.15 }
    ];

    this.fingers = [];
    fingerDefs.forEach(fd => {
      const finger = new FingerJointLink(fd.name, fd.x, fd.z, fd.len, fd.r, fd.maxAngle, colorHex);
      finger.mesh.userData = { handName: name };
      this.group.add(finger.getGroup());
      this.fingers.push(finger);
    });

    if (isFacingRotated) {
      this.group.rotation.y = Math.PI;
    }
  }

  syncInternalState() {
    this.internalState.px = this.group.position.x;
    this.internalState.py = this.group.position.y;
    this.internalState.pz = this.group.position.z;
    this.internalState.rx = this.group.rotation.x;
    this.internalState.ry = this.group.rotation.y;
    this.internalState.rz = this.group.rotation.z;
    this.internalState.lastUpdated = Date.now();
    return this.internalState;
  }

  exportToExternal() {
    this.syncInternalState();
    const storageKey = (this.name === "Hand A") ? "tcp_handA" : "tcp_handB";
    localStorage.setItem(storageKey, JSON.stringify(this.internalState));
    return this.internalState;
  }

  importFromExternal() {
    const storageKey = (this.name === "Hand A") ? "tcp_handA" : "tcp_handB";
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      const data = JSON.parse(raw);
      this.setPosition(data.px, data.py, data.pz);
      this.setRotation(data.rx, data.ry, data.rz);
      this.internalState = data;
      return true;
    }
    return false;
  }

  setHighlight(visible) {
    this.selectMesh.material.visible = visible;
    this.tcpAxes.setVisible(true);
  }

  setPosition(x, y, z) {
    this.group.position.set(x, y, z);
    this.syncInternalState();
  }

  setRotation(rx, ry, rz) {
    this.group.rotation.set(rx, ry, rz);
    this.syncInternalState();
  }

  setFingerCurl(curlAmount, isNegative = false) {
    this.fingers.forEach(f => {
      const clampedAngle = Math.min(curlAmount, f.maxAngle);
      f.setRotationX(isNegative ? -clampedAngle : clampedAngle);
    });
  }

  setAllShieldColors(colorHex) {
    this.palm.setShieldColor(colorHex);
    this.fingers.forEach(f => f.setShieldColor(colorHex));
  }

  getGroup() {
    return this.group;
  }
}
