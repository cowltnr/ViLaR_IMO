import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    home = os.path.expanduser("~")
    sdv_dir = os.path.join(home, "ViLaR_IMO_semantic-dynamic-map")
    launch_ollama = LaunchConfiguration("launch_ollama")
    launch_edge = LaunchConfiguration("launch_edge")

    return LaunchDescription([
        DeclareLaunchArgument("launch_ollama", default_value="true"),
        DeclareLaunchArgument("launch_edge", default_value="true"),

        ExecuteProcess(
            cmd=["python", os.path.join(sdv_dir, "imo_server_lidar.py")],
            cwd=sdv_dir,
            output="screen",
        ),

        ExecuteProcess(
            cmd=["python", os.path.join(sdv_dir, "k8s_server.py")],
            cwd=sdv_dir,
            output="screen",
        ),

        ExecuteProcess(
            cmd=["ollama", "serve"],
            output="screen",
            condition=IfCondition(launch_ollama),
        ),

        TimerAction(
            period=3.0,
            actions=[
                ExecuteProcess(
                    cmd=["python", os.path.join(sdv_dir, "vlm_server.py")],
                    cwd=sdv_dir,
                    output="screen",
                )
            ],
        ),

        TimerAction(
            period=5.0,
            actions=[
                ExecuteProcess(
                    cmd=["python", os.path.join(sdv_dir, "edge_control.py")],
                    cwd=sdv_dir,
                    output="screen",
                    condition=IfCondition(launch_edge),
                )
            ],
        ),
    ])
