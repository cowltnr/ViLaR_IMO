import unittest

from scripts import configure_warehouse_worker_behavior as behavior


class ShelfGoalTest(unittest.TestCase):
    def test_one_way_command_has_final_heading_and_no_return(self):
        lines = behavior.build_destination_commands('Worker_01', (2, 5, 0.04), 90, 10)
        self.assertEqual(lines, ['Worker_01 Idle 2',
                                'Worker_01 GoTo 2.00000 5.00000 0.04000 90.00000',
                                'Worker_01 Idle 10.000'])

    def test_rejects_invalid_destination_values(self):
        for goal, yaw, wait in [((float('nan'), 0, 0), 0, 10),
                                ((1, 2, 3), float('inf'), 10),
                                ((1, 2, 3), 0, -1)]:
            with self.assertRaises(ValueError):
                behavior.build_destination_commands('Worker_01', goal, yaw, wait)

    def test_offset_compensation_preserves_cart_target(self):
        from scripts.warehouse_shelf_goal_config import worker_goal_for_cart
        self.assertEqual(worker_goal_for_cart((0, -1, 0), (0, 0, 0), (2, 20, 0)),
                         (2, 19, 0))

    def test_partial_path_is_rejected(self):
        with self.assertRaises(RuntimeError):
            behavior.validate_destination_path([(0, 0, 0), (1, 0, 0)],
                                               (0, 0, 0), (5, 0, 0))

    def test_full_path_is_accepted(self):
        behavior.validate_destination_path([(0, 0, 0), (1, 2, 0), (5, 0, 0)],
                                           (0, 0, 0), (5, 0, 0))
