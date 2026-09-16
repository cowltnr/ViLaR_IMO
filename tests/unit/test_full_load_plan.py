import unittest
from scripts.warehouse_composite_support import LidSurface


class FullLoadPlanTest(unittest.TestCase):
    def test_requested_second_box_is_supported_by_first(self):
        from scripts.warehouse_composite_support import plan_full_load
        result=plan_full_load((('a',(.5,.5,.2)),('b',(.5,.5,.2))),
            (LidSurface('floor',(0,0),(2,2),1,1,True),),
            stack_second_on_first=True,worker_position=(1,-1,0),
            max_center_height=2,clearance=.03,max_gap=.01,max_height_delta=.002,
            min_coverage=.95,edge_margin=.02,placement_gap=.01)
        self.assertTrue(result.complete)
        a,b=result.placements
        self.assertAlmostEqual(b.bounds.lower[2],a.bounds.upper[2]+.01)

    def test_small_boxes_far_large_boxes_near_worker(self):
        from scripts.warehouse_composite_support import plan_full_load
        lids=(LidSurface('floor',(0,0),(.8,1.2),1,1,True),)
        result=plan_full_load(tuple((str(i),(.5,.5,.2)) for i in range(4)),lids,
            worker_position=(.4,-1,0),max_center_height=2,clearance=.03,max_states=256,
            max_gap=.01,max_height_delta=.002,min_coverage=.95,edge_margin=.02,placement_gap=.01)
        self.assertTrue(result.complete)
        for i,p in enumerate(result.placements):
            y=(p.bounds.lower[1]+p.bounds.upper[1])/2
            self.assertTrue(y>.6 if i<2 else y<.6)

    def test_reserves_large_base_for_later_larger_box(self):
        from scripts.warehouse_composite_support import plan_full_load
        lids = (LidSurface('floor', (0,0), (1.2,.6), 1,1,True),)
        boxes = (('small',(.4,.4,.2)), ('large',(.55,.55,.3)))
        policy = dict(max_gap=.01,max_height_delta=.002,min_coverage=.95,
                      edge_margin=.02,placement_gap=.01)
        result = plan_full_load(boxes,lids,max_center_height=2,clearance=.03,
                                max_states=256,**policy)
        self.assertEqual(len(result.placements),2)
        self.assertEqual(tuple(p.box_id for p in result.placements),('small','large'))

    def test_unavailable_capacity_returns_prefix_not_false_success(self):
        from scripts.warehouse_composite_support import plan_full_load
        lids = (LidSurface('floor',(0,0),(.6,.6),1,1,True),)
        result = plan_full_load((('a',(.5,.5,.3)),('b',(.55,.55,.3))),lids,
            max_center_height=1.4,clearance=.03,max_states=256,
            max_gap=.01,max_height_delta=.002,min_coverage=.95,
            edge_margin=.02,placement_gap=.01)
        self.assertFalse(result.complete)
        self.assertEqual(len(result.placements),1)
