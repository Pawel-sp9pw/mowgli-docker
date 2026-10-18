ARG BASE_IMAGE=ghcr.io/jeremysalwen/open_mower_ros@sha256:8b3336582fa2351254632f3b904ba302f35eeca6ddd68c712e6d4d0605f5cd8e
FROM ${BASE_IMAGE} AS build
USER root
COPY docker/openmower-docking /tmp/mowgli-docking
RUN python3 /tmp/mowgli-docking/apply_patch.py /opt/open_mower_ros
RUN bash -c 'source /opt/ros/noetic/setup.bash && source /opt/open_mower_ros/devel/setup.bash && cmake -S /tmp/mowgli-docking -B /tmp/mowgli-docking-build -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/mowgli-docking-build --parallel 2'
RUN bash -c 'source /opt/ros/noetic/setup.bash && source /opt/open_mower_ros/devel/setup.bash && ldd -r /tmp/mowgli-docking-build/libftc_local_planner.so > /tmp/mowgli-link-check && ldd -r /tmp/mowgli-docking-build/mower_logic >> /tmp/mowgli-link-check && ldd -r /tmp/mowgli-docking-build/xbot_positioning >> /tmp/mowgli-link-check && cat /tmp/mowgli-link-check && ! grep -E "not found|undefined symbol" /tmp/mowgli-link-check'

FROM ${BASE_IMAGE}
USER root
COPY --from=build /tmp/mowgli-docking-build/libftc_local_planner.so /opt/open_mower_ros/devel/lib/libftc_local_planner.so
COPY --from=build /tmp/mowgli-docking-build/mower_logic /opt/open_mower_ros/devel/lib/mower_logic/mower_logic
COPY --from=build /tmp/mowgli-docking-build/xbot_positioning /opt/open_mower_ros/devel/lib/xbot_positioning/xbot_positioning
COPY --from=build /opt/open_mower_ros/src/lib/xbot_positioning/src/xbot_positioning.cpp /opt/open_mower_ros/src/lib/xbot_positioning/src/xbot_positioning.cpp
COPY docker/openmower-docking/heading_checkpoint.h docker/openmower-docking/heading_ros.h /opt/open_mower_ros/src/lib/xbot_positioning/src/
COPY --from=build /opt/open_mower_ros/src/lib/ftc_local_planner/src/ftc_planner.cpp /opt/open_mower_ros/src/lib/ftc_local_planner/src/ftc_planner.cpp
COPY --from=build /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/ftc_planner.h /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/ftc_planner.h
COPY --from=build /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/DockingBehavior.cpp /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/DockingBehavior.cpp
COPY --from=build /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/IdleBehavior.cpp /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/IdleBehavior.cpp
COPY --from=build /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/AreaRecordingBehavior.cpp /opt/open_mower_ros/src/mower_logic/src/mower_logic/behaviors/AreaRecordingBehavior.cpp
COPY --from=build /opt/open_mower_ros/src/open_mower/params/move_base_flex.yaml /opt/open_mower_ros/src/open_mower/params/move_base_flex.yaml
COPY --from=build /opt/open_mower_ros/src/open_mower/launch/include/_move_base.launch /opt/open_mower_ros/src/open_mower/launch/include/_move_base.launch
COPY docker/openmower-docking/register_controller.py /opt/mowgli-docking/register_controller.py
COPY docker/openmower-docking/gps_watchdog.py /opt/open_mower_ros/src/open_mower/scripts/gps_watchdog.py
COPY --from=build /opt/open_mower_ros/src/open_mower/launch/include/_comms.launch /opt/open_mower_ros/src/open_mower/launch/include/_comms.launch
RUN chmod +x /opt/open_mower_ros/src/open_mower/scripts/gps_watchdog.py
COPY docker/openmower-docking/docking_control.h /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/docking_control.h
LABEL io.mowgli.docking-fix="no-spin-v6"
USER openmower
