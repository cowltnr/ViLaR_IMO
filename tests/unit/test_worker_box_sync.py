import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import warehouse_worker_reach_gesture as module


class BoxSyncMathTest(unittest.TestCase):
    def test_height_feedback_is_bounded_and_corrects_in_right_direction(self):
        self.assertTrue(hasattr(module, 'height_feedback_step'))
        self.assertLess(module.height_feedback_step(0, 1.1, 1.2, .1, .1, .3), 0)
        self.assertEqual(module.height_feedback_step(-.1, 1.1, 2, 1, .1, .3), -.1)
        self.assertEqual(module.height_feedback_step(0, 1.1, 1.2, 0, .1, .3), 0)

    def test_hand_height_tracks_box_without_stretching(self):
        self.assertTrue(hasattr(module, 'height_matched_target'))
        p = module.height_matched_target((0, 0, 1.4), (4, 0, 1.6), .4, .5)
        self.assertAlmostEqual(p[2], 1.6)
        self.assertAlmostEqual(p[0], .4)
        p = module.height_matched_target((0, 0, 1.4), (4, 0, 3), .4, .5)
        self.assertLessEqual(math.dist(p, (0, 0, 1.4)), .500001)

    def test_heading_wraps_short_way_with_bounded_rate(self):
        self.assertTrue(hasattr(module, 'follow_yaw'))
        self.assertEqual(module.follow_yaw(170, -170, .1, 40), 174)
        self.assertEqual(module.follow_yaw(10, 80, 0, 40), 10)


class BoxSyncRuntimeTest(unittest.TestCase):
    def test_walking_does_not_overwrite_people_root(self):
        g=self.make_gesture()
        poses=[]
        variables={}
        character=SimpleNamespace(set_variable=lambda k,v:variables.update({k:v}),
            get_variable=lambda k:[variables[k]],
            set_world_transform=lambda *v:poses.append(v))
        with patch.dict('sys.modules',carb=SimpleNamespace(Float3=lambda *v:v,Float4=lambda *v:v)):
            g.start(0,character,((0,0,0),(0,0,0,1)),(3,0,1.6))
            poses.clear()
            g.walking_pose=((2,3,0),(0,0,0,1))
            g.update(2)
        self.assertEqual(poses,[])
        self.assertEqual(g.position,(2,3,0))

    def test_runtime_shoulders_are_refreshed_atomically(self):
        gesture = module.BoxSynchronizedReach.__new__(module.BoxSynchronizedReach)
        gesture.feedback_enabled = True
        gesture.shoulders = {'old': (0,0,1)}
        fail_right = [True]
        def read(name, p, q):
            if name == 'RightArm' and fail_right[0]:
                return False
            p.x, p.y, p.z = 10, 20 + (.2 if name == 'LeftArm' else -.2), 1.5
            return True
        character = SimpleNamespace(get_joint_transform=read)
        with patch.dict('sys.modules', carb=SimpleNamespace(
                Float3=lambda x,y,z:SimpleNamespace(x=x,y=y,z=z), Float4=lambda *v:v)):
            with self.assertRaises(RuntimeError):
                gesture.refresh_shoulders(character, ((10,20,0),(0,0,0,1)))
            self.assertEqual(gesture.shoulders, {'old':(0,0,1)})
            fail_right[0] = False
            gesture.refresh_shoulders(character, ((10,20,0),(0,0,0,1)))
            self.assertAlmostEqual(gesture.shoulders['left'][2], 1.5)
            self.assertAlmostEqual(gesture.shoulders['right'][1], -.2)

    def test_face_runtime_does_not_overwrite_synced_heading_and_updates_box_first(self):
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        events = []
        r = FaceBoxRuntime.__new__(FaceBoxRuntime)
        r.timeline = SimpleNamespace(is_playing=lambda: True, get_current_time=lambda: 7)
        r.state, r.start_time, r.duration = 'facing', 0, 3
        r.start_yaw, r.end_yaw, r.position = 0, 90, (0, 0, 0)
        r.approach = None
        r.transfer = SimpleNamespace(update=lambda now: events.append('box'))
        r.gesture = SimpleNamespace(controls_heading=True, update=lambda now: events.append('gesture'))
        r.sync = SimpleNamespace(_character=SimpleNamespace(set_world_transform=lambda *args: events.append('overwrite')))
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v:v, Float4=lambda *v:v)):
            r._on_update(None)
        self.assertEqual(events, ['box', 'gesture'])

    def make_gesture(self):
        self.assertTrue(hasattr(module, 'BoxSynchronizedReach'))
        gesture = module.BoxSynchronizedReach.__new__(module.BoxSynchronizedReach)
        gesture.shoulders = {'left': (0, .2, 1.4), 'right': (0, -.2, 1.4)}
        gesture.arm_lengths = {'left': .57, 'right': .57}
        gesture.distance, gesture.reach, gesture.lower = .4, 2, 2
        gesture.started, gesture.done = None, False
        gesture.transfer = SimpleNamespace(state='waiting', current_center=(3, 0, 1.6))
        gesture.forward_yaw, gesture.yaw_rate = 0, 45
        return gesture

    def test_follows_updated_box_and_only_lowers_after_loaded(self):
        g = self.make_gesture()
        variables, poses = {}, []
        character = SimpleNamespace(set_variable=lambda k, v: variables.update({k:v}),
                                    get_variable=lambda k: [variables[k]],
                                    set_world_transform=lambda p, q: poses.append((p,q)))
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v:v, Float4=lambda *v:v)):
            g.start(0, character, ((0,0,0), (0,0,0,1)), (3,0,1.6))
            g.update(2)
            self.assertAlmostEqual(variables['WarehouseReachLeftTarget'][2], 1.6)
            g.transfer.state = 'moving'
            g.transfer.current_center = (1, 1, 1.7)
            g.update(3)
            self.assertAlmostEqual(variables['WarehouseReachLeftTarget'][2], 1.7)
            self.assertNotEqual(poses[-1][1], (0,0,0,1))
            self.assertEqual(poses[-1][0], (0,0,0))
            g.update(30)  # Delay must not trigger neutral pose while box is still moving.
            self.assertFalse(g.done)
            g.transfer.state = 'loaded'
            g.update(31)
            g.update(33)
            self.assertTrue(g.done)
            self.assertLess(variables['WarehouseReachLeftTarget'][2], 1)
            self.assertEqual(variables['WarehouseReachWeight'], 1)
            g.reset()
            self.assertEqual(variables['WarehouseReachWeight'], 0)
            self.assertIsNone(g.started)
