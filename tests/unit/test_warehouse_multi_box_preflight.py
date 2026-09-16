import unittest


class MultiBoxPreflightTest(unittest.TestCase):
    def report(self, **entry):
        return {
            'stage_modified': False,
            'navmesh': {'status': 'queried_not_motion_validated'},
            'source_approaches': [{
                'path': '/a', 'status': 'connected_probe_selected',
                'navmesh_point': [1, 2, 0], 'path_points': [[0, 0, 0], [1, 2, 0]],
                'snap_distance_m': .05, 'box_horizontal_distance_m': 1.0,
                **entry,
            }],
        }

    def test_collects_valid_source_approach(self):
        from scripts.warehouse_multi_box_preflight import collect_source_approaches
        result, reason = collect_source_approaches(self.report(), ('/a',))
        self.assertIsNone(reason)
        self.assertEqual(result[0].navmesh_point, (1.0, 2.0, 0.0))

    def test_blocks_missing_or_modified_inputs(self):
        from scripts.warehouse_multi_box_preflight import collect_source_approaches
        result, reason = collect_source_approaches(self.report(), ('/missing',))
        self.assertEqual(result, ())
        self.assertIn('no_connected_source_approach', reason)
        report = self.report()
        report['stage_modified'] = True
        self.assertEqual(collect_source_approaches(report, ('/a',))[1],
                         'stage_modified_during_inspection')

    def test_blocks_far_snap_and_invalid_path(self):
        from scripts.warehouse_multi_box_preflight import collect_source_approaches
        result, reason = collect_source_approaches(
            self.report(snap_distance_m=.3), ('/a',))
        self.assertEqual(result, ())
        self.assertIn('source_snap_too_far', reason)
        result, reason = collect_source_approaches(
            self.report(path_points=[]), ('/a',))
        self.assertEqual(result, ())
        self.assertIn('invalid_source_path', reason)


if __name__ == '__main__':
    unittest.main()
