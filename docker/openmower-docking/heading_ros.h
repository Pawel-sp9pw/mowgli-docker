#ifndef MOWGLI_HEADING_ROS_H
#define MOWGLI_HEADING_ROS_H

#include "heading_checkpoint.h"
#include <cerrno>
#include <cstdlib>

bool mowgli_restore_heading = true;
bool mowgli_heading_known = false;
bool mowgli_heading_pending = false;
bool mowgli_heading_saved = false;
int mowgli_heading_samples = 0;
std::string mowgli_heading_path;
mowgli_heading::Checkpoint mowgli_saved_heading;
ros::WallTime mowgli_stationary_since;
ros::WallTime mowgli_last_heading_save;
ros::WallTime mowgli_last_speed;

bool mowgli_invalidate_heading_checkpoint() {
    mowgli_heading_pending = false;
    if (!mowgli_restore_heading || mowgli_heading_path.empty())
        return true;
    if (std::remove(mowgli_heading_path.c_str()) == 0 || errno == ENOENT) {
        mowgli_heading_saved = false;
        return true;
    } else {
        mowgli_heading_known = false;
        ROS_ERROR_THROTTLE(5, "Mowgli heading v4: cannot invalidate old checkpoint; stop and repair persistent storage before restarting.");
        return false;
    }
}

void mowgli_initialize_heading(ros::NodeHandle &parameters) {
    parameters.param("mowgli_restore_stationary_heading", mowgli_restore_heading, true);
    if (!mowgli_restore_heading)
        return;
    const char *ros_home = std::getenv("ROS_HOME");
    const char *home = std::getenv("HOME");
    const std::string directory = ros_home ? ros_home : (home ? std::string(home) + "/.ros" : "/nonexistent");
    mowgli_heading_path = directory + "/mowgli-heading-v1.txt";
    mowgli_heading_pending = mowgli_heading::read(
        mowgli_heading_path, mowgli_saved_heading, ros::WallTime::now().toSec());
    mowgli_heading_saved = mowgli_heading_pending;
    ROS_WARN_STREAM("Mowgli heading v4: checkpoint=" << mowgli_heading_pending
        << "; restore requires unchanged physical heading while powered off.");
    if (!mowgli_heading_pending)
        ROS_WARN("Mowgli heading v4: no valid stationary checkpoint; initialize pose at the dock before autonomous travel.");
}

void mowgli_track_stationary(double angular_velocity) {
    if (!mowgli_restore_heading)
        return;
    const auto now = ros::WallTime::now();
    if (!mowgli_heading::stationary(vx, angular_velocity)) {
        mowgli_stationary_since = ros::WallTime();
        mowgli_heading_samples = 0;
        if (mowgli_heading_pending)
            ROS_ERROR("Mowgli heading v4: startup motion; saved heading rejected.");
        if (mowgli_heading_pending || mowgli_heading_saved)
            mowgli_invalidate_heading_checkpoint();
        return;
    }
    if ((now - mowgli_last_speed).toSec() > 0.5) {
        mowgli_stationary_since = ros::WallTime();
        mowgli_heading_samples = 0;
        if (!mowgli_last_speed.isZero() && (mowgli_heading_pending || mowgli_heading_saved))
            mowgli_invalidate_heading_checkpoint();
        return;
    }
    if (mowgli_stationary_since.isZero())
        mowgli_stationary_since = now;
    if (!mowgli_heading_known || !has_gps || (now - mowgli_stationary_since).toSec() < 2.0 ||
        (now - mowgli_last_heading_save).toSec() < 5.0 ||
        (ros::Time::now() - last_gps_time).toSec() < 0.0 ||
        (ros::Time::now() - last_gps_time).toSec() > 10.0)
        return;
    const auto state = core.getState();
    mowgli_heading::Checkpoint checkpoint;
    checkpoint.saved_at = now.toSec();
    checkpoint.yaw = state.theta();
    checkpoint.antenna_x = antenna_offset_x;
    checkpoint.antenna_y = antenna_offset_y;
    checkpoint.gps_x = state.x_pos() + std::cos(checkpoint.yaw) * antenna_offset_x - std::sin(checkpoint.yaw) * antenna_offset_y;
    checkpoint.gps_y = state.y_pos() + std::sin(checkpoint.yaw) * antenna_offset_x + std::cos(checkpoint.yaw) * antenna_offset_y;
    if (std::hypot(checkpoint.gps_x - last_gps.pose.pose.position.x,
                   checkpoint.gps_y - last_gps.pose.pose.position.y) > 0.25)
        return;
    mowgli_last_heading_save = now;
    if (mowgli_heading::write(mowgli_heading_path, checkpoint)) {
        mowgli_heading_saved = true;
        ROS_INFO_THROTTLE(30, "Mowgli heading v4: stationary heading checkpoint saved.");
    } else {
        ROS_ERROR_THROTTLE(30, "Mowgli heading v4: checkpoint write failed; restart heading will not be restored.");
    }
}

void mowgli_try_restore_heading(const xbot_msgs::AbsolutePose &gps) {
    if (!mowgli_restore_heading || !mowgli_heading_pending || !has_gyro ||
        mowgli_stationary_since.isZero() ||
        (ros::WallTime::now() - mowgli_stationary_since).toSec() < 2.0)
        return;
    const double gps_age = (ros::Time::now() - gps.header.stamp).toSec();
    const double imu_age = (ros::Time::now() - last_imu.header.stamp).toSec();
    if ((gps.flags & xbot_msgs::AbsolutePose::FLAG_GPS_RTK_FIXED) == 0 ||
        !std::isfinite(max_gps_accuracy) || max_gps_accuracy <= 0.0 ||
        !std::isfinite(gps.position_accuracy) || gps.position_accuracy < 0.0 ||
        gps.position_accuracy > max_gps_accuracy || gps_age < 0.0 || gps_age > 1.0 ||
        imu_age < 0.0 || imu_age > 0.5 ||
        (ros::WallTime::now() - mowgli_last_speed).toSec() > 0.5 ||
        !mowgli_heading::stationary(vx, last_imu.angular_velocity.z - gyro_offset)) {
        mowgli_heading_samples = 0;
        return;
    }
    if (!mowgli_heading::matches(mowgli_saved_heading, gps.pose.pose.position.x, gps.pose.pose.position.y,
                                 antenna_offset_x, antenna_offset_y, ros::WallTime::now().toSec())) {
        mowgli_heading_pending = false;
        ROS_ERROR("Mowgli heading v4: checkpoint position, antenna configuration or age mismatch; initialize pose again.");
        return;
    }
    if (++mowgli_heading_samples < 10)
        return;
    const double yaw = mowgli_saved_heading.yaw;
    const double base_x = gps.pose.pose.position.x - std::cos(yaw) * antenna_offset_x + std::sin(yaw) * antenna_offset_y;
    const double base_y = gps.pose.pose.position.y - std::sin(yaw) * antenna_offset_x - std::cos(yaw) * antenna_offset_y;
    core.setState(base_x, base_y, yaw, 0.0, 0.0);
    mowgli_heading_known = true;
    mowgli_heading_pending = false;
    ROS_WARN_STREAM("Mowgli heading v4 restored after stationary GPS validation: yaw_deg=" << yaw * (180.0 / std::acos(-1.0)));
}

#endif
