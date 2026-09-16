import unittest


class MultiBoxRuntimeTest(unittest.TestCase):
    def report(self):
        return {
            'stage_modified': False,
            'navmesh': {'status': 'queried_not_motion_validated'},
            'source_approaches': [
                {'path': '/a', 'status': 'connected_probe_selected',
                 'navmesh_point': [1, 2, 0], 'path_points': [[0, 0, 0], [1, 2, 0]],
                 'snap_distance_m': .05, 'box_horizontal_distance_m': 1.0},
                {'path': '/b', 'status': 'connected_probe_selected',
                 'navmesh_point': [2, 2, 0], 'path_points': [[0, 0, 0], [2, 2, 0]],
                 'snap_distance_m': .05, 'box_horizontal_distance_m': 1.0},
            ],
        }

    def test_prepare_exposes_source_approach_without_starting_sim(self):
        from scripts.warehouse_multi_box_runtime import WarehouseMultiBoxRuntime
        runtime = WarehouseMultiBoxRuntime(('/a', '/b'))
        prepared = runtime.prepare(self.report(), 'cart_pose')
        self.assertEqual(prepared.action.kind, 'plan')
        self.assertEqual(prepared.action.box_id, '/a')
        self.assertEqual(prepared.source_approach.navmesh_point, (1., 2., 0.))

    def test_blocked_preflight_does_not_create_sequence(self):
        from scripts.warehouse_multi_box_runtime import WarehouseMultiBoxRuntime
        runtime = WarehouseMultiBoxRuntime(('/missing',))
        result = runtime.prepare(self.report(), 'pose')
        self.assertEqual(result['status'], 'blocked')
        with self.assertRaises(RuntimeError):
            runtime.complete(('none',), {'status': 'loaded'})

    def test_completion_preserves_source_mapping_and_handles_return(self):
        from scripts.warehouse_multi_box_runtime import WarehouseMultiBoxRuntime
        runtime = WarehouseMultiBoxRuntime(('/a', '/b'))
        current = runtime.prepare(self.report(), 'pose')
        current = runtime.complete(current.action.token, {'status': 'loaded'})
        self.assertEqual(current.action.box_id, '/b')
        self.assertEqual(current.source_approach.navmesh_point, (2., 2., 0.))
        current = runtime.complete(current.action.token, {'status': 'loaded'})
        self.assertEqual(current.action.kind, 'return')
        current = runtime.complete(current.action.token, {'status': 'returned'})
        self.assertEqual(current.action.kind, 'attention')


if __name__ == '__main__':
    unittest.main()
