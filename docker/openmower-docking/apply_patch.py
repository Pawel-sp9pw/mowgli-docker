import argparse
from pathlib import Path


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError("Unsupported FTC source: expected exactly one occurrence of " + repr(old))
    return source.replace(old, new, 1)


def patch(workspace):
    package = workspace / "src/lib/ftc_local_planner"
    header_path = package / "include/ftc_local_planner/ftc_planner.h"
    source_path = package / "src/ftc_planner.cpp"
    header = header_path.read_text()
    source = source_path.read_text()

    header = replace_once(header, "        FTCPlannerConfig config;", """        FTCPlannerConfig config;
        bool mowgli_docking_enabled = false;
        bool mowgli_docking_active = false;""")
    source = replace_once(source, "#include <ftc_local_planner/ftc_planner.h>", """#include <ftc_local_planner/ftc_planner.h>
#include \"ftc_local_planner/docking_control.h\"""")
    source = replace_once(source, '        ros::NodeHandle private_nh("~/" + name);', """        ros::NodeHandle private_nh("~/" + name);
        private_nh.param("mowgli_docking_no_spin", mowgli_docking_enabled, true);
        mowgli_docking_enabled = mowgli_docking_enabled && name == "DockingFTCPlanner";
        if (mowgli_docking_enabled)
            ROS_WARN("Mowgli docking no-spin patch active (forward straight plans only).");""")
    source = replace_once(source, "        global_plan = plan;", """        mowgli_docking_active = false;
        if (mowgli_docking_enabled && plan.size() > 2)
        {
            Eigen::Affine3d start_pose;
            tf2::fromMsg(plan.front().pose, start_pose);
            const Eigen::Quaterniond start_rotation(start_pose.linear());
            double previous_forward = 0.0;
            bool straight_forward = true;
            for (const auto &waypoint : plan)
            {
                Eigen::Affine3d waypoint_pose;
                tf2::fromMsg(waypoint.pose, waypoint_pose);
                const Eigen::Vector3d relative = start_pose.inverse() * waypoint_pose.translation();
                const Eigen::Quaterniond rotation(waypoint_pose.linear());
                if (!relative.allFinite() || !rotation.coeffs().allFinite() ||
                    std::abs(relative.y()) > 0.0001 || std::abs(relative.z()) > 0.0001 ||
                    relative.x() < previous_forward - 0.0001 ||
                    start_rotation.angularDistance(rotation) > 0.0001)
                {
                    straight_forward = false;
                    break;
                }
                previous_forward = relative.x();
            }
            mowgli_docking_active = straight_forward && previous_forward > 0.0;
        }
        global_plan = plan;""")
    source = replace_once(source, "        update_control_point(dt);", """        if (mowgli_docking_active && (!std::isfinite(dt) || dt <= 0.0))
        {
            is_crashed = true;
            cmd_vel.twist.linear.x = 0.0;
            cmd_vel.twist.angular.z = 0.0;
            return RET_COLLISION;
        }
        update_control_point(dt);
        if (mowgli_docking_active &&
            !mowgli_docking::valid_pose(lon_error, lat_error, angle_error, config.max_follow_distance))
        {
            ROS_ERROR("Mowgli docking: alignment or position limit exceeded; stopping without rotation.");
            is_crashed = true;
            cmd_vel.twist.linear.x = 0.0;
            cmd_vel.twist.angular.z = 0.0;
            return RET_COLLISION;
        }""")
    source = replace_once(source, "        case PRE_ROTATE:\n        {", """        case PRE_ROTATE:
        {
            if (mowgli_docking_active)
                return FOLLOWING;""")
    source = replace_once(source, "        case WAITING_FOR_GOAL_APPROACH:\n        {\n            double distance = local_control_point.translation().norm();", """        case WAITING_FOR_GOAL_APPROACH:
        {
            double distance = local_control_point.translation().norm();
            if (mowgli_docking_active)
            {
                if (distance < std::min(config.max_goal_distance_error, mowgli_docking::goal_distance))
                    return FINISHED;
                if (time_in_current_state() > config.goal_timeout || lon_error <= 0.0)
                {
                    ROS_ERROR("Mowgli docking: final position not reached; stopping without rotation.");
                    is_crashed = true;
                    return FINISHED;
                }
                return WAITING_FOR_GOAL_APPROACH;
            }""")
    source = replace_once(source, "        case POST_ROTATE:\n        {", """        case POST_ROTATE:
        {
            if (mowgli_docking_active)
            {
                is_crashed = true;
                return FINISHED;
            }""")
    anchor = "    void FTCPlanner::calculate_velocity_commands("
    prefix, separator, commands = source.partition(anchor)
    if not separator or commands.count("        if (current_state == FOLLOWING)\n") != 2:
        raise RuntimeError("Unsupported FTC source: velocity command branches changed")
    commands = commands.replace("        if (current_state == FOLLOWING)\n", """        if (current_state == FOLLOWING ||
            (mowgli_docking_active && current_state == WAITING_FOR_GOAL_APPROACH))
""")
    commands = replace_once(commands, "        if (config.debug_pid)\n", """        if (mowgli_docking_active)
        {
            const auto command = mowgli_docking::limit_command(
                cmd_vel.twist.linear.x, cmd_vel.twist.angular.z,
                config.max_cmd_vel_speed, config.max_cmd_vel_ang);
            cmd_vel.twist.linear.x = command.linear;
            cmd_vel.twist.angular.z = command.angular;
            if (command.failed)
                is_crashed = true;
        }

        if (config.debug_pid)
""")
    source = prefix + separator + commands

    header_path.write_text(header)
    source_path.write_text(source)
    helper = Path(__file__).with_name("docking_control.h").read_text()
    (header_path.parent / "docking_control.h").write_text(helper)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    patch(parser.parse_args().workspace)
