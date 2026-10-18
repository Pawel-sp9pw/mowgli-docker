#!/usr/bin/env python3
"""Restart only the ROS GPS driver on persistent RTK FLOAT while the mower is stopped."""
import subprocess
import time

import rospy
from geometry_msgs.msg import TwistStamped
from mower_msgs.msg import HighLevelStatus
from xbot_msgs.msg import AbsolutePose


class GPSWatchdog:
    def __init__(self):
        self.float_since = None
        self.last_restart = 0.0
        self.attempts = 0
        self.last_gps_at = 0.0
        self.last_twist_at = 0.0
        self.stopped_since = None
        self.state = None
        self.fixed = False
        self.float_seen = False
        rospy.Subscriber("/ll/position/gps", AbsolutePose, self.on_gps, queue_size=5)
        rospy.Subscriber("/ll/diff_drive/measured_twist", TwistStamped, self.on_twist, queue_size=5)
        rospy.Subscriber("/mower_logic/current_state", HighLevelStatus, self.on_state, queue_size=5)

    def on_gps(self, msg):
        now = time.monotonic()
        self.last_gps_at = now
        self.fixed = bool(msg.flags & AbsolutePose.FLAG_GPS_RTK_FIXED)
        self.float_seen = bool(msg.flags & AbsolutePose.FLAG_GPS_RTK_FLOAT)
        if self.fixed or not self.float_seen:
            self.float_since = None
        elif self.float_since is None:
            self.float_since = now

    def on_twist(self, msg):
        now = time.monotonic()
        self.last_twist_at = now
        stationary = abs(msg.twist.linear.x) < 0.01 and abs(msg.twist.angular.z) < 0.02
        if not stationary:
            self.stopped_since = None
        elif self.stopped_since is None:
            self.stopped_since = now

    def on_state(self, msg):
        self.state = msg.state_name

    def eligible(self, now):
        return (
            self.float_since is not None
            and not self.fixed
            and self.float_seen
            and now - self.float_since >= 10.0
            and now - self.last_gps_at <= 2.0
            and self.state in ("IDLE", "PAUSED")
            and self.stopped_since is not None
            and now - self.stopped_since >= 2.0
            and now - self.last_twist_at <= 1.0
            and self.attempts < 3
            and (self.attempts == 0 or now - self.last_restart >= 60.0)
        )

    def run(self):
        rate = rospy.Rate(2)
        while not rospy.is_shutdown():
            now = time.monotonic()
            if self.eligible(now):
                self.attempts += 1
                self.last_restart = now
                self.float_since = None  # Require 10 more seconds of fresh FLOAT after restart.
                rospy.logwarn("Mowgli RTK watchdog: FLOAT for 10s, stopped mower; restarting GPS node only (%d/3)", self.attempts)
                try:
                    subprocess.run(["rosnode", "kill", "/ll/services/gps"], timeout=8, check=True)
                except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    rospy.logerr("Mowgli RTK watchdog: GPS node restart request failed: %s", exc)
            rate.sleep()


if __name__ == "__main__":
    rospy.init_node("mowgli_gps_watchdog")
    GPSWatchdog().run()
