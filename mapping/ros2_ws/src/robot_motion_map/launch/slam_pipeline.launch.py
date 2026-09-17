import os

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    project_share = get_package_share_directory('robot_motion_map')
    slam_toolbox_share = get_package_share_directory('slam_toolbox')

    box_filter_config = os.path.join(
        project_share,
        'config',
        'box_filter.yaml'
    )

    slam_config = os.path.join(
        project_share,
        'config',
        'limo_slam.yaml'
    )

    # 1. /sim/scan timestamp 보정
    timestamp_sync = Node(
        package='robot_motion_map',
        executable='scan_timestamp_sync',
        name='scan_timestamp_sync',
        output='screen',
        parameters=[
            {'use_sim_time': True}
        ]
    )

    # 2. LIMO 자기 차체 LiDAR Point 제거
    laser_filter = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        namespace='sim',
        name='scan_to_scan_filter_chain',
        output='screen',
        parameters=[
            box_filter_config
        ],
        remappings=[
            ('scan', '/sim/scan_sync'),
            ('scan_filtered', '/sim/scan_filtered'),
        ]
    )

    # 3. SLAM Toolbox
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                slam_toolbox_share,
                'launch',
                'online_async_launch.py'
            )
        ),
        launch_arguments={
            'slam_params_file': slam_config,
            'use_sim_time': 'true',
        }.items()
    )

    return LaunchDescription([
        timestamp_sync,
        laser_filter,
        slam,
    ])
