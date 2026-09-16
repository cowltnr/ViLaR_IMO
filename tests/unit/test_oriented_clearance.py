import math
import unittest
from scripts.warehouse_oriented_clearance import OrientedBox,collisions


class OrientedClearanceTest(unittest.TestCase):
    def test_transfer_bypasses_body_without_raising_box(self):
        from scripts.warehouse_oriented_clearance import route_around
        box=OrientedBox('box',(-2,0,1),(.2,.2,.2),0)
        body=OrientedBox('worker',(0,0,1),(.3,.3,.7),0)
        points=[(-2,0,.8),(-2,0,.9),(-1.5,0,.9),(-1.5,0,1),(2,0,1),(2,0,.8)]
        result=route_around(points,box,[body],.05)
        self.assertIsNotNone(result)
        self.assertEqual(collisions(result,box,[body]),())
        self.assertEqual(max(p[2] for p in result),1)

    def test_rotated_boxes_separated_despite_overlapping_aabbs(self):
        a=OrientedBox('a',(0,0,1),(.5,.1,.1),math.pi/4)
        b=OrientedBox('b',(-.2,.2,1),(.5,.1,.1),math.pi/4)
        self.assertEqual(collisions([a.center,a.center],a,[b]),())

    def test_continuous_sweep_detects_torso_between_endpoints(self):
        a=OrientedBox('box',(-2,0,1),(.25,.25,.25),0)
        torso=OrientedBox('worker',(0,0,1),(.3,.3,.6),0)
        self.assertEqual(collisions([(-2,0,1),(2,0,1)],a,[torso]),('worker',))
