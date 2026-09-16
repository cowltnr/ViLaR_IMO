import unittest


class WalkingCarryTest(unittest.TestCase):
    def test_box_follows_worker_translation_not_original_pickup_position(self):
        from scripts.warehouse_walking_carry import held_center
        self.assertEqual(held_center(((0,0,0),(0,0,0,1)),.65,1.1),(0.,-.65,1.1))
        self.assertEqual(held_center(((2,3,0),(0,0,0,1)),.65,1.1),(2.,2.35,1.1))

    def test_segment_reuses_original_layer_restore_reference(self):
        from scripts.warehouse_walking_carry import begin_segment
        from types import SimpleNamespace
        transfer=SimpleNamespace(source=(9,9,9),layer='owned')
        begin_segment(transfer,[(0,0,1),(1,0,1)],2,3)
        self.assertEqual(transfer.source,(9,9,9))
        self.assertEqual(transfer.layer,'owned')
        self.assertEqual(transfer.state,'moving')

    def test_pickup_completion_walks_before_release_or_placement(self):
        from scripts.warehouse_walking_carry import WalkingCarry
        from types import SimpleNamespace
        from unittest.mock import Mock
        transfer=SimpleNamespace(state='loaded',current_center=(0,0,1),update=Mock())
        gesture=SimpleNamespace(update=Mock())
        owner=SimpleNamespace(transfer=transfer,gesture=gesture,move=Mock(),
            sync=SimpleNamespace(_read_worker_pose=lambda:((0,0,0),(0,0,0,1))))
        carry=WalkingCarry.__new__(WalkingCarry)
        carry.r,carry.phase,carry.goal,carry.drop_heading=owner,'pickup',(2,3,0),90
        carry.update(3)
        self.assertEqual(transfer.state,'moving')
        owner.move.assert_called_once_with((2,3,0),'walking_load',heading='90.00000')
        self.assertEqual(carry.phase,'walking')

    def test_count_advances_only_after_placement_and_arm_release(self):
        from scripts.warehouse_walking_carry import WalkingCarry
        from types import SimpleNamespace
        from unittest.mock import Mock
        owner=SimpleNamespace(transfer=SimpleNamespace(state='loaded',current_center=(0,0,1),update=Mock()),
            gesture=SimpleNamespace(done=False,update=Mock()),loaded=[],index=0,placement='first',
            sync=SimpleNamespace(_read_worker_pose=lambda:((0,0,0),(0,0,0,1))))
        carry=WalkingCarry.__new__(WalkingCarry)
        carry.r,carry.phase=owner,'placing'
        carry.update(3)
        self.assertEqual(owner.index,0)
        owner.gesture.done=True
        carry.update(4)
        self.assertEqual(owner.loaded,['first'])
        self.assertEqual(owner.state,'next')
