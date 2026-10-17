import os
import sys


def with_approach_controller(controllers):
    if not isinstance(controllers, list) or not all(isinstance(item, dict) for item in controllers):
        raise RuntimeError("Mowgli docking: invalid navigation controller list")
    if not any(item.get("name") == "FTCPlanner" for item in controllers):
        raise RuntimeError("Mowgli docking: FTCPlanner must remain configured")
    approach = {"name": "DockingApproachFTCPlanner", "type": "ftc_local_planner/FTCPlanner"}
    existing = [item for item in controllers if item.get("name") == approach["name"]]
    if existing and (len(existing) != 1 or existing[0].get("type") != approach["type"]):
        raise RuntimeError("Mowgli docking: conflicting approach controller")
    return [item for item in controllers if item.get("name") != approach["name"]] + [approach]


if __name__ == "__main__":
    import rosgraph

    if len(sys.argv) < 2:
        raise RuntimeError("Mowgli docking: missing navigation executable")
    master = rosgraph.Master("/mowgli_docking_bootstrap")
    controller_path = "/move_base_flex/controllers"
    master.setParam(controller_path, with_approach_controller(master.getParam(controller_path)))
    os.execv(sys.argv[1], sys.argv[1:])
