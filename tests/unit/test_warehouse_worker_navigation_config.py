import math
import unittest

from scripts.warehouse_worker_navigation_config import (
    camera_target_distance,
    compute_navmesh_transform,
)


class WarehouseWorkerNavigationConfigTest(unittest.TestCase):
    def test_camera_target_distance_detects_collapsed_focus(self):
        distance = camera_target_distance(
            (-75.18466653595017, -45.46622404953717, 54.3585072151),
            (-75.17912853081683, -45.46292327670512, 54.35561255924889),
        )

        self.assertLess(distance, 0.01)
        self.assertTrue(math.isclose(distance, 0.0070670811, rel_tol=1e-6))

    def test_navmesh_transform_covers_floor_without_ceiling(self):
        center, scale = compute_navmesh_transform(
            minimum=(-20.0, -10.0, -0.1),
            maximum=(30.0, 15.0, 12.0),
            floor_z=0.0,
            margin_xy=1.0,
            below_floor=0.2,
            height=3.0,
        )

        self.assertEqual(center, (5.0, 2.5, 1.4))
        self.assertEqual(scale, (52.0, 27.0, 3.2))
        self.assertLess(center[2] + scale[2] / 2.0, 12.0)

    def test_navmesh_transform_rejects_invalid_bounds(self):
        with self.assertRaisesRegex(ValueError, "maximum"):
            compute_navmesh_transform(
                minimum=(1.0, 0.0, 0.0),
                maximum=(0.0, 1.0, 1.0),
                floor_z=0.0,
                margin_xy=1.0,
                below_floor=0.2,
                height=3.0,
            )


if __name__ == "__main__":
    unittest.main()
