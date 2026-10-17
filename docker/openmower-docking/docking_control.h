#ifndef MOWGLI_DOCKING_CONTROL_H
#define MOWGLI_DOCKING_CONTROL_H

#include <algorithm>
#include <cmath>

namespace mowgli_docking {

constexpr double max_speed = 0.1;
constexpr double max_lateral_error = 0.1;
constexpr double max_angle_error = 0.17453292519943295;
constexpr double goal_distance = 0.02;
constexpr double max_curvature = 2.0;

inline bool valid_pose(double longitudinal, double lateral, double angle, double follow_distance) {
    return std::isfinite(longitudinal) && std::isfinite(lateral) && std::isfinite(angle) &&
           std::isfinite(follow_distance) && follow_distance > 0.0 &&
           std::hypot(longitudinal, lateral) <= follow_distance &&
           std::abs(lateral) <= max_lateral_error && std::abs(angle) <= max_angle_error;
}

struct Command {
    double linear;
    double angular;
    bool failed;
};

inline Command limit_command(double linear, double angular, double speed_limit, double angular_limit) {
    if (!std::isfinite(linear) || !std::isfinite(angular) || !std::isfinite(speed_limit) ||
        !std::isfinite(angular_limit) || speed_limit <= 0.0 || angular_limit < 0.0) {
        return {0.0, 0.0, true};
    }
    const double speed = std::max(0.0, std::min(linear, std::min(speed_limit, max_speed)));
    const double turn_limit = std::min(angular_limit, max_curvature * speed);
    return {speed, std::max(-turn_limit, std::min(angular, turn_limit)), false};
}

}

#endif
