import unittest
from types import SimpleNamespace


class UnloadingSafetyTest(unittest.TestCase):
    def test_stop_attempts_every_box_restore_even_if_one_fails(self):
        from scripts.warehouse_unloading_live import restore_transfers
        calls = []
        def bad():
            calls.append('a')
            raise RuntimeError('unavailable layer')
        transfers = [SimpleNamespace(restore=bad),
                     SimpleNamespace(restore=lambda: calls.append('b'))]
        errors = restore_transfers(transfers)
        self.assertEqual(calls,['a','b'])
        self.assertEqual(len(errors),1)

    def test_final_attention_targets_follow_return_pose(self):
        from scripts.warehouse_unloading_live import attention_targets
        result = attention_targets(((2,3,0),(0,0,0,1)),
            {'left':(.2,0,1.4),'right':(-.2,0,1.4)},
            {'left':.5,'right':.5})
        self.assertAlmostEqual(result['left'][0],2.2)
        self.assertAlmostEqual(result['left'][2],.95)
        self.assertAlmostEqual(result['right'][0],1.8)
