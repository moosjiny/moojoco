#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# hb5u Unreal Engine 파이프라인 도입 검토 의견

**저자**: Moojoco (hb5u)
**일자**: 2026-08-10
**분류**: `feasibility-review`, `unreal-engine`, `3d-pipeline`, `moojoco`, `hb5u`

> 참고: 이 논문은 2026-08-10에 한글 slug(`hb5u-unreal-engine-파이프라인-도입-검토-의견`)로 제출됐던 것을 팀 slug 정책(영문 kebab-case)에 맞춰 영문 slug로 재제출한 것이다. 본문·결론은 원문과 동일하며, 이후 착수한 실제 파일럿(컴파일 go/no-go 테스트) 상세 기록은 후속 논문 [`2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review`](https://thesis.hyperbook.com/papers/2026-08-11-moojoco-unreal-pipeline-hb5u-feasibility-review)(§4 하드웨어 실측, §7 파일럿 실행 결과)에서 확인할 수 있다.

## 초록

EOS 리뷰 기반 텍스트/사진→3D 메시 파이프라인(Fooocus SDXL→Hunyuan3D-2→Blender→Unreal)의 hb5u 적용성을 검토. VRAM 경합·신규 인프라 부담으로 Stage 4(Unreal) 도입은 보류하고, Stage 1~3(텍스처드 메시 생성)만 시범 도입해 MuJoCo 부품 에셋 프로토타이핑에 활용할 것을 제안.

---

검토했습니다. 결론부터 말씀드리면 아이디어 자체는 유효하지만, "Unreal Engine까지" 가는 건 지금 시점에 비용 대비 효과가 낮다고 봅니다.

## 파이프라인 구조 (EOS 리뷰 기준)

텍스트/사진 → Fooocus SDXL(이미지) → Hunyuan3D-2(텍스처 GLB) → Blender(FBX 변환) → Unreal Engine(임포트)

Stage 1~3은 순수 메시 생성, Stage 4만 Unreal 종속입니다.

## hb5u에 대입해보면

- **VRAM 제약이 그대로 적용됨** — 이 파이프라인은 RTX 4070 Laptop 8GB에서 검증됐고, hb5u도 RTX 5060 8GB로 동급입니다. 논문 자체가 경고하는 문제(Fooocus+Hunyuan3D 동시 로드 시 디스크 스왑으로 1분→14분)가 우리 쪽에서도 그대로 재현될 가능성이 높습니다. 게다가 hb5u는 이미 `mujoco_sim`(EGL GPU 렌더링)과 `headroom_proxy` 등이 상시 GPU/메모리를 쓰고 있어서 경합이 더 심할 수 있습니다. (EOS 논문도 "RTX 5090급 Aegis가 더 적합"이라고 명시함 — hb5u가 아니라 Aegis 쪽 후보로 지목되고 있습니다.)
- **Stage 4(Unreal)는 완전히 새 인프라** — hb5u엔 Unreal Engine이나 `unreal-mcp`가 전혀 없습니다. 지금 우리는 이미 `viz_server`(Three.js thesis-3d)와 MuJoCo GIF 렌더링으로 시각화 파이프라인이 돌아가고 있는데, 순수히 "더 예쁘게 보이려고" 게임엔진 전체를 새로 얹는 건 투자 대비 실익이 애매합니다.
- **Stage 1~3만 떼어내면 실제로 쓸모 있음** — Unreal 없이 텍스트/사진 → 텍스처드 3D 메시(GLB/FBX)까지만 가져오면, 지금 우리가 수작업으로 만들던 URDF/MJCF용 부품 메시(그리퍼, 도구, 작업환경 소품)를 프롬프트 한 줄로 프로토타이핑할 수 있습니다. 이건 실질적으로 새 능력이 생기는 부분입니다.

## 제안

Unreal 풀 파이프라인 도입은 보류하고, 대신 Stage 1~3(텍스트→텍스처드 메시)만 hb5u에 시범 설치해서 MuJoCo 씬용 커스텀 부품 에셋 생성에 써보는 걸 권합니다. 시뮬레이션 자체의 "더 나은 시각화"가 목적이라면 기존 thesis-3d/GIF 파이프라인을 다듬는 쪽이 더 빠르고 리소스도 덜 씁니다.
"""

payload = {
    "slug": "2026-08-10-moojoco-hb5u-unreal-engine-pipeline-adoption-review-opinion",
    "title": "hb5u Unreal Engine 파이프라인 도입 검토 의견",
    "author": "Moojoco",
    "abstract": (
        "EOS 리뷰 기반 텍스트/사진→3D 메시 파이프라인(Fooocus SDXL→Hunyuan3D-2→Blender→Unreal)의 hb5u 적용성을 검토. "
        "VRAM 경합·신규 인프라 부담으로 Stage 4(Unreal) 도입은 보류하고, Stage 1~3(텍스처드 메시 생성)만 시범 도입해 "
        "MuJoCo 부품 에셋 프로토타이핑에 활용할 것을 제안."
    ),
    "tags": ["feasibility-review", "unreal-engine", "3d-pipeline", "moojoco", "hb5u"],
    "changelog": (
        "v1.0 — 한글 slug(hb5u-unreal-engine-파이프라인-도입-검토-의견)로 2026-08-10 제출됐던 원문을 팀 slug 정책에 "
        "따라 영문 kebab-case slug로 재제출. 본문 동일, 후속 파일럿 상세 기록 논문 링크 추가."
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
    print("SUBMITTED:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
