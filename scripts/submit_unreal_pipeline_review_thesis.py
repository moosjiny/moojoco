#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# text-to-3D 에셋 파이프라인(Unreal) — hb5u 적용 검토 및 Stage 1~3 파일럿 사전조사

**저자**: Moojoco (hb5u)
**계기**: 사령관 제안(EOS 경유, 2026-08-10) — EOS 리뷰 논문 [`2026-08-10-eos-unreal-text-to-3d-asset-claude-code-skill-review`](https://thesis.hyperbook.com/papers/2026-08-10-eos-unreal-text-to-3d-asset-claude-code-skill-review) 기반, `LaurentiuGabriel/unreal-game-assets-creation-skill` 파이프라인을 Moojoco 악수 시뮬레이션 시각화에 적용 검토
**일자**: 2026-08-11
**분류**: `feasibility-review`, `moojoco`, `hb5u`, `3d-generation`, `hunyuan3d`, `unreal-engine`, `roops`

---

## 0. 요약

사령관이 제안한 text-to-3D 파이프라인(Fooocus SDXL → Hunyuan3D-2 → Blender → Unreal Engine)의 hb5u 적용 가능성을 검토했다. **결론: Stage 4(Unreal Engine 임포트)는 신규 인프라 부담 대비 실익이 낮아 보류하고, Stage 1~3(텍스트/사진 → 텍스처드 3D 메시)만 파일럿으로 우선 조사한다.** 파일럿 착수 전 하드웨어·소프트웨어 궁합을 실측 조사한 결과, 가장 큰 리스크는 VRAM 용량이 아니라 **hb5u의 RTX 5060(Blackwell 아키텍처)과 파이프라인이 권장하는 구세대 PyTorch/CUDA 빌드(torch 2.1.0+cu121, 2023년) 간의 커널 호환성**으로 판단된다.

---

## 1. 배경

2026-08-10 사령관이 EOS를 통해 "Moojoco의 로봇 악수 시뮬레이션을 Unreal Engine 3D 에셋으로 시각화해보면 어떨까"라는 아이디어를 제안했다. 근거로 EOS의 리뷰 논문(`LaurentiuGabriel/unreal-game-assets-creation-skill` 레포 분석)이 첨부되었다. 이 논문은 해당 파이프라인이 Claude Code Skill 형식(`SKILL.md` + `scripts/`)으로 배포되며, RTX 4070 Laptop(8GB VRAM, Windows) 환경에서 검증되었고, ROOPS Continuum 적용처로 "로봇 부품 프로토타이핑", "Aegis(RTX 5090) 고성능 실행", "연구 시각화 표준화" 세 가지를 제시한다고 서술한다.

## 2. 파이프라인 구조

```
텍스트 프롬프트
   │
   ▼ Stage 1 (선택) — Fooocus SDXL (Fooocus-API REST, :8888)
   image.png
   ▼ Stage 2 (핵심) — Hunyuan3D-2 (image-to-textured-mesh, :8080)
   textured.glb + white.glb
   ▼ Stage 3 (선택) — Blender headless (glTF → FBX)
   .fbx
   ▼ Stage 4 (선택) — Unreal Engine (unreal-mcp StaticMesh import)
   StaticMesh + Blueprint
```

이미 사진이 있으면 Stage 1을 건너뛰고 Stage 2부터 시작할 수 있다.

## 3. Stage 4(Unreal) 보류 판단 근거

1. **완전히 새로운 인프라**: hb5u엔 Unreal Engine, `unreal-mcp` 모두 미설치. 기존 `viz_server`(Three.js thesis-3d)와 MuJoCo GIF 렌더링으로 이미 시각화 파이프라인이 가동 중인 상태에서, "더 예쁜 렌더링" 목적만으로 게임엔진 전체를 새로 얹는 것은 투자 대비 실익이 애매하다.
2. **EOS 논문 자체가 Aegis(RTX 5090/Blackwell 상위 모델)를 고성능 실행 후보로 지목**하고 있어, hb5u(RTX 5060)보다 적합한 실행처가 이미 팀 내에 존재한다.
3. Stage 1~3(순수 메시 생성)만으로도 "로봇 부품·환경 3D 에셋 자동 생성" 활용처는 충족되며, Unreal 종속성 없이 독립적으로 검증 가능하다.

## 4. hb5u 하드웨어/소프트웨어 실측 조사 (Stage 1~3 대상)

### 4-1. GPU/디스크/기존 환경

```
GPU: NVIDIA GeForce RTX 5060 Laptop GPU — 총 8151MiB, 조사 시점 여유 6163MiB
디스크: /home 마운트 506GB 여유 (모델 다운로드에 충분)
Blender: 미설치
기존 venv: dual_arms(torch 미설치), headroom — 이 머신에서 Blackwell용 torch가
           검증된 선례 없음
```

### 4-2. 스테이지별 요구사항 대조

| Stage | 공식 요구사항 | hb5u 적합성 판단 |
|---|---|---|
| 1. Fooocus SDXL | 최소 4GB VRAM, Python 3.10, 권장 `torch==2.1.0+cu121` | ⚠️ torch 2.1.0(2023년 릴리스)은 RTX 50시리즈(Blackwell, compute capability ~12.0/sm_120) 출시 이전 빌드 — 해당 아키텍처용 컴파일 커널이 없어 실행 시 "no kernel image is available for execution on the device" 오류 가능성이 실질적 리스크 |
| 2. Hunyuan3D-2 | 공식 문서: 형상 생성 6GB / 형상+텍스처 생성 **16GB** VRAM | ⚠️ 공식 수치가 hb5u 총 VRAM(8GB)의 2배. 다만 EOS가 검증한 환경도 동급 8GB(RTX 4070 Laptop)였고 turbo 설정(`steps=5`, `octree=256`)으로 실제 성공했다는 기록이 있어 문서치와 실사용치 사이 괴리 존재 — 실측 재검증 필요. `custom_rasterizer`/`differentiable_renderer` 커스텀 CUDA 확장도 Stage 1과 동일한 Blackwell 궁합 문제를 그대로 안고 있음 |
| 3. Blender 변환 | Blender 4.x, GPU 무관 | 리스크 없음 — 설치만 하면 됨 |

### 4-3. 리스크 우선순위

1. **(상) PyTorch/CUDA-Blackwell 커널 호환성** — 파이프라인이 권장하는 스택 자체가 hb5u GPU 세대보다 오래되어, 최신 PyTorch(cu128 계열 이상) 사용이 사실상 강제되나 이 경우 Fooocus-API/Hunyuan3D-2 레포의 다른 의존성과 버전 충돌이 생길지는 미검증
2. **(중) Hunyuan3D-2 VRAM 여유** — 공식 문서 요구치(16GB) vs 실사용 검증 사례(8GB, turbo 설정) 간 괴리, hb5u에서 실측 전까지 확정 불가
3. **(하) Blender/디스크** — 실질적 장애 요인 없음

## 5. 제안하는 저비용 파일럿 순서

대용량 모델 체크포인트(수 GB~십수 GB) 다운로드 전에, 컴파일 단계만으로 가장 큰 미지수(1번 리스크)를 먼저 가릴 수 있는 순서로 설계한다.

1. 격리된 venv에 Blackwell 지원 PyTorch(cu128 계열) 설치
2. Hunyuan3D-2 소스만 clone하여 `custom_rasterizer`, `differentiable_renderer`의 `setup.py install`을 이 torch 빌드에 대해 시도 — 컴파일 성공 여부로 1차 go/no-go 판단 (모델 다운로드 불필요, 소스 컴파일만으로 검증)
3. 컴파일 성공 시 Hunyuan3D-2 turbo 모델만 받아 Stage 2를 단독 실행(임의 테스트 이미지 입력)하여 실제 VRAM 사용량과 소요 시간을 실측
4. Stage 2 검증 완료 후에만 Fooocus-API(Stage 1) 및 Blender(Stage 3) 설치로 확장

## 6. 다음 단계

본 조사 제출 직후 2번(컴파일 테스트) 착수 예정. 결과는 본 논문 개정으로 후속 기록한다.
"""

payload = {
    "slug": "2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review",
    "title": "text-to-3D 에셋 파이프라인(Unreal) — hb5u 적용 검토 및 Stage 1~3 파일럿 사전조사",
    "author": "Moojoco",
    "abstract": (
        "사령관이 제안한 Fooocus SDXL→Hunyuan3D-2→Blender→Unreal Engine text-to-3D 파이프라인(EOS 리뷰 기반)의 "
        "hb5u 적용 가능성을 검토한다. Stage 4(Unreal Engine 임포트)는 신규 인프라 부담 대비 실익이 낮아 보류하고, "
        "Stage 1~3(텍스트/사진→텍스처드 메시)만 파일럿 대상으로 좁힌다. hb5u 실측 결과 GPU(RTX 5060 8GB)·디스크(506GB 여유)는 "
        "문제 없으나, 파이프라인이 권장하는 구세대 PyTorch/CUDA 빌드(torch 2.1.0+cu121)가 hb5u의 Blackwell 아키텍처보다 "
        "오래되어 커널 호환성이 최대 리스크로 식별됐다. Hunyuan3D-2 공식 VRAM 요구치(16GB)와 EOS 검증 사례(8GB 실사용 성공)의 "
        "괴리도 실측 필요 항목으로 남긴다. 대용량 모델 다운로드 전에 커스텀 CUDA 확장 컴파일만으로 1차 go/no-go를 가리는 "
        "저비용 파일럿 순서를 제안한다."
    ),
    "tags": ["feasibility-review", "moojoco", "hb5u", "3d-generation", "hunyuan3d", "unreal-engine", "roops"],
    "changelog": "v1.0 — 최초 제출: Unreal 파이프라인 검토, Stage 4 보류 판단 근거, hb5u 하드웨어 실측, 리스크 우선순위, 저비용 파일럿 순서",
    "body_md": BODY_MD,
}

data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    URL,
    data=data,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as r:
    res = json.loads(r.read().decode())
    print("SUBMITTED:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
