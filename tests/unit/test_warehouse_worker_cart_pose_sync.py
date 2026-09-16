import math
import unittest

from scripts.warehouse_worker_cart_pose_sync import (
    PoseSyncController,
    compose_pose,
    normalize_quaternion_xyzw,
    relative_pose,
)


class WarehouseWorkerCartPoseMathTest(unittest.TestCase):
    def assertPoseAlmostEqual(self, actual, expected, places=7):
        for actual_value, expected_value in zip(actual[0], expected[0]):
            self.assertAlmostEqual(actual_value, expected_value, places=places)
        for actual_value, expected_value in zip(actual[1], expected[1]):
            self.assertAlmostEqual(actual_value, expected_value, places=places)

    def test_relative_pose_round_trip_preserves_cart_pose(self):
        worker = ((1.0, 2.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        cart = ((1.05, 3.185, 0.0), (0.0, 0.0, 0.0, 1.0))

        result = compose_pose(worker, relative_pose(worker, cart))

        self.assertPoseAlmostEqual(result, cart)

    def test_compose_rotates_offset_with_worker(self):
        half_sqrt_two = math.sqrt(0.5)
        worker = ((2.0, 3.0, 0.0), (0.0, 0.0, half_sqrt_two, half_sqrt_two))
        relative = ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))

        result = compose_pose(worker, relative)

        self.assertPoseAlmostEqual(result, ((1.0, 3.0, 0.0), worker[1]))

    def test_relative_pose_handles_rotated_initial_worker(self):
        half_sqrt_two = math.sqrt(0.5)
        worker = ((2.0, 3.0, 0.0), (0.0, 0.0, half_sqrt_two, half_sqrt_two))
        cart = ((1.0, 3.0, 0.0), (0.0, 0.0, half_sqrt_two, half_sqrt_two))

        result = relative_pose(worker, cart)

        self.assertPoseAlmostEqual(result, ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))

    def test_normalize_rejects_zero_length_quaternion(self):
        with self.assertRaisesRegex(ValueError, "zero-length"):
            normalize_quaternion_xyzw((0.0, 0.0, 0.0, 0.0))

    def test_compose_rejects_wrong_position_length(self):
        with self.assertRaisesRegex(ValueError, "position"):
            compose_pose(
                ((0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
                ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
            )


class PoseSyncControllerTest(unittest.TestCase):
    def test_motion_guard_rejects_before_cart_write(self):
        self.playing=True
        self.controller.update()
        count=len(self.written_poses)
        self.controller.motion_guard=lambda worker,cart:False
        self.worker_pose=((9.,9.,0.),(0.,0.,0.,1.))
        with self.assertRaisesRegex(RuntimeError,'guard rejected'):
            self.controller.update()
        self.assertEqual(len(self.written_poses),count)
        self.assertPoseAlmostEqual(self.controller.held_pose,self.cart_pose)
        self.controller.stop()
        self.assertIsNone(self.controller.motion_guard)

    def test_resume_rejects_wrong_heading_and_preserves_cart_when_aligned(self):
        self.playing=True
        self.controller.update()
        self.controller.hold()
        expected=self.worker_pose
        self.worker_pose=(expected[0],(0.,0.,1.,0.))
        self.assertTrue(hasattr(self.controller,'resume'))
        with self.assertRaises(RuntimeError):
            self.controller.resume(expected,.1,5.)
        self.assertIsNotNone(self.controller.held_pose)
        self.worker_pose=expected
        self.controller.resume(expected,.1,5.)
        self.controller.update()
        self.assertPoseAlmostEqual(self.written_poses[-1],self.cart_pose)
        self.worker_pose=((0.,1.,0.),expected[1])
        self.controller.update()
        self.assertPoseAlmostEqual(self.written_poses[-1],((.05,2.185,0.),expected[1]))

    def assertPoseAlmostEqual(self, actual, expected, places=7):
        for actual_value, expected_value in zip(actual[0], expected[0]):
            self.assertAlmostEqual(actual_value, expected_value, places=places)
        for actual_value, expected_value in zip(actual[1], expected[1]):
            self.assertAlmostEqual(actual_value, expected_value, places=places)

    def setUp(self):
        self.worker_pose = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        self.cart_pose = ((0.05, 1.185, 0.0), (0.0, 0.0, 0.0, 1.0))
        self.playing = False
        self.written_poses = []
        self.clear_count = 0
        self.controller = PoseSyncController(
            read_worker_pose=lambda: self.worker_pose,
            read_cart_pose=lambda: self.cart_pose,
            write_cart_pose=self.written_poses.append,
            clear_cart_override=self._clear_override,
            is_playing=lambda: self.playing,
        )

    def _clear_override(self):
        self.clear_count += 1

    def test_paused_update_does_not_calibrate_or_write(self):
        updated = self.controller.update()

        self.assertFalse(updated)
        self.assertIsNone(self.controller.relative_transform)
        self.assertEqual(self.written_poses, [])

    def test_first_playing_update_calibrates_and_preserves_initial_cart_pose(self):
        self.playing = True

        updated = self.controller.update()

        self.assertTrue(updated)
        self.assertEqual(self.controller.calibration_count, 1)
        self.assertEqual(len(self.written_poses), 1)
        self.assertPoseAlmostEqual(self.written_poses[0], self.cart_pose)

    def test_later_update_uses_one_calibration_for_new_worker_pose(self):
        self.playing = True
        self.controller.update()
        self.worker_pose = ((0.0, 2.0, 0.0), (0.0, 0.0, 0.0, 1.0))

        self.controller.update()

        self.assertEqual(self.controller.calibration_count, 1)
        self.assertPoseAlmostEqual(
            self.written_poses[-1],
            ((0.05, 3.185, 0.0), (0.0, 0.0, 0.0, 1.0)),
        )

    def test_stop_clears_override_and_rearms_calibration(self):
        self.playing = True
        self.controller.update()

        self.controller.stop()

        self.assertEqual(self.clear_count, 1)
        self.assertIsNone(self.controller.relative_transform)


if __name__ == "__main__":
    unittest.main()
