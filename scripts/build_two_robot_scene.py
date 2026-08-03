"""
dual_openarm.xml의 로봇 서브트리(base_plate 이하)를 복제해 이름에 r2_ 접두를 붙이고
위치를 옮겨 붙인 "2대 로봇" 씬 XML을 만든다. 원본 파일은 읽기만 하고 수정하지 않음.
actuator 항목도 함께 복제(joint 참조 갱신)해야 컴파일이 통과한다.
"""
import copy
import xml.etree.ElementTree as ET

SRC_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_2robots.xml"

R2_POS = "1.6 0 0"
R2_QUAT = "0 0 0 1"  # z축 180도 회전 — 로봇1과 마주보게


def prefix_names(elem, prefix):
    for el in elem.iter():
        if "name" in el.attrib:
            el.set("name", prefix + el.attrib["name"])


def main():
    tree = ET.parse(SRC_PATH)
    root = tree.getroot()

    worldbody = root.find("worldbody")
    base_plate = None
    for child in worldbody:
        if child.tag == "body" and child.attrib.get("name") == "base_plate":
            base_plate = child
            break
    if base_plate is None:
        raise RuntimeError("base_plate body를 찾지 못함")

    robot2 = copy.deepcopy(base_plate)
    prefix_names(robot2, "r2_")
    robot2.set("pos", R2_POS)
    robot2.set("quat", R2_QUAT)
    worldbody.append(robot2)

    actuator = root.find("actuator")
    orig_actuators = list(actuator)
    for act in orig_actuators:
        act2 = copy.deepcopy(act)
        act2.set("name", "r2_" + act2.attrib["name"])
        act2.set("joint", "r2_" + act2.attrib["joint"])
        actuator.append(act2)

    tree.write(OUT_PATH, encoding="unicode" if False else None, xml_declaration=False)
    print(f"저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
