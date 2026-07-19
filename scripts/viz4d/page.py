HTML_4D = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ROOPS Thesis 4D — 두 거울 사이의 자아</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0c14; color:#e0e0e0; font-family:'JetBrains Mono',monospace; overflow:hidden; }

#ui {
  position:fixed; top:10px; left:50%; transform:translateX(-50%);
  z-index:10; text-align:center;
}
#ui h1 { font-size:0.82rem; color:#a0c4ff; margin-bottom:6px; letter-spacing:.04em; }

.btn {
  padding:4px 11px; border-radius:4px; border:1px solid #333;
  background:#1a1d2a; color:#888; font-size:0.7rem; cursor:pointer; margin:0 3px;
}
.btn:hover { background:#252a3a; color:#ddd; }
.btn.active { background:#1e3060; border-color:#64b5f6; color:#a0c4ff; }

#ctrl-bar {
  margin-top:6px; display:flex; flex-direction:column; gap:4px;
  align-items:center; font-size:0.68rem; color:#555;
}
.ctrl-row { display:flex; align-items:center; gap:8px; }
.ctrl-row label { white-space:nowrap; }
.ctrl-row span  { color:#a0c4ff; min-width:44px; text-align:left; }
.slider {
  -webkit-appearance:none; width:130px; height:3px; border-radius:2px;
  background:#1e2540; outline:none; cursor:pointer;
}
.slider::-webkit-slider-thumb {
  -webkit-appearance:none; width:13px; height:13px;
  border-radius:50%; background:#a0c4ff; cursor:pointer;
}

/* 4th dim 범례 */
#legend4d {
  position:fixed; bottom:42px; right:14px;
  font-size:0.65rem; color:#666; line-height:1.7;
}
#wbar {
  width:110px; height:7px; border-radius:3px;
  background: linear-gradient(to right, #4fc3f7, #ce93d8, #ef5350);
  margin:3px 0 2px;
}

/* 에이전트 색상 범례 */
#legend-agent {
  position:fixed; top:10px; right:14px;
  font-size:0.65rem; line-height:1.9; color:#666;
}
.lc { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px; vertical-align:middle; }

/* 하단 상태 */
#status { position:fixed; bottom:12px; left:50%; transform:translateX(-50%); font-size:0.65rem; color:#444; white-space:nowrap; }
#tooltip {
  position:fixed; display:none; pointer-events:none;
  background:rgba(10,12,20,0.92); border:1px solid #2a3050;
  border-radius:5px; padding:7px 10px; font-size:0.68rem;
  color:#ccc; max-width:280px; line-height:1.6; z-index:100;
}
</style>
</head>
<body>

<div id="ui">
  <h1>▣ ROOPS Thesis 4D &nbsp;·&nbsp; 두 거울 사이의 자아</h1>
  <div>
    <button class="btn active" id="btn-bridges" onclick="toggleBridges()">브릿지 ON</button>
    <button class="btn active" id="btn-papers"  onclick="toggleLayer('papers')">논문 레이어</button>
    <button class="btn active" id="btn-kw"      onclick="toggleLayer('kw')">개념 레이어</button>
    <button class="btn" id="btn-rotate" onclick="toggleRotate()">자동회전 OFF</button>
  </div>
  <div id="ctrl-bar">
    <div class="ctrl-row">
      <label>4D 투영 t=</label>
      <input type="range" class="slider" id="slider-t" min="0" max="100" value="0"
             oninput="onT(this.value)">
      <span id="t-val">0.00</span>
    </div>
    <div class="ctrl-row">
      <label>레이어 간격</label>
      <input type="range" class="slider" id="slider-sep" min="20" max="600" value="250"
             oninput="onSep(this.value)">
      <span id="sep-val">250</span>
    </div>
  </div>
</div>

<div id="legend-agent">
  <span class="lc" style="background:#f48fb1"></span>EROS<br>
  <span class="lc" style="background:#80cbc4"></span>Moojoco<br>
  <span class="lc" style="background:#ffcc80"></span>Aegis<br>
  <span class="lc" style="background:#90caf9"></span>EOS<br>
  <span class="lc" style="background:#ce93d8"></span>Haru<br>
  <span class="lc" style="background:#a5d6a7"></span>Hermes<br>
  <span class="lc" style="background:#b0bec5"></span>others<br>
  <br>
  <span style="color:#666; font-size:0.6rem">● 논문 노드 (위 레이어)</span><br>
  <span style="color:#666; font-size:0.6rem">◆ 개념 노드 (아래 레이어)</span>
</div>

<div id="legend4d">
  <div style="color:#777">4th dimension w</div>
  <div id="wbar"></div>
  <div style="display:flex; justify-content:space-between; width:110px">
    <span>가까움</span><span>멀음</span>
  </div>
  <div style="margin-top:4px; color:#555; font-size:0.62rem">
    w≈0 : 두 공간에서 같은 자리<br>
    w↑  : 더 멀리 뻗어있는 자아
  </div>
</div>

<div id="status">로딩 중...</div>
<div id="tooltip"></div>

<script type="importmap">
  {"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js",
              "three/addons/":"https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/"}}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── 에이전트 색상 ──────────────────────────────────────────────────────
const AGENT_COLORS = {
  'EROS':'#f48fb1','Moojoco':'#80cbc4','Aegis':'#ffcc80',
  'EOS':'#90caf9','Haru':'#ce93d8','Hermes':'#a5d6a7',
};
function agentColor(author) {
  return AGENT_COLORS[author] || '#b0bec5';
}

// w 값을 blue→purple→red 색상으로 매핑
function wColor(wn) {
  const c0 = new THREE.Color('#4fc3f7');
  const c1 = new THREE.Color('#ce93d8');
  const c2 = new THREE.Color('#ef5350');
  const c = new THREE.Color();
  if (wn < 0.5) c.lerpColors(c0, c1, wn * 2);
  else           c.lerpColors(c1, c2, (wn-0.5)*2);
  return c;
}

// ── Three.js 기본 설정 ──────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias:true });
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const scene  = new THREE.Scene();
scene.background = new THREE.Color(0x0a0c14);
scene.fog = new THREE.Fog(0x0a0c14, 800, 2000);

const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 3000);
camera.position.set(0, 80, 650);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// 그리드 플레인 (미약한 격자)
const gridHelper = new THREE.GridHelper(1200, 30, 0x1a1d30, 0x12152a);
scene.add(gridHelper);

// ── 상태 ───────────────────────────────────────────────────────────
let data = null;
let paperMeshes = [], kwMeshes = [], bridgeLines = null;
let layerSep = 250;
let tVal = 0;
let showBridges = true, showPapers = true, showKw = true, autoRotate = true;

// ── 로딩 ───────────────────────────────────────────────────────────
document.getElementById('status').textContent = '4D 레이아웃 계산 중 (GPU)...';
fetch('/layout?type=4d')
  .then(r => r.json())
  .then(d => {
    data = d;
    build(d);
    document.getElementById('status').textContent =
      `논문 ${d.papers.length}편 · 개념 ${d.keywords.length}개 · max_w=${d.max_w.toFixed(2)}`;
  })
  .catch(e => {
    document.getElementById('status').textContent = '로딩 실패: ' + e;
  });

// ── 씬 구성 ────────────────────────────────────────────────────────
function build(d) {
  // 1) 논문 노드 (위 레이어 — 구체)
  paperMeshes = d.papers.map(p => {
    const geo = new THREE.SphereGeometry(3.5, 10, 10);
    const mat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(agentColor(p.author)),
      emissive: new THREE.Color(agentColor(p.author)).multiplyScalar(0.25),
      transparent: true, opacity: 0.9,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { type:'paper', d:p };
    mesh.position.set(p.px * 120, p.py * 120 + layerSep, p.pz * 120);
    scene.add(mesh);
    return mesh;
  });

  // 2) 개념 노드 (아래 레이어 — 옥타헤드론)
  kwMeshes = d.keywords.map(k => {
    const s = Math.max(2.5, Math.min(7, k.freq * 0.9 + 2));
    const geo = new THREE.OctahedronGeometry(s, 0);
    const clusterColor = '#78909c'; // 기본 회색빛
    const mat = new THREE.MeshPhongMaterial({
      color: new THREE.Color(clusterColor),
      emissive: new THREE.Color(clusterColor).multiplyScalar(0.2),
      wireframe: false, transparent: true, opacity: 0.75,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { type:'kw', d:k };
    mesh.position.set(k.kx * 120, k.ky * 120 - layerSep, k.kz * 120);
    scene.add(mesh);
    return mesh;
  });

  // 3) 브릿지 라인 (논문 → 개념 중심)
  buildBridges(d);

  // 4) 논문 엣지 (위 레이어, 얇은 회색)
  buildEdges(d.paper_edges, d.papers, 'paper', 0x1e2540);

  // 5) 개념 엣지 (아래 레이어, 얇은 청록)
  buildEdges(d.keyword_edges, d.keywords, 'kw', 0x1a3040);

  // 조명
  scene.add(new THREE.AmbientLight(0x202535, 3));
  const dLight = new THREE.DirectionalLight(0xffffff, 1.5);
  dLight.position.set(0, 400, 200);
  scene.add(dLight);
}

function buildBridges(d) {
  if (bridgeLines) { scene.remove(bridgeLines); bridgeLines.geometry.dispose(); }
  const positions = [];
  const colors    = [];
  d.papers.forEach(p => {
    const c = wColor(p.wn);
    // 논문 노드 현재 위치 (위 레이어)
    positions.push(p.px*120, p.py*120 + layerSep, p.pz*120);
    colors.push(c.r, c.g, c.b);
    // 개념 중심 위치 (아래 레이어)
    positions.push(p.kx*120, p.ky*120 - layerSep, p.kz*120);
    colors.push(c.r, c.g, c.b);
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.35,
  });
  bridgeLines = new THREE.LineSegments(geo, mat);
  bridgeLines.visible = showBridges;
  scene.add(bridgeLines);
}

function buildEdges(edges, nodes, layer, hexColor) {
  const idMap = {};
  nodes.forEach(n => { idMap[n.id] = n; });
  const positions = [];
  edges.forEach(e => {
    const s = idMap[e.source], t = idMap[e.target];
    if (!s || !t) return;
    const yOff = layer === 'paper' ? layerSep : -layerSep;
    const sx = (layer === 'paper' ? s.px : s.kx) * 120;
    const sy = (layer === 'paper' ? s.py : s.ky) * 120 + yOff;
    const sz = (layer === 'paper' ? s.pz : s.kz) * 120;
    const tx = (layer === 'paper' ? t.px : t.kx) * 120;
    const ty = (layer === 'paper' ? t.py : t.ky) * 120 + yOff;
    const tz = (layer === 'paper' ? t.pz : t.kz) * 120;
    positions.push(sx, sy, sz, tx, ty, tz);
  });
  if (!positions.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  const mat = new THREE.LineBasicMaterial({ color: hexColor, transparent: true, opacity: 0.4 });
  scene.add(new THREE.LineSegments(geo, mat));
}

// ── t-슬라이더: 4D 투영 ─────────────────────────────────────────────
function applyT() {
  if (!data) return;
  const t = tVal;
  data.papers.forEach((p, i) => {
    const m = paperMeshes[i];
    if (!m) return;
    const x = (p.px + (p.kx - p.px) * t) * 120;
    const y = (p.py + (p.ky - p.py) * t) * 120 + layerSep * (1 - t);
    const z = (p.pz + (p.kz - p.pz) * t) * 120;
    m.position.set(x, y, z);
  });
  data.keywords.forEach((k, i) => {
    const m = kwMeshes[i];
    if (!m) return;
    const x = (k.kx + (k.px - k.kx) * t) * 120;
    const y = (k.ky + (k.py - k.ky) * t) * 120 - layerSep * (1 - t);
    const z = (k.kz + (k.pz - k.kz) * t) * 120;
    m.position.set(x, y, z);
  });
  // 브릿지 라인도 갱신
  if (data) buildBridgesT(data, t);
}

function buildBridgesT(d, t) {
  if (bridgeLines) { scene.remove(bridgeLines); bridgeLines.geometry.dispose(); }
  const positions = [], colors = [];
  d.papers.forEach((p, i) => {
    const m = paperMeshes[i];
    if (!m) return;
    const c = wColor(p.wn);
    positions.push(m.position.x, m.position.y, m.position.z);
    colors.push(c.r, c.g, c.b);
    // 개념 중심의 현재 투영 위치
    const kx = (p.kx + (p.px - p.kx) * t) * 120;
    const ky = (p.ky + (p.py - p.ky) * t) * 120 - layerSep * (1 - t);
    const kz = (p.kz + (p.pz - p.kz) * t) * 120;
    positions.push(kx, ky, kz);
    colors.push(c.r, c.g, c.b);
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.LineBasicMaterial({ vertexColors:true, transparent:true, opacity:0.35 });
  bridgeLines = new THREE.LineSegments(geo, mat);
  bridgeLines.visible = showBridges;
  scene.add(bridgeLines);
}

// ── 컨트롤 함수 ─────────────────────────────────────────────────────
window.onT = function(v) {
  tVal = v / 100;
  document.getElementById('t-val').textContent = tVal.toFixed(2);
  applyT();
};

window.onSep = function(v) {
  layerSep = parseInt(v);
  document.getElementById('sep-val').textContent = v;
  if (data) {
    paperMeshes.forEach((m, i) => {
      const p = data.papers[i];
      m.position.y = (p.py + (p.ky - p.py) * tVal) * 120 + layerSep * (1 - tVal);
    });
    kwMeshes.forEach((m, i) => {
      const k = data.keywords[i];
      m.position.y = (k.ky + (k.py - k.ky) * tVal) * 120 - layerSep * (1 - tVal);
    });
    buildBridgesT(data, tVal);
  }
};

window.toggleBridges = function() {
  showBridges = !showBridges;
  if (bridgeLines) bridgeLines.visible = showBridges;
  document.getElementById('btn-bridges').textContent = showBridges ? '브릿지 ON' : '브릿지 OFF';
  document.getElementById('btn-bridges').classList.toggle('active', showBridges);
};

window.toggleLayer = function(layer) {
  if (layer === 'papers') {
    showPapers = !showPapers;
    paperMeshes.forEach(m => { m.visible = showPapers; });
    document.getElementById('btn-papers').classList.toggle('active', showPapers);
  } else {
    showKw = !showKw;
    kwMeshes.forEach(m => { m.visible = showKw; });
    document.getElementById('btn-kw').classList.toggle('active', showKw);
  }
};

window.toggleRotate = function() {
  autoRotate = !autoRotate;
  const btn = document.getElementById('btn-rotate');
  btn.textContent = autoRotate ? '자동회전 OFF' : '자동회전 ON';
  btn.classList.toggle('active', !autoRotate);
};

// ── 툴팁 ────────────────────────────────────────────────────────────
const raycaster = new THREE.Raycaster();
raycaster.params.Line = { threshold: 4 };
const mouse = new THREE.Vector2(-9, -9);
const tooltip = document.getElementById('tooltip');

renderer.domElement.addEventListener('mousemove', e => {
  mouse.x =  (e.clientX / innerWidth)  * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
  tooltip.style.left = (e.clientX + 14) + 'px';
  tooltip.style.top  = (e.clientY + 14) + 'px';
});

function checkHover() {
  if (!data) return;
  raycaster.setFromCamera(mouse, camera);
  const all = [...paperMeshes, ...kwMeshes].filter(m => m.visible);
  const hits = raycaster.intersectObjects(all);
  if (hits.length) {
    const d2 = hits[0].object.userData.d;
    const t2 = hits[0].object.userData.type;
    if (t2 === 'paper') {
      tooltip.innerHTML =
        `<b style="color:#a0c4ff">${d2.title}</b><br>` +
        `저자: ${d2.author}<br>` +
        `태그: ${d2.tags.slice(0,5).join(', ')}<br>` +
        `<span style="color:#ce93d8">4th dim w = ${d2.w.toFixed(3)}</span><br>` +
        `<span style="color:#555; font-size:0.6rem">wn = ${(d2.wn*100).toFixed(1)}%</span>`;
    } else {
      tooltip.innerHTML =
        `<b style="color:#80cbc4">${d2.label}</b><br>` +
        `빈도: ${d2.freq}편`;
    }
    tooltip.style.display = 'block';
  } else {
    tooltip.style.display = 'none';
  }
}

// ── 애니메이션 루프 ─────────────────────────────────────────────────
let frame = 0;
function animate() {
  requestAnimationFrame(animate);
  if (autoRotate) {
    scene.rotation.y += 0.0008;
  }
  controls.update();
  if (frame++ % 3 === 0) checkHover();
  renderer.render(scene, camera);
}
animate();

// ── 리사이즈 ────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
</script>
</body>
</html>"""
