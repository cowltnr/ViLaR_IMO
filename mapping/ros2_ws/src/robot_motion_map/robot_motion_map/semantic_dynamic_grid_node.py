import math

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    DurabilityPolicy,
    HistoryPolicy,
)

from nav_msgs.msg import OccupancyGrid

from robot_motion_interfaces.msg import (
    SemanticDynamicGrid,
    ObjectDelta,
)


class SemanticDynamicGridNode(Node):

    def __init__(self):
        super().__init__("semantic_dynamic_grid_node")

        # Static map은 늦게 구독해도 마지막 map을 받아야 하므로
        # Transient Local 사용
        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.map_info = None

        # 현재 살아 있는 객체
        # key   : object_id
        # value : ObjectState
        self.objects = {}

        self.map_sub = self.create_subscription(
            OccupancyGrid,
            "/map",
            self.map_callback,
            map_qos,
        )

        # 기존 /semantic_object 직접 구독 제거
        # Object Table의 Delta를 입력으로 사용
        self.delta_sub = self.create_subscription(
            ObjectDelta,
            "/object_delta",
            self.delta_callback,
            10,
        )

        self.grid_pub = self.create_publisher(
            SemanticDynamicGrid,
            "/semantic_dynamic_grid",
            map_qos,
        )

        # RViz 시각화용
        self.viz_pub = self.create_publisher(
            OccupancyGrid,
            "/semantic_dynamic_grid_viz",
            map_qos,
        )

        self.get_logger().info(
            "Semantic Dynamic Grid Node started "
            "(input: /object_delta)"
        )

    def map_callback(self, msg):
        self.map_info = msg.info

        self.get_logger().info(
            f"Map initialized: "
            f"{msg.info.width} x {msg.info.height}, "
            f"resolution={msg.info.resolution}"
        )

        self.rebuild_and_publish()

    def delta_callback(self, msg):

        object_id = msg.object.object_id

        if msg.operation == ObjectDelta.CREATE:
            self.objects[object_id] = msg.object

            self.get_logger().info(
                f"GRID CREATE: "
                f"id={object_id}, "
                f"class={msg.object.class_name}"
            )

        elif msg.operation == ObjectDelta.UPDATE:
            self.objects[object_id] = msg.object

            self.get_logger().info(
                f"GRID UPDATE: "
                f"id={object_id}, "
                f"class={msg.object.class_name}"
            )

        elif msg.operation == ObjectDelta.DELETE:
            if object_id in self.objects:
                del self.objects[object_id]

            self.get_logger().info(
                f"GRID DELETE: id={object_id}"
            )

        else:
            self.get_logger().warning(
                f"Unknown ObjectDelta operation: "
                f"{msg.operation}"
            )
            return

        self.rebuild_and_publish()

    def rebuild_and_publish(self):

        if self.map_info is None:
            return

        width = self.map_info.width
        height = self.map_info.height
        resolution = self.map_info.resolution

        origin_x = self.map_info.origin.position.x
        origin_y = self.map_info.origin.position.y

        # 매번 현재 Object Table 상태를 기준으로 Grid 재구성
        grid_data = [-1] * (width * height)

        for object_id, obj in self.objects.items():

            gx = math.floor(
                (obj.position.x - origin_x)
                / resolution
            )

            gy = math.floor(
                (obj.position.y - origin_y)
                / resolution
            )

            if (
                gx < 0
                or gx >= width
                or gy < 0
                or gy >= height
            ):
                self.get_logger().warning(
                    f"Object outside grid: "
                    f"id={object_id}, "
                    f"grid=({gx}, {gy})"
                )
                continue

            index = gy * width + gx

            # class_id 0 -> encoded 1
            # class_id 1 -> encoded 2
            # ...
            encoded_value = int(obj.class_id) + 1

            grid_data[index] = encoded_value

            self.get_logger().info(
                f"GRID OBJECT: "
                f"id={object_id}, "
                f"class={obj.class_name}, "
                f"encoded={encoded_value}, "
                f"map=({obj.position.x:.3f}, "
                f"{obj.position.y:.3f}) "
                f"-> grid=({gx}, {gy})"
            )

        self.publish_grids(grid_data)

        self.get_logger().info(
            f"Active objects: {len(self.objects)}"
        )

    def publish_grids(self, grid_data):

        if self.map_info is None:
            return

        now = self.get_clock().now().to_msg()

        # Custom Semantic-Dynamic Grid
        semantic_grid = SemanticDynamicGrid()

        semantic_grid.header.stamp = now
        semantic_grid.header.frame_id = "map"

        semantic_grid.info = self.map_info
        semantic_grid.data = grid_data

        self.grid_pub.publish(semantic_grid)

        # RViz용 OccupancyGrid
        viz_grid = OccupancyGrid()

        viz_grid.header.stamp = now
        viz_grid.header.frame_id = "map"

        viz_grid.info = self.map_info

        viz_data = []

        for value in grid_data:

            if value == -1:
                viz_data.append(-1)

            elif value == 0:
                viz_data.append(0)

            else:
                # Semantic object는 RViz에서는 occupied로 표시
                viz_data.append(100)

        viz_grid.data = viz_data

        self.viz_pub.publish(viz_grid)


def main(args=None):
    rclpy.init(args=args)

    node = SemanticDynamicGridNode()

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
