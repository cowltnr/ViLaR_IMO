import unittest


class SourceSpacingTest(unittest.TestCase):
    def test_shift_points_away_and_keeps_stack_together(self):
        from scripts.warehouse_source_spacing import separation_offset
        delta=separation_offset((0,1,0),(0,0,0),.04)
        self.assertEqual(delta,(0.,-.04,0.))

    def test_coincident_stack_centers_are_not_guessed(self):
        from scripts.warehouse_source_spacing import separation_offset
        with self.assertRaises(ValueError):
            separation_offset((0,0,0),(0,0,0),.04)
