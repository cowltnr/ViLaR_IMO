import math
import unittest

from scripts.warehouse_worker_cart_pose_sync import PoseSyncController


class CartHoldTest(unittest.TestCase):
    def test_hold_keeps_last_cart_pose_and_stop_rearms_follow(self):
        worker = [((0, 0, 0), (0, 0, 0, 1))]
        writes, clears = [], []
        c = PoseSyncController(read_worker_pose=lambda: worker[0],
                              read_cart_pose=lambda: ((0, 1, 0), (0, 0, 0, 1)),
                              write_cart_pose=writes.append,
                              clear_cart_override=lambda: clears.append(True),
                              is_playing=lambda: True)
        c.update()
        c.hold()
        worker[0] = ((0, 0, 0), (0, 0, 1, 0))
        c.update()
        self.assertEqual(writes[-1], ((0, 1, 0), (0, 0, 0, 1)))
        self.assertEqual(clears, [])
        c.stop()
        self.assertIsNone(c.held_pose)
        self.assertEqual(clears, [True])


class FaceBoxMathTest(unittest.TestCase):
    def test_carb_payload_requires_explicit_get_default(self):
        from scripts.warehouse_worker_face_box import matches_arrival

        class CarbPayload:
            # Match the binding signature reported by Isaac Sim, not dict.get.
            def __init__(self, values):
                self.values = values

            def get(self, key, default):
                return self.values.get(key, default)

        command = 'Worker_01 GoTo -7.49629 18.43615 0.04270 175.14907'
        payload = dict(agent_name='Worker_01', command_name='GoTo',
                       status='default', command=command)
        self.assertTrue(matches_arrival(CarbPayload(payload), command))
        self.assertFalse(matches_arrival(CarbPayload(dict(payload, command_name='Idle')), command))
        self.assertFalse(matches_arrival(CarbPayload(dict(payload, status='failed')), command))
        self.assertFalse(matches_arrival(CarbPayload({}), command))

    def test_negative_y_forward_faces_positive_x_at_90_degrees(self):
        from scripts.warehouse_worker_face_box import target_yaw
        self.assertAlmostEqual(target_yaw((0, 0, 0), (2, 0, 3), -90), 90)

    def test_shortest_turn_across_wrap(self):
        from scripts.warehouse_worker_face_box import turn_yaw
        self.assertAlmostEqual(turn_yaw(170, -170, 0.5), 180)

    def test_vertical_target_rejected(self):
        from scripts.warehouse_worker_face_box import target_yaw
        with self.assertRaises(ValueError):
            target_yaw((1, 2, 0), (1, 2, 4), -90)

    def test_only_expected_successful_goto_matches(self):
        from scripts.warehouse_worker_face_box import matches_arrival
        payload = dict(agent_name='Worker_01', command_name='GoTo',
                       status='default', command='Worker_01 GoTo 1 2 0 90')
        self.assertTrue(matches_arrival(payload, payload['command']))
        self.assertFalse(matches_arrival(dict(payload, status='failed'), payload['command']))
        self.assertFalse(matches_arrival(dict(payload, agent_name='Other'), payload['command']))
        self.assertFalse(matches_arrival(payload, 'Worker_01 GoTo 3 4 0 90'))
