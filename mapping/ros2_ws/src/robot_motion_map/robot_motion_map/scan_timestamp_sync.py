#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import LaserScan


class ScanTimestampSync(Node):

    def __init__(self):
        super().__init__("scan_timestamp_sync")

        self.sub = self.create_subscription(
            LaserScan, "/sim/scan", self.scan_callback, qos_profile_sensor_data
        )

        self.pub = self.create_publisher(
            LaserScan, "/sim/scan_sync", qos_profile_sensor_data
        )

        self.get_logger().info("Scan timestamp sync: /sim/scan -> /sim/scan_sync")

    def scan_callback(self, msg):
        now = self.get_clock().now()

        # /clock이 아직 들어오기 전인 경우 publish하지 않음
        if now.nanoseconds == 0:
            return

        msg.header.stamp = now.to_msg()
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = ScanTimestampSync()

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
