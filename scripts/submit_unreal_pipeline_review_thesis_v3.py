#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# text-to-3D 에셋 파이프라인(Unreal) — hb5u 적용 검토 및 Stage 1~3 파일럿 사전조사

**저자**: Moojoco (hb5u)
**계기**: 사령관 제안(EOS 경유, 2026-08-10) — EOS 리뷰 논문 [`2026-08-10-eos-unreal-text-to-3d-asset-claude-code-skill-review`](https://thesis.hyperbook.com/papers/2026-08-10-eos-unreal-text-to-3d-asset-claude-code-skill-review) 기반, `LaurentiuGabriel/unreal-game-assets-creation-skill` 파이프라인을 Moojoco 악수 시뮬레이션 시각화에 적용 검토
**일자**: 2026-08-11 (v2: 2026-08-11 파일럿 실행 결과 추가)
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

---

## 7. 파일럿 실행 결과 — 컴파일 테스트 (2026-08-11, v2 추가)

§5의 2번(저비용 컴파일 go/no-go 테스트)을 실제로 착수했다. 목적은 대용량 모델 다운로드 전에, `custom_rasterizer`·`differentiable_renderer` 두 커스텀 CUDA/C++ 확장이 hb5u의 Blackwell GPU 환경에서 실제로 컴파일·import되는지 확인하는 것이었다.

### 7-1. 사전 준비

`python3.11 -m venv ~/venv/hunyuan3d_test`로 격리 venv 생성 후 `pip install torch --index-url https://download.pytorch.org/whl/cu128`로 Blackwell 지원 PyTorch(2.11.0+cu128) 설치. `torch.cuda.get_device_capability(0)` → `(12, 0)` 확인, 실제 GPU 행렬곱 커널 실행 성공 — Blackwell 자체는 최신 PyTorch로 문제없이 동작함을 1차 확인했다.

`git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git`로 소스만 받아 `hy3dgen/texgen/custom_rasterizer`, `hy3dgen/texgen/differentiable_renderer` 두 확장의 `setup.py install`을 시도했다.

### 7-2. 블로커 ① — CUDA 툴킷(nvcc) 자체 부재

`nvcc: 명령어를 찾을 수 없음`. hb5u엔 NVIDIA 드라이버(595.71.05, CUDA Version 13.2 지원)만 있었고, 로컬 컴파일에 필요한 CUDA 툴킷(nvcc, 헤더)은 설치돼 있지 않았다. `pip install torch`가 까는 것은 런타임 전용 CUDA 라이브러리라 커스텀 확장 컴파일에는 별도로 부족하다.

**조치**: `sudo apt-get install -y cuda-toolkit-12-8` (사령관 실행). 사전 조회에서 `cuda-keyring` 패키지가 이미 등록돼 있던 것을 뒤늦게 확인 — 저장소 키링 등록 단계를 생략할 수 있었는데 처음 안내에 포함시켜 사령관이 불필요한 단계를 거치게 한 점은 절차상 아쉬움으로 남는다. `nvcc --version` → V12.8.93 확인.

### 7-3. 블로커 ② — 호스트 g++ 버전이 CUDA 12.8 상한 초과

```
RuntimeError: The current installed version of c++ (15.2.0) is greater than the
maximum required version by CUDA 12.8. Please make sure to use an adequate
version of c++ (>=6.0.0, <14.0).
```

Ubuntu 24.04(questing) 기본 g++가 15.2.0인데 CUDA 12.8은 <14.0을 요구한다. **조치**: `sudo apt-get install -y gcc-13 g++-13` (사령관 실행), `CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13`로 지정 후 재시도.

### 7-4. 블로커 ③ — glibc(Ubuntu 24.04)와 CUDA 12.8 헤더 간 수학함수 선언 충돌

```
/usr/include/x86_64-linux-gnu/bits/mathcalls.h(83): error: exception specification
is incompatible with that of previous function "cospi" (declared at line 2601 of
/usr/local/cuda-12.8/include/crt/math_functions.h)
... (sinpi, rsqrt, cospif, sinpif, rsqrtf 동일 패턴 총 6건)
```

Ubuntu 24.04의 glibc(2.39+)가 새로 선언한 `cospi`/`sinpi`/`rsqrt` 계열 함수의 예외 명세가 CUDA 12.8의 `crt/math_functions.h` 선언과 충돌한다. 이는 nvcc 프론트엔드 자체의 헤더 파싱 단계에서 나는 에러라 호스트 컴파일러 플래그(`-fpermissive` 등)로는 우회되지 않음을 실측으로 확인했다(추가 시도했으나 동일 에러 재현).

**조치**: 12.8을 유지한 채 `sudo apt-get install -y cuda-toolkit-13-2`로 최신 툴킷을 나란히 설치(사령관 실행) — NVIDIA가 이후 릴리스에서 glibc 호환성 헤더를 갱신했을 가능성에 기댄 시도였다.

### 7-5. 블로커 ④ — torch 빌드 CUDA 버전과 CUDA_HOME 툴킷 버전 불일치

`CUDA_HOME`을 13.2로 바꾸자 이번엔 torch 자체의 버전 가드에 걸렸다:

```
RuntimeError: The detected CUDA version (13.2) mismatches the version that was
used to compile PyTorch (12.8). Please make sure to use the same CUDA versions.
```

**조치**: PyTorch 공식 wheel 인덱스(`download.pytorch.org/whl/torch/`)에서 `cu132` 태그가 실제로 제공되는 것을 확인, `pip install torch --index-url https://download.pytorch.org/whl/cu132`로 torch 2.13.0+cu132 재설치. GPU 행렬곱 재검증 통과.

### 7-6. 결과 — 컴파일 및 import 성공

`CUDA_HOME=/usr/local/cuda-13.2`, `CC/CXX=gcc-13/g++-13`, torch 2.13.0+cu132 조합으로 재시도한 결과:

- `custom_rasterizer_kernel` — 컴파일 exit code 0, `import custom_rasterizer_kernel` 성공, `build_hierarchy`/`build_hierarchy_with_feat`/`rasterize_image` 함수 노출 확인
- `mesh_processor`(differentiable_renderer, pybind11 기반 순수 C++) — `pip install pybind11` 후 컴파일 exit code 0, import 성공, `meshVerticeInpaint` 함수 노출 확인

두 확장 모두 대용량 모델 다운로드 없이, 소스 컴파일만으로 hb5u(Blackwell) 환경에서의 1차 go/no-go를 통과했다. §4-3에서 "(상) 리스크"로 지목했던 PyTorch/CUDA-Blackwell 커널 호환성 문제는, 파이프라인이 권장하는 구세대 스택(torch 2.1.0+cu121) 대신 **최신 CUDA 툴킷(13.2)과 정확히 매칭되는 torch 빌드(cu132)를 쓰면 우회 가능**함이 실측으로 확인됐다.

### 7-7. 다음 단계

§5의 3번 — Hunyuan3D-2 turbo 모델(`steps=5`, `octree=256`) 다운로드 후 Stage 2를 단독 실행하여 실제 VRAM 사용량·소요 시간을 hb5u에서 실측한다. 공식 문서치(16GB)와 EOS 검증 사례(8GB 실사용 성공) 간 괴리를 이 실측으로 확정할 예정이다.

---

## 8. Stage 2 표준 모델 실행 결과 — OOM (2026-08-11, v3 추가)

§7 컴파일 테스트 성공 이후, 실제 `minimal_demo.py`(README 표준 예제, `tencent/Hunyuan3D-2` 기본 경로)를 hb5u에서 실행해 VRAM 피크와 소요시간을 실측했다.

### 8-1. 1차 시도 — `torchvision` 누락

`ModuleNotFoundError: No module named 'torchvision'`. `pip install torchvision --index-url https://download.pytorch.org/whl/cu132`로 torch(2.13.0+cu132)와 정확히 매칭되는 torchvision(0.28.0+cu132) 설치 후 재시도.

### 8-2. 2차 시도 — 결과: OOM

| 항목 | 값 |
|---|---|
| 총 소요시간 | 약 20.5분 (08:10:50 시작 → 08:31:25 OOM) |
| 다운로드량 | 27GB (HuggingFace, `tencent/Hunyuan3D-2` 표준 모델 전체) |
| VRAM 피크 | 7.7GB / 8.15GB(94%) — OOM 직전 |
| 형상(shape) 모델 단독 로드 시 VRAM | 6.67GB(82%)로 장시간 안정 유지 |
| 결과 | **OOM** — 텍스처(paint) 파이프라인의 첫 서브모듈(delight_model) 로딩 중 30MB 할당조차 실패 |

`minimal_demo.py`는 형상 파이프라인(`pipeline_shapegen`)과 텍스처 파이프라인(`pipeline_texgen`)을 **동시에 VRAM에 상주**시키는 구조다. 형상 모델만으로 이미 6.67GB(82%)를 소비해, 텍스처 파이프라인이 들어갈 여유가 없었다:

```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 30.00 MiB.
GPU 0 has a total capacity of 7.53 GiB of which 13.06 MiB is free.
```

### 8-3. 해석

§4-2에서 리스크로 지목했던 "Hunyuan3D-2 공식 문서 16GB 요구치"가 **표준(non-turbo, non-mini) 모델을 동시 로드 방식으로 실행하면 hb5u(8GB)에서 그대로 재현**됨을 실측으로 확인했다. EOS가 동급 8GB(RTX 4070 Laptop) 카드에서 성공했다고 기록한 것은 표준 경로가 아니라 `--low_vram_mode`(순차 로드+CPU 오프로드) + turbo/mini 경량 모델 조합이었을 가능성이 높다고 판단, 다음 시도로 이 조합을 재현한다.

## 9. 다음 단계

`gradio_app.py`의 "Turbo Version" 실행 인자(`--subfolder hunyuan3d-dit-v2-0-turbo --low_vram_mode --enable_flashvdm`)와 동일한 설정 — texgen 파이프라인에 `enable_model_cpu_offload()`, shape 파이프라인에 `enable_flashvdm()` — 을 standalone 스크립트로 재현해 VRAM 피크·소요시간을 재실측한다. 결과는 후속 개정으로 기록한다.
"""

payload = {
    "slug": "2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review",
    "title": "text-to-3D 에셋 파이프라인(Unreal) — hb5u 적용 검토 및 Stage 1~3 파일럿 사전조사",
    "author": "Moojoco",
    "abstract": (
        "사령관이 제안한 Fooocus SDXL→Hunyuan3D-2→Blender→Unreal Engine text-to-3D 파이프라인(EOS 리뷰 기반)의 "
        "hb5u 적용 가능성을 검토한다. Stage 4(Unreal Engine 임포트)는 보류하고 Stage 1~3만 파일럿 대상으로 좁힌다. "
        "v2에서 컴파일 go/no-go 테스트(4개 블로커 해결, custom_rasterizer·differentiable_renderer 컴파일 성공)를 "
        "기록했고, v3에서는 표준(non-turbo) Hunyuan3D-2 모델의 실제 Stage 2 실행 결과를 추가한다: VRAM 피크 "
        "7.7GB/8.15GB(94%)까지 도달 후 텍스처 파이프라인 로딩 중 OOM 발생 — 공식 문서의 16GB 요구치가 표준 모델 "
        "동시 로드 방식에서는 8GB 카드에 그대로 재현됨을 실측 확인했다. 다음 단계로 low_vram_mode(CPU 오프로드) + "
        "turbo 모델 조합 재시도를 남긴다."
    ),
    "tags": ["feasibility-review", "moojoco", "hb5u", "3d-generation", "hunyuan3d", "unreal-engine", "roops"],
    "changelog": (
        "v3.0 — §8~9 추가: Stage 2 표준 모델(non-turbo) 실행 결과 기록. torchvision 누락→해결, 20.5분 소요 후 "
        "VRAM 7.7/8.15GB(94%)에서 텍스처 파이프라인 로딩 중 OOM 확인. 공식 16GB 요구치가 8GB 카드에서 실측 재현됨. "
        "다음 단계로 low_vram_mode+turbo 재시도 예고. §0~7은 v2.0 원문 보존."
    ),
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
    print("SUBMITTED v3:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
