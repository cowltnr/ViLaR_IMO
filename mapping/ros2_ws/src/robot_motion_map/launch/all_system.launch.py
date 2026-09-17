import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory("robot_motion_map")
    launch_dir = os.path.join(pkg_share, "launch")

    launch_rviz = LaunchConfiguration("launch_rviz")
    launch_ollama = LaunchConfiguration("launch_ollama")
    launch_edge = LaunchConfiguration("launch_edge")

    return LaunchDescription([
        DeclareLaunchArgument(
            "launch_rviz",
            default_value="true"
        ),

        DeclareLaunchArgument(
            "launch_ollama",
            default_value="true"
        ),

        DeclareLaunchArgument(
            "launch_edge",
            default_value="true"
        ),

        # ROS Core
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(launch_dir, "robot_core.launch.py")
            ),
            launch_arguments={
                "launch_rviz": launch_rviz,
            }.items(),
        ),

        # SDV_Robocar Services
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(launch_dir, "sdv_services.launch.py")
            ),
            launch_arguments={
                "launch_ollama": launch_ollama,
                "launch_edge": launch_edge,
            }.items(),
        ),
    ])
