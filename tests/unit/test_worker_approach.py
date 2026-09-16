import unittest


class ApproachTest(unittest.TestCase):
    def test_cart_is_held_before_approach_and_turn_waits_for_second_arrival(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        events = []
        position = [(0, -2, 0)]
        a = SimpleNamespace(command='Worker_01 GoTo 0 -0.55 0 _', goal=(0, -0.55, 0),
                            max_distance=0.75, timeout=60, started=0,
                            begin=lambda *v: events.append('begin'), cancel=lambda: events.append('cancel'))
        r = FaceBoxRuntime.__new__(FaceBoxRuntime)
        r.approach, r.transfer = a, None
        r.timeline = SimpleNamespace(is_playing=lambda: True, get_current_time=lambda: 0)
        r.state, r.worker_goal, r.cart_goal, r.target = 'arrival_pending', (0, -2, 0), (0, -1, 0), (0, 0, 1.5)
        r.tolerance, r.forward_yaw, r.duration = 0.25, -90, 3
        r.sync = SimpleNamespace(_read_worker_pose=lambda: (position[0], (0, 0, 0, 1)),
                                 _read_cart_pose=lambda: ((0, -1, 0), (0, 0, 0, 1)),
                                 hold=lambda: events.append('hold'),
                                 _character=SimpleNamespace(set_world_transform=lambda *v: events.append('turn')))
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v: v, Float4=lambda *v: v)):
            r._on_update(None)
            self.assertEqual(events, ['hold', 'begin'])
            self.assertEqual(r.state, 'approaching')
            r._on_update(None)
            self.assertEqual(events, ['hold', 'begin'])
            r._on_command(SimpleNamespace(payload=dict(agent_name='Worker_01', command_name='GoTo',
                                                       status='default', command=a.command)))
            position[0] = a.goal
            r._on_update(None)
        self.assertEqual(events, ['hold', 'begin', 'turn'])
        self.assertEqual(r.state, 'turning')

    def test_candidates_stay_on_worker_side_at_ground_height(self):
        from scripts.warehouse_worker_approach import approach_candidates
        points = approach_candidates((0, -2, 0.04), (0, 0, 1.5), (0.55,), (0,))
        self.assertEqual(points, [(0.0, -0.55, 0.04)])

    def test_partial_path_rejected(self):
        from scripts.warehouse_worker_approach import select_approach
        with self.assertRaises(RuntimeError):
            select_approach((0, -2, 0), (0, 0, 1.5), [(0, -0.55, 0)],
                            lambda p: p, lambda a, b: [a, (0, -1, 0)], 0.15, 0.75)

    def test_far_snap_rejected(self):
        from scripts.warehouse_worker_approach import select_approach
        with self.assertRaises(RuntimeError):
            select_approach((0, -2, 0), (0, 0, 1.5), [(0, -0.55, 0)],
                            lambda p: (0, -1, 0), lambda a, b: [a, b], 0.15, 0.75)

    def test_valid_path_keeps_target(self):
        from scripts.warehouse_worker_approach import select_approach
        goal, count = select_approach((0, -2, 0), (0, 0, 1.5), [(0, -0.55, 0)],
                                     lambda p: p, lambda a, b: [a, b], 0.15, 0.75)
        self.assertEqual(goal, (0, -0.55, 0))
        self.assertEqual(count, 2)
