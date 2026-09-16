import unittest


class AuditRegressionTest(unittest.TestCase):
    def test_zero_wait_commands_have_no_idle(self):
        from scripts.configure_warehouse_worker_behavior import build_destination_commands
        commands = build_destination_commands('Worker_01', (1, 2, 0), 90, 0, initial_wait=0)
        self.assertEqual(len(commands), 1)
        self.assertTrue(commands[0].startswith('Worker_01 GoTo '))

    def test_failed_return_does_not_claim_attention(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        seq = Sequence(('a',))
        action = seq.start('pose')
        action = seq.complete(action.token, {'reason': 'no_valid_load_plan'})
        self.assertIsNone(seq.complete(action.token, {'reason': 'blocked_return'}))
        self.assertEqual(seq.failure_reason, 'blocked_return')
        self.assertIsNone(seq.current_action)

    def test_other_session_completion_is_ignored(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        a, b = Sequence(('a',)), Sequence(('a',))
        first, second = a.start('pose'), b.start('pose')
        self.assertIsNone(b.complete(first.token, {'status': 'loaded'}))
        self.assertEqual(b.current_action, second)
