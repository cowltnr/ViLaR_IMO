import importlib.util
import unittest


class RuntimeProbeTest(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.inspect_worker_arm_runtime'))
        from scripts import inspect_worker_arm_runtime
        return inspect_worker_arm_runtime

    def test_vector_rejects_missing_and_nonfinite_measurement(self):
        m = self.module()
        self.assertEqual(m.vector3((1,2,3)), [1.,2.,3.])
        self.assertIsNone(m.vector3((float('nan'),2,3)))
        self.assertIsNone(m.vector3(None))

    def test_waits_for_full_reach_and_skips_stopped_or_finished(self):
        from types import SimpleNamespace
        m = self.module()
        g = SimpleNamespace(started=10, reach=2, done=False, character=object())
        self.assertFalse(m.ready_to_sample(g, 11, True))
        self.assertTrue(m.ready_to_sample(g, 12.5, True))
        self.assertFalse(m.ready_to_sample(g, 12.5, False))
        g.done = True
        self.assertFalse(m.ready_to_sample(g, 30, True))

    def test_height_direction_distinguishes_too_low_from_too_high(self):
        from scripts import warehouse_worker_reach_gesture as m
        self.assertTrue(hasattr(m, 'height_limit_direction'))
        self.assertEqual(m.height_limit_direction(.94, .835), 'below_minimum')
        self.assertEqual(m.height_limit_direction(1.91, 2.1), 'above_maximum')
        self.assertIsNone(m.height_limit_direction(1.1, 1.1))

    def test_collect_keeps_invalid_joint_distinct_from_zero_position(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        m = self.module()
        def joint(name, p, r):
            if name != 'LeftHand':
                return False
            p.x, p.y, p.z = 1, 2, 1.05
            return True
        character = SimpleNamespace(get_joint_transform=joint,
            get_variable=lambda name: [1.] if name.endswith('Weight') else [(1.,2.,1.1)])
        gesture = SimpleNamespace(character=character, started=0, shoulders={}, arm_lengths={},
                                  graph=SimpleNamespace(chains={}))
        transfer = SimpleNamespace(box_path='/Box', state='moving', current_center=(1,2,1.1))
        with patch.dict('sys.modules', carb=SimpleNamespace(
                Float3=lambda x,y,z: SimpleNamespace(x=x,y=y,z=z), Float4=lambda *v:v)):
            report = m.collect(gesture, transfer, 3)
        self.assertEqual(report['joints']['LeftHand']['world_position'], [1,2,1.05])
        self.assertIsNone(report['joints']['RightHand']['world_position'])
        self.assertFalse(report['joints']['RightHand']['valid'])
        self.assertEqual(report['targets']['left'], [1,2,1.1])
