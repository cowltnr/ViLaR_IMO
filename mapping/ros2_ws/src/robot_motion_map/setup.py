from setuptools import find_packages, setup
from glob import glob
import os

package_name = "robot_motion_map"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "rviz"), glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="eunjin",
    maintainer_email="eunijhwang@gmail.com",
    description="TODO: Package description",
    license="TODO: License declaration",
    extras_require={
        "test": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "scan_timestamp_sync = robot_motion_map.scan_timestamp_sync:main",
            "dynamic_grid_node = robot_motion_map.dynamic_grid_node:main",
            "semantic_localization_node = robot_motion_map.semantic_localization_node:main",
            "semantic_dynamic_grid_node = robot_motion_map.semantic_dynamic_grid_node:main",
            "object_table_node = robot_motion_map.object_table_node:main",
        ],
    },
)
