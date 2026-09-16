import unittest

from scripts import warehouse_multi_box_config as config


class SourceStackTest(unittest.TestCase):
    def test_offset_worker_does_not_pull_into_adjacent_box(self):
        from scripts.warehouse_unloading_live import pallet_transfer_points, path_collisions
        points = pallet_transfer_points((0,0,.835),(-1.74,.416,1.10146),
            (-1.038,-.344,.0427),(-.254,-.254,.21),(.254,.254,.71),
            (.51887,.51887,.25),.1,.03,3,1.912)
        adjacent = [('neighbor',(-.247,-.777,.71),(.265,-.265,.96))]
        self.assertEqual(path_collisions(points,(.51887,.51887,.25),adjacent),())
        self.assertAlmostEqual(points[2][1],0)

    def test_actual_supports_and_top_first_order(self):
        self.assertTrue(hasattr(config, 'SOURCE_SUPPORT_PATHS'))
        a, b, c, d = config.BOX_PATHS
        self.assertEqual(config.SOURCE_SUPPORT_PATHS[a], '/World/Environment/Warehouse/Box_25976/SM_CardBoxB_01')
        self.assertEqual(config.SOURCE_SUPPORT_PATHS[b], '/World/Environment/Warehouse/Box_25978/SM_CardBoxB_01')
        self.assertEqual(config.SOURCE_SUPPORT_PATHS[c], '/World/Environment/Warehouse/Box_25980/SM_CardBoxB_01')
        self.assertEqual(config.SOURCE_SUPPORT_PATHS[d], '/World/Environment/Warehouse/Box_25982/SM_CardBoxB_01')
        self.assertFalse(config.SOURCE_SEPARATION_ENABLED)

    def test_lift_before_horizontal_extraction(self):
        from scripts.warehouse_unloading_live import pallet_transfer_points
        points = pallet_transfer_points((0, 0, .835), (2, 0, 1.1),
            (-2, 0, 0), (-.3, -.3, .21), (.3, .3, .71),
            (.5, .5, .25), .1, .03, 3, 1.5)
        self.assertEqual(points[0], (0, 0, .835))
        self.assertEqual(points[1][:2], points[0][:2])
        self.assertAlmostEqual(points[1][2], .865)
        self.assertLess(points[2][0], 0)
        self.assertGreater(points[2][2] - .125, .71)
        self.assertEqual(points[-1], (2, 0, 1.1))

    def test_height_limit_is_not_relaxed(self):
        from scripts.warehouse_unloading_live import pallet_transfer_points
        with self.assertRaises(ValueError):
            pallet_transfer_points((0, 0, .835), (2, 0, 1.1),
                (-2, 0, 0), (-.3, -.3, .21), (.3, .3, .71),
                (.5, .5, .25), .1, .03, 3, 1.0)
