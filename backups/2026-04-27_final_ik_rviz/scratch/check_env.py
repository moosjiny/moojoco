import mujoco
import rerun as rr
import sys

def check():
    print(f"Python version: {sys.version}")
    print(f"MuJoCo version: {mujoco.__version__}")
    print(f"Rerun version: {rr.__version__}")
    
    try:
        # Just check if we can initialize a small model
        xml = "<mujoco><worldbody><light pos='0 0 1'/></worldbody></mujoco>"
        model = mujoco.MjModel.from_xml_string(xml)
        print("MuJoCo Model Loading: OK")
    except Exception as e:
        print(f"MuJoCo Error: {e}")

if __name__ == "__main__":
    check()
