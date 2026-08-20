"""손바닥 접촉 기하학 재설계(v3) — urdf/amazinghand_5finger_docking_v3.xml 생성기.

## 계기
[[2026-08-20-moojoco-handshake-palm-contact-geometry-flaw]]에서, 지금까지
Stage 1~4가 써온 v2 모델은 baseline 목표 자세에서 손바닥이 18.8mm 떨어져
있고 손가락끼리만 허공에서 엇갈려 끼우는 동작이었음을 실측으로 확인했다.
사령관 지시("1번" — 손 모델 자체를 다시 설계) 후 재설계한 버전이다.

## 왜 손가락 2관절(MCP+PIP)이 필요했나
1관절(단일 힌지) 손가락은 자기 관절을 중심으로 원을 그릴 뿐이라, 손바닥을
맞댄 채로 상대 손을 "감싸 쥘" 수 없다 — 180도를 굽혀도 결국 자기 손목
쪽으로 돌아올 뿐, 두 손 사이에 있는 물체(상대 손바닥)를 피해 뒤로 돌아갈
방법이 없다(§검증: L=45mm 손가락이 curl 0/60/90/120/180도에서 그리는
궤적을 직접 계산해 확인). 사람 손의 MCP+PIP 관절처럼 마디를 하나 더 주면
"C"자 모양으로 굽어 물체를 감쌀 수 있다 — 그래서 각 손가락을 근위(MCP)/
원위(PIP) 2세그먼트로 나눴다.

## 실측 중 발견한 버그 두 개 (둘 다 이 파일에서 고침)
1. **손가락 자기 관절 자기충돌**: 근위-원위 캡슐이 관절점에서 겹치는
   반경(6mm+5.1mm=11.1mm)만큼 항상 서로 관통 — curl 각도와 무관하게 항상
   -11.1mm로 측정됨. `<contact><exclude .../></contact>`로 각 손가락의
   근위-원위 body 쌍을 명시적으로 충돌 제외해야 한다(MuJoCo는 부모-자식
   body를 자동으로 충돌 제외하지 않는다).
2. **테스트 스크립트 자체의 버그**(모델 결함 아님, 기록용): 손목 접근을
   흉내 낸 첫 검증에서 `handB_lateral`/`handB_height`를 제어하지 않고
   두면(damping만 있고 목표 유지 PD가 없으면) 어떤 충돌 힘이든 그 축을
   무한정 밀어버려 두 손이 순식간에 1000mm 이상 날아가 버린다 — 실제
   파이프라인(Stage 1.5~통합 스크립트)은 항상 이 두 축을 kp=2000으로
   붙잡고 있어서 문제없지만, 빠른 확인용 스크립트를 짤 때는 반드시 이
   축도 같이 잡아야 한다는 걸 이번에 다시 확인했다.

## 검증 결과 (물리 시뮬레이션, mj_step 기반)
손목을 A_START/B_START에서 A_END=-0.028/B_END=0.114로 4초간 서서히
접근시키고 손가락을 curl 스케줄대로 오므리면: 팔목이 근접하는 동안
`palm_gap`이 0mm까지 줄어드는 순간이 실제로 발생하고(진짜 접촉),
최종적으로는 손가락-손가락 접촉(6곳, prox 세그먼트 위주)이 발생해
25mm 안팎에서 안정적으로 자리잡는다 — 폭발 없이 안정적으로 수렴한다.
손바닥이 완전히 눌려 붙는 수준까지는 아직 아니라 커브 튜닝이 남아있다.
"""
FINGER_JOINTS = ["thumb", "index", "middle", "ring", "pinky"]
X_OFFSET = {"thumb": -0.026, "index": -0.013, "middle": 0.0, "ring": 0.013, "pinky": 0.026}
TOTAL_LEN = {"thumb": 0.038, "index": 0.045, "middle": 0.048, "ring": 0.044, "pinky": 0.036}
RADIUS = 0.006
MCP_RANGE = "0 1.4"
PIP_RANGE = "0 1.5"

def finger_block(hand, fn, color):
    x = X_OFFSET[fn]
    total = TOTAL_LEN[fn]
    prox_len = total * 0.55
    dist_len = total * 0.45
    dist_radius = RADIUS * 0.85
    return f'''      <body name="{hand}_finger_{fn}" pos="{x} 0.017 0">
        <joint name="{hand}_{fn}_mcp" type="hinge" axis="1 0 0" range="{MCP_RANGE}" />
        <geom name="{hand}_{fn}_prox_geom" type="capsule" fromto="0 0 0 0 {prox_len:.4f} 0" size="{RADIUS}" rgba="{color}" />
        <body name="{hand}_{fn}_distal" pos="0 {prox_len:.4f} 0">
          <joint name="{hand}_{fn}_pip" type="hinge" axis="1 0 0" range="{PIP_RANGE}" />
          <geom name="{hand}_{fn}_dist_geom" type="capsule" fromto="0 0 0 0 {dist_len:.4f} 0" size="{dist_radius:.4f}" rgba="{color}" />
        </body>
      </body>'''

def actuator_block(hand, fn):
    return (f'    <general name="{hand}_{fn}_mcp_ctrl" joint="{hand}_{fn}_mcp" ctrllimited="true" ctrlrange="-2 2" />\n'
            f'    <general name="{hand}_{fn}_pip_ctrl" joint="{hand}_{fn}_pip" ctrllimited="true" ctrlrange="-2 2" />')

color_a = "0.22 0.74 0.97 1"
color_b = "0.98 0.57 0.23 1"

fingers_a = "\n".join(finger_block("handA", fn, color_a) for fn in FINGER_JOINTS)
fingers_b = "\n".join(finger_block("handB", fn, color_b) for fn in FINGER_JOINTS)
act_a = "\n".join(actuator_block("handA", fn) for fn in FINGER_JOINTS)
act_b = "\n".join(actuator_block("handB", fn) for fn in FINGER_JOINTS)

xml = f'''<mujoco model="amazinghand_5finger_docking_v3">
  <compiler angle="radian" />
  <option gravity="0 0 -9.81" timestep="0.002" />

  <default>
    <geom density="600" friction="1.0 0.02 0.001" solref="0.01 1" solimp="0.9 0.95 0.001" />
    <joint damping="0.15" frictionloss="0.01" />
  </default>

  <worldbody>
    <light name="light_top" pos="0 0 1.2" dir="0 0 -1" diffuse="0.8 0.8 0.8" directional="true" />
    <light name="light_side" pos="0.8 -0.6 0.6" dir="-0.8 0.6 -0.4" diffuse="0.5 0.5 0.5" directional="true" />
    <camera name="cam_dock" mode="fixed" pos="0.55 -0.55 0.35" xyaxes="0.707 0.707 0 -0.25 0.25 0.935" />

    <geom name="floor" type="plane" size="1 1 0.01" pos="0 0 -0.15" rgba="0.15 0.15 0.18 1" contype="0" conaffinity="0" />

    <body name="obstacle" mocap="true" pos="0 5 0.05">
      <geom name="obstacle_geom" type="box" size="0.06 0.004 0.05" rgba="0.9 0.25 0.2 0.55" />
    </body>

    <body name="handA_wrist" pos="0 0 0.05">
      <joint name="handA_approach" type="slide" axis="0 1 0" damping="1.0" />
      <inertial pos="0 0 0" mass="0.35" diaginertia="0.0006 0.0006 0.0006" />
      <geom name="handA_palm" type="box" size="0.024 0.017 0.008" rgba="{color_a}" />
{fingers_a}
    </body>

    <body name="handB_wrist" pos="0.007 0.12 0.05" euler="0 0 3.14159">
      <joint name="handB_approach" type="slide" axis="0 1 0" damping="1.0" />
      <joint name="handB_lateral" type="slide" axis="1 0 0" damping="1.0" />
      <joint name="handB_height" type="slide" axis="0 0 1" damping="1.0" />
      <inertial pos="0 0 0" mass="0.35" diaginertia="0.0006 0.0006 0.0006" />
      <geom name="handB_palm" type="box" size="0.024 0.017 0.008" rgba="{color_b}" />
{fingers_b}
    </body>
  </worldbody>

  <contact>
    <exclude body1="handA_finger_thumb" body2="handA_thumb_distal" />
    <exclude body1="handA_finger_index" body2="handA_index_distal" />
    <exclude body1="handA_finger_middle" body2="handA_middle_distal" />
    <exclude body1="handA_finger_ring" body2="handA_ring_distal" />
    <exclude body1="handA_finger_pinky" body2="handA_pinky_distal" />
    <exclude body1="handB_finger_thumb" body2="handB_thumb_distal" />
    <exclude body1="handB_finger_index" body2="handB_index_distal" />
    <exclude body1="handB_finger_middle" body2="handB_middle_distal" />
    <exclude body1="handB_finger_ring" body2="handB_ring_distal" />
    <exclude body1="handB_finger_pinky" body2="handB_pinky_distal" />
  </contact>

  <actuator>
    <general name="handA_approach_ctrl" joint="handA_approach" ctrllimited="true" ctrlrange="-5 5" />
{act_a}
    <general name="handB_approach_ctrl" joint="handB_approach" ctrllimited="true" ctrlrange="-5 5" />
    <general name="handB_lateral_ctrl" joint="handB_lateral" ctrllimited="true" ctrlrange="-5 5" />
    <general name="handB_height_ctrl" joint="handB_height" ctrllimited="true" ctrlrange="-5 5" />
{act_b}
  </actuator>
</mujoco>
'''

with open("/home/moos/dev_ws/dual_arms/urdf/amazinghand_5finger_docking_v3.xml", "w") as f:
    f.write(xml)
print("written", len(xml), "bytes")
