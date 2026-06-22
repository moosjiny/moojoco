import mujoco
import numpy as np

URDF_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.urdf"

def debug():
    try:
        model = mujoco.MjModel.from_xml_path(URDF_PATH)
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        
        print(f"Model Bodies: {model.nbody}")
        for i in range(model.nbody):
            name = model.body(i).name
            pos = data.xpos[i]
            print(f"Body {i}: {name} at {pos}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug()
