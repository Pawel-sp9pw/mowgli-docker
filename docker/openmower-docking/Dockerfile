ARG BASE_IMAGE=ghcr.io/jeremysalwen/open_mower_ros@sha256:8b3336582fa2351254632f3b904ba302f35eeca6ddd68c712e6d4d0605f5cd8e
FROM ${BASE_IMAGE} AS build
USER root
COPY docker/openmower-docking /tmp/mowgli-docking
RUN python3 /tmp/mowgli-docking/apply_patch.py /opt/open_mower_ros
RUN bash -c 'source /opt/ros/noetic/setup.bash && source /opt/open_mower_ros/devel/setup.bash && cmake -S /tmp/mowgli-docking -B /tmp/mowgli-docking-build -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/mowgli-docking-build --parallel 2'
RUN bash -c 'source /opt/ros/noetic/setup.bash && source /opt/open_mower_ros/devel/setup.bash && ldd -r /tmp/mowgli-docking-build/libftc_local_planner.so > /tmp/mowgli-link-check && cat /tmp/mowgli-link-check && ! grep -E "not found|undefined symbol" /tmp/mowgli-link-check'

FROM ${BASE_IMAGE}
USER root
COPY --from=build /tmp/mowgli-docking-build/libftc_local_planner.so /opt/open_mower_ros/devel/lib/libftc_local_planner.so
COPY --from=build /opt/open_mower_ros/src/lib/ftc_local_planner/src/ftc_planner.cpp /opt/open_mower_ros/src/lib/ftc_local_planner/src/ftc_planner.cpp
COPY --from=build /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/ftc_planner.h /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/ftc_planner.h
COPY docker/openmower-docking/docking_control.h /opt/open_mower_ros/src/lib/ftc_local_planner/include/ftc_local_planner/docking_control.h
LABEL io.mowgli.docking-fix="no-spin-v1"
USER openmower
