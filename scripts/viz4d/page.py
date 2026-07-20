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
#selRect {
  position:fixed; border:2px dashed #a0c4ff; background:rgba(100,180,255,0.08);
  pointer-events:none; display:none; z-index:50;
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
  <div class="ctrl-row" style="margin-top:6px">
    <label>보정자</label>
    <input type="text" id="corrector-name" placeholder="이름/콜사인"
           style="width:110px; background:#1a1d2a; border:1px solid #333; color:#ccc; font-size:0.68rem; padding:2px 6px; border-radius:3px;">
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
      <input type="range" class="slider" id="slider-sep" min="20" max="400" value="80"
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
<div id="selRect"></div>

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
camera.position.set(0, 0, 550);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// 그리드 플레인 (미약한 격자)
const gridHelper = new THREE.GridHelper(1200, 30, 0x1a1d30, 0x12152a);
scene.add(gridHelper);

// ── 상태 ───────────────────────────────────────────────────────────
let data = null;
let paperMeshes = [], kwMeshes = [], bridgeLines = null;
let layerSep = 80;
let tVal = 0;
let showBridges = true, showPapers = true, showKw = true, autoRotate = true;

// ── 보정자 이름 (localStorage에 기억) ─────────────────────────────────
const correctorInput = document.getElementById('corrector-name');
correctorInput.value = localStorage.getItem('viz4d_corrector') || '';
correctorInput.addEventListener('change', () => {
  localStorage.setItem('viz4d_corrector', correctorInput.value.trim());
});

// ── 로딩 ───────────────────────────────────────────────────────────
document.getElementById('status').textContent = '4D 레이아웃 계산 중 (GPU)...';
Promise.all([
  fetch('/layout?type=4d').then(r => r.json()),
  fetch('/viz4d/corrections').then(r => r.json()).catch(() => ({})),
]).then(([d, corrections]) => {
    data = d;
    let correctedCount = 0;
    d.papers.forEach(p => {
      const c = corrections[p.id];
      if (c) { p.px = c.x; p.py = c.y; p.pz = c.z; correctedCount++; }
    });
    build(d);
    document.getElementById('status').textContent =
      `논문 ${d.papers.length}편 · 개념 ${d.keywords.length}개 · max_w=${d.max_w.toFixed(2)}` +
      (correctedCount ? ` · 보정 ${correctedCount}건 적용` : '');
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

  // 3) 브릿지 라인 (논문 → 실제 태그 키워드 노드, 태그별로 각각)
  buildBridgesT(d);

  // 4) 논문 엣지 (위 레이어, 얇은 회색) — 드래그 중 노드를 따라가야 하므로
  //    paperMeshes의 현재 위치를 매번 다시 읽어 그리는 buildPaperEdges 사용
  buildPaperEdges(d.paper_edges);

  // 5) 개념 엣지 (아래 레이어, 얇은 청록)
  buildKeywordEdges(d.keyword_edges);

  // 조명
  scene.add(new THREE.AmbientLight(0x202535, 3));
  const dLight = new THREE.DirectionalLight(0xffffff, 1.5);
  dLight.position.set(0, 400, 200);
  scene.add(dLight);
}

// 논문↔논문, 개념↔개념 엣지 — 각 레이어 메시의 "현재" 위치를 읽어서 그리므로,
// 노드가 드래그·t-슬라이더·레이어 간격 변경으로 움직일 때마다 다시 불러주면
// 연결된 엣지가 전부 함께 따라온다. (연결이 끊긴 정적 렌더링 방지)
function _buildLiveEdges(edges, meshes, ids, hexColor) {
  const idxOf = {};
  ids.forEach((id, i) => { idxOf[id] = i; });
  const positions = [];
  edges.forEach(e => {
    const si = idxOf[e.source], ti = idxOf[e.target];
    if (si === undefined || ti === undefined) return;
    const s = meshes[si].position, t = meshes[ti].position;
    positions.push(s.x, s.y, s.z, t.x, t.y, t.z);
  });
  const geo = new THREE.BufferGeometry();
  if (positions.length) {
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  }
  const mat = new THREE.LineBasicMaterial({ color: hexColor, transparent: true, opacity: 0.7 });
  return new THREE.LineSegments(geo, mat);
}

let paperEdgeLines = null;
function buildPaperEdges(edges) {
  if (paperEdgeLines) { scene.remove(paperEdgeLines); paperEdgeLines.geometry.dispose(); }
  paperEdgeLines = _buildLiveEdges(edges, paperMeshes, data.papers.map(p => p.id), 0x3d5afe);
  scene.add(paperEdgeLines);
}

let keywordEdgeLines = null;
function buildKeywordEdges(edges) {
  if (keywordEdgeLines) { scene.remove(keywordEdgeLines); keywordEdgeLines.geometry.dispose(); }
  keywordEdgeLines = _buildLiveEdges(edges, kwMeshes, data.keywords.map(k => k.id), 0x00b0ff);
  scene.add(keywordEdgeLines);
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
  // 브릿지·엣지 라인도 새 위치로 갱신
  buildBridgesT(data);
  buildPaperEdges(data.paper_edges);
  buildKeywordEdges(data.keyword_edges);
}

// 브릿지 = 논문 → "그 논문이 가진 각 태그"의 실제 키워드 노드로 각각 하나씩.
// (예전엔 태그들의 무게중심 한 점으로만 이었는데, 그 중심점은 대개 어느 키워드
//  노드와도 일치하지 않아 "연결이 안 된 것처럼" 보였다. 이제 태그 수만큼
//  실제 노드에 닿는 여러 개의 얇은 선으로 그린다. t는 더 이상 쓰지 않음 —
//  양끝 다 현재 mesh.position을 그대로 읽으므로 투영/간격 변경에 자동 반영됨.)
function buildBridgesT(d) {
  if (bridgeLines) { scene.remove(bridgeLines); bridgeLines.geometry.dispose(); }
  const kwIdx = {};
  d.keywords.forEach((k, j) => { kwIdx[k.id] = j; });
  const positions = [], colors = [];
  d.papers.forEach((p, i) => {
    const m = paperMeshes[i];
    if (!m) return;
    const c = wColor(p.wn);
    (p.tags || []).forEach(tag => {
      const j = kwIdx[tag];
      if (j === undefined || !kwMeshes[j]) return;
      const kPos = kwMeshes[j].position;
      positions.push(m.position.x, m.position.y, m.position.z);
      colors.push(c.r, c.g, c.b);
      positions.push(kPos.x, kPos.y, kPos.z);
      colors.push(c.r, c.g, c.b);
    });
  });
  const geo = new THREE.BufferGeometry();
  if (positions.length) {
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color',    new THREE.Float32BufferAttribute(colors, 3));
  }
  const mat = new THREE.LineBasicMaterial({ vertexColors:true, transparent:true, opacity:0.5 });
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
    buildBridgesT(data);
    buildPaperEdges(data.paper_edges);
    buildKeywordEdges(data.keyword_edges);
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
  if (dragTarget || isBoxSelecting) { tooltip.style.display = 'none'; return; }
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

// ── 노드 드래그 = 4D 위치 보정 (t=0, 논문 레이어에서만) ─────────────────
// 계산된 좌표가 원본, 사용자가 옮기면 그 위에 얹는 보정값으로 취급한다.
// 서버(SQLite)에 slug·좌표·보정자·시각을 저장해 누구든 다음 로드부터 반영받는다.
// Shift+드래그로 박스 선택 → 여러 노드를 그룹으로 한 번에 보정할 수도 있다.
let dragTarget = null;
const dragPlane  = new THREE.Plane();
const dragPoint  = new THREE.Vector3();
const dragOffset = new THREE.Vector3();

let selectedIds = new Set();
let isBoxSelecting = false;
let boxStart = { x: 0, y: 0 };
let boxCurrent = { x: 0, y: 0 };
let groupDragOffsets = null;  // Map<paperId, THREE.Vector3 월드 오프셋>
const selRectEl = document.getElementById('selRect');

function setMouseFromEvent(e) {
  mouse.x =  (e.clientX / innerWidth)  * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
}

function meshById(id) {
  return paperMeshes.find(m => m.userData.d.id === id);
}

function toScreen(worldPos) {
  const v = worldPos.clone().project(camera);
  return { x: (v.x + 1) / 2 * innerWidth, y: (-v.y + 1) / 2 * innerHeight };
}

function updateSelRectDOM() {
  const x1 = Math.min(boxStart.x, boxCurrent.x);
  const y1 = Math.min(boxStart.y, boxCurrent.y);
  selRectEl.style.left   = x1 + 'px';
  selRectEl.style.top    = y1 + 'px';
  selRectEl.style.width  = Math.abs(boxCurrent.x - boxStart.x) + 'px';
  selRectEl.style.height = Math.abs(boxCurrent.y - boxStart.y) + 'px';
}

function updateSelectionVisual() {
  paperMeshes.forEach(m => {
    if (selectedIds.size === 0) {
      m.material.opacity = 0.9;
      m.scale.setScalar(1);
    } else if (selectedIds.has(m.userData.d.id)) {
      m.material.opacity = 1.0;
      m.scale.setScalar(1.4);
    } else {
      m.material.opacity = 0.2;
      m.scale.setScalar(1);
    }
  });
}

function pickNodesInBox() {
  const x1 = Math.min(boxStart.x, boxCurrent.x), x2 = Math.max(boxStart.x, boxCurrent.x);
  const y1 = Math.min(boxStart.y, boxCurrent.y), y2 = Math.max(boxStart.y, boxCurrent.y);
  selectedIds.clear();
  const wp = new THREE.Vector3();
  paperMeshes.forEach(m => {
    if (!m.visible) return;
    m.getWorldPosition(wp);
    const s = toScreen(wp);
    if (s.x >= x1 && s.x <= x2 && s.y >= y1 && s.y <= y2) selectedIds.add(m.userData.d.id);
  });
  updateSelectionVisual();
}

renderer.domElement.addEventListener('pointerdown', e => {
  if (tVal !== 0 || !showPapers) return;  // 투영 중엔 "논문 위치"가 아니므로 보정 비활성

  if (e.shiftKey) {
    isBoxSelecting = true;
    boxStart = boxCurrent = { x: e.clientX, y: e.clientY };
    selRectEl.style.display = 'block';
    updateSelRectDOM();
    controls.enabled = false;
    return;
  }

  setMouseFromEvent(e);
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(paperMeshes.filter(m => m.visible));
  if (!hits.length) {
    if (selectedIds.size) { selectedIds.clear(); updateSelectionVisual(); }
    return;
  }
  dragTarget = hits[0].object;
  const nodeId = dragTarget.userData.d.id;
  controls.enabled = false;
  // scene이 자동회전 중이면 mesh.position(로컬)과 레이캐스터 결과(월드)가 어긋나므로
  // 전 과정을 월드 좌표로 계산하고 최종 대입 시점에만 로컬로 변환한다.
  const targetWorldPos = new THREE.Vector3();
  dragTarget.getWorldPosition(targetWorldPos);
  const normal = new THREE.Vector3();
  camera.getWorldDirection(normal);
  dragPlane.setFromNormalAndCoplanarPoint(normal, targetWorldPos);
  raycaster.ray.intersectPlane(dragPlane, dragPoint);
  dragOffset.copy(targetWorldPos).sub(dragPoint);  // 월드 좌표 기준 오프셋

  if (selectedIds.has(nodeId) && selectedIds.size > 1) {
    // 이미 선택된 그룹 안의 노드를 잡으면 그룹 전체를 함께 옮긴다
    groupDragOffsets = new Map();
    selectedIds.forEach(id => {
      const m = meshById(id);
      if (!m) return;
      const wp = new THREE.Vector3();
      m.getWorldPosition(wp);
      groupDragOffsets.set(id, wp.sub(targetWorldPos));
    });
    document.getElementById('status').textContent = `${selectedIds.size}개 그룹 보정 중... 놓으면 저장됩니다`;
  } else {
    selectedIds.clear();
    updateSelectionVisual();
    groupDragOffsets = null;
    document.getElementById('status').textContent = '보정 중... 놓으면 저장됩니다';
  }
  tooltip.style.display = 'none';
});

renderer.domElement.addEventListener('pointermove', e => {
  setMouseFromEvent(e);

  if (isBoxSelecting) {
    boxCurrent = { x: e.clientX, y: e.clientY };
    updateSelRectDOM();
    return;
  }
  if (!dragTarget) return;

  raycaster.setFromCamera(mouse, camera);
  if (!raycaster.ray.intersectPlane(dragPlane, dragPoint)) return;
  const newWorldPos = dragPoint.clone().add(dragOffset);

  if (groupDragOffsets) {
    groupDragOffsets.forEach((offset, id) => {
      const m = meshById(id);
      if (!m) return;
      const wp = newWorldPos.clone().add(offset);
      m.position.copy(m.parent.worldToLocal(wp));
    });
  } else {
    dragTarget.position.copy(dragTarget.parent.worldToLocal(newWorldPos));
  }

  if (data) {
    buildBridgesT(data);
    buildPaperEdges(data.paper_edges);
  }
});

window.addEventListener('pointerup', e => {
  if (isBoxSelecting) {
    isBoxSelecting = false;
    selRectEl.style.display = 'none';
    controls.enabled = true;
    boxCurrent = { x: e.clientX, y: e.clientY };  // 마지막 pointermove 이후 놓인 지점까지 반영
    pickNodesInBox();
    return;
  }
  if (!dragTarget) return;

  const correctedBy = correctorInput.value.trim() || '익명';
  localStorage.setItem('viz4d_corrector', correctedBy);
  const targetIds = groupDragOffsets ? Array.from(groupDragOffsets.keys()) : [dragTarget.userData.d.id];
  let savedCount = 0;

  targetIds.forEach(id => {
    const m = meshById(id);
    if (!m) return;
    const idx = paperMeshes.indexOf(m);
    const p = data.papers[idx];
    p.px = m.position.x / 120;
    p.py = (m.position.y - layerSep) / 120;
    p.pz = m.position.z / 120;
    fetch('/viz4d/correction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: p.id, x: p.px, y: p.py, z: p.pz, corrected_by: correctedBy }),
    })
      .then(() => {
        savedCount++;
        document.getElementById('status').textContent = targetIds.length > 1
          ? `보정 저장됨 · ${savedCount}/${targetIds.length}개 (그룹) → ${correctedBy}`
          : `보정 저장됨 · ${p.title.slice(0,24)}… → ${correctedBy}`;
      })
      .catch(() => {
        document.getElementById('status').textContent = '보정 저장 실패 (네트워크)';
      });
  });

  dragTarget = null;
  groupDragOffsets = null;
  controls.enabled = true;
});

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
