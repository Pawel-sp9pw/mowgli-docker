#ifndef MOWGLI_HEADING_CHECKPOINT_H
#define MOWGLI_HEADING_CHECKPOINT_H

#include <cmath>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <string>

namespace mowgli_heading {

enum class IntervalAction { Integrate, Discard, Reset };

inline IntervalAction classify_interval(double interval) {
    if (!std::isfinite(interval) || interval > 0.5 || interval < -0.5)
        return IntervalAction::Reset;
    if (interval <= 0.0)
        return IntervalAction::Discard;
    return IntervalAction::Integrate;
}

struct Checkpoint {
    double saved_at = 0.0;
    double gps_x = 0.0;
    double gps_y = 0.0;
    double yaw = 0.0;
    double antenna_x = 0.0;
    double antenna_y = 0.0;
};

inline bool valid(const Checkpoint &checkpoint, double now) {
    return std::isfinite(now) && std::isfinite(checkpoint.saved_at) && checkpoint.saved_at > 0.0 &&
           now >= checkpoint.saved_at && now - checkpoint.saved_at <= 86400.0 &&
           std::isfinite(checkpoint.gps_x) && std::isfinite(checkpoint.gps_y) &&
           std::isfinite(checkpoint.yaw) && std::isfinite(checkpoint.antenna_x) &&
           std::isfinite(checkpoint.antenna_y);
}

inline bool matches(const Checkpoint &checkpoint, double gps_x, double gps_y,
                    double antenna_x, double antenna_y, double now) {
    return valid(checkpoint, now) && std::isfinite(gps_x) && std::isfinite(gps_y) &&
           std::isfinite(antenna_x) && std::isfinite(antenna_y) &&
           std::hypot(gps_x - checkpoint.gps_x, gps_y - checkpoint.gps_y) <= 0.25 &&
           std::abs(antenna_x - checkpoint.antenna_x) < 0.0001 &&
           std::abs(antenna_y - checkpoint.antenna_y) < 0.0001;
}

inline bool stationary(double linear, double angular) {
    return std::isfinite(linear) && std::isfinite(angular) &&
           std::abs(linear) < 0.01 && std::abs(angular) < 0.02;
}

inline bool read(const std::string &path, Checkpoint &checkpoint, double now) {
    std::ifstream input(path);
    std::string version;
    Checkpoint candidate;
    if (!(input >> version >> candidate.saved_at >> candidate.gps_x >> candidate.gps_y >>
          candidate.yaw >> candidate.antenna_x >> candidate.antenna_y) || version != "mowgli-heading-v1" ||
        !valid(candidate, now))
        return false;
    checkpoint = candidate;
    return true;
}

inline bool write(const std::string &path, const Checkpoint &checkpoint) {
    if (!valid(checkpoint, checkpoint.saved_at))
        return false;
    const std::string temporary = path + ".tmp";
    std::ofstream output(temporary, std::ios::trunc);
    output << "mowgli-heading-v1 " << std::setprecision(17) << checkpoint.saved_at << ' ' <<
        checkpoint.gps_x << ' ' << checkpoint.gps_y << ' ' << checkpoint.yaw << ' ' <<
        checkpoint.antenna_x << ' ' << checkpoint.antenna_y << '\n';
    output.close();
    if (!output || std::rename(temporary.c_str(), path.c_str()) != 0) {
        std::remove(temporary.c_str());
        return false;
    }
    return true;
}

}

#endif
