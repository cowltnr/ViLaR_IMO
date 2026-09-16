import unittest


class WorkPositionTest(unittest.TestCase):
    def test_invalid_backward_path_does_not_prevent_valid_side_candidate(self):
        from scripts.warehouse_work_position import select_work_position
        def path(a,b):
            return [] if b[0] < -.1 else [a,b]
        result=select_work_position((0,0,0),(1,0,0),(.35,),(0,90,-90),
            lambda p:p,path,lambda goal,route:goal[1]<0,.15)
        self.assertAlmostEqual(result[0],0)
        self.assertAlmostEqual(result[1],-.35)

    def test_valid_navigation_but_blocked_box_route_is_rejected(self):
        from scripts.warehouse_work_position import select_work_position
        self.assertIsNone(select_work_position((0,0,0),(1,0,0),(.35,),
            (0,90),lambda p:p,lambda a,b:[a,b],lambda p,r:False,.15))
