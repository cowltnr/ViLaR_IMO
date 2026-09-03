import unittest

from scripts.configure_warehouse_worker_behavior import (
    build_goal_candidates,
    build_worker_command_lines,
)


class ConfigureWarehouseWorkerBehaviorTest(unittest.TestCase):
    def test_builds_idle_goto_idle_and_return_sequence(self):
        lines = build_worker_command_lines(
            "Worker_01",
            start=(0.0, -1.25, 0.0),
            goal=(0.0, 4.75, 0.0),
        )

        self.assertEqual(
            lines,
            [
                "Worker_01 Idle 2",
                "Worker_01 GoTo 0.000 4.750 0.000 _",
                "Worker_01 Idle 3",
                "Worker_01 GoTo 0.000 -1.250 0.000 _",
                "Worker_01 Idle 3",
            ],
        )

    def test_rejects_identical_start_and_goal(self):
        with self.assertRaisesRegex(ValueError, "different"):
            build_worker_command_lines(
                "Worker_01",
                start=(1.0, 2.0, 0.0),
                goal=(1.0, 2.0, 0.0),
            )

    def test_builds_deterministic_six_meter_goal_candidates(self):
        candidates = build_goal_candidates((1.0, 2.0, 0.0))

        self.assertEqual(
            candidates,
            [
                (1.0, 8.0, 0.0),
                (7.0, 2.0, 0.0),
                (-5.0, 2.0, 0.0),
                (1.0, -4.0, 0.0),
                (5.0, 6.0, 0.0),
                (-3.0, 6.0, 0.0),
                (5.0, -2.0, 0.0),
                (-3.0, -2.0, 0.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
