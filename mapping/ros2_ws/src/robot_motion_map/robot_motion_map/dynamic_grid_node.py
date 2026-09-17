#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.qos import DurabilityPolicy
from rclpy.qos import ReliabilityPolicy

from geometry_msgs.msg import PointStamped
from nav_msgs.msg import OccupancyGrid


class DynamicGridNode(Node):

    def __init__(self):
        super().__init__("dynamic_grid_node")

        # Static Map은 한 번 받은 뒤에도 사용할 수 있도록
        # TRANSIENT_LOCAL QoS 사용
        map_qos = QoSProfile(depth=1)
        map_qos.reliability = ReliabilityPolicy.RELIABLE
        map_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.map_msg = None

        # Static Map
        self.map_sub = self.create_subscription(
            OccupancyGrid, "/map", self.map_callback, map_qos
        )

        # 테스트 Dynamic Object 위치
        self.object_sub = self.create_subscription(
            PointStamped, "/dynamic_object", self.object_callback, 10
        )

        # Dynamic Layer
        self.dynamic_pub = self.create_publisher(
            OccupancyGrid, "/dynamic_grid", map_qos
        )

        self.get_logger().info("Dynamic Grid Node started")

    def map_callback(self, msg):

        self.map_msg = msg

        self.get_logger().info(
            "Static map received: "
            f"{msg.info.width} x {msg.info.height}, "
            f"resolution={msg.info.resolution}"
        )

    def object_callback(self, msg):

        if self.map_msg is None:
            self.get_logger().warning("Static /map has not been received yet.")
            return

        if msg.header.frame_id not in ["", "map"]:
            self.get_logger().warning(
                f"Unsupported frame_id: {msg.header.frame_id}. " "Expected map."
            )
            return

        map_x = msg.point.x
        map_y = msg.point.y

        grid_x, grid_y = self.map_to_grid(map_x, map_y)

        width = self.map_msg.info.width
        height = self.map_msg.info.height

        if not (0 <= grid_x < width and 0 <= grid_y < height):
            self.get_logger().warning(
                f"Object outside map: "
                f"map=({map_x:.3f}, {map_y:.3f}), "
                f"grid=({grid_x}, {grid_y})"
            )
            return

        dynamic_map = OccupancyGrid()

        dynamic_map.header.stamp = self.get_clock().now().to_msg()

        dynamic_map.header.frame_id = "map"

        # Static Map과 완전히 같은 Grid 구조 사용
        dynamic_map.info = self.map_msg.info

        # -1:
        # 해당 Cell에 Dynamic 정보 없음
        dynamic_map.data = [-1] * (width * height)

        # OccupancyGrid index
        index = grid_y * width + grid_x

        # Dynamic Object 위치
        dynamic_map.data[index] = 100

        self.dynamic_pub.publish(dynamic_map)

        self.get_logger().info(
            f"Dynamic object: "
            f"map=({map_x:.5f}, {map_y:.5f}) "
            f"-> grid=({grid_x}, {grid_y}) "
            f"index={index}"
        )

    def map_to_grid(self, map_x, map_y):

        origin = self.map_msg.info.origin
        resolution = self.map_msg.info.resolution

        origin_x = origin.position.x
        origin_y = origin.position.y

        # 현재 Static Map yaw=0이므로
        # 기본 X/Y 변환 적용
        grid_x = math.floor((map_x - origin_x) / resolution)

        grid_y = math.floor((map_y - origin_y) / resolution)

        return grid_x, grid_y


def main(args=None):
    rclpy.init(args=args)

    node = DynamicGridNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
