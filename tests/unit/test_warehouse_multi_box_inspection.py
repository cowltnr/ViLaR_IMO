import unittest


class ProbeTest(unittest.TestCase):
    def test_launcher_refuses_playing_without_reading_or_editing_stage(self):
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch
        from scripts import inspect_warehouse_multi_box as launcher
        omni = ModuleType('omni')
        omni.timeline = SimpleNamespace(get_timeline_interface=lambda: SimpleNamespace(is_stopped=lambda: False))
        def forbidden():
            self.fail('Stage access must not occur when Timeline is not stopped')
        omni.usd = SimpleNamespace(get_context=forbidden)
        with patch.dict('sys.modules', {'omni': omni, 'omni.timeline': omni.timeline, 'omni.usd': omni.usd}):
            with self.assertRaisesRegex(RuntimeError, 'Stop'):
                launcher.run()

    def test_probe_marks_partial_or_far_snap_path_unusable(self):
        from scripts.warehouse_multi_box_inspection import probe_navmesh
        report = {'worker_authored_position': (0, 0, 0),
                  'boxes': [{'path': '/Box', 'world_center': (2, 0, 1)}]}
        straight = lambda a, b: [a, b]
        result = probe_navmesh(report, lambda p: p, straight, (.5,), (180,), .15)
        point = result['boxes'][0]['probes'][0]
        self.assertTrue(point['connected'])
        self.assertAlmostEqual(point['navmesh_point'][0], 1.5)
        result = probe_navmesh(report, lambda p: p, lambda a, b: [a, (.2, 0, 0)], (.5,), (180,), .15)
        self.assertFalse(result['boxes'][0]['probes'][0]['connected'])
        result = probe_navmesh(report, lambda p: (p[0] + .3, p[1], p[2]), straight, (.5,), (180,), .15)
        self.assertEqual(result['status'], 'worker_outside_snap_tolerance')

    def test_report_writer_uses_unique_runs_and_does_not_overwrite(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from scripts.warehouse_multi_box_inspection import save_report
        with TemporaryDirectory() as temp:
            first = save_report({'motion_ready': False}, Path(temp))
            second = save_report({'motion_ready': False}, Path(temp))
            self.assertNotEqual(first, second)
            self.assertFalse(json.loads(first.read_text())['motion_ready'])
            self.assertTrue(first.exists())

    def test_select_source_approaches_prefers_closest_connected_probe(self):
        from scripts.warehouse_multi_box_inspection import select_source_approaches
        result = select_source_approaches({'boxes': [{
            'path': '/box',
            'probes': [
                {'connected': True, 'box_horizontal_distance_m': 1.0,
                 'snap_distance_m': .1, 'navmesh_point': [1, 0, 0],
                 'path_points': [[0, 0, 0], [1, 0, 0]]},
                {'connected': True, 'box_horizontal_distance_m': .8,
                 'snap_distance_m': .2, 'navmesh_point': [.8, 0, 0],
                 'path_points': [[0, 0, 0], [.8, 0, 0]]},
            ]}, {'path': '/unreachable', 'probes': []}]})
        self.assertEqual(result[0]['navmesh_point'], [.8, 0, 0])
        self.assertFalse(result[0]['extraction_clearance_validated'])
        self.assertEqual(result[1]['status'], 'no_connected_probe')


class MultiBoxInspectionUsdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd, UsdGeom, Gf
        except ImportError:
            raise unittest.SkipTest('Bundled OpenUSD required for scene inspection tests')
        cls.Usd, cls.UsdGeom, cls.Gf = Usd, UsdGeom, Gf

    def fixture(self):
        stage = self.Usd.Stage.CreateInMemory()
        self.UsdGeom.SetStageMetersPerUnit(stage, 1)
        self.UsdGeom.SetStageUpAxis(stage, 'Z')
        box = self.UsdGeom.Cube.Define(stage, '/World/Warehouse/Box/Mesh')
        box.GetSizeAttr().Set(.4)
        box.AddTranslateOp().Set(self.Gf.Vec3d(10, 0, 1))
        pallet = self.UsdGeom.Cube.Define(stage, '/World/Cart/Pallet')
        pallet.GetSizeAttr().Set(1)
        pallet.AddTranslateOp().Set(self.Gf.Vec3d(10, -2, .5))
        pallet.AddRotateZOp().Set(90)
        self.UsdGeom.Xform.Define(stage, '/World/Worker')
        rack = self.UsdGeom.Cube.Define(stage, '/World/Warehouse/SM_RackShelf_01/Mesh')
        rack.GetSizeAttr().Set(2)
        rack.AddTranslateOp().Set(self.Gf.Vec3d(10, 0, 1))
        return stage

    def inspect(self, stage, **kwargs):
        from scripts.warehouse_multi_box_inspection import inspect_stage
        return inspect_stage(stage, ('/World/Warehouse/Box/Mesh',), '/World/Cart/Pallet',
                             '/World/Worker', '/World/Warehouse', **kwargs)

    def test_world_local_geometry_and_single_leaf_rack_without_any_stage_edit(self):
        stage = self.fixture()
        before = [layer.ExportToString() for layer in stage.GetLayerStack()]
        report = self.inspect(stage)
        box = report['boxes'][0]
        self.assertEqual(box['rack_candidates'], ['/World/Warehouse/SM_RackShelf_01'])
        for actual, expected in zip(box['world_center'], (10, 0, 1)):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(box['pallet_local_center'], (2, 0, .5)):
            self.assertAlmostEqual(actual, expected)
        self.assertFalse(report['motion_ready'])
        self.assertEqual(report['geometry_errors'], [])
        self.assertEqual(before, [layer.ExportToString() for layer in stage.GetLayerStack()])

    def test_missing_box_geometry_and_ambiguous_rack_are_not_guessed(self):
        stage = self.fixture()
        rack = self.UsdGeom.Cube.Define(stage, '/World/Warehouse/SM_RackShelf_02/Mesh')
        rack.GetSizeAttr().Set(2)
        rack.AddTranslateOp().Set(self.Gf.Vec3d(10, 0, 1))
        report = self.inspect(stage)
        self.assertEqual(len(report['boxes'][0]['rack_candidates']), 2)
        self.assertIn('ambiguous_rack', report['boxes'][0]['issues'])
        stage.RemovePrim('/World/Warehouse/Box')
        report = self.inspect(stage)
        self.assertTrue(report['geometry_errors'])
        self.assertIsNone(report['boxes'][0]['world_center'])

    def test_nested_rack_geometry_is_one_logical_rack_not_ambiguous(self):
        stage = self.fixture()
        # A Boundable can contain geometry children: counting both as racks is wrong.
        parent = self.UsdGeom.Cube.Define(stage, '/World/Warehouse/SM_RackShelf_01')
        parent.GetSizeAttr().Set(24)
        result = self.inspect(stage)
        self.assertEqual(len(result['boxes'][0]['rack_candidates']), 1)
        self.assertNotIn('ambiguous_rack', result['boxes'][0]['issues'])

    def test_box_scale_is_flagged_and_yaw_alone_is_permitted_for_inspection(self):
        stage = self.fixture()
        box = self.UsdGeom.Xformable(stage.GetPrimAtPath('/World/Warehouse/Box/Mesh'))
        box.AddRotateZOp().Set(30)
        report = self.inspect(stage)
        self.assertEqual(report['boxes'][0]['issues'], [])
        box.AddScaleOp().Set(self.Gf.Vec3f(2, 1, 1))
        report = self.inspect(stage)
        self.assertIn('non_rigid_transform', report['boxes'][0]['issues'])

    def test_scaled_or_tilted_pallet_is_not_used_for_meter_packing(self):
        for kind in ('scale', 'tilt'):
            with self.subTest(kind=kind):
                stage = self.fixture()
                pallet = self.UsdGeom.Xformable(stage.GetPrimAtPath('/World/Cart/Pallet'))
                if kind == 'scale':
                    pallet.AddScaleOp().Set(self.Gf.Vec3f(2, 1, 1))
                else:
                    pallet.AddRotateXOp().Set(20)
                report = self.inspect(stage)
                self.assertFalse(report['pallet']['rigid_upright'])
                self.assertTrue(report['geometry_errors'])
                self.assertIsNone(report['boxes'][0]['pallet_local_center'])

    def test_active_rigid_body_and_unknown_units_are_reported(self):
        from pxr import UsdPhysics
        stage = self.fixture()
        UsdPhysics.RigidBodyAPI.Apply(stage.GetPrimAtPath('/World/Warehouse/Box'))
        report = self.inspect(stage)
        self.assertIn('active_rigid_body', report['boxes'][0]['issues'])
        self.UsdGeom.SetStageMetersPerUnit(stage, .01)
        report = self.inspect(stage)
        self.assertIn('requires_meter_Z_up_stage', report['geometry_errors'])


if __name__ == '__main__':
    unittest.main()
