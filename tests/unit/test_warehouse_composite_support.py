import unittest


class CompositeSupportTest(unittest.TestCase):
    def lids(self, gap=.005, dz=0):
        from scripts.warehouse_composite_support import LidSurface
        return (LidSurface('left', (0, 0), (.4, .6), 1, 1, verified=True),
                LidSurface('right', (.4 + gap, 0), (.8 + gap, .6), 1 + dz, 1 + dz, verified=True))

    def assess(self, lids, lower=(.1, .05), upper=(.7, .55)):
        from scripts.warehouse_composite_support import evaluate_support
        return evaluate_support(lower, upper, lids, max_gap=.01, max_height_delta=.002,
                                min_coverage=.95)

    def test_small_seam_is_supported_by_two_fixed_lids(self):
        result = self.assess(self.lids())
        self.assertTrue(result.accepted)
        self.assertAlmostEqual(result.coverage, (.6 - .005) / .6)
        self.assertAlmostEqual(result.max_gap, .005)
        self.assertEqual(result.support_ids, ('left', 'right'))

    def test_large_gap_and_height_step_are_rejected(self):
        self.assertFalse(self.assess(self.lids(gap=.03)).accepted)
        self.assertFalse(self.assess(self.lids(dz=.02)).accepted)

    def test_thin_lid_mesh_uses_upper_support_elevation(self):
        from scripts.warehouse_composite_support import LidSurface, evaluate_support
        lids = (LidSurface('a', (0, 0), (1, 1), .90, 1.00, True),
                LidSurface('b', (1, 0), (2, 1), .91, 1.00, True))
        result = evaluate_support((.1, .1), (1.9, .9), lids,
                                  max_gap=.01, max_height_delta=.002,
                                  min_coverage=.95)
        self.assertTrue(result.accepted)

    def test_overlap_does_not_double_count_area_or_hide_missing_support(self):
        from scripts.warehouse_composite_support import LidSurface
        lid = LidSurface('one', (0, 0), (.4, .6), 1, 1, verified=True)
        duplicate = LidSurface('two', (0, 0), (.4, .6), 1, 1, verified=True)
        result = self.assess((lid, duplicate))
        self.assertAlmostEqual(result.coverage, .5)
        self.assertFalse(result.accepted)

    def test_unverified_aabb_never_becomes_support(self):
        from scripts.warehouse_composite_support import LidSurface
        from dataclasses import asdict
        import json
        result = self.assess((LidSurface('unknown', (0, 0), (1, 1), 1, 1),))
        self.assertFalse(result.accepted)
        json.dumps(asdict(result), allow_nan=False)

    def test_internal_hole_rejected_even_with_supported_corners(self):
        from scripts.warehouse_composite_support import LidSurface
        patches = [((0, 0), (1, .4)), ((0, .6), (1, 1)),
                   ((0, .4), (.4, .6)), ((.6, .4), (1, .6))]
        lids = tuple(LidSurface(str(i), a, b, 1, 1, verified=True) for i, (a, b) in enumerate(patches))
        result = self.assess(lids, (0, 0), (1, 1))
        self.assertAlmostEqual(result.coverage, .96)
        self.assertFalse(result.accepted)  # Area alone would incorrectly pass 95%.

    def test_planner_keeps_fixed_lids_and_places_new_boxes_without_overlap(self):
        from scripts.warehouse_composite_support import plan_on_lids
        lids = self.lids()
        kwargs = dict(max_gap=.01, max_height_delta=.002, min_coverage=.95,
                      edge_margin=.02, placement_gap=.01, max_top=2)
        first = plan_on_lids('a', (.5, .25, .3), lids, (), **kwargs)
        self.assertIsNotNone(first)
        self.assertAlmostEqual(first.bounds.lower[2], 1.01)
        second = plan_on_lids('b', (.5, .25, .3), lids, (first,), **kwargs)
        self.assertIsNotNone(second)
        self.assertGreaterEqual(second.bounds.lower[1], first.bounds.upper[1] + .01 - 1e-8)
        self.assertEqual(lids, self.lids())
        self.assertIsNone(plan_on_lids('c', (.5, .5, .3), lids, (first, second), **kwargs))

    def test_planner_can_stack_on_a_previously_placed_box(self):
        from scripts.warehouse_composite_support import plan_on_lids
        lids = (self.lids()[0],)
        kwargs = dict(max_gap=.01, max_height_delta=.002, min_coverage=.95,
                      edge_margin=.02, placement_gap=.01, max_top=3)
        first = plan_on_lids('a', (.35, .35, .3), lids, (), **kwargs)
        second = plan_on_lids('b', (.35, .35, .3), lids, (first,), **kwargs)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(second.support_ids, ('a',))
        self.assertAlmostEqual(second.bounds.lower[2], first.bounds.upper[2] + .01)

    def test_invalid_dimensions_and_policy_are_rejected(self):
        from scripts.warehouse_composite_support import LidSurface, evaluate_support
        with self.assertRaises(ValueError):
            LidSurface('a', (0, 0), (1, 1), float('nan'), 1, verified=True)
        with self.assertRaises(ValueError):
            LidSurface('a', (0, 0), (1, 1), 1, 1, verified='false')
        with self.assertRaises(ValueError):
            evaluate_support((0, 0), (1, 1), self.lids(), max_gap=-1,
                             max_height_delta=.002, min_coverage=.95)

    def test_edge_margin_must_not_dilute_missing_area_under_actual_box(self):
        from scripts.warehouse_composite_support import LidSurface, plan_on_lids
        surfaces = (LidSurface('a', (0, 0), (.12, .25), 1, 1, True),
                    LidSurface('b', (.129, 0), (.25, .25), 1, 1, True))
        self.assertIsNone(plan_on_lids('box', (.15, .15, .1), surfaces, (), max_gap=.01,
                          max_height_delta=.002, min_coverage=.95, edge_margin=.05,
                          placement_gap=.01, max_top=2))

    def test_margin_support_cannot_raise_box_above_its_actual_support(self):
        from scripts.warehouse_composite_support import LidSurface, plan_on_lids
        ring = [((0, 0), (.042, .02)), ((0, .22), (.042, .24)),
                ((0, .02), (.02, .22)), ((.022, .02), (.042, .22))]
        surfaces = tuple(LidSurface(str(i), a, b, 1.02, 1.02, True)
                         for i, (a, b) in enumerate(ring)) + (
                    LidSurface('low', (.02, .02), (.022, .22), 1, 1, True),)
        self.assertIsNone(plan_on_lids('box', (.002, .2, .1), surfaces, (), max_gap=.01,
                          max_height_delta=.002, min_coverage=.95, edge_margin=.02,
                          placement_gap=.01, max_top=2))


class LidMeshCollectionTest(unittest.TestCase):
    def test_mesh_report_requires_horizontal_top_face_before_support_certification(self):
        from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report
        report = [{
            'path': '/Pallet/Lid_01/Mesh', 'support_verified': False,
            'points_local': [(0, 0, .1), (1, 0, .1), (1, 1, .1), (0, 1, .1)],
            'face_vertex_counts': [4], 'face_vertex_indices': [0, 1, 2, 3],
            'hole_indices': [], 'visibility': 'inherited',
            'world_matrix': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
        }]
        surfaces = lid_surfaces_from_mesh_report(report)
        self.assertEqual(len(surfaces), 1)
        self.assertFalse(surfaces[0].verified)
        self.assertEqual(surfaces[0].surface_id, '/Pallet/Lid_01/Mesh')

    def test_mesh_with_hole_or_tilt_is_not_certified(self):
        from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report
        base = {
            'path': '/Pallet/Lid_01/Mesh', 'support_verified': False,
            'points_local': [(0,0,0), (1,0,0), (1,1,0), (0,1,0)],
            'face_vertex_counts': [4], 'face_vertex_indices': [0,1,2,3],
            'visibility': 'inherited',
            'world_matrix': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
        }
        hole = dict(base, hole_indices=[0])
        tilt = dict(base, world_matrix=[[1,0,0,0],[0,.99,.1,0],[0,-.1,.99,0],[0,0,0,1]])
        self.assertFalse(lid_surfaces_from_mesh_report([hole])[0].verified)
        self.assertFalse(lid_surfaces_from_mesh_report([tilt])[0].verified)

    def test_complex_thin_mesh_uses_usd_row_translation_and_explicit_allowlist(self):
        from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report
        report = [{
            'path': '/Pallet/Lid_01/Mesh', 'support_verified': False,
            'points_local': [(0, 0, 0), (1, 0, 0), (1, 1, .02), (0, 1, .02),
                             (.2, .2, .01), (.8, .8, .01)],
            'face_vertex_counts': [3, 3], 'face_vertex_indices': [0, 1, 4, 1, 2, 5],
            'hole_indices': [], 'visibility': 'inherited',
            # USD Gf.Matrix4d stores translation in row 3.
            'world_matrix': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[2,3,4,1]],
        }]
        surface = lid_surfaces_from_mesh_report(
            report, verified_ids=('/Pallet/Lid_01/Mesh',))[0]
        self.assertTrue(surface.verified)
        self.assertEqual(surface.lower, (2.0, 3.0))
        self.assertEqual(surface.upper, (3.0, 4.0))
        self.assertAlmostEqual(surface.z_min, 4.0)
        self.assertAlmostEqual(surface.z_max, 4.02)

    def test_collects_lid_topology_and_visibility_without_stage_changes(self):
        try:
            from pxr import Usd, UsdGeom
        except ImportError:
            self.skipTest('Bundled OpenUSD required')
        from scripts.warehouse_multi_box_inspection import collect_lid_meshes
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage, '/Pallet')
        UsdGeom.Xform.Define(stage, '/Pallet/Lid_01')
        for name in ('Lid_01/Mesh', 'PlasticBody'):
            mesh = UsdGeom.Mesh.Define(stage, '/Pallet/' + name)
            mesh.GetPointsAttr().Set([(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)])
            mesh.GetFaceVertexCountsAttr().Set([4])
            mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
        UsdGeom.Imageable(stage.GetPrimAtPath('/Pallet')).CreateVisibilityAttr().Set('invisible')
        before = stage.GetRootLayer().ExportToString()
        report = collect_lid_meshes(stage, '/Pallet')
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['face_vertex_indices'], [0, 1, 2, 3])
        self.assertEqual(report[0]['visibility'], 'invisible')
        self.assertFalse(report[0]['support_verified'])
        self.assertEqual(before, stage.GetRootLayer().ExportToString())
