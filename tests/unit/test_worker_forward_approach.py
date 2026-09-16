import unittest
from scripts import warehouse_worker_approach as m


class ForwardTest(unittest.TestCase):
    def test_rotates_before_approach_and_waits_before_box_transfer(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        events, now, position = [], [0], [(0,0,0)]
        def begin(*args):
            events.append('advance')
            return True
        a = SimpleNamespace(after_turn=True, begin=begin, timeout=60, started=3,
                            goal=(1,0,0), command='Worker_01 GoTo 1 0 0 _',
                            cancel=lambda: events.append('cancel'))
        r = FaceBoxRuntime.__new__(FaceBoxRuntime)
        r.approach, r.gesture = a, None
        r.transfer = SimpleNamespace(start=lambda *args: events.append('box_start'),
                                      update=lambda *args: None)
        r.timeline = SimpleNamespace(is_playing=lambda:True, get_current_time=lambda:now[0])
        r.state, r.worker_goal, r.cart_goal, r.target = 'arrival_pending', (0,0,0), (-1,0,0), (2,0,1)
        r.tolerance, r.forward_yaw, r.duration = .25, -90, 3
        r.sync = SimpleNamespace(_read_worker_pose=lambda:(position[0], (0,0,0,1)),
            _read_cart_pose=lambda:((-1,0,0),(0,0,0,1)), hold=lambda:events.append('hold'),
            _character=SimpleNamespace(set_world_transform=lambda *args:events.append('turn')))
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v:v, Float4=lambda *v:v)):
            r._on_update(None)
            self.assertEqual(events, ['hold','turn'])
            now[0] = 3
            r._on_update(None)
            self.assertEqual(r.state, 'approaching')
            self.assertNotIn('box_start', events)
            before = list(events)
            now[0] = 4
            r._on_update(None)
            self.assertEqual(events, before)
            position[0] = (1,0,0)
            r._on_command(SimpleNamespace(payload=dict(agent_name='Worker_01', command_name='GoTo',
                                                       status='default', command=a.command)))
            r._on_update(None)
            self.assertNotIn('box_start', events)
            now[0] = 7
            r._on_update(None)
            self.assertEqual(events.count('box_start'), 1)
            self.assertEqual(events.count('advance'), 1)
            self.assertEqual(r.position, (1,0,0))

    def test_boundary_point_farther_than_old_contact_threshold_is_allowed(self):
        self.assertTrue(hasattr(m, 'select_forward_approach'))
        def closest(p):
            return (min(p[0], 1), 0, 0)
        goal, count = m.select_forward_approach((0,0,0), (2,0,1), closest,
                                               lambda a,b:[a,b], .15, .05, .55)
        self.assertEqual(goal, (1,0,0))
        self.assertEqual(count, 2)

    def test_no_advancing_connected_point_keeps_start(self):
        self.assertTrue(hasattr(m, 'select_forward_approach'))
        goal, count = m.select_forward_approach((0,0,0), (2,0,1), lambda p:p,
                                               lambda a,b:[], .15, .05, .55)
        self.assertEqual(goal, (0,0,0))

    def test_detour_outside_forward_corridor_is_rejected(self):
        self.assertTrue(hasattr(m, 'select_forward_approach'))
        goal, count = m.select_forward_approach((0,0,0), (2,0,1), lambda p:p,
                          lambda a,b:[a,(0,3,0),b], .15, .05, .55)
        self.assertEqual(goal, (0,0,0))
