"""
악수(Handshake) 데모용 2대 로봇 씬. build_two_robot_scene.py와 같은 방식(base_plate
서브트리를 r2_ 접두사로 복제)이지만, 로봇 팔의 실제 가동 방향(월드 +y)에 맞춰
로봇2를 y축으로 띄워 배치한다 — x축 오프셋(dual_openarm_2robots.xml, 1단계 산출물)은
팔이 닿지 않는 배치라 악수엔 못 쓴다(오른팔 리치가 rest에서 y방향으로 0.541m 고정,
x/z 방향 가동범위는 관절을 굽혀도 ±0.22m 수준에 불과함 — 실측으로 확인).
"""
import copy
import xml.etree.ElementTree as ET

SRC_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm.xml"
OUT_PATH = "/home/moos/dev_ws/dual_arms/urdf/dual_openarm_handshake.xml"

R2_POS = "0 1.05 0"   # 로봇1 오른팔(rest 리치 0.541m)과 로봇2 오른팔(180도 반전 후 -y로 리치)이
                      # 살짝 겹치게(약 2cm) 배치 — 접촉 물리가 없어 "맞잡은" 모습을 위한 의도적 오버랩
R2_QUAT = "0 0 0 1"


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
    for act in list(actuator):
        act2 = copy.deepcopy(act)
        act2.set("name", "r2_" + act2.attrib["name"])
        act2.set("joint", "r2_" + act2.attrib["joint"])
        actuator.append(act2)

    tree.write(OUT_PATH, encoding=None, xml_declaration=False)
    print(f"저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
