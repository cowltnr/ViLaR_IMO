import importlib.util
import unittest


class GestureMathTest(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.warehouse_worker_reach_gesture'),
                             'Reach gesture implementation is missing')
        from scripts import warehouse_worker_reach_gesture
        return warehouse_worker_reach_gesture

    def test_reach_hold_lower_envelope(self):
        m = self.module()
        self.assertEqual(m.gesture_sample(0, 2, 8, 2), (0, 1))
        self.assertEqual(m.gesture_sample(2, 2, 8, 2), (1, 1))
        self.assertEqual(m.gesture_sample(10, 2, 8, 2), (1, 0.6))
        self.assertEqual(m.gesture_sample(12, 2, 8, 2), (0, 0.6))
        with self.assertRaises(ValueError):
            m.gesture_sample(0, 0, 8, 2)

    def test_chain_uses_reference_skeleton_not_worker_names(self):
        m = self.module()
        joints = ['Root', 'Root/L_Arm', 'Root/L_Arm/L_Elbow',
                  'Root/L_Arm/L_Elbow/L_Wrist', 'Root/R_Arm',
                  'Root/R_Arm/R_Elbow', 'Root/R_Arm/R_Elbow/R_Wrist']
        self.assertEqual(m.arm_chains(joints)['left'], ('L_Arm', 'L_Elbow', 'L_Wrist'))
        with self.assertRaises(ValueError):
            m.arm_chains(['Root'])

    def test_target_is_reachable_direction_not_distant_box(self):
        m = self.module()
        self.assertEqual(m.reach_target((0, 0, 1), (5, 0, 1), 0.4), (0.4, 0, 1))
        with self.assertRaises(ValueError):
            m.reach_target((0, 0, 1), (0, 0, 1), 0.4)


class GestureLayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd
        except ImportError:
            raise unittest.SkipTest('OpenUSD unavailable')

    def test_graph_install_and_restore_preserve_root_and_other_session_edits(self):
        from pxr import Usd, Sdf
        from scripts.warehouse_worker_reach_gesture import GestureGraphLayer
        stage = Usd.Stage.CreateInMemory()
        graph = stage.DefinePrim('/Graph', 'AnimationGraph')
        graph.CreateRelationship('inputs:pose').SetTargets(['/Graph/Idle'])
        stage.DefinePrim('/Graph/Idle', 'AnimationClip')
        original = stage.GetRootLayer().ExportToString()
        layer = GestureGraphLayer(stage, '/Graph',
                                  {'left': ('A', 'B', 'C'), 'right': ('D', 'E', 'F')})
        layer.install()
        self.assertEqual(str(graph.GetRelationship('inputs:pose').GetTargets()[0]),
                         '/Graph/WarehouseReachRightIK')
        self.assertEqual(stage.GetPrimAtPath('/Graph/WarehouseReachLeftIK')
                         .GetRelationship('inputs:pose').GetTargets(), [Sdf.Path('/Graph/Idle')])
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            graph.CreateAttribute('userNote', Sdf.ValueTypeNames.String).Set('keep')
        layer.restore()
        layer.restore()
        self.assertEqual(graph.GetRelationship('inputs:pose').GetTargets(), [Sdf.Path('/Graph/Idle')])
        self.assertEqual(graph.GetAttribute('userNote').Get(), 'keep')
        self.assertEqual(stage.GetRootLayer().ExportToString(), original)


class GestureSequenceTest(unittest.TestCase):
    def test_stop_reset_tolerates_destroyed_character_and_clears_run_state(self):
        from types import SimpleNamespace
        from scripts.warehouse_worker_reach_gesture import ReachGesture
        def expired(*args):
            raise RuntimeError('Character destroyed by Timeline Stop')
        gesture = ReachGesture.__new__(ReachGesture)
        gesture.character = SimpleNamespace(set_variable=expired)
        gesture.started, gesture.done = 3, True
        gesture.reset()
        self.assertIsNone(gesture.character)
        self.assertIsNone(gesture.started)
        self.assertFalse(gesture.done)

    def test_reach_starts_once_after_turn_and_resets_on_stop(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        events = []
        r = FaceBoxRuntime.__new__(FaceBoxRuntime)
        r.timeline = SimpleNamespace(is_playing=lambda: True, get_current_time=lambda: clock[0])
        r.transfer = None
        r.approach = None
        r.gesture = SimpleNamespace(start=lambda *args: events.append('reach'),
                                    update=lambda now: events.append('update'),
                                    reset=lambda: events.append('reset'))
        r.state, r.start_time, r.duration = 'turning', 0, 3
        r.start_yaw, r.end_yaw, r.position, r.target = 0, 90, (0, 0, 0), (3, 0, 1)
        r.sync = SimpleNamespace(_character=SimpleNamespace(set_world_transform=lambda p, q: None),
                                 _read_worker_pose=lambda: ((0, 0, 0), (0, 0, 0, 1)))
        r._stop_type = 99
        clock = [2]
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v: v, Float4=lambda *v: v)):
            r._on_update(None)
            self.assertEqual(events, [])
            clock[0] = 3
            r._on_update(None)
            clock[0] = 4
            r._on_update(None)
        self.assertEqual(events, ['reach', 'update', 'update'])
        r._on_timeline(SimpleNamespace(type=99))
        self.assertEqual(events[-1], 'reset')
