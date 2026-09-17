import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    home = os.path.expanduser("~")
    pkg_share = get_package_share_directory("robot_motion_map")

    default_map = os.path.join(
        home,
        "ViLaR_IMO_semantic-dynamic-map",
        "mapping",
        "maps",
        "static",
        "static_map.yaml",
    )
    default_rviz = os.path.join(
        pkg_share,
        "rviz",
        "robot_motion_map.rviz",
    )

    map_yaml = LaunchConfiguration("map_yaml")
    launch_rviz = LaunchConfiguration("launch_rviz")
    rviz_config = LaunchConfiguration("rviz_config")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "map_yaml",
                default_value=default_map,
                description="Static map YAML path",
            ),
            DeclareLaunchArgument(
                "launch_rviz",
                default_value="true",
                description="Launch RViz2",
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=default_rviz,
                description="RViz2 config path",
            ),
            Node(
                package="robot_motion_map",
                executable="scan_timestamp_sync",
                name="scan_timestamp_sync",
                output="screen",
                parameters=[{"use_sim_time": True}],
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="map_to_odom_tf",
                output="screen",
                arguments=[
                    "--x",
                    "0",
                    "--y",
                    "0",
                    "--z",
                    "0",
                    "--roll",
                    "0",
                    "--pitch",
                    "0",
                    "--yaw",
                    "3.141592653589793",
                    "--frame-id",
                    "map",
                    "--child-frame-id",
                    "odom",
                ],
            ),
            LifecycleNode(
                package="nav2_map_server",
                executable="map_server",
                name="map_server",
                namespace="",
                output="screen",
                parameters=[
                    {"yaml_filename": map_yaml},
                    {"use_sim_time": True},
                ],
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_map",
                output="screen",
                parameters=[
                    {"use_sim_time": True},
                    {"autostart": True},
                    {"node_names": ["map_server"]},
                ],
            ),
            Node(
                package="robot_motion_map",
                executable="semantic_localization_node",
                name="semantic_localization_node",
                output="screen",
                parameters=[{"use_sim_time": True}],
            ),
            Node(
                package="robot_motion_map",
                executable="object_table_node",
                name="object_table_node",
                output="screen",
                parameters=[
                    {"use_sim_time": True},
                    {"ttl_sec": 2.0},
                    {"source_robot": "robot_0"},
                ],
            ),
            Node(
                package="robot_motion_map",
                executable="semantic_dynamic_grid_node",
                name="semantic_dynamic_grid_node",
                output="screen",
                parameters=[
                    {"use_sim_time": True},
                ],
            ),
            Node(
                package="robot_motion_map",
                executable="dynamic_grid_node",
                name="dynamic_grid_node",
                output="screen",
                parameters=[{"use_sim_time": True}],
            ),
            Node(
                package="waypoint_tools",
                executable="intent_decision",
                name="intent_decision",
                output="screen",
                parameters=[{"use_sim_time": True}],
            ),
            Node(
                package="waypoint_tools",
                executable="pure_pursuit_follower",
                name="pure_pursuit_follower",
                output="screen",
                parameters=[{"use_sim_time": True}],
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
                parameters=[{"use_sim_time": True}],
                condition=IfCondition(launch_rviz),
            ),
        ]
    )
