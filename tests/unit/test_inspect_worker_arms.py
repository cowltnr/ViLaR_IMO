import unittest


class ArmInspectionTest(unittest.TestCase):
    def test_selects_arm_joints_by_leaf_not_parent_name(self):
        from scripts.inspect_worker_arms import arm_joint_indices
        self.assertEqual(arm_joint_indices(['root', 'root/LeftShoulder',
                                           'root/LeftShoulder/LeftArm',
                                           'root/LeftShoulder/LeftArm/LeftHand',
                                           'root/LeftShoulder/LeftArm/LeftHand/Index1',
                                           'root/LeftShoulder/other']), [1, 2, 3])

    def test_empty_joint_list(self):
        from scripts.inspect_worker_arms import arm_joint_indices
        self.assertEqual(arm_joint_indices([]), [])
