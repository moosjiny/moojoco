# 듀얼암 디지털 트윈 정렬 오류 재발 방지 대책

본 문서는 `dual_arm_alignment_resolution.md`에서 식별된 기술적 문제점들이 향후 개발 과정에서 재발하지 않도록 하기 위한 핵심 분석 및 예방 대책을 정의합니다.

## 1. 핵심 문제점 (Core Issues) 분석

이번 정렬 과정에서 발생한 문제는 크게 4가지 기술적 영역으로 구분됩니다.

### ① 물리 엔진의 최적화 로직 간과 (Body Fusion)
- **문제**: MuJoCo가 고정 관절을 하나로 합치면서 시각화 스크립트가 해당 링크의 개별 좌표 정보를 잃어버림.
- **교훈**: 시뮬레이터의 성능 최적화 옵션(`fusestatic`)이 디지털 트윈의 시각적 정확도를 저해할 수 있음을 인지해야 함.

### ② 메쉬 데이터 검증 부족 (Geometry Blindness)
- **문제**: `base_link.stl`이 단순 모터 베이스가 아닌 거대 스탠드 기둥임을 수치적으로 확인하지 않고 작업을 진행함.
- **교훈**: 파일 이름에 의존하지 말고, 작업 전 반드시 메쉬의 실제 Bounding Box(XYZ 크기)를 코드상으로 출력해봐야 함.

### ③ 비일관된 대칭 규칙 (Incomplete Symmetry)
- **문제**: 전체 팔이 거울 대칭일 것이라는 선입견으로 인해 하박부(Link 1-3)와 상박부(Link 4-7)의 조립 차이를 놓침.
- **교훈**: 복합 기구 시스템에서 대칭은 부분적으로 적용될 수 있으며, 조인트 축(Axis) 하나하나를 대조하는 검증 과정이 필수적임.

### ④ 부착 지점의 하드코딩 (Magic Numbers)
- **문제**: 베이스 표면의 실제 좌표를 고려하지 않고 임의의 수치로 URDF Origin을 설정하여 간극이 발생함.
- **교훈**: 부착 좌표는 부모 메쉬의 끝단 좌표(Surface Coordinate)와 자식 메쉬의 조인트 오프셋을 합산한 '수학적 결과'여야 함.

---

## 2. 재발 방지 대책 (Action Plan)

### [대책 1] 디지털 트윈 전용 시뮬레이션 설정 표준화
- 새로운 로봇 모델 도입 시, URDF 상단에 아래의 설정을 반드시 포함하여 바디 병합을 방지함.
  ```xml
  <mujoco>
    <compiler fusestatic="false" discardvisual="false"/>
  </mujoco>
  ```

### [대책 2] 메쉬 전수 조사 스크립트(Mesh Sanity Check) 실행
- 작업 시작 전, 모든 STL 파일의 크기와 중심점을 자동으로 출력하는 스크립트를 실행하여 설계치와 대조함.
  - *도구*: `scripts/analyze_meshes.py` (이번에 작성된 스크립트 활용)

### [대책 3] 링크별 '대칭 속성' 문서화
- URDF 내부에 각 링크가 거울 대칭(`Mirrored`)인지 동일 복사(`Identical`)인지 주석으로 명시하여 렌더링 코드 작성 시 실수를 방지함.
  ```xml
  <!-- Mirrored from Left Arm -->
  <link name="right_link2"> ...
  <!-- Identical to Left Arm -->
  <link name="right_link6"> ...
  ```

### [대책 4] 제로-갭(Zero-Gap) 캘리브레이션 프로세스 도입
- 메쉬 간 결합 시, 아래의 공식을 사용하여 URDF 좌표를 산출함.
  - `URDF Origin = (Parent Surface Coord) + (Child Joint Offset in STL)`
- 수동으로 눈대중 조절을 금지하고, 반드시 소수점 4자리까지의 계산된 수치를 적용함.

---

## 3. 결론
이번 정렬 이슈는 하드웨어의 물리적 특성과 시뮬레이터의 소프트웨어적 특성 사이의 이해 차이에서 발생했습니다. 위 대책을 준수함으로써 향후 로봇 암의 추가나 변경 시에도 **'오차 없는 1:1 대응 디지털 트윈'**을 신속하게 구축할 수 있을 것입니다.
---

## 부록: 표준 백업 절차 (Standard Backup Procedure)

정상적으로 정렬이 완료된 상태를 보존하기 위해 아래 커맨드를 사용하여 정기적으로 백업을 생성할 것을 권장합니다.

```bash
# 1. 작업 디렉토리로 이동
# 2. 가상환경 및 불필요한 파일을 제외하고 압축 실행
tar -czvf dual_arm_backup_alignment_v[버전].tar.gz -C /home/addinedu/dev_ws/dual_arms . \
    --exclude='./venv' \
    --exclude='./.git' \
    --exclude='./dual_arm_backup_alignment_v[버전].tar.gz'
```
