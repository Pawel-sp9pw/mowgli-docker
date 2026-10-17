cmake_minimum_required(VERSION 3.10)
project(mowgli_docking_patch LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(catkin REQUIRED COMPONENTS
    costmap_2d dynamic_reconfigure geometry_msgs mbf_costmap_core mbf_msgs
    nav_core nav_msgs pluginlib roscpp std_msgs tf tf2_eigen tf2_geometry_msgs tf2_ros)
find_package(Eigen3 REQUIRED)

set(FTC_SOURCE /opt/open_mower_ros/src/lib/ftc_local_planner)
add_library(ftc_local_planner SHARED
    ${FTC_SOURCE}/src/ftc_planner.cpp
    ${FTC_SOURCE}/src/oscillation_detector.cpp)
target_include_directories(ftc_local_planner PRIVATE
    ${FTC_SOURCE}/include /opt/open_mower_ros/devel/include
    ${catkin_INCLUDE_DIRS} ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(ftc_local_planner ${catkin_LIBRARIES} Eigen3::Eigen)
