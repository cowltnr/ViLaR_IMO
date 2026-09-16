import unittest


class BoxTransferMathTest(unittest.TestCase):
    def test_low_lift_obeys_arm_cap_and_rejects_unreachable_path(self):
        from scripts.warehouse_box_transfer import transfer_points
        args = ((0,0,1.1), (0,-4,1.2), (0,-3,0), (-1,-1,0), (1,1,2),
                (.4,.4,.4), .1, .03, 3)
        points = transfer_points(*args, max_center_height=1.3)
        self.assertAlmostEqual(max(p[2] for p in points), 1.23)
        with self.assertRaises(ValueError):
            transfer_points(*args, max_center_height=1.22)
        with self.assertRaises(ValueError):
            transfer_points(*args, max_center_height=float('nan'))

    def test_pallet_target_places_box_bottom_above_top(self):
        from scripts.warehouse_box_transfer import placement_center
        self.assertEqual(placement_center((-1, -1, 0), (1, 1, 0.2),
                                           (0.4, 0.6, 0.5), 0.05, 0.01),
                         (0, 0, 0.46))

    def test_oversize_box_is_rejected(self):
        from scripts.warehouse_box_transfer import placement_center
        with self.assertRaises(ValueError):
            placement_center((-1, -1, 0), (1, 1, 0.2), (3, 1, 1), 0.05, 0.01)

    def test_extraction_clears_expanded_rack_before_lifting(self):
        from scripts.warehouse_box_transfer import transfer_points
        points = transfer_points((0, 0, 1), (0, -4, 1), (0, -3, 0),
                                 (-2, -0.5, 0), (2, 0.5, 3),
                                 (0.4, 0.4, 0.4), 0.1, 0.3, 3)
        self.assertAlmostEqual(points[1][1], -0.8)
        self.assertEqual(points[1][2], 1)
        self.assertEqual(points[-1], (0, -4, 1))

    def test_interpolation_clamps_to_endpoints(self):
        from scripts.warehouse_box_transfer import sample_path
        path = [(0, 0, 0), (2, 0, 0), (2, 2, 0)]
        self.assertEqual(sample_path(path, -1), (0, 0, 0))
        self.assertEqual(sample_path(path, 0.5), (2, 0, 0))
        self.assertEqual(sample_path(path, 2), (2, 2, 0))


class BoxTransferUsdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd, UsdGeom, Gf
        except ImportError:
            raise unittest.SkipTest('Bundled OpenUSD required for USD integration tests')
        cls.Usd, cls.UsdGeom, cls.Gf = Usd, UsdGeom, Gf

    def test_transfer_changes_only_box_and_restores_session(self):
        from scripts.warehouse_box_transfer import BoxTransfer
        stage = self.Usd.Stage.CreateInMemory()
        self.UsdGeom.SetStageMetersPerUnit(stage, 1)
        self.UsdGeom.SetStageUpAxis(stage, 'Z')
        box = self.UsdGeom.Cube.Define(stage, '/Box')
        box.GetSizeAttr().Set(0.4)
        box.AddTranslateOp().Set(self.Gf.Vec3d(0, 0, 1))
        pallet = self.UsdGeom.Cube.Define(stage, '/Pallet')
        pallet.GetSizeAttr().Set(1)
        pallet.AddTranslateOp().Set(self.Gf.Vec3d(0, -4, 0.5))
        rack = self.UsdGeom.Cube.Define(stage, '/Rack')
        rack.GetSizeAttr().Set(1)
        root_before = stage.GetRootLayer().ExportToString()
        session_before = stage.GetSessionLayer().ExportToString()
        t = BoxTransfer(stage, '/Box', '/Pallet', '/Rack', delay=1, duration=8,
                        edge_margin=0.02, gap=0.01, pull_margin=0.1,
                        lift_clearance=0.3, max_pull=3)
        t.start(0, (0, -3, 0))
        self.assertEqual(t.current_center, (0, 0, 1))
        t.update(0.5)
        self.assertEqual(stage.GetSessionLayer().ExportToString(), session_before)
        t.update(9)
        pos = self.UsdGeom.Xformable(box).ComputeLocalToWorldTransform(0).ExtractTranslation()
        self.assertAlmostEqual(pos[1], -4)
        self.assertAlmostEqual(pos[2], 1.21)
        self.assertAlmostEqual(t.current_center[1], -4)
        self.assertAlmostEqual(t.current_center[2], 1.21)
        self.assertEqual(stage.GetRootLayer().ExportToString(), root_before)
        t.restore()
        self.assertEqual(stage.GetSessionLayer().ExportToString(), session_before)
        t.restore()
        # Replay and stop midway must also remove only the transfer layer.
        t.start(20, (0, -3, 0))
        t.update(24)
        actual = self.UsdGeom.Xformable(box).ComputeLocalToWorldTransform(0).ExtractTranslation()
        for i in range(3):
            self.assertAlmostEqual(t.current_center[i], actual[i])
        with self.Usd.EditContext(stage, stage.GetSessionLayer()):
            from pxr import Sdf
            stage.GetPrimAtPath('/Rack').CreateAttribute('userNote', Sdf.ValueTypeNames.String).Set('keep')
        t.restore()
        pos = self.UsdGeom.Xformable(box).ComputeLocalToWorldTransform(0).ExtractTranslation()
        self.assertEqual(tuple(pos), (0, 0, 1))
        self.assertEqual(stage.GetPrimAtPath('/Rack').GetAttribute('userNote').Get(), 'keep')
        self.assertEqual(stage.GetRootLayer().ExportToString(), root_before)
        # A height failure must leave the box/layers untouched, before first update.
        t.max_center_height_offset = 1.0
        session_before_limit = stage.GetSessionLayer().ExportToString()
        with self.assertRaises(ValueError):
            t.start(40, (0, -3, 0))
        self.assertEqual(t.state, 'ready')
        self.assertIsNone(t.layer)
        self.assertEqual(stage.GetSessionLayer().ExportToString(), session_before_limit)


class TransferSequenceTest(unittest.TestCase):
    def test_transfer_starts_once_after_turn_and_restores_on_stop(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        events = []
        timeline = SimpleNamespace(is_playing=lambda: True, get_current_time=lambda: current[0])
        transfer = SimpleNamespace(start=lambda now, pos: events.append(('start', now)),
                                   update=lambda now: events.append(('update', now)),
                                   restore=lambda: events.append(('restore',)))
        runtime = FaceBoxRuntime.__new__(FaceBoxRuntime)
        runtime.timeline, runtime.transfer = timeline, transfer
        runtime.approach = None
        runtime.gesture = None
        runtime.state, runtime.start_time, runtime.duration = 'turning', 0, 3
        runtime.start_yaw, runtime.end_yaw, runtime.position = 0, 90, (0, 0, 0)
        runtime.sync = SimpleNamespace(_character=SimpleNamespace(set_world_transform=lambda p, q: None))
        runtime._stop_type = 99
        current = [2]
        with patch.dict('sys.modules', carb=SimpleNamespace(Float3=lambda *v: v, Float4=lambda *v: v)):
            runtime._on_update(None)
            self.assertEqual(events, [])
            current[0] = 3
            runtime._on_update(None)
            current[0] = 4
            runtime._on_update(None)
        self.assertEqual(events, [('start', 3), ('update', 3), ('update', 4)])
        runtime._on_timeline(SimpleNamespace(type=99))
        self.assertEqual(events[-1], ('restore',))
        self.assertEqual(runtime.state, 'waiting_arrival')
