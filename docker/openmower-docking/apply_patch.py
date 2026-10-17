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
        bool mowgli_approach_controller = false;
        ros::Publisher mowgli_approach_plan_pub;
        bool mowgli_docking_enabled = false;
        bool mowgli_docking_active = false;""")
    source = replace_once(source, "#include <ftc_local_planner/ftc_planner.h>", """#include <ftc_local_planner/ftc_planner.h>
#include \"ftc_local_planner/docking_control.h\"
#include <stdexcept>""")
    source = replace_once(source, "    FTCPlanner::FTCPlanner()", """    ros::Publisher mowgli_compatible_plan_publisher()
    {
        static ros::NodeHandle legacy_nh("~/FTCPlanner");
        static ros::Publisher publisher = legacy_nh.advertise<nav_msgs::Path>("global_plan", 1, true);
        return publisher;
    }

    FTCPlanner::FTCPlanner()""")
    source = replace_once(source, '        ros::NodeHandle private_nh("~/" + name);', """        ros::NodeHandle private_nh("~/" + name);
        mowgli_approach_controller = name == "DockingApproachFTCPlanner";
        if (mowgli_approach_controller)
        {
            ros::NodeHandle controller_nh("~");
            XmlRpc::XmlRpcValue approach_config;
            if (!controller_nh.getParam("FTCPlanner", approach_config))
                throw std::runtime_error("Mowgli docking: missing FTCPlanner configuration");
            controller_nh.setParam(name, approach_config);
        }
        private_nh.param("mowgli_docking_no_spin", mowgli_docking_enabled, true);
        mowgli_docking_enabled = mowgli_docking_enabled &&
            (name == "DockingFTCPlanner" || mowgli_approach_controller);
        if (mowgli_docking_enabled)
            ROS_WARN_STREAM("Mowgli docking no-spin v4 initialized: " << name);""")
    source = replace_once(source,
        '        global_plan_pub = private_nh.advertise<nav_msgs::Path>("global_plan", 1, true);',
        """        global_plan_pub = name == "FTCPlanner" ? mowgli_compatible_plan_publisher() :
            private_nh.advertise<nav_msgs::Path>("global_plan", 1, true);
        if (mowgli_approach_controller)
            mowgli_approach_plan_pub = mowgli_compatible_plan_publisher();""")
    source = replace_once(source, "        global_plan_pub.publish(path);", """        global_plan_pub.publish(path);
        if (mowgli_approach_controller)
            mowgli_approach_plan_pub.publish(path);""")
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
        if (mowgli_docking_active || mowgli_approach_controller)
            ROS_WARN_STREAM("Mowgli docking v4 plan: approach=" << mowgli_approach_controller
                << ", straight_no_spin=" << mowgli_docking_active);
        global_plan = plan;""")
    source = replace_once(source, "        update_control_point(dt);", """        if ((mowgli_docking_active || mowgli_approach_controller) &&
            (!std::isfinite(dt) || dt <= 0.0 ||
             !std::isfinite(config.max_follow_distance) || config.max_follow_distance <= 0.0 ||
             !std::isfinite(config.max_cmd_vel_speed) || config.max_cmd_vel_speed <= 0.0 ||
             !std::isfinite(config.speed_fast) || config.speed_fast < 0.0 ||
             !std::isfinite(config.speed_slow) || config.speed_slow < 0.0 ||
             !std::isfinite(config.acceleration) || config.acceleration < 0.0))
        {
            is_crashed = true;
            cmd_vel.twist.linear.x = 0.0;
            cmd_vel.twist.angular.z = 0.0;
            return RET_COLLISION;
        }
        update_control_point(dt);
        const bool valid_docking_pose = mowgli_approach_controller ?
            mowgli_docking::valid_approach_pose(lon_error, lat_error, angle_error,
                config.max_follow_distance, config.max_goal_distance_error,
                config.max_goal_angle_error * (M_PI / 180.0)) :
            mowgli_docking::valid_pose(lon_error, lat_error, angle_error, config.max_follow_distance);
        if (mowgli_docking_active && !valid_docking_pose)
        {
            ROS_ERROR_STREAM("Mowgli docking v4 limit: stage=" << (mowgli_approach_controller ? "approach" : "entry")
                << ", lon=" << lon_error << ", lat=" << lat_error
                << ", angle_deg=" << angle_error * (180.0 / M_PI)
                << ", follow_limit=" << config.max_follow_distance
                << ", lateral_limit=" << (mowgli_approach_controller ? config.max_follow_distance : mowgli_docking::max_lateral_error)
                << ", angle_limit_deg=" << (mowgli_approach_controller ? 45.0 : 10.0));
            is_crashed = true;
            cmd_vel.twist.linear.x = 0.0;
            cmd_vel.twist.angular.z = 0.0;
            return RET_COLLISION;
        }
        if (mowgli_approach_controller && !mowgli_docking_active &&
            current_state == WAITING_FOR_GOAL_APPROACH &&
            (!std::isfinite(lon_error) || !std::isfinite(lat_error) || !std::isfinite(angle_error) ||
             local_control_point.translation().norm() > config.max_follow_distance))
        {
            ROS_ERROR("Mowgli docking approach: invalid final position; stopping.");
            is_crashed = true;
            cmd_vel.twist.linear.x = 0.0;
            cmd_vel.twist.angular.z = 0.0;
            return RET_COLLISION;
        }""")
    source = replace_once(source, "            current_state = new_planner_state;", """            current_state = new_planner_state;
            if (mowgli_approach_controller && current_state == POST_ROTATE)
            {
                cmd_vel.twist.linear.x = 0.0;
                cmd_vel.twist.angular.z = 0.0;
                return RET_SUCCESS;
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
                const bool reached = mowgli_approach_controller ?
                    mowgli_docking::approach_goal_reached(distance, angle_error,
                        config.max_goal_distance_error, config.max_goal_angle_error * (M_PI / 180.0)) :
                    distance < std::min(config.max_goal_distance_error, mowgli_docking::goal_distance);
                if (reached)
                    return FINISHED;
                if (time_in_current_state() > config.goal_timeout || lon_error <= 0.0)
                {
                    ROS_ERROR_STREAM("Mowgli docking v4 final pose not reached: approach=" << mowgli_approach_controller
                        << ", distance=" << distance << ", lon=" << lon_error << ", lat=" << lat_error
                        << ", angle_deg=" << angle_error * (180.0 / M_PI));
                    is_crashed = true;
                    return FINISHED;
                }
                return WAITING_FOR_GOAL_APPROACH;
            }
            if (mowgli_approach_controller)
            {
                if (distance < config.max_goal_distance_error)
                    return POST_ROTATE;
                if (time_in_current_state() > config.goal_timeout || lon_error <= 0.0)
                {
                    ROS_ERROR("Mowgli docking approach: final position not reached; stopping without rotation.");
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
    source = replace_once(source, "            speed = speed * velocity_limit;", """            if (mowgli_docking_active)
            {
                speed = mowgli_docking::reference_speed(speed, config.max_cmd_vel_speed);
                current_movement_speed = mowgli_docking::reference_speed(
                    current_movement_speed, config.max_cmd_vel_speed);
            }
            speed = speed * velocity_limit;""")
    anchor = "    void FTCPlanner::calculate_velocity_commands("
    prefix, separator, commands = source.partition(anchor)
    if not separator or commands.count("        if (current_state == FOLLOWING)\n") != 2:
        raise RuntimeError("Unsupported FTC source: velocity command branches changed")
    commands = commands.replace("        if (current_state == FOLLOWING)\n", """        if (current_state == FOLLOWING ||
            ((mowgli_docking_active || mowgli_approach_controller) && current_state == WAITING_FOR_GOAL_APPROACH))
""")
    commands = replace_once(commands, "        if (config.debug_pid)\n", """        if (mowgli_docking_active ||
            (mowgli_approach_controller && current_state == WAITING_FOR_GOAL_APPROACH))
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

    behavior_path = workspace / "src/mower_logic/src/mower_logic/behaviors/DockingBehavior.cpp"
    behavior = behavior_path.read_text()
    if behavior.count('controller = "FTCPlanner";') != 2:
        raise RuntimeError("Unsupported docking behavior: expected two approach goals")
    behavior = behavior.replace('controller = "FTCPlanner";', 'controller = "DockingApproachFTCPlanner";')
    if behavior.count('controller = "DockingFTCPlanner";') != 1:
        raise RuntimeError("Unsupported docking behavior: final docking controller changed")

    params_path = workspace / "src/open_mower/params/move_base_flex.yaml"
    params = params_path.read_text()
    controller_entry = "  - name: DockingFTCPlanner\n    type: ftc_local_planner/FTCPlanner"
    params = replace_once(params, controller_entry, controller_entry +
        "\n  - name: DockingApproachFTCPlanner\n    type: ftc_local_planner/FTCPlanner")

    launch_path = workspace / "src/open_mower/launch/include/_move_base.launch"
    launch = replace_once(launch_path.read_text(),
        '<node name="move_base_flex" pkg="mbf_costmap_nav"',
        '<node launch-prefix="/usr/bin/python3 /opt/mowgli-docking/register_controller.py" '
        'name="move_base_flex" pkg="mbf_costmap_nav"')

    positioning_path = workspace / "src/lib/xbot_positioning/src/xbot_positioning.cpp"
    positioning = positioning_path.read_text()
    positioning = replace_once(positioning, "void onImu(const sensor_msgs::Imu::ConstPtr &msg) {",
        '#include "heading_ros.h"\n\nvoid onImu(const sensor_msgs::Imu::ConstPtr &msg) {')
    positioning = replace_once(positioning,
        "    core.predict(vx, msg->angular_velocity.z - gyro_offset, (msg->header.stamp - last_imu.header.stamp).toSec());",
        """    const double mowgli_imu_dt = (msg->header.stamp - last_imu.header.stamp).toSec();
    if (!std::isfinite(mowgli_imu_dt) || mowgli_imu_dt <= 0.0 || mowgli_imu_dt > 0.5)
    {
        last_imu = *msg;
        if (mowgli_restore_heading)
        {
            mowgli_invalidate_heading_checkpoint();
            mowgli_heading_known = false;
        }
        ROS_ERROR_THROTTLE(5, "Mowgli heading v4: invalid IMU interval; initialize heading again.");
        return;
    }
    mowgli_track_stationary(msg->angular_velocity.z - gyro_offset);
    core.predict(vx, msg->angular_velocity.z - gyro_offset, mowgli_imu_dt);""")
    positioning = replace_once(positioning,
        '            ROS_WARN("Skipped gyro calibration");\n            has_gyro = true;',
        '            ROS_WARN("Skipped gyro calibration");\n            last_imu = *msg;\n            has_gyro = true;')
    positioning = replace_once(positioning, "    xb_absolute_pose_msg.orientation_valid = true;",
        "    xb_absolute_pose_msg.orientation_valid = !mowgli_restore_heading || mowgli_heading_known;")
    positioning = replace_once(positioning, "    vx = d_ticks / dt;",
        "    vx = d_ticks / dt;\n    mowgli_last_speed = ros::WallTime::now();")
    positioning = replace_once(positioning, "    vx = msg->twist.linear.x;",
        "    vx = msg->twist.linear.x;\n    mowgli_last_speed = ros::WallTime::now();")
    positioning = replace_once(positioning, "    tf2::Matrix3x3 m(q);",
        "    if (!std::isfinite(q.length2()) || std::abs(q.length2() - 1.0) > 0.001)\n"
        "        return false;\n    tf2::Matrix3x3 m(q);")
    positioning = replace_once(positioning, "    core.setState(req.robot_pose.position.x, req.robot_pose.position.y, yaw, 0, 0);",
        """    if (!std::isfinite(req.robot_pose.position.x) || !std::isfinite(req.robot_pose.position.y) ||
        !std::isfinite(yaw))
        return false;
    if (!mowgli_invalidate_heading_checkpoint())
        return false;
    core.setState(req.robot_pose.position.x, req.robot_pose.position.y, yaw, 0, 0);
    mowgli_heading_known = true;
    mowgli_heading_pending = false;""")
    positioning = replace_once(positioning, "void onPose(const xbot_msgs::AbsolutePose::ConstPtr &msg) {",
        "void onPose(const xbot_msgs::AbsolutePose::ConstPtr &msg) {\n    mowgli_try_restore_heading(*msg);")
    positioning = replace_once(positioning, "    core.setAntennaOffset(antenna_offset_x, antenna_offset_y);",
        "    core.setAntennaOffset(antenna_offset_x, antenna_offset_y);\n    mowgli_initialize_heading(paramNh);")

    idle_path = workspace / "src/mower_logic/src/mower_logic/behaviors/IdleBehavior.cpp"
    idle = replace_once(idle_path.read_text(), "extern mower_msgs::Power getPower();",
        "extern mower_msgs::Power getPower();\nextern xbot_msgs::AbsolutePose getPose();")
    idle = replace_once(idle, "  ros::Rate r(25);", "  bool mowgli_dock_pose_initialized = false;\n  ros::Rate r(25);")
    idle = replace_once(idle,
        "    const float last_charge_v = utils::GetFirstValid({last_power.charge_voltage_adc, last_power.charge_voltage});",
        """    const float last_charge_v = utils::GetFirstValid({last_power.charge_voltage_adc, last_power.charge_voltage});
    const double mowgli_power_age = (ros::Time::now() - last_power.stamp).toSec();
    if (!mowgli_dock_pose_initialized && !getPose().orientation_valid &&
        last_charge_v > 5.0 && mowgli_power_age >= 0.0 && mowgli_power_age < 1.0)
    {
      setRobotPose(docking_pose_stamped.pose);
      mowgli_dock_pose_initialized = true;
      ROS_WARN("Mowgli heading v4: initialized heading from the charging dock.");
    }""")

    header_path.write_text(header)
    source_path.write_text(source)
    behavior_path.write_text(behavior)
    params_path.write_text(params)
    launch_path.write_text(launch)
    positioning_path.write_text(positioning)
    idle_path.write_text(idle)
    for helper_name in ("heading_checkpoint.h", "heading_ros.h"):
        (positioning_path.parent / helper_name).write_text(Path(__file__).with_name(helper_name).read_text())
    helper = Path(__file__).with_name("docking_control.h").read_text()
    (header_path.parent / "docking_control.h").write_text(helper)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    patch(parser.parse_args().workspace)
