cmake_minimum_required(VERSION 3.10)
project(mowgli_docking_patch LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(catkin REQUIRED COMPONENTS
    actionlib costmap_2d dynamic_reconfigure geometry_msgs mbf_costmap_core mbf_msgs
    mower_map mower_msgs nav_core nav_msgs pluginlib robot_localization rosbag roscpp
    sensor_msgs slic3r_coverage_planner std_msgs tf tf2_eigen tf2_geometry_msgs tf2_ros
    xbot_msgs xbot_positioning)
find_package(Eigen3 REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(CRYPTOPP REQUIRED libcrypto++)

set(FTC_SOURCE /opt/open_mower_ros/src/lib/ftc_local_planner)
add_library(ftc_local_planner SHARED
    ${FTC_SOURCE}/src/ftc_planner.cpp
    ${FTC_SOURCE}/src/oscillation_detector.cpp)
target_include_directories(ftc_local_planner PRIVATE
    ${FTC_SOURCE}/include /opt/open_mower_ros/devel/include
    ${catkin_INCLUDE_DIRS} ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(ftc_local_planner ${catkin_LIBRARIES} Eigen3::Eigen)

set(MOWER_SOURCE /opt/open_mower_ros/src/mower_logic)
file(GLOB MOWER_BEHAVIORS ${MOWER_SOURCE}/src/mower_logic/behaviors/*.cpp)
add_executable(mower_logic ${MOWER_SOURCE}/src/mower_logic/mower_logic.cpp ${MOWER_BEHAVIORS})
target_include_directories(mower_logic PRIVATE
    ${MOWER_SOURCE}/include ${FTC_SOURCE}/include /opt/open_mower_ros/devel/include
    ${catkin_INCLUDE_DIRS} ${CRYPTOPP_INCLUDE_DIRS} ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(mower_logic ftc_local_planner ${catkin_LIBRARIES} ${CRYPTOPP_LIBRARIES} Eigen3::Eigen)

set(POSITIONING_SOURCE /opt/open_mower_ros/src/lib/xbot_positioning)
add_executable(xbot_positioning
    ${POSITIONING_SOURCE}/src/xbot_positioning.cpp
    ${POSITIONING_SOURCE}/src/xbot_positioning_core.cpp)
target_include_directories(xbot_positioning PRIVATE
    ${POSITIONING_SOURCE}/include /opt/open_mower_ros/devel/include
    ${catkin_INCLUDE_DIRS} ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(xbot_positioning ${catkin_LIBRARIES} Eigen3::Eigen)
