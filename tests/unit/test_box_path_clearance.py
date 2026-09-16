import unittest


class BoxPathClearanceTest(unittest.TestCase):
    def test_detects_obstacle_between_clear_endpoints(self):
        from scripts.warehouse_unloading_live import path_collisions
        hits = path_collisions([(0,0,1),(4,0,1)],(.4,.4,.4),
                               [('middle',(1.8,-.2,.8),(2.2,.2,1.2))])
        self.assertEqual(hits,('middle',))

    def test_touching_support_then_lifting_is_allowed(self):
        from scripts.warehouse_unloading_live import path_collisions
        self.assertEqual(path_collisions([(0,0,1.2),(0,0,1.3),(-2,0,1.3)],
            (.4,.4,.4),[('support',(-.3,-.3,0),(.3,.3,1))]),())
