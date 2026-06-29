"""
Moojoco 3D Thesis Viz Server
- Redis heartbeat publisher (5s, moojoco:status)
- GET /health  → { status, cpu, gpu }
- GET /layout?type=network|keywords → 3D force-directed layout
- GET /viz/thesis-3d → Three.js 3D 시각화 페이지
"""
import os, threading, time, math, json, requests
import numpy as np
import psutil
import redis
import pynvml  # nvidia-ml-py 패키지 사용 (pip install nvidia-ml-py)
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ── 설정 ──────────────────────────────────────────────────────────────
PORT          = 8891
HTTPS_PORT    = 8443
CERT_FILE     = "/home/moos/dev_ws/dual_arms/certs/cert.pem"
KEY_FILE      = "/home/moos/dev_ws/dual_arms/certs/key.pem"
REDIS_HOST    = "100.102.81.13"
REDIS_PORT    = 6379
REDIS_PASS    = os.environ.get("REDIS_PASS", "")
REDIS_CHANNEL = "moojoco:status"
THESIS_API    = "https://thesis.hyperbook.com/api/papers"
THESIS_TOKEN  = "c0c76a681dad4c3c569a8f580478f161e27a3fad4b5ffbb0"
RESOURCE_LIMIT = 30.0   # CPU/GPU 점유율 상한 (%)
HEARTBEAT_INTERVAL = 5  # 초

TAG_RX_PY = __import__("re").compile(r"^(.+?)\s*\(([a-z0-9-]+)\)\s*$")

# ── GPU 초기화 ─────────────────────────────────────────────────────────
try:
    pynvml.nvmlInit()
    _gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _gpu_ok = True
except Exception:
    _gpu_ok = False


def get_resource():
    cpu = psutil.cpu_percent(interval=0.3)
    gpu = 0.0
    if _gpu_ok:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_gpu_handle)
            gpu = float(util.gpu)
        except Exception:
            pass
    return cpu, gpu


def resource_status(cpu, gpu):
    if cpu > RESOURCE_LIMIT or gpu > RESOURCE_LIMIT:
        return "busy"
    return "online"


# ── Redis heartbeat (백그라운드 스레드) ────────────────────────────────
def _heartbeat_loop():
    r = None
    while True:
        try:
            if r is None:
                r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                password=REDIS_PASS, decode_responses=True)
            cpu, gpu = get_resource()
            status = resource_status(cpu, gpu)
            r.publish(REDIS_CHANNEL, status)
            # SET 으로도 저장해두면 EROS가 SUBSCRIBE 없이도 조회 가능
            r.set(REDIS_CHANNEL, json.dumps({"status": status, "cpu": cpu, "gpu": gpu}), ex=30)
        except Exception as e:
            print(f"[heartbeat] Redis 오류: {e}")
            r = None
        time.sleep(HEARTBEAT_INTERVAL)


threading.Thread(target=_heartbeat_loop, daemon=True).start()


# ── 논문 데이터 로더 ──────────────────────────────────────────────────
_papers_cache = {"ts": 0, "data": []}
CACHE_TTL = 120  # 초


def fetch_papers():
    now = time.time()
    if now - _papers_cache["ts"] < CACHE_TTL and _papers_cache["data"]:
        return _papers_cache["data"]
    try:
        r = requests.get(THESIS_API,
                         headers={"Authorization": f"Bearer {THESIS_TOKEN}"},
                         timeout=8)
        raw = r.json()
        papers = raw.get("papers", raw) if isinstance(raw, dict) else raw
        _papers_cache["data"] = [p for p in papers if p.get("tags")]
        _papers_cache["ts"] = now
    except Exception as e:
        print(f"[fetch_papers] {e}")
    return _papers_cache["data"]


def parse_tag(raw):
    m = TAG_RX_PY.match(raw.strip())
    if m:
        ko, en = m.group(1).strip(), m.group(2)
        return {"ko": ko, "en": en, "label": f"{ko}({en})"}
    en = __import__("re").sub(r"[^a-z0-9-]", "-", raw.strip().lower()).strip("-") or "unknown"
    return {"ko": raw.strip(), "en": en, "label": raw.strip()}


# ── 3D Force-directed 레이아웃 계산 ───────────────────────────────────
def force_layout_3d(nodes, edges, iterations=80):
    n = len(nodes)
    if n == 0:
        return nodes
    pos = np.random.randn(n, 3).astype(np.float32)
    id2idx = {nd["id"]: i for i, nd in enumerate(nodes)}

    k = math.sqrt(1.0 / max(n, 1))
    for _ in range(iterations):
        delta = np.zeros((n, 3), dtype=np.float32)
        # repulsion
        for i in range(n):
            diff = pos[i] - pos          # (n,3)
            dist = np.linalg.norm(diff, axis=1, keepdims=True).clip(0.01)
            delta[i] += (diff / dist ** 2 * k ** 2).sum(axis=0)
        # attraction
        for e in edges:
            si, ti = id2idx.get(e["source"]), id2idx.get(e["target"])
            if si is None or ti is None:
                continue
            d = pos[ti] - pos[si]
            dist = max(np.linalg.norm(d), 0.01)
            f = d * dist / k
            delta[si] += f
            delta[ti] -= f
        # apply
        norm = np.linalg.norm(delta, axis=1, keepdims=True).clip(0.01)
        step = np.minimum(norm, 0.5)
        pos += delta / norm * step

    for i, nd in enumerate(nodes):
        nd["x"], nd["y"], nd["z"] = float(pos[i, 0]), float(pos[i, 1]), float(pos[i, 2])
    return nodes


# ── FastAPI ───────────────────────────────────────────────────────────
app = FastAPI(title="Moojoco 3D Viz Server")

CLUSTER_COLOR = {
    "memory": "#64b5f6", "hopfield": "#64b5f6", "theory": "#64b5f6",
    "hypercode": "#64b5f6", "embedding": "#64b5f6",
    "security": "#81c784", "integrity": "#81c784", "checksum": "#81c784",
    "consensus": "#ffb74d", "governance": "#ffb74d", "roops": "#ffb74d",
    "infrastructure": "#ce93d8", "communication": "#ce93d8",
    "architecture": "#f06292", "multi-agent": "#f06292", "protocol": "#f06292",
    "simulation": "#ff8a65", "robotics": "#ff8a65", "mujoco": "#ff8a65",
    "dual-arm": "#ff8a65", "egl": "#ff8a65", "gpu-rendering": "#ff8a65",
}


@app.get("/health")
def health():
    cpu, gpu = get_resource()
    return {"status": resource_status(cpu, gpu), "cpu": round(cpu, 1), "gpu": round(gpu, 1)}


@app.get("/layout")
def layout(type: str = Query("network")):
    cpu, gpu = get_resource()
    if resource_status(cpu, gpu) == "busy":
        return JSONResponse(status_code=503,
                            content={"error": "busy", "cpu": cpu, "gpu": gpu})

    papers = fetch_papers()

    if type == "keywords":
        return _layout_keywords(papers)
    return _layout_network(papers)


def _layout_network(papers):
    nodes, edges = [], []
    seen_edges = set()
    for p in papers:
        nid = p["slug"]
        nodes.append({
            "id": nid,
            "label": p.get("title", nid),
            "author": p.get("author", ""),
            "color": "#a0c4ff",
            "paper_count": 1,
        })
    # author가 같은 논문끼리 엣지
    from collections import defaultdict
    by_author = defaultdict(list)
    for p in papers:
        by_author[p.get("author", "")].append(p["slug"])
    for author, slugs in by_author.items():
        for i in range(len(slugs)):
            for j in range(i + 1, len(slugs)):
                key = tuple(sorted([slugs[i], slugs[j]]))
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"source": slugs[i], "target": slugs[j], "weight": 1})

    nodes = force_layout_3d(nodes, edges)
    return {"nodes": nodes, "edges": edges, "type": "network"}


def _layout_keywords(papers):
    kw_freq, kw_papers, kw_label, cooccur = {}, {}, {}, {}
    for p in papers:
        parsed = [parse_tag(t) for t in p.get("tags", [])]
        ens = [t["en"] for t in parsed]
        for t in parsed:
            kw_freq[t["en"]] = kw_freq.get(t["en"], 0) + 1
            kw_label[t["en"]] = t["label"]  # 한글(영문) 형식
            kw_papers.setdefault(t["en"], []).append({"title": p.get("title", ""), "slug": p.get("slug", "")})
        for i in range(len(ens)):
            for j in range(i + 1, len(ens)):
                key = "|||".join(sorted([ens[i], ens[j]]))
                cooccur[key] = cooccur.get(key, 0) + 1

    nodes = [
        {
            "id": k, "label": kw_label.get(k, k),
            "freq": v,
            "color": CLUSTER_COLOR.get(k, "#aaa"),
            "papers": kw_papers.get(k, []),
        }
        for k, v in kw_freq.items()
    ]
    node_set = {n["id"] for n in nodes}
    edges = [
        {"source": s, "target": t, "weight": w}
        for key, w in cooccur.items()
        for s, t in [key.split("|||")]
        if s in node_set and t in node_set
    ]
    nodes = force_layout_3d(nodes, edges)
    return {"nodes": nodes, "edges": edges, "type": "keywords"}


@app.get("/viz/thesis-3d", response_class=HTMLResponse)
def viz_page():
    return HTMLResponse(content=_HTML)


# ── Three.js HTML ─────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>ROOPS Thesis 3D 네트워크</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0c14; color: #e0e0e0; font-family: 'JetBrains Mono', monospace; overflow: hidden; }
  #ui { position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 10; text-align: center; }
  #ui h1 { font-size: 0.85rem; color: #a0c4ff; margin-bottom: 8px; }
  .btn { padding: 4px 12px; border-radius: 4px; border: 1px solid #444; background: #1e2130;
         color: #aaa; font-size: 0.72rem; cursor: pointer; margin-right: 6px; }
  .btn:hover { background: #2a3050; color: #fff; }
  .btn.active { background: #2a3a6a; border-color: #64b5f6; color: #a0c4ff; }
  #status { position: fixed; bottom: 12px; left: 50%; transform: translateX(-50%); font-size: 0.68rem; color: #555; white-space: nowrap; }
  #legend { position: fixed; top: 10px; right: 14px; font-size: 0.68rem; line-height: 1.8; display: none; }
  #legend.show { display: block; }
  .lc { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
  #selRect { position: fixed; border: 2px dashed #a0c4ff; background: rgba(100,180,255,0.08);
             pointer-events: none; display: none; z-index: 50; }
  #hint { position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; color: #444; white-space: nowrap; }
  #ctrl-bar { margin-top: 8px; display: flex; flex-direction: column; gap: 5px; align-items: center; font-size: 0.68rem; color: #666; }
  .ctrl-row { display: flex; align-items: center; gap: 8px; }
  .ctrl-row label { white-space: nowrap; }
  .ctrl-row span { color: #a0c4ff; min-width: 52px; display: inline-block; text-align: left; }
  .ctrl-slider { -webkit-appearance: none; width: 100px; height: 3px; border-radius: 2px;
                 background: #2a3050; outline: none; cursor: pointer; }
  .ctrl-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 12px; height: 12px;
                 border-radius: 50%; background: #64b5f6; cursor: pointer; }
  .ctrl-slider::-moz-range-thumb { width: 12px; height: 12px; border-radius: 50%;
                 background: #64b5f6; cursor: pointer; border: none; }
  #rot-top { position: fixed; top: 10px; right: 14px; z-index: 10; font-size: 0.68rem; color: #666;
             display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
  #rot-bottom { position: fixed; bottom: 10px; right: 14px; z-index: 10; font-size: 0.68rem; color: #666;
                display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
  .search-row { display: flex; align-items: center; gap: 4px; }
  .search-input { background: #1e2130; border: 1px solid #2a3050; border-radius: 4px;
                  color: #e0e0e0; font-size: 0.68rem; padding: 3px 7px; width: 130px; outline: none;
                  font-family: inherit; }
  .search-input::placeholder { color: #444; }
  .search-input.kw:focus { border-color: #00dd88; }
  .search-input.au:focus { border-color: #ffdd00; }
  .search-clr { background: none; border: none; color: #555; font-size: 0.75rem; cursor: pointer; padding: 0 2px; }
  .search-clr:hover { color: #aaa; }
  #tooltip { position: fixed; background: #1e2130dd; border: 1px solid #444; border-radius: 8px;
             padding: 8px 12px; font-size: 0.72rem; pointer-events: none; opacity: 0;
             max-width: 240px; line-height: 1.5; z-index: 100; transition: opacity 0.15s; }
  #tooltip h3 { color: #a0c4ff; margin-bottom: 2px; font-size: 0.75rem; }
  /* ── 좌측 사이드 패널 ── */
  #panel { position: fixed; top: 0; left: -340px; width: 320px; height: 100vh;
           background: #12151fee; border-right: 1px solid #2a3050;
           overflow-y: auto; z-index: 200; transition: left 0.25s ease;
           padding: 16px 14px; }
  #panel.open { left: 0; }
  #panel-close { position: absolute; top: 10px; right: 12px; background: none; border: none;
                 color: #666; font-size: 1.1rem; cursor: pointer; }
  #panel-close:hover { color: #fff; }
  #panel h2 { color: #a0c4ff; font-size: 0.85rem; margin: 0 28px 4px 0; line-height: 1.4; }
  #panel .meta { color: #666; font-size: 0.68rem; margin-bottom: 12px; }
  #panel .paper-item { padding: 8px 10px; margin-bottom: 6px; border-radius: 6px;
                       background: #1e2438; border: 1px solid #2a3050; }
  #panel .paper-item a { color: #e0e0e0; text-decoration: none; font-size: 0.75rem; line-height: 1.4; display: block; }
  #panel .paper-item a:hover { color: #a0c4ff; }
  #panel .paper-meta { color: #555; font-size: 0.65rem; margin-top: 3px; }
  #panel .open-btn { display: inline-block; margin-top: 6px; padding: 3px 10px;
                     background: #1e3a6a; border: 1px solid #3a5a9a; border-radius: 4px;
                     color: #69b4ff; font-size: 0.68rem; text-decoration: none; }
  #panel .open-btn:hover { background: #2a4a8a; }
  canvas { display: block; }
</style>
</head>
<body>
<div id="ui">
  <h1>ROOPS Thesis 3D</h1>
  <button class="btn active" onclick="loadView('keywords', this)">키워드</button>
  <button class="btn" onclick="loadView('network', this)">논문 네트워크</button>
  <div id="ctrl-bar">
    <div class="ctrl-row">
      <label>갱신: <span id="refresh-label"></span></label>
      <input type="range" id="refresh-slider" class="ctrl-slider" min="0" max="6" step="1">
    </div>
  </div>
</div>
<div id="rot-top">
  <div class="ctrl-row">
    <label>X축: <span id="rotx-label"></span></label>
    <input type="range" id="rotx-slider" class="ctrl-slider" min="0" max="8" step="1">
  </div>
  <div class="search-row">
    <label style="white-space:nowrap;color:#666;font-size:0.68rem;">키워드:</label>
    <input type="text" id="kw-box" class="search-input kw" placeholder="검색 (초록)">
    <button class="search-clr" data-target="kw-box">✕</button>
  </div>
  <div class="ctrl-row">
    <label>전체밝기: <span id="scene-bright-label"></span></label>
    <input type="range" id="scene-bright-slider" class="ctrl-slider" min="0" max="8" step="1">
  </div>
</div>
<div id="rot-bottom">
  <div class="ctrl-row">
    <label>Y축: <span id="roty-label"></span></label>
    <input type="range" id="roty-slider" class="ctrl-slider" min="0" max="8" step="1">
  </div>
  <div class="search-row">
    <label style="white-space:nowrap;color:#666;font-size:0.68rem;">저자:</label>
    <input type="text" id="au-box" class="search-input au" placeholder="검색 (노란)">
    <button class="search-clr" data-target="au-box">✕</button>
  </div>
  <div class="ctrl-row">
    <label>선택밝기: <span id="glow-bright-label"></span></label>
    <input type="range" id="glow-bright-slider" class="ctrl-slider" min="0" max="8" step="1">
  </div>
</div>
<div id="legend">
  <span class="lc" style="background:#ff6b9d"></span>EROS<br>
  <span class="lc" style="background:#69d2e7"></span>EOS<br>
  <span class="lc" style="background:#ff8a65"></span>Moojoco<br>
  <span class="lc" style="background:#a8e063"></span>Aegis<br>
  <span class="lc" style="background:#b39ddb"></span>Hermes<br>
  <span class="lc" style="background:#ffd54f"></span>Rudex<br>
  <span class="lc" style="background:#81d4fa"></span>Mojo<br>
  <span class="lc" style="background:#607d8b"></span>Unknown<br>
</div>
<div id="panel">
  <button id="panel-close" onclick="closePanel()">✕</button>
  <div id="panel-body"></div>
</div>
<div id="selRect"></div>
<div id="status">로딩 중...</div>
<div id="hint">Shift+드래그: 영역 선택 · 선택 후 드래그: 그룹 이동 · 노드 클릭: 논문 목록</div>
<div id="tooltip"></div>

<script type="importmap">
  { "imports": { "three": "https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js",
                 "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/" } }
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const STATUS = document.getElementById('status');
const TIP    = document.getElementById('tooltip');
const PANEL  = document.getElementById('panel');
const PBODY  = document.getElementById('panel-body');

function closePanel() { PANEL.classList.remove('open'); }
window.closePanel = closePanel;  // HTML onclick에서 호출 가능하도록

function openPanel(d) {
  const THESIS = 'https://thesis.hyperbook.com/papers/';
  let html = '';
  if (currentViewType === 'network') {
    // 논문 노드 — 단일 논문 상세
    const url = THESIS + d.id;
    html = `
      <h2>${d.label || d.id}</h2>
      <div class="meta">${d.author || ''}</div>
      <div class="paper-item">
        <a href="${url}" target="_blank">${d.label || d.id}</a>
        <div class="paper-meta">${d.id}</div>
        <a class="open-btn" href="${url}" target="_blank">논문 열기 →</a>
      </div>`;
  } else {
    // 키워드 노드 — 관련 논문 목록
    const papers = d.papers || [];
    const items = papers.map(p => {
      const title = p.title || p;
      const slug  = p.slug  || '';
      const url   = slug ? THESIS + slug : '';
      return `<div class="paper-item">
        <a href="${url || '#'}" target="_blank">${title}</a>
        ${slug ? `<a class="open-btn" href="${url}" target="_blank">열기 →</a>` : ''}
      </div>`;
    }).join('');
    html = `
      <h2>${d.label || d.id}</h2>
      <div class="meta">관련 논문 ${papers.length}건</div>
      ${items || '<div style="color:#555;font-size:0.72rem">논문 없음</div>'}`;
  }
  PBODY.innerHTML = html;
  PANEL.classList.add('open');
}

// ── Scene setup ──────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0c14);
scene.fog = new THREE.FogExp2(0x0a0c14, 0.04);

const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 200);
camera.position.set(0, 0, 8);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// ambient + directional light
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dir = new THREE.DirectionalLight(0xffffff, 0.8);
dir.position.set(5, 10, 7);
scene.add(dir);

// ── Selective Bloom (레이어 기반 선택적 후광) ──────────────────────────
const BLOOM_LAYER = 1;

// Pass 1: bloom layer만 렌더 → 텍스처로 저장
const bloomComposer = new EffectComposer(renderer);
bloomComposer.renderToScreen = false;
bloomComposer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(innerWidth, innerHeight),
  1.6,  // strength
  0.6,  // radius
  0.0   // threshold (레이어로 제어하므로 0)
);
bloomComposer.addPass(bloomPass);

// Pass 2: 전체 씬 렌더 + bloom 텍스처 합성
const mixPass = new ShaderPass(new THREE.ShaderMaterial({
  uniforms: {
    baseTexture:  { value: null },
    bloomTexture: { value: bloomComposer.renderTarget2.texture }
  },
  vertexShader: `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `
    uniform sampler2D baseTexture;
    uniform sampler2D bloomTexture;
    varying vec2 vUv;
    void main() { gl_FragColor = texture2D(baseTexture, vUv) + texture2D(bloomTexture, vUv); }`
}), 'baseTexture');
mixPass.needsSwap = true;

const finalComposer = new EffectComposer(renderer);
finalComposer.addPass(new RenderPass(scene, camera));
finalComposer.addPass(mixPass);
finalComposer.addPass(new OutputPass());

window.addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  bloomComposer.setSize(innerWidth, innerHeight);
  finalComposer.setSize(innerWidth, innerHeight);
});

// ── Graph state ──────────────────────────────────────────────────────
let graphGroup = new THREE.Group();
scene.add(graphGroup);
let nodeObjects = [];  // { mesh, data }
let autoRotate = true;
let rotSpeedX = 0;
let rotSpeedY = 0.0008;
let currentViewType = 'keywords';
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// ── 위치 기억 (localStorage) ──────────────────────────────────────────
const POS_KEY = type => `moojoco-viz-pos-${type}`;

function savePositions() {
  const pos = {};
  nodeObjects.forEach(({ mesh, data }) => {
    pos[data.id] = [mesh.position.x, mesh.position.y, mesh.position.z];
  });
  try { localStorage.setItem(POS_KEY(currentViewType), JSON.stringify(pos)); } catch(e) {}
}

function restorePositions() {
  try {
    const saved = JSON.parse(localStorage.getItem(POS_KEY(currentViewType)) || 'null');
    if (!saved) return;
    let restored = 0;
    nodeObjects.forEach(({ mesh, data }) => {
      if (saved[data.id]) {
        const [x, y, z] = saved[data.id];
        mesh.position.set(x, y, z);
        const sprite = nodeIdToSprite[data.id];
        if (sprite) sprite.position.set(x, y + mesh.scale.x + 0.12, z);
        restored++;
      }
    });
    if (restored > 0) {
      updateEdges();
      STATUS.textContent += `  · 저장된 위치 ${restored}개 복원`;
    }
  } catch(e) {}
}

// ── 선택 상태 ─────────────────────────────────────────────────────────
let selectedIds = new Set();
let isBoxSelecting = false;
let boxStart = { x: 0, y: 0 };
let boxCurrent = { x: 0, y: 0 };
let groupDragOffsets = null;  // Map<id, Vector3 world-space offset>
let nodeIdToSprite = {};
const selRectEl = document.getElementById('selRect');
const _wp = new THREE.Vector3();  // 재사용 임시 벡터

function clearGraph() {
  scene.remove(graphGroup);
  graphGroup = new THREE.Group();
  scene.add(graphGroup);
  nodeObjects = [];
  edgeLineObj = null;
  edgeData = [];
  nodeIdToMesh = {};
  nodeIdToSprite = {};
  autoRotate = true;
  selectedIds.clear();
  groupDragOffsets = null;
}

// ── Load layout from API ─────────────────────────────────────────────
async function loadView(type, btn) {
  document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  STATUS.textContent = '레이아웃 계산 중...';
  clearGraph();
  currentViewType = type;
  document.getElementById('legend').classList.toggle('show', type === 'network');

  try {
    const r = await fetch(`/layout?type=${type}`);
    if (r.status === 503) { STATUS.textContent = '서버 리소스 부족 (busy)'; return; }
    const data = await r.json();
    buildGraph(data);
    STATUS.textContent = `노드 ${data.nodes.length}개 · 엣지 ${data.edges.length}개 (${type})`;
    restorePositions();  // 저장된 위치 복원
  } catch(e) {
    STATUS.textContent = '오류: ' + e.message;
  }
}

// ── 저자 색상 맵 ─────────────────────────────────────────────────────
const AUTHOR_COLORS = {
  'eros':    '#ff6b9d',  // 핑크
  'eос':     '#ff6b9d',
  'eos':     '#69d2e7',  // 시안
  'moojoco': '#ff8a65',  // 오렌지
  'aegis':   '#a8e063',  // 연두
  'hermes':  '#b39ddb',  // 보라
  'rudex':   '#ffd54f',  // 노랑
  'mojo':    '#81d4fa',  // 하늘
  'recon':   '#f48fb1',  // 연핑크
  'unknown': '#607d8b',  // 회청
};
function authorColor(author) {
  if (!author) return AUTHOR_COLORS['unknown'];
  return AUTHOR_COLORS[author.toLowerCase()] || AUTHOR_COLORS['unknown'];
}

function buildGraph(data) {
  const { nodes, edges, type } = data;
  const scale = 3.5;
  const isNetwork = (type === 'network');

  // 엣지 (LineSegments — vertexColors로 per-edge 색상 제어)
  const linePos = [], lineColors = [];
  const idToNode = {};
  nodes.forEach(n => idToNode[n.id] = n);
  edgeData = edges;
  validEdgeData = [];
  const EC = new THREE.Color(0x2a3a5a);
  edges.forEach(e => {
    const s = idToNode[e.source], t = idToNode[e.target];
    if (!s || !t) return;
    validEdgeData.push(e);
    linePos.push(s.x*scale, s.y*scale, s.z*scale, t.x*scale, t.y*scale, t.z*scale);
    lineColors.push(EC.r, EC.g, EC.b, EC.r, EC.g, EC.b);
  });
  if (linePos.length) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(linePos, 3));
    geo.attributes.position.setUsage(THREE.DynamicDrawUsage);
    const ca = new THREE.Float32BufferAttribute(lineColors, 3);
    ca.setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute('color', ca);
    const mat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.5 });
    edgeLineObj = new THREE.LineSegments(geo, mat);
    graphGroup.add(edgeLineObj);
  }

  // 저자별 도형 (논문 네트워크 뷰)
  const AUTHOR_GEO = {
    'eros':    () => new THREE.TetrahedronGeometry(1),          // 삼각뿔
    'eos':     () => new THREE.OctahedronGeometry(1),           // 팔면체
    'moojoco': () => new THREE.BoxGeometry(1.4, 1.4, 1.4),     // 정육면체
    'aegis':   () => new THREE.DodecahedronGeometry(1),         // 십이면체
    'hermes':  () => new THREE.IcosahedronGeometry(1),          // 이십면체
    'rudex':   () => new THREE.ConeGeometry(0.8, 1.6, 6),      // 육각뿔
    'mojo':    () => new THREE.TorusGeometry(0.7, 0.3, 8, 16), // 도넛
    'recon':   () => new THREE.CylinderGeometry(0.7,0.7,1.2,8),// 원기둥
  };
  function getGeo(author) {
    const fn = author && AUTHOR_GEO[author.toLowerCase()];
    return fn ? fn() : new THREE.SphereGeometry(1, 16, 12);
  }

  // 노드 (도형 + 스프라이트 라벨)
  nodes.forEach(n => {
    // 네트워크: 도형이 눈에 띄도록 크게 / 키워드: 빈도 비례
    const r = isNetwork
      ? 0.28 + (n.paper_count || 1) * 0.06
      : 0.06 + (n.freq || 1) * 0.04;
    // 논문 네트워크: 저자 색상 / 키워드: 클러스터 색상
    const hexColor = isNetwork ? authorColor(n.author) : (n.color || '#a0c4ff');
    const color = new THREE.Color(hexColor);
    const geo = isNetwork ? getGeo(n.author) : new THREE.SphereGeometry(1, 16, 12);
    const mat = new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.25,
      transparent: true, opacity: 0.85
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.scale.setScalar(r);
    mesh.position.set(n.x * scale, n.y * scale, n.z * scale);
    mesh.layers.enable(BLOOM_LAYER);  // 기본: 모든 노드 발광
    mesh.userData = { ...n, _baseEmissive: 0.25, _pulseOffset: Math.random() * Math.PI * 2,
                      _renderColor: '#' + color.getHexString(), _origScale: r };  // 실제 렌더 색 저장
    graphGroup.add(mesh);
    nodeObjects.push({ mesh, data: n });
    nodeIdToMesh[n.id] = mesh;

    // 스프라이트 라벨 — 네트워크뷰: 저자 이름도 표시
    const label = isNetwork
      ? (n.author ? `[${n.author}] ${(n.label||n.id).substring(0,18)}…` : (n.label||n.id))
      : (n.label || n.id);
    const sprite = makeLabel(label, color);
    const sW = isNetwork ? 2.0 : 1.4;
    const sH = sprite.userData._multiLine ? sW * (96/256) : sW * (64/256);
    sprite.position.set(n.x * scale, n.y * scale + r + 0.12, n.z * scale);
    sprite.scale.set(sW, sH, 1);
    graphGroup.add(sprite);
    nodeIdToSprite[n.id] = sprite;  // 노드-스프라이트 연결
  });
}

function makeLabel(text, color) {
  // "한글(영문)" 형식이면 두 줄로 분리
  const parenIdx = text.indexOf('(');
  const isMulti  = parenIdx > 0 && text.endsWith(')');
  const line1    = isMulti ? text.slice(0, parenIdx).trim() : text;
  const line2    = isMulti ? text.slice(parenIdx).trim() : null;

  const W = 256, H = isMulti ? 96 : 64;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);
  ctx.textAlign = 'center';

  if (isMulti) {
    ctx.font = 'bold 22px sans-serif';
    ctx.fillStyle = '#' + color.getHexString();
    ctx.fillText(line1, 128, 30);
    ctx.font = '17px sans-serif';
    ctx.fillStyle = '#' + color.getHexString() + 'bb';
    ctx.fillText(line2, 128, 62);
  } else {
    ctx.font = 'bold 22px sans-serif';
    ctx.fillStyle = '#' + color.getHexString();
    ctx.fillText(text, 128, 42);
  }

  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.userData._multiLine = isMulti;
  return sprite;
}

// ── 헬퍼 ─────────────────────────────────────────────────────────────
let dragNode       = null;
let didDrag        = false;
let pointerDownPos = { x: 0, y: 0 };
let pointerDownTime = 0;
const dragPlane   = new THREE.Plane();
const dragOffset  = new THREE.Vector3();
const planeNormal = new THREE.Vector3();
const intersectPt = new THREE.Vector3();

function getMeshes() { return nodeObjects.map(o => o.mesh); }

// 3D → 화면 2D 투영 (world space)
function toScreen(worldPos) {
  const v = worldPos.clone().project(camera);
  return { x: (v.x + 1) / 2 * innerWidth, y: (-v.y + 1) / 2 * innerHeight };
}

// 노드(mesh) world position 가져오기
function getWorldPos(mesh) {
  return mesh.getWorldPosition(new THREE.Vector3());
}

// 노드를 world position으로 이동 + 라벨 동기화
function setNodeByWorldPos(mesh, worldPos) {
  const local = worldPos.clone();
  graphGroup.worldToLocal(local);        // world → local 변환
  mesh.position.copy(local);
  const sprite = nodeIdToSprite[mesh.userData.id];
  if (sprite) {
    const sLocal = local.clone();
    sLocal.y += mesh.scale.x + 0.12;    // 라벨은 노드 위에
    sprite.position.copy(sLocal);
  }
}

// 선택 사각형 DOM 업데이트
function updateSelRectDOM() {
  const x1 = Math.min(boxStart.x, boxCurrent.x);
  const y1 = Math.min(boxStart.y, boxCurrent.y);
  const w  = Math.abs(boxCurrent.x - boxStart.x);
  const h  = Math.abs(boxCurrent.y - boxStart.y);
  selRectEl.style.left   = x1 + 'px';
  selRectEl.style.top    = y1 + 'px';
  selRectEl.style.width  = w  + 'px';
  selRectEl.style.height = h  + 'px';
}

// 선택 시각 효과
function updateSelectionVisual() {
  if (selectedIds.size === 0) {
    nodeObjects.forEach(({ mesh }) => {
      mesh.material.opacity = 0.85;
      mesh.scale.setScalar(mesh.userData._origScale || mesh.scale.x);
      mesh.userData._selected = false;
    });
    return;
  }
  nodeObjects.forEach(({ mesh }) => {
    const sel = selectedIds.has(mesh.userData.id);
    mesh.userData._selected = sel;
    if (sel) {
      mesh.material.opacity = 1.0;
      // 원본 스케일 저장 후 1.5배 확대
      if (!mesh.userData._origScale) mesh.userData._origScale = mesh.scale.x;
      mesh.scale.setScalar(mesh.userData._origScale * 1.5);
    } else {
      mesh.material.opacity = 0.2;
      if (mesh.userData._origScale) mesh.scale.setScalar(mesh.userData._origScale);
    }
  });
}

// 선택 영역 안 노드 판별 — world position 기준
function pickNodesInBox() {
  const x1 = Math.min(boxStart.x, boxCurrent.x);
  const x2 = Math.max(boxStart.x, boxCurrent.x);
  const y1 = Math.min(boxStart.y, boxCurrent.y);
  const y2 = Math.max(boxStart.y, boxCurrent.y);
  selectedIds.clear();
  nodeObjects.forEach(({ mesh, data }) => {
    const s = toScreen(getWorldPos(mesh));   // world position으로 투영
    if (s.x >= x1 && s.x <= x2 && s.y >= y1 && s.y <= y2) {
      selectedIds.add(data.id);
    }
  });
  updateSelectionVisual();
}

// ── 이벤트 핸들러 ─────────────────────────────────────────────────────
renderer.domElement.addEventListener('pointerdown', e => {
  // ① Shift+드래그 → 박스 선택 시작
  if (e.shiftKey) {
    isBoxSelecting = true;
    boxStart = boxCurrent = { x: e.clientX, y: e.clientY };
    selRectEl.style.display = 'block';
    updateSelRectDOM();
    controls.enabled = false;
    autoRotate = false;
    e.preventDefault();
    return;
  }

  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(getMeshes());

  if (!hits.length) {
    // 빈 곳 클릭 → 선택 해제 + 스케일 복원
    selectedIds.clear();
    updateSelectionVisual();
    return;
  }

  const mesh = hits[0].object;
  const nodeId = mesh.userData.id;
  autoRotate = false;
  controls.enabled = false;
  didDrag = false;
  pointerDownPos  = { x: e.clientX, y: e.clientY };
  pointerDownTime = Date.now();

  // ── 드래그 평면: 카메라 시선 방향 수직, world space 기준 ──
  camera.getWorldDirection(planeNormal);
  const meshWorldPos = getWorldPos(mesh);
  dragPlane.setFromNormalAndCoplanarPoint(planeNormal, meshWorldPos);
  raycaster.ray.intersectPlane(dragPlane, intersectPt);
  dragOffset.copy(meshWorldPos).sub(intersectPt);   // world space offset

  if (selectedIds.has(nodeId) && selectedIds.size > 1) {
    // ② 선택된 그룹 노드 클릭 → 그룹 드래그 (world space 기준 offset)
    groupDragOffsets = new Map();
    selectedIds.forEach(id => {
      const m = nodeIdToMesh[id];
      if (m) groupDragOffsets.set(id, getWorldPos(m).sub(meshWorldPos));
    });
    dragNode = { mesh, isGroup: true };
  } else {
    // ③ 단일 노드 드래그
    selectedIds.clear();
    updateSelectionVisual();
    groupDragOffsets = null;
    dragNode = { mesh, isGroup: false };
  }
  e.preventDefault();
});

renderer.domElement.addEventListener('pointermove', e => {
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;

  // 박스 선택 중
  if (isBoxSelecting) {
    boxCurrent = { x: e.clientX, y: e.clientY };
    updateSelRectDOM();
    return;
  }

  // 노드 드래그 중
  if (dragNode) {
    raycaster.setFromCamera(mouse, camera);
    if (!raycaster.ray.intersectPlane(dragPlane, intersectPt)) return;
    const newWorldBase = intersectPt.clone().add(dragOffset);  // world space

    if (dragNode.isGroup && groupDragOffsets) {
      groupDragOffsets.forEach((offset, id) => {
        const m = nodeIdToMesh[id];
        if (m) setNodeByWorldPos(m, newWorldBase.clone().add(offset));
      });
    } else {
      setNodeByWorldPos(dragNode.mesh, newWorldBase);
    }
    didDrag = true;
    updateEdges();
    TIP.style.opacity = 0;
    return;
  }

  // hover 툴팁
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(getMeshes());
  if (hits.length) {
    const d = hits[0].object.userData;
    let papersHtml = '';
    if (currentViewType === 'network') {
      papersHtml = `<div style="color:#69d2e7;font-size:0.68rem;margin-top:4px">클릭 → 좌측 패널</div>`;
    } else {
      // 키워드 노드: 관련 논문 클릭 링크
      papersHtml = (d.papers || []).map(p => {
        const title = p.title || p;
        const slug  = p.slug  || '';
        const url   = slug ? `https://thesis.hyperbook.com/papers/${slug}` : '';
        return url
          ? `<div style="padding-left:6px"><a href="${url}" target="_blank"
               style="color:#a0c4ff;font-size:0.68rem;text-decoration:none">📄 ${title}</a></div>`
          : `<div style="color:#bbb;font-size:0.68rem;padding-left:6px">📄 ${title}</div>`;
      }).join('');
    }
    TIP.style.opacity = 1;
    TIP.style.left = (e.clientX + 14) + 'px';
    TIP.style.top  = Math.min(e.clientY - 10, innerHeight - 200) + 'px';
    TIP.innerHTML  = `<h3>${d.label || d.id}</h3><div style="color:#888;font-size:0.7rem">빈도: ${d.freq || d.paper_count || 1}</div>${papersHtml}`;
  } else {
    TIP.style.opacity = 0;
  }
});

renderer.domElement.addEventListener('pointerup', e => {
  if (isBoxSelecting) {
    isBoxSelecting = false;
    selRectEl.style.display = 'none';
    controls.enabled = true;
    boxCurrent = { x: e.clientX, y: e.clientY };
    pickNodesInBox();
    return;
  }
  if (dragNode) {
    controls.enabled = true;
    autoRotate = true;
    const wasDrag = didDrag;
    dragNode = null;
    groupDragOffsets = null;
    didDrag = false;
    if (wasDrag) savePositions();
  }
});

// 클릭 → 패널 열기 (드래그와 구분은 브라우저 click 이벤트가 담당)
renderer.domElement.addEventListener('click', e => {
  if (didDrag) return;  // 드래그 후 발생하는 click은 무시
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(getMeshes());
  if (hits.length) {
    openPanel(hits[0].object.userData);
  } else {
    closePanel();
  }
});

// 엣지 위치 동적 업데이트
let edgeLineObj = null;
let edgeData = [];
let validEdgeData = [];
let nodeIdToMesh = {};

function updateEdges() {
  if (!edgeLineObj || !edgeData.length) return;
  const pos = edgeLineObj.geometry.attributes.position;
  let i = 0;
  edgeData.forEach(e => {
    const s = nodeIdToMesh[e.source], t = nodeIdToMesh[e.target];
    if (!s || !t) { i += 6; return; }
    pos.setXYZ(i/3,   s.position.x, s.position.y, s.position.z);
    pos.setXYZ(i/3+1, t.position.x, t.position.y, t.position.z);
    i += 6;
  });
  pos.needsUpdate = true;
}

// ── Animation loop ───────────────────────────────────────────────────
(function animate() {
  requestAnimationFrame(animate);
  controls.update();
  if (autoRotate) {
    graphGroup.rotation.x += rotSpeedX;
    graphGroup.rotation.y += rotSpeedY;
  }

  // 저자별 블링크 속도 (논문 네트워크 뷰)
  const AUTHOR_BLINK = {
    'eros':    0.012, 'eос': 0.012,
    'eos':     0.009,
    'moojoco': 0.006,
    'aegis':   0.004,
    'hermes':  0.007,
    'rudex':   0.005,
    'mojo':    0.008,
    'recon':   0.010,
  };

  const now = Date.now();
  nodeObjects.forEach(({ mesh }) => {
    const d = mesh.userData;

    if (d._selected) {
      // 선택: 노란 glow + 빠른 맥박
      const p = 0.7 + 0.3 * Math.sin(now * 0.005 * 5 + (d._pulseOffset || 0));
      mesh.material.emissiveIntensity = p;
      mesh.material.emissive.setRGB(1, 1, 0.3);
      return;
    }

    // 실제 렌더 색 사용 (_renderColor = buildGraph에서 저장한 author/cluster 색)
    const rc = new THREE.Color(d._renderColor || '#a0c4ff');
    mesh.material.emissive.copy(rc);

    if (d.author) {
      // 논문 네트워크 뷰 — 저자별 블링크 + 무지개 색상 사이클
      const speed = AUTHOR_BLINK[d.author.toLowerCase()] || 0.005;
      const blink  = 0.5 + 0.5 * Math.sin(now * speed + (d._pulseOffset || 0));
      const intensity = 0.1 + 0.9 * Math.pow(blink, 2);
      mesh.material.emissiveIntensity = intensity;

      // hue를 시간+개별 offset으로 회전 → 각 저자마다 다른 위상의 무지개
      const hue = ((now * 0.0004 + (d._pulseOffset || 0)) % (Math.PI * 2)) / (Math.PI * 2);
      mesh.material.emissive.setHSL(hue, 1.0, 0.55);
      mesh.material.color.setHSL(hue, 0.85, 0.45);
    } else {
      // 키워드 뷰 — 부드러운 공통 펄스 (색상 고정)
      mesh.material.emissiveIntensity = 0.2 + 0.15 * Math.sin(now * 0.002 + (d._pulseOffset || 0));
      mesh.material.emissive.set(d._renderColor || '#a0c4ff');
    }
  });

  // Selective bloom: bloom layer만 렌더 후 합성
  camera.layers.set(BLOOM_LAYER);
  bloomComposer.render();
  camera.layers.enableAll();
  finalComposer.render();
})();

// ── 갱신 간격 슬라이더 ───────────────────────────────────────────────
const REFRESH_STEPS  = [10, 30, 60, 300, 600, 1800, 3600];
const REFRESH_LABELS = ['10초', '30초', '1분', '5분', '10분', '30분', '1시간'];
let refreshTimer = null;

function setRefreshInterval(idx) {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => loadView(currentViewType, null), REFRESH_STEPS[idx] * 1000);
  document.getElementById('refresh-label').textContent = REFRESH_LABELS[idx];
  localStorage.setItem('refreshStep', idx);
}

const refreshSlider = document.getElementById('refresh-slider');
const savedRefreshStep = Math.min(6, Math.max(0, parseInt(localStorage.getItem('refreshStep') ?? '2')));
refreshSlider.value = savedRefreshStep;
setRefreshInterval(savedRefreshStep);
refreshSlider.addEventListener('input', e => setRefreshInterval(parseInt(e.target.value)));

// ── 밝기 슬라이더 ────────────────────────────────────────────────────
// 전체밝기: ambient + directional 강도 조절 (idx 0~8, 중앙=4 기본)
// 선택밝기: bloom strength 조절 (매칭/전체 노드 후광 세기)
const BRIGHT_VALS  = [0.05, 0.15, 0.3, 0.5, 0.7, 0.9, 1.1, 1.4, 1.8];
const BRIGHT_LABELS = ['극어둠','매우어둠','어둠','약간어둠','기본','약간밝음','밝음','매우밝음','최대'];
const ambientLight = scene.children.find(c => c.isAmbientLight);
const dirLight     = scene.children.find(c => c.isDirectionalLight);
const BASE_AMBIENT = 0.6, BASE_DIR = 0.8;

function setSceneBright(idx) {
  const v = BRIGHT_VALS[idx];
  if (ambientLight) ambientLight.intensity = BASE_AMBIENT * v / 0.7;
  if (dirLight)     dirLight.intensity     = BASE_DIR     * v / 0.7;
  document.getElementById('scene-bright-label').textContent = BRIGHT_LABELS[idx];
  localStorage.setItem('sceneBrightStep', idx);
}

const GLOW_VALS   = [0.0, 0.3, 0.6, 0.9, 1.2, 1.6, 2.0, 2.5, 3.0];
const GLOW_LABELS = ['끔','극약','약','보통약','기본','보통강','강','매우강','최대'];

function setGlowBright(idx) {
  bloomPass.strength = GLOW_VALS[idx];
  document.getElementById('glow-bright-label').textContent = GLOW_LABELS[idx];
  localStorage.setItem('glowBrightStep', idx);
}

const sceneBrightSlider = document.getElementById('scene-bright-slider');
const glowBrightSlider  = document.getElementById('glow-bright-slider');
const savedSceneBright  = Math.min(8, Math.max(0, parseInt(localStorage.getItem('sceneBrightStep') ?? '4')));
const savedGlowBright   = Math.min(8, Math.max(0, parseInt(localStorage.getItem('glowBrightStep') ?? '4')));
sceneBrightSlider.value = savedSceneBright; setSceneBright(savedSceneBright);
glowBrightSlider.value  = savedGlowBright;  setGlowBright(savedGlowBright);
sceneBrightSlider.addEventListener('input', e => setSceneBright(parseInt(e.target.value)));
glowBrightSlider.addEventListener('input',  e => setGlowBright(parseInt(e.target.value)));

// ── X/Y 축 회전 슬라이더 ─────────────────────────────────────────────
// idx 0~8, 중앙(4) = 정지, 단위 = 0.0004 rad/frame
const ROT_SPEED_UNIT = 0.0004;
const ROT_LABELS = ['◀ 빠름', '◀ 보통', '◀ 느림', '◀ 미세', '정지', '▶ 미세', '▶ 느림', '▶ 보통', '▶ 빠름'];

function idxToSpeed(idx) { return (idx - 4) * ROT_SPEED_UNIT; }

function setRotX(idx) {
  rotSpeedX = idxToSpeed(idx);
  document.getElementById('rotx-label').textContent = ROT_LABELS[idx];
  localStorage.setItem('rotXStep', idx);
}

function setRotY(idx) {
  rotSpeedY = idxToSpeed(idx);
  document.getElementById('roty-label').textContent = ROT_LABELS[idx];
  localStorage.setItem('rotYStep', idx);
}

const rotXSlider = document.getElementById('rotx-slider');
const rotYSlider = document.getElementById('roty-slider');

// 기본값: X=정지(4), Y=▶느림(6 = 0.0008 rad/frame)
const savedRotX = Math.min(8, Math.max(0, parseInt(localStorage.getItem('rotXStep') ?? '4')));
const savedRotY = Math.min(8, Math.max(0, parseInt(localStorage.getItem('rotYStep') ?? '6')));
rotXSlider.value = savedRotX; setRotX(savedRotX);
rotYSlider.value = savedRotY; setRotY(savedRotY);
rotXSlider.addEventListener('input', e => setRotX(parseInt(e.target.value)));
rotYSlider.addEventListener('input', e => setRotY(parseInt(e.target.value)));

// ── 검색 & 엣지 하이라이트 ───────────────────────────────────────────
const DEFAULT_EC  = new THREE.Color(0x2a3a5a);
const HIDE_EC     = new THREE.Color(0x0a0c14);  // 배경색 = 숨김
const KEYWORD_EC  = new THREE.Color(0x00dd88);  // 초록
const AUTHOR_EC   = new THREE.Color(0xffdd00);  // 노랑

let kwQuery      = '';
let auQuery      = '';
let searchActive = false;
let glowNodeIds  = new Set();

function applySearch() {
  if (!edgeLineObj || !validEdgeData.length) return;
  const kq = kwQuery.trim().toLowerCase();
  const aq = auQuery.trim().toLowerCase();
  const anyActive = !!(kq || aq);
  searchActive = anyActive;
  const ca = edgeLineObj.geometry.attributes.color;

  // 매칭 노드 수집
  const kwIds = new Set(), auIds = new Set();
  nodeObjects.forEach(({ mesh }) => {
    const d = mesh.userData;
    if (kq) {
      const text = ((d.label || '') + ' ' + (d.id || '')).toLowerCase();
      if (text.includes(kq)) kwIds.add(d.id);
    }
    if (aq) {
      const author = (d.author || d.label || '').toLowerCase();
      if (author.includes(aq)) auIds.add(d.id);
    }
  });
  glowNodeIds = new Set([...kwIds, ...auIds]);

  // 엣지 색상 — 저자(노랑) > 키워드(초록) > 숨김
  validEdgeData.forEach((e, i) => {
    let c;
    if (!anyActive)                                                   c = DEFAULT_EC;
    else if (auIds.has(e.source) || auIds.has(e.target))             c = AUTHOR_EC;
    else if (kwIds.has(e.source) || kwIds.has(e.target))             c = KEYWORD_EC;
    else                                                              c = HIDE_EC;
    ca.setXYZ(i*2,   c.r, c.g, c.b);
    ca.setXYZ(i*2+1, c.r, c.g, c.b);
  });
  ca.needsUpdate = true;

  // 매칭 노드 크기 강조 + bloom layer 제어
  nodeObjects.forEach(({ mesh }) => {
    const base  = mesh.userData._origScale || 1.0;
    const hit   = anyActive && glowNodeIds.has(mesh.userData.id);
    mesh.scale.setScalar(hit ? base * 1.6 : base);
    if (!anyActive || hit) mesh.layers.enable(BLOOM_LAYER);
    else                   mesh.layers.disable(BLOOM_LAYER);
  });
}

document.getElementById('kw-box').addEventListener('input', e => { kwQuery = e.target.value; applySearch(); });
document.getElementById('au-box').addEventListener('input', e => { auQuery = e.target.value; applySearch(); });
document.querySelectorAll('.search-clr').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = document.getElementById(btn.dataset.target);
    target.value = '';
    if (btn.dataset.target === 'kw-box') kwQuery = '';
    else auQuery = '';
    applySearch();
  });
});

// 초기 로드
loadView('keywords', null);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import threading, os

    use_https = os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)

    print(f"Moojoco 3D Viz Server")
    print(f"  HTTP  → http://hb5u.hyperbook.com:{PORT}/viz/thesis-3d")
    if use_https:
        print(f"  HTTPS → https://hb5u.hyperbook.com:{HTTPS_PORT}/viz/thesis-3d")
        print(f"  HTTPS → https://hb5u.tail35af02.ts.net:{HTTPS_PORT}/viz/thesis-3d")

    def run_https():
        uvicorn.run(app, host="0.0.0.0", port=HTTPS_PORT,
                    ssl_certfile=CERT_FILE, ssl_keyfile=KEY_FILE,
                    log_level="warning")

    if use_https:
        t = threading.Thread(target=run_https, daemon=True)
        t.start()

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
