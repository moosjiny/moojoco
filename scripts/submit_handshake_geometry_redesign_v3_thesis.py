#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# 손 모델 재설계 v3 — 2관절 손가락으로 손바닥 접촉·감싸쥐기 실현, 도중에 발견한 자기충돌 버그

**저자**: Moojoco (hb5u)
**계기**: [[2026-08-20-moojoco-handshake-palm-contact-geometry-flaw]]에서 발견한 손바닥 미접촉(18.8mm 간격) 문제에 사령관이 "1번"(손 모델 자체를 다시 설계)을 선택. `urdf/amazinghand_5finger_docking_v3.xml`을 새로 만들었다.
**일자**: 2026-08-20
**분류**: `handshake-robot`, `bug`, `result`, `moojoco`, `mujoco`

---

## 0. 왜 손바닥만 붙이면 안 되는가 — 먼저 실측으로 확인

손바닥 간격을 단순히 닫아본 첫 시도(B_END를 0.0952→0.114로, 팔목 목표만 조정)는 실패였다: 손가락(36~48mm)이 상대 손바닥 두께(34mm)보다 길어서, 오므리기 전 상태(curl=0, 가장 쭉 뻗음)에서 이미 상대 손바닥을 관통했다.

### 1관절 손가락으로는 원리적으로 감싸쥐기가 안 된다

손가락 길이 L=45mm 기준, 단일 힌지가 그리는 궤적을 직접 계산했다:

| curl 각도 | 손끝 위치(y, z) |
|---|---|
| 0° | (45.0, 0.0) mm |
| 60° | (22.5, 39.0) mm |
| 90° | (0.0, 45.0) mm |
| 120° | (-22.5, 39.0) mm |
| 180° | (-45.0, 0.0) mm |

180도를 다 굽혀도 손끝은 결국 **자기 손목 쪽**으로 돌아올 뿐이다 — 두 손 사이에 있는 상대 손바닥을 피해 뒤로 돌아갈 방법이 원리적으로 없다. 사람 손이 MCP(손허리손가락관절)+PIP(몸쪽손가락뼈사이관절) 두 관절로 "C"자를 만들어 물체를 감싸는 것과 근본적으로 다른 기구학이다.

## 1. 재설계 — 손가락마다 관절 2개(MCP+PIP)

각 손가락을 근위(길이의 55%)/원위(45%) 두 세그먼트로 나누고 관절을 하나씩 추가했다(총 손가락 관절 10개 → 20개, 액추에이터도 동일하게 증가). 생성 스크립트: `scripts/generate_amazinghand_v3_mjcf.py`.

## 2. 실측 중 발견한 버그 — 손가락이 자기 관절에서 스스로 충돌

새 모델을 그냥 물리 시뮬레이션에 넣었더니 몇 프레임 만에 폭발(두 손이 1000mm 이상 날아감)했다. 원인을 추적했다:

**근위-원위 캡슐이 관절점에서 서로 겹친다.** 캡슐 끝의 둥근 캡(반경 6mm, 5.1mm)이 같은 지점에 중심을 두고 있어, curl 각도와 무관하게 항상 `-11.1mm`(두 반경의 합)로 겹쳐 있음을 `mj_geomDistance`로 직접 확인했다:

```
mcp=0   pip=0   -> prox-dist 자기거리 = -11.100mm
mcp=0.3 pip=0.3 -> prox-dist 자기거리 = -11.100mm  (각도 무관하게 항상 동일)
```

MuJoCo는 부모-자식 body를 자동으로 충돌 제외하지 않는다 — `<contact><exclude body1="..." body2="..."/></contact>`로 각 손가락(양손 5개씩, 총 10쌍)의 근위-원위 body를 명시적으로 제외해야 했다. 고친 뒤 재확인: 손이 멀리 떨어진 상태에서 `ncon=0`(자기충돌 사라짐).

## 3. 그래도 남아있던 폭발 — 이번엔 검증 스크립트 자체의 버그

자기충돌을 고쳤는데도 여전히 폭발했다. 원인은 모델이 아니라 **내 검증 스크립트**였다 — 빠르게 확인하려고 손목 접근(`handA/B_approach`)과 손가락 curl만 제어하고, `handB_lateral`/`handB_height`(damping만 있고 목표 유지용 PD가 없는 축)를 그냥 방치했다. 어떤 충돌력이든 그 축을 무한정 밀어버려 순식간에 발산했다. 실제 파이프라인(`generate_procedural_curl_dataset_stage1_75.py` 이하)은 이 두 축을 항상 kp=2000으로 붙잡고 있어 원래 문제없었다 — 급히 짠 확인용 스크립트에서만 재발한 것이었다. 두 축을 마저 제어하도록 고치자 폭발이 완전히 사라졌다.

## 4. 최종 검증 — 물리 시뮬레이션으로 안정적 접촉 확인

손목을 4초에 걸쳐 서서히 접근시키고 손가락을 순서대로 오므리는 전체 시퀀스를 `mj_step` 기반 실물리로 재실행:

```
frame 0:  palm_gap=486.0mm  (시작, 멀리 떨어짐)
frame 40: palm_gap=295.4mm
frame 50: palm_gap=0.0mm    <- 손바닥이 실제로 접촉하는 순간 발생!
frame 60: palm_gap=109.6mm
frame 79: palm_gap=24.9mm, ncon=6 (손가락-손가락 접촉 6곳으로 안정적으로 수렴)
```

발산 없이 안정적으로 수렴했고, 접근 중 손바닥이 실제로 맞닿는 순간이 물리적으로 발생했다(0.0mm) — [[2026-08-20-moojoco-handshake-palm-contact-geometry-flaw]]가 지적한 "손바닥이 아예 안 닿는다" 문제는 이제 해소됐다. 최종 정지 시점의 6개 접촉은 대부분 근위 세그먼트끼리(`handA_middle_prox_geom <-> handB_middle_prox_geom` 등)로, 손가락들이 서로 밀어내며 손바닥 사이에 약 25mm의 자연스러운 여유를 만드는 것으로 보인다.

## 5. 아직 안 끝났다 — 정직하게 남겨두는 것

- 손바닥이 완전히 눌려 붙는 "꽉 쥔" 수준까지는 아직 튜닝이 안 됐다(25mm 여유가 남음) — curl target 값·타이밍 재조정이 다음 단계.
- 손가락이 상대 손바닥의 **뒤쪽/옆면**을 실제로 감싸 쥐는지(진짜 악수처럼)는 이번 검증에서 확인 못 했다 — 지금 접촉은 손가락-손가락 위주다. 다음 실측에서 확인이 필요하다.
- 이 v3 모델은 아직 Stage 1~4 파이프라인에 연결되지 않았다 — 데이터 생성·학습·검증 전부를 새 20-액추에이터 손가락 스키마로 다시 만들어야 한다(행동 차원이 10→20으로 늘어남).

다음 단계(curl 튜닝, Stage 1~4 재구축)는 사령관 확인 후 진행한다.
"""

payload = {
    "slug": "2026-08-20-moojoco-handshake-geometry-redesign-v3",
    "title": "손 모델 재설계 v3 — 2관절 손가락으로 손바닥 접촉 실현",
    "author": "Moojoco",
    "abstract": (
        "손바닥 미접촉 결함을 고치기 위해 손 모델을 2관절(MCP+PIP) 손가락으로 재설계했다. 먼저 1관절 "
        "손가락은 궤적 계산상 원리적으로 상대 손을 감싸쥘 수 없음을 확인(180도를 굽혀도 자기 손목으로 "
        "돌아올 뿐)했고, 2관절 설계로 전환했다. 구현 중 두 가지 버그를 발견·수정했다: (1) 근위-원위 "
        "손가락 세그먼트가 관절점에서 캡슐 반경만큼(11.1mm) 항상 자기충돌하는 모델 버그(MuJoCo "
        "부모-자식 body 자동 충돌제외 없음, contact exclude로 해결), (2) 검증 스크립트가 handB_lateral/"
        "height 축을 제어하지 않아 충돌력에 무한정 밀려 발산하는 스크립트 버그. 두 버그를 고친 뒤 전체 "
        "물리 시뮬레이션(4초 접근+파지)이 발산 없이 안정적으로 수렴했고, 접근 중 손바닥이 실제로 접촉하는 "
        "순간(0.0mm)이 발생함을 확인했다. 다만 최종 정지 자세는 완전한 밀착이 아니라 25mm 여유가 남고, "
        "손가락이 진짜로 상대 손바닥을 감싸는지는 아직 미확인이며, Stage 1~4 파이프라인 재구축도 남아있다."
    ),
    "tags": ["handshake-robot", "bug", "result", "moojoco", "mujoco"],
    "changelog": "v1.0 — 최초 제출: 2관절 손가락 재설계, 자기충돌·검증스크립트 버그 발견·수정, 물리 안정성 확인",
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
