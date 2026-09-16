import unittest

from scripts.warehouse_cart_packing import Bounds
from scripts.warehouse_composite_support import CargoPlacement, LidSurface


class CompositeSlideTest(unittest.TestCase):
    def test_runtime_slide_preserves_original_restore_reference(self):
        from scripts.warehouse_unloading_live import PlacedTransfer
        obj = PlacedTransfer.__new__(PlacedTransfer)
        obj.state, obj.layer = 'loaded', object()
        obj.current_center, obj.source = (1, 2, 3), (-5, 0, 1)
        obj.original_world = object()
        origin, layer = obj.original_world, obj.layer
        obj.relocate((1.2, 2, 3), 10, 2, 1)
        self.assertEqual(obj.points, [(1, 2, 3), (1.2, 2, 3)])
        self.assertEqual(obj.source, (-5, 0, 1))
        self.assertIs(obj.original_world, origin)
        self.assertIs(obj.layer, layer)
        self.assertEqual(obj.state, 'waiting')
        self.assertEqual(obj.start_time, 11)

    def test_relocation_makes_room_without_mutating_input(self):
        from scripts.warehouse_composite_support import plan_with_slides, plan_on_lids
        lids = (LidSurface('fixed', (0, 0), (2, 1), 1, 1, True),)
        a = CargoPlacement('a', Bounds((.8, .1, 1.01), (1.2, .5, 1.31)), ('fixed',))
        kw = dict(max_gap=.01, max_height_delta=.002, min_coverage=.95,
                  edge_margin=.02, placement_gap=.01, max_top=1.5)
        self.assertIsNone(plan_on_lids('new', (.8, .8, .4), lids, (a,), **kw))
        plan = plan_with_slides('new', (.8, .8, .4), lids, (a,), **kw)
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.slides), 1)
        self.assertEqual(plan.slides[0].box_id, 'a')
        self.assertEqual(a.bounds.lower, (.8, .1, 1.01))
        self.assertIsNone(plan_with_slides('new', (.8, .8, .4), lids, (a,),
                                         max_relocations=0, **kw))

    def test_slide_checks_entire_sweep_and_preserves_fixed_lids(self):
        from scripts.warehouse_composite_support import can_slide_on_lids
        lids = (LidSurface('fixed', (0, 0), (2, 1), 1, 1, True),)
        a = CargoPlacement('a', Bounds((.1, .1, 1.01), (.5, .5, 1.31)), ('fixed',))
        end = Bounds((1.4, .1, 1.01), (1.8, .5, 1.31))
        kw = dict(max_gap=.01, max_height_delta=.002, min_coverage=.95,
                  edge_margin=.02, placement_gap=.01)
        self.assertTrue(can_slide_on_lids(a, end, lids, (a,), **kw))
        obstacle = CargoPlacement('b', Bounds((.8, .1, 1.01), (1.2, .5, 1.31)), ('fixed',))
        self.assertFalse(can_slide_on_lids(a, end, lids, (a, obstacle), **kw))
        top = CargoPlacement('top', Bounds((.1, .1, 1.32), (.5, .5, 1.5)), ('a',))
        self.assertFalse(can_slide_on_lids(a, end, lids, (a, top), **kw))

    def test_slide_cannot_cross_missing_support(self):
        from scripts.warehouse_composite_support import can_slide_on_lids
        lids = (LidSurface('left', (0, 0), (.6, 1), 1, 1, True),
                LidSurface('right', (1.2, 0), (2, 1), 1, 1, True))
        a = CargoPlacement('a', Bounds((.1, .1, 1.01), (.5, .5, 1.31)), ('left',))
        self.assertFalse(can_slide_on_lids(a, Bounds((1.4, .1, 1.01), (1.8, .5, 1.31)),
            lids, (a,), max_gap=.01, max_height_delta=.002, min_coverage=.95,
            edge_margin=.02, placement_gap=.01))
