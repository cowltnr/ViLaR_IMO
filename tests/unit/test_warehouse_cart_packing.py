"""Hand-derived packing fixtures: no Isaac Sim process or scene edits."""

import unittest


class PackingTest(unittest.TestCase):
    def test_stackable_requires_explicit_boolean_not_truthy_configuration(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        for value in ('false', 1, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Placement('a', Bounds((.02, .02, .11), (.98, .98, .41)), 'pallet', stackable=value)
                with self.assertRaises(ValueError):
                    plan_load('a', (.4, .4, .3), surface, (), margin=.02, gap=.01,
                              max_top=1, stackable=value)

    def test_enclosing_box_is_not_implicitly_a_verified_stack_support(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        # Could be a rotated box: outer AABB corners are NOT actual support.
        old = Placement('a', Bounds((.02, .02, .11), (.98, .98, .41)), 'pallet')
        self.assertIsNone(plan_load('b', (.4, .4, .3), surface, (old,),
                                    margin=.02, gap=.01, max_top=1))

    def test_slides_loaded_box_only_when_direct_layout_is_unavailable(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, .5, .1))
        old = Placement('a', Bounds((.35, .02, .11), (.65, .48, .41)), 'pallet')
        kwargs = dict(margin=.02, gap=.01, max_top=.5)
        self.assertIsNone(plan_load('b', (.4, .46, .3), surface, (old,),
                                    max_relocations=0, **kwargs))
        plan = plan_load('b', (.4, .46, .3), surface, (old,), **kwargs)
        self.assertEqual(len(plan.slides), 1)
        self.assertEqual(plan.slides[0].box_id, 'a')
        self.assertEqual(plan.slides[0].start, old.bounds)
        self.assertAlmostEqual(plan.slides[0].end.lower[0], .02)
        self.assertAlmostEqual(plan.placement.bounds.lower[0], .33)
        self.assertEqual(old.bounds.lower, (.35, .02, .11))
        self.assertIsNone(plan_load('b', (.4, .46, .3), surface, (old,), max_states=1, **kwargs))

    def test_slide_checks_whole_sweep_not_just_free_endpoint(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, can_slide
        surface = Bounds((0, 0, 0), (3, 1, .1))
        moving = Placement('a', Bounds((.02, .02, .11), (.42, .42, .41)), 'pallet')
        blocker = Placement('b', Bounds((1, .02, .11), (1.4, .42, .41)), 'pallet')
        end = Bounds((2, .02, .11), (2.4, .42, .41))
        self.assertFalse(can_slide(moving, end, surface, (moving, blocker), margin=.02, gap=.01))
        self.assertTrue(can_slide(moving, end, surface, (moving,), margin=.02, gap=.01))
        outside = Bounds((2.8, .02, .11), (3.2, .42, .41))
        self.assertFalse(can_slide(moving, outside, surface, (moving,), margin=.02, gap=.01))
        resized = Bounds((2, .02, .11), (2.6, .42, .41))
        self.assertFalse(can_slide(moving, resized, surface, (moving,), margin=.02, gap=.01))

    def test_never_pushes_a_box_supporting_another_box(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, can_slide
        surface = Bounds((0, 0, 0), (2, 1, .1))
        bottom = Placement('a', Bounds((.02, .02, .11), (.62, .62, .41)), 'pallet', stackable=True)
        top = Placement('b', Bounds((.12, .12, .42), (.42, .42, .62)), 'a')
        end = Bounds((1.02, .02, .11), (1.62, .62, .41))
        self.assertFalse(can_slide(bottom, end, surface, (bottom, top), margin=.02, gap=.01))
        top_end = Bounds((.2, .12, .42), (.5, .42, .62))
        # The initial implementation only slides pallet-supported, unburdened boxes.
        self.assertFalse(can_slide(top, top_end, surface, (bottom, top), margin=.02, gap=.01))

    def test_two_support_boxes_do_not_allow_bridging_their_tops(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, .5, .1))
        loaded = (Placement('a', Bounds((.02, .02, .11), (.48, .48, .41)), 'pallet', stackable=True),
                  Placement('b', Bounds((.50, .02, .11), (.96, .48, .41)), 'pallet', stackable=True))
        self.assertIsNone(plan_load('c', (.8, .4, .3), surface, loaded,
                                    margin=.02, gap=.01, max_top=1))

    def test_places_beside_existing_box_before_stacking(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        existing = Placement('a', Bounds((.02, .02, .11), (.42, .42, .41)), 'pallet')
        loaded = (existing,)
        result = plan_load('b', (.4, .4, .3), surface, loaded,
                           margin=.02, gap=.01, max_top=1)
        self.assertEqual(result.placement.support_id, 'pallet')
        self.assertAlmostEqual(result.placement.bounds.lower[2], .11)
        b = result.placement.bounds
        self.assertTrue(b.lower[0] >= .43 - 1e-9 or b.lower[1] >= .43 - 1e-9)
        self.assertEqual(result.slides, ())
        self.assertEqual(loaded, (existing,))

    def test_stacks_only_on_one_support_with_full_footprint(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        loaded = (Placement('a', Bounds((.02, .02, .11), (.98, .98, .41)), 'pallet', stackable=True),)
        result = plan_load('b', (.5, .5, .3), surface, loaded,
                           margin=.02, gap=.01, max_top=1)
        self.assertEqual(result.placement.support_id, 'a')
        self.assertAlmostEqual(result.placement.bounds.lower[2], .42)
        self.assertGreaterEqual(result.placement.bounds.lower[0], .02)
        self.assertLessEqual(result.placement.bounds.upper[0], .98)

    def test_no_room_or_height_returns_none_without_changing_input(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        loaded = (Placement('a', Bounds((.02, .02, .11), (.98, .98, .41)), 'pallet', stackable=True),)
        self.assertIsNone(plan_load('b', (.5, .5, .3), surface, loaded,
                                    margin=.02, gap=.01, max_top=.6))
        self.assertIsNone(plan_load('b', (1.1, .5, .3), surface, (),
                                    margin=.02, gap=.01, max_top=1))
        self.assertEqual(loaded[0].bounds.upper, (.98, .98, .41))

    def test_rejects_invalid_inputs_and_invalid_initial_occupancy(self):
        from scripts.warehouse_cart_packing import Bounds, Placement, plan_load
        surface = Bounds((0, 0, 0), (1, 1, .1))
        for size in ((0, .2, .2), (float('nan'), .2, .2), (.2, .2)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                plan_load('a', size, surface, (), margin=.02, gap=.01, max_top=1)
        floating = Placement('x', Bounds((.02, .02, .5), (.3, .3, .7)), 'pallet')
        with self.assertRaises(ValueError):
            plan_load('a', (.2, .2, .2), surface, (floating,), margin=.02, gap=.01, max_top=1)
        box = Placement('x', Bounds((.02, .02, .11), (.3, .3, .31)), 'pallet')
        overlap = Placement('y', Bounds((.1, .1, .11), (.4, .4, .31)), 'pallet')
        with self.assertRaises(ValueError):
            plan_load('a', (.2, .2, .2), surface, (box, overlap), margin=.02, gap=.01, max_top=1)
        with self.assertRaises(ValueError):
            plan_load('x', (.2, .2, .2), surface, (box,), margin=.02, gap=.01, max_top=1)

    def test_four_different_boxes_have_deterministic_nonoverlapping_layout(self):
        from scripts.warehouse_cart_packing import Bounds, plan_load
        surface = Bounds((0, 0, 0), (1.2, .8, .1))
        def pack():
            loaded = ()
            for name, size in (('a', (.4, .3, .2)), ('b', (.4, .3, .2)),
                               ('c', (.3, .3, .25)), ('d', (.3, .3, .25))):
                plan = plan_load(name, size, surface, loaded, margin=.02, gap=.01, max_top=1)
                self.assertIsNotNone(plan)
                loaded = plan.placements
            return loaded
        result = pack()
        self.assertEqual(result, pack())
        self.assertEqual(len(result), 4)
        for i, box in enumerate(result):
            for other in result[:i]:
                self.assertTrue(any(box.bounds.upper[k] <= other.bounds.lower[k] - .01 + 1e-8
                                    or other.bounds.upper[k] <= box.bounds.lower[k] - .01 + 1e-8
                                    for k in range(3)))


if __name__ == '__main__':
    unittest.main()
