import React, { useState } from 'react';
import { X, Copy, Check, Cpu, Code2, BookOpen, Layers, ShieldCheck, Terminal } from 'lucide-react';
import { soundEngine } from '../utils/audio';

interface MujocoCodeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MujocoCodeModal: React.FC<MujocoCodeModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'python' | 'math' | 'mjcf'>('python');
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const pythonCode = `import mujoco
import numpy as np

# 1. 모델 및 데이터 로드 (로봇 팔 및 손 XML)
model = mujoco.MjModel.from_xml_path("handshake_robot.xml")
data = mujoco.MjData(model)

# 엔드이펙터(손목/손 중심) Body ID 및 Site ID 설정
ee_site_name = "end_effector_site"
ee_site_id = model.site(ee_site_name).id

# 임피던스 제어 게인 설정 (Virtual Stiffness & Damping)
# 악수 시 유연성을 위해 Kx(강성)를 비교적 낮게 설정합니다.
Kx = np.diag([150.0, 150.0, 100.0, 20.0, 20.0, 20.0])  # x, y, z, rx, ry, rz
Dx = np.diag([20.0, 20.0, 15.0, 2.0, 2.0, 2.0])      # Damping

# 목표 악수 위치 (Target Pose)
x_des = np.array([0.5, 0.0, 0.4])  # 사람 손과 만날 목표 위치 (x, y, z)
R_des = np.eye(3)                  # 목표 자세 (Rotation matrix)

def compute_impedance_torque(m, d):
    # 1. 현재 엔드이펙터 위치 및 자세 추출
    x_curr = d.site(ee_site_id).xpos
    R_curr = d.site(ee_site_id).xmat.reshape(3, 3)

    # 2. 위치 및 회전 오차 계산
    pos_err = x_des - x_curr
    
    # 회전 오차 (Orientation Error via skew-symmetric matrix)
    R_err = R_des @ R_curr.T
    rot_err = 0.5 * np.array([
        R_err[2, 1] - R_err[1, 2],
        R_err[0, 2] - R_err[2, 0],
        R_err[1, 0] - R_err[0, 1]
    ])
    
    delta_x = np.concatenate([pos_err, rot_err])

    # 3. 자코비안(Jacobian) 계산 (Translational + Rotational)
    jacp = np.zeros((3, m.nv))
    jacr = np.zeros((3, m.nv))
    mujoco.mj_jacSite(m, d, jacp, jacr, ee_site_id)
    J = np.vstack([jacp, jacr])

    # 4. 현재 작업 공간 속도 계산 (dx = J * dq)
    dx = J @ d.qvel

    # 5. 작업 공간 제어력 (Task-Space Force) 계산
    F_task = Kx @ delta_x - Dx @ dx

    # 6. 관절 토크 변환 (Tau = J^T * F + Gravity Compensation)
    tau_impedance = J.T @ F_task
    tau_gravity = d.qfrc_bias  # 중력 및 코리올리 보상 항

    return tau_impedance + tau_gravity

# 메인 제어 루프
while data.time < 10.0:
    # 컨트롤러 토크 계산 및 인가
    tau = compute_impedance_torque(model, data)
    
    # 관절 구동기(Actuator)에 토크 입력 (Torque Motor 기준)
    data.ctrl[:model.nu] = tau[:model.nu]

    # 손가락 파지 제어 (접촉 센서 피드백에 따른 파지력 제어 예시)
    touch_force = data.sensor("hand_touch_sensor").data[0]
    if touch_force > 0.5:  # 손이 닿으면
        data.ctrl[model.nu-1] = 0.3  # 손가락 살짝 쥐기 (유연한 파지)
    else:
        data.ctrl[model.nu-1] = 0.0  # 대기 상태

    # 시뮬레이션 Step
    mujoco.mj_step(model, data)`;

  const mjcfXml = `<mujoco model="handshake_robot">
  <compiler angle="radian" coordinate="local"/>
  <option timestep="0.002" gravity="0 0 -9.81"/>

  <worldbody>
    <!-- Base & Robot Right Arm Structure -->
    <body name="upper_arm" pos="0 0 1.2">
      <joint name="shoulder_pitch" type="hinge" axis="0 1 0" range="-2.0 1.57"/>
      <joint name="shoulder_roll" type="hinge" axis="1 0 0" range="-1.57 1.57"/>
      <geom type="capsule" size="0.04" fromto="0 0 0 0.3 0 0" density="800"/>

      <body name="forearm" pos="0.3 0 0">
        <joint name="elbow_flexion" type="hinge" axis="0 1 0" range="0 2.5"/>
        <geom type="capsule" size="0.03" fromto="0 0 0 0.28 0 0" density="600"/>

        <body name="hand_palm" pos="0.28 0 0">
          <site name="end_effector_site" pos="0.08 0 0" size="0.01"/>
          <geom name="finger_pad" type="box" size="0.04 0.03 0.01" friction="1.5 0.005 0.0001" condim="4"/>
        </body>
      </body>
    </body>
  </worldbody>

  <sensor>
    <touch name="hand_touch_sensor" site="end_effector_site"/>
  </sensor>
</mujoco>`;

  const handleCopy = () => {
    navigator.clipboard.writeText(pythonCode);
    setCopied(true);
    soundEngine.playClick(950);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in font-sans">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-[#0F0F10] border border-[#222226] rounded-xl shadow-2xl text-zinc-100 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 bg-[#111113] border-b border-[#222226]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#10B981]/20 text-[#10B981] rounded-lg border border-[#10B981]/30">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold uppercase tracking-wide text-white font-mono flex items-center gap-2">
                MuJoCo Task-Space Impedance Control Engine
              </h2>
              <p className="text-[11px] text-zinc-400 font-mono">
                강체 제어가 아닌 유연성(Compliance) 및 중력보상 토크 제어 가이드
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-[#18181B] text-zinc-400 hover:text-white border border-[#27272A] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-2 px-5 py-2.5 bg-[#141416] border-b border-[#222226] text-xs font-mono">
          <button
            onClick={() => setActiveTab('python')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              activeTab === 'python'
                ? 'bg-[#1D4ED8] text-white font-bold border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Code2 className="w-3.5 h-3.5 text-[#3B82F6]" />
            Python (Py-binding) Code
          </button>
          <button
            onClick={() => setActiveTab('math')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              activeTab === 'math'
                ? 'bg-[#1D4ED8] text-white font-bold border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-[#10B981]" />
            Control Math & Architecture
          </button>
          <button
            onClick={() => setActiveTab('mjcf')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded transition-colors ${
              activeTab === 'mjcf'
                ? 'bg-[#1D4ED8] text-white font-bold border border-[#3B82F6]'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#F59E0B]" />
            MJCF (XML) Model Setup
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 font-mono text-xs">
          {activeTab === 'python' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between bg-[#141416] p-3 rounded border border-[#222226]">
                <div className="flex items-center gap-2 text-zinc-300">
                  <Terminal className="w-4 h-4 text-[#10B981]" />
                  <span>mujoco_impedance_handshake.py</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1 bg-[#10B981]/20 hover:bg-[#10B981]/30 text-[#10B981] border border-[#10B981]/40 rounded text-xs transition-all font-bold"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied!' : 'Copy Python Code'}
                </button>
              </div>

              <pre className="p-4 bg-[#09090B] border border-[#1F1F23] rounded-lg text-emerald-400 text-[11px] leading-relaxed overflow-x-auto selection:bg-[#10B981]/30 selection:text-white">
                <code>{pythonCode}</code>
              </pre>
            </div>
          )}

          {activeTab === 'math' && (
            <div className="space-y-4 text-zinc-300">
              {/* Formula Block */}
              <div className="p-4 bg-[#141416] border border-[#222226] rounded-lg space-y-2">
                <span className="text-[10px] uppercase font-bold text-[#3B82F6] tracking-widest block">
                  Task-Space Impedance Torque Equation
                </span>
                <div className="p-3 bg-[#09090B] border border-[#1A1A1E] rounded text-emerald-300 font-bold text-center text-sm">
                  τ = J(q)ᵀ [ M_x (ẍ_d - ẍ) + D_x (ẋ_d - ẋ) + K_x (x_d - x) ] + C(q, q̇) + g(q)
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed pt-1 font-sans">
                  * MuJoCo에서는 코리올리 및 중력보상 항 <code className="text-[#3B82F6]">C(q, q̇) + g(q)</code>이{' '}
                  <code className="text-[#10B981]">d.qfrc_bias</code> 변수에 미리 계산되어 제공되므로, 임피던스 외력 토크에 간편히 더해 중력 보상을 완료할 수 있습니다.
                </p>
              </div>

              {/* Key Concepts Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3.5 bg-[#141416] border border-[#222226] rounded-lg space-y-1.5 font-sans">
                  <h4 className="text-xs font-bold text-[#10B981] font-mono flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4" /> 1. Arm - Task-Space Impedance
                  </h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    강체 Position Control 대신 가상의 질량-스프링-댐퍼 시스템($K_x, D_x$)을 구축하여 상대방이 손을 흔들거나 당길 때 자연스럽게 순응(Compliant)하며 추종합니다.
                  </p>
                </div>

                <div className="p-3.5 bg-[#141416] border border-[#222226] rounded-lg space-y-1.5 font-sans">
                  <h4 className="text-xs font-bold text-[#F59E0B] font-mono flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4" /> 2. Hand - Direct Force Feedback
                  </h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    <code className="font-mono text-[#F59E0B]">hand_touch_sensor</code> 피드백 센서를 실시간 측정하여, 손 접촉 시 과도한 압박 없이 안전한 파지력(Grasping Force)을 선형 제어합니다.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'mjcf' && (
            <div className="space-y-3">
              <div className="p-3 bg-[#141416] rounded border border-[#222226] text-xs text-zinc-300 font-sans">
                <b>MJCF XML Configuration Tips:</b>
                <ul className="list-disc list-inside mt-1 space-y-1 text-zinc-400 font-mono text-[11px]">
                  <li>
                    Actuator는 <code className="text-[#3B82F6]">&lt;motor&gt;</code> 태그 토크 모드를 추천합니다.
                  </li>
                  <li>
                    손가락 패드에는 높은 마찰 계수 <code className="text-[#F59E0B]">friction="1.5 0.005 0.0001"</code>를 지정하여 악수 시 손이 미끄러지지 않도록 구성합니다.
                  </li>
                </ul>
              </div>

              <pre className="p-4 bg-[#09090B] border border-[#1F1F23] rounded-lg text-sky-300 text-[11px] leading-relaxed overflow-x-auto">
                <code>{mjcfXml}</code>
              </pre>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 bg-[#111113] border-t border-[#222226] flex items-center justify-between text-xs font-mono">
          <span className="text-zinc-500 text-[11px]">
            MuJoCo Py-binding Task-Space Impedance Integration
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-[#1D4ED8] hover:bg-[#2563EB] text-white border border-[#3B82F6] rounded font-bold uppercase transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
