import rclpy

from rclpy.node import Node

from robot_motion_interfaces.msg import (
    SemanticObject,
    ObjectState,
    ObjectDelta,
)


class ObjectTableNode(Node):

    def __init__(self):
        super().__init__("object_table_node")

        self.declare_parameter("ttl_sec", 2.0)
        self.declare_parameter("source_robot", "robot_0")

        self.ttl_sec = (
            self.get_parameter("ttl_sec")
            .get_parameter_value()
            .double_value
        )

        self.source_robot = (
            self.get_parameter("source_robot")
            .get_parameter_value()
            .string_value
        )

        self.objects = {}

        self.subscription = self.create_subscription(
            SemanticObject,
            "/semantic_object",
            self.object_callback,
            10,
        )

        self.delta_pub = self.create_publisher(
            ObjectDelta,
            "/object_delta",
            10,
        )

        self.timer = self.create_timer(
            0.2,
            self.check_ttl,
        )

        self.get_logger().info(
            f"Object Table Node started, TTL={self.ttl_sec:.1f}s"
        )

    def object_callback(self, msg):

        # 현재는 closest_person 한 명만 처리하므로 임시 ID
        object_id = "person_0"

        is_new = object_id not in self.objects

        state = ObjectState()

        state.header = msg.header
        state.object_id = object_id

        state.class_id = msg.class_id
        state.class_name = msg.class_name

        state.confidence = msg.confidence

        state.position = msg.position

        state.last_seen = msg.header.stamp

        state.source_robot = self.source_robot

        self.objects[object_id] = {
            "state": state,
            "last_seen_ns":
                msg.header.stamp.sec * 1_000_000_000
                + msg.header.stamp.nanosec,
        }

        delta = ObjectDelta()

        if is_new:
            delta.operation = ObjectDelta.CREATE
            operation_name = "CREATE"
        else:
            delta.operation = ObjectDelta.UPDATE
            operation_name = "UPDATE"

        delta.object = state

        self.delta_pub.publish(delta)

        self.get_logger().info(
            f"{operation_name}: "
            f"id={object_id}, "
            f"class={state.class_name}, "
            f"pos=({state.position.x:.3f}, "
            f"{state.position.y:.3f})"
        )

    def check_ttl(self):

        now = self.get_clock().now().nanoseconds

        expired = []

        for object_id, record in self.objects.items():

            age_sec = (
                now - record["last_seen_ns"]
            ) / 1_000_000_000.0

            if age_sec > self.ttl_sec:
                expired.append(object_id)

        for object_id in expired:

            state = self.objects[
                object_id
            ]["state"]

            delta = ObjectDelta()

            delta.operation = ObjectDelta.DELETE
            delta.object = state

            self.delta_pub.publish(delta)

            del self.objects[object_id]

            self.get_logger().info(
                f"DELETE: id={object_id} "
                f"(TTL expired)"
            )


def main(args=None):

    rclpy.init(args=args)

    node = ObjectTableNode()

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
