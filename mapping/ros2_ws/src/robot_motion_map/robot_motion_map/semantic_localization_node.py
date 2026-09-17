import json
import math

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.clock import ClockType

from std_msgs.msg import String
from geometry_msgs.msg import PointStamped
from visualization_msgs.msg import Marker
from robot_motion_interfaces.msg import SemanticObject

from tf2_ros import Buffer, TransformListener, TransformException

CLASS_TO_ID = {
    "person": 0,
}
class SemanticLocalizationNode(Node):

    def __init__(self):
        super().__init__("semantic_localization_node")

        self.tf_buffer = Buffer(cache_time=Duration(seconds=30.0))
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.subscription = self.create_subscription(
            String,
            "/dynamic_object_detection",
            self.detection_callback,
            10,
        )

        self.publisher = self.create_publisher(
            PointStamped,
            "/dynamic_object",
            10,
        )

        self.marker_publisher = self.create_publisher(
            Marker,
            "/dynamic_object_marker",
            10,
        )
        self.semantic_object_pub = self.create_publisher(
            SemanticObject,
            "/semantic_object",
            10,
        )
        self.get_logger().info("Semantic Localization Node started")

    def detection_callback(self, msg):

        try:
            data = json.loads(msg.data)
        except Exception as e:
            self.get_logger().error(f"JSON parse error: {e}")
            return

        distance = data.get("distance")
        angle_deg = data.get("angle_deg")
        timestamp = data.get("ros_timestamp")

        if distance is None or angle_deg is None or timestamp is None:
            self.get_logger().warning("Missing detection data")
            return

        sec = int(timestamp["sec"])
        nanosec = int(timestamp["nanosec"])

        # degree → radian
        angle_rad = math.radians(float(angle_deg))

        # laser_link 기준 객체 상대 좌표
        x_laser = float(distance) * math.cos(angle_rad)
        y_laser = float(distance) * math.sin(angle_rad)

        # LiDAR 측정 시각
        query_time = Time(
            nanoseconds=sec * 1_000_000_000 + nanosec,
            clock_type=ClockType.ROS_TIME,
        )

        try:
            transform = self.tf_buffer.lookup_transform(
                "map",
                "laser_link",
                query_time,
                timeout=Duration(seconds=0.2),
            )

        except TransformException as e:
            self.get_logger().warning(f"TF lookup failed at {sec}.{nanosec:09d}: {e}")
            return

        tx = transform.transform.translation.x
        ty = transform.transform.translation.y

        q = transform.transform.rotation

        # Quaternion → yaw
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )

        # laser_link → map
        map_x = tx + math.cos(yaw) * x_laser - math.sin(yaw) * y_laser
        map_y = ty + math.sin(yaw) * x_laser + math.cos(yaw) * y_laser

        point = PointStamped()

        point.header.frame_id = "map"
        point.header.stamp.sec = sec
        point.header.stamp.nanosec = nanosec

        point.point.x = map_x
        point.point.y = map_y
        point.point.z = 0.0

        self.publisher.publish(point)

        # RViz 시각화용 Person Marker
        marker = Marker()

        marker.header.frame_id = "map"
        marker.header.stamp.sec = sec
        marker.header.stamp.nanosec = nanosec

        marker.ns = "dynamic_person"
        marker.id = 0

        marker.type = Marker.CYLINDER
        marker.action = Marker.ADD

        # 계산된 Person Global 위치
        marker.pose.position.x = map_x
        marker.pose.position.y = map_y

        # 바닥 위에 보이도록 높이의 절반만큼 올림
        marker.pose.position.z = 0.85

        marker.pose.orientation.x = 0.0
        marker.pose.orientation.y = 0.0
        marker.pose.orientation.z = 0.0
        marker.pose.orientation.w = 1.0

        # 시각화용 크기
        marker.scale.x = 0.5
        marker.scale.y = 0.5
        marker.scale.z = 1.7

        # 빨간색
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
        marker.color.a = 1.0

        # 일정 시간 새 검출이 없으면 Marker 제거
        marker.lifetime.sec = 2
        self.marker_publisher.publish(marker)

        self.get_logger().info(
            f"Person: distance={distance:.3f} m, "
            f"angle={angle_deg:.2f} deg "
            f"-> map=({map_x:.3f}, {map_y:.3f})"
        )
        
        class_name = data.get("class", "unknown")

        # Semantic Object publish
        class_name = data.get("class", "unknown")

        if class_name in CLASS_TO_ID:
            semantic_msg = SemanticObject()

            semantic_msg.header.frame_id = "map"
            semantic_msg.header.stamp.sec = sec
            semantic_msg.header.stamp.nanosec = nanosec

            semantic_msg.class_id = CLASS_TO_ID[class_name]
            semantic_msg.class_name = class_name
            semantic_msg.confidence = float(data.get("conf", 0.0))

            semantic_msg.position.x = float(map_x)
            semantic_msg.position.y = float(map_y)
            semantic_msg.position.z = 0.0

            self.semantic_object_pub.publish(semantic_msg)

            self.get_logger().info(
                f"Semantic Object: "
                f"class={class_name}, "
                f"class_id={semantic_msg.class_id}, "
                f"conf={semantic_msg.confidence:.2f}, "
                f"map=({map_x:.3f}, {map_y:.3f})"
            )


def main(args=None):
    rclpy.init(args=args)

    node = SemanticLocalizationNode()

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
