import unittest


class MultiBoxSequenceTest(unittest.TestCase):
    def test_successful_boxes_then_return_and_attention(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        sequence = Sequence(('a', 'b'))
        action = sequence.start({'position': (0, 0, 0), 'yaw': 0})
        self.assertEqual(action.kind, 'plan')
        self.assertEqual(action.box_id, 'a')
        action = sequence.complete(action.token, {'status': 'loaded'})
        self.assertEqual(action.kind, 'plan')
        self.assertEqual(action.box_id, 'b')
        action = sequence.complete(action.token, {'status': 'loaded'})
        self.assertEqual(action.kind, 'return')
        action = sequence.complete(action.token, {'status': 'returned'})
        self.assertEqual(action.kind, 'attention')
        self.assertIsNone(sequence.complete(action.token, {'status': 'done'}))
        self.assertEqual(sequence.completed_box_ids, ('a', 'b'))

    def test_no_valid_plan_returns_without_dropping_completed_boxes(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        sequence = Sequence(('a', 'b', 'c'))
        action = sequence.start('cart_pose')
        action = sequence.complete(action.token, {'status': 'loaded'})
        self.assertEqual(action.box_id, 'b')
        action = sequence.complete(action.token, {'reason': 'no_valid_load_plan'})
        self.assertEqual(action.kind, 'return')
        self.assertEqual(sequence.completed_box_ids, ('a',))

    def test_stale_completion_is_ignored(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        sequence = Sequence(('a', 'b'))
        first = sequence.start('pose')
        second = sequence.complete(first.token, {'status': 'loaded'})
        self.assertEqual(second.kind, 'plan')
        self.assertIsNone(sequence.complete(first.token, {'status': 'loaded'}))
        self.assertEqual(sequence.current_action.token, second.token)

    def test_rejects_invalid_lifecycle(self):
        from scripts.warehouse_multi_box_sequence import Sequence
        with self.assertRaises(ValueError):
            Sequence(())
        sequence = Sequence(('a',))
        with self.assertRaises(RuntimeError):
            sequence.complete(('wrong',), {'status': 'loaded'})


if __name__ == '__main__':
    unittest.main()
