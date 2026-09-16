import unittest
from scripts.warehouse_oriented_clearance import OrientedBox,collisions


class ClearPathTest(unittest.TestCase):
    def test_gestures_do_not_disable_side_pull_or_allow_loaded_box_overlap(self):
        from scripts import warehouse_stack_gesture as module
        from types import SimpleNamespace as NS
        self.assertTrue(hasattr(module,'pull_policy'))
        config=NS(STACK_GESTURES_ENABLED=True,STACK_ALLOW_SIDE_BOX_OVERLAP=True,
            STACK_VISUAL_PULL_DISTANCES_M=(.7,1.),STACK_PULL_DISTANCES_M=(.35,),
            WAREHOUSE_PATH='/Warehouse')
        proxies=[NS(name=p) for p in ['/Warehouse/Box_side','/Warehouse/Box_loaded','WorkerBody']]
        policy=module.pull_policy(config,proxies,('/Warehouse/Box_loaded',))
        self.assertEqual(policy['pull_distances'],(.7,1.))
        self.assertEqual(policy['allowed_side_boxes'],('/Warehouse/Box_side',))

    def test_parked_box_mode_starts_without_face_or_gesture(self):
        from scripts.warehouse_stack_gesture import StackGestureRuntime
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        from types import SimpleNamespace as NS
        from unittest.mock import Mock,patch
        obj=StackGestureRuntime.__new__(StackGestureRuntime)
        stage=object()
        obj.stage=stage
        obj.timeline=NS(is_playing=lambda:True,get_current_time=lambda:5.)
        obj.sync=NS(_read_worker_pose=lambda:((0,0,0),None))
        obj.gesture=None
        obj.state='arrival_pending'
        obj.transfer=NS(start=Mock(),update=Mock(),state='moving')
        obj.sequence=NS(transfers=[obj.transfer])
        obj.planned_transfer=obj.transfer
        usd=NS(get_context=lambda:NS(get_stage=lambda:stage))
        with patch.dict('sys.modules',{'omni':NS(usd=usd),'omni.usd':usd}), \
                patch.object(FaceBoxRuntime,'_on_update') as face:
            obj._on_update(None)
            face.assert_not_called()
        obj.transfer.start.assert_called_once_with(5.,(0,0,0))
        obj.transfer.update.assert_called_once_with(5.)
        self.assertEqual(obj.state,'facing')

    def test_visual_pull_can_cross_named_side_box_but_clears_endpoint(self):
        from scripts.warehouse_stack_gesture import pull_then_path_steps
        box=OrientedBox('moving',(0,0,1),(.1,.1,.1),0)
        side=OrientedBox('/Warehouse/Box_side',(-.3,0,1),(.1,.1,.1),0)
        steps=pull_then_path_steps((0,0,1),(-2,0,1.5),box,[side],.03,
            allowed_prefix='/Warehouse/Box_',pull_distances=(.7,),
            allowed_side_boxes=(side.name,))
        while True:
            try: next(steps)
            except StopIteration as result:
                self.assertEqual(result.value[1],(-.7,0,1))
                self.assertEqual(collisions(result.value[1:],box,[side]),())
                break

    def test_authorized_initial_overlap_pulls_toward_cart_before_lifting(self):
        from scripts.warehouse_stack_gesture import pull_then_path_steps
        box=OrientedBox('moving',(0,0,1),(.25,.25,.25),0)
        neighbour=OrientedBox('/Warehouse/Box_2',(.4,0,1),(.25,.25,.25),0)
        steps=pull_then_path_steps((0,0,1),(-2,0,1.5),box,[neighbour],.03,
            allowed_prefix='/Warehouse/Box_',pull_distances=(.35,.7))
        while True:
            try:
                next(steps)
            except StopIteration as result:
                path=result.value
                break
        self.assertEqual(path[:2],[(0,0,1),(-.35,0,1)])
        self.assertEqual(path[-1],(-2,0,1.5))
        self.assertEqual(collisions(path[1:],box,[neighbour]),())

    def test_initial_overlap_permission_does_not_allow_new_obstacles(self):
        from scripts.warehouse_stack_gesture import pull_then_path_steps,PathSearchError
        box=OrientedBox('moving',(0,0,1),(.25,.25,.25),0)
        obstacles=[OrientedBox('/Warehouse/Box_2',(.4,0,1),(.25,.25,.25),0),
                   OrientedBox('WorkerBody',(-.6,0,1),(.25,.25,.8),0)]
        with self.assertRaises(PathSearchError):
            list(pull_then_path_steps((0,0,1),(-2,0,1.5),box,obstacles,.03,
                allowed_prefix='/Warehouse/Box_',pull_distances=(.35,.7)))

    def test_worker_overlap_is_never_implicitly_authorized(self):
        from scripts.warehouse_stack_gesture import pull_then_path_steps,PathSearchError
        box=OrientedBox('moving',(0,0,1),(.25,.25,.25),0)
        with self.assertRaisesRegex(PathSearchError,'source'):
            list(pull_then_path_steps((0,0,1),(-2,0,1.5),box,
                [OrientedBox('WorkerBody',(0,0,1),(.3,.3,.8),0)],.03,
                allowed_prefix='/Warehouse/Box_'))
    def test_live_search_is_sliced_and_does_not_mark_ready_early(self):
        from scripts.warehouse_stack_gesture import StackGestureRuntime
        from types import SimpleNamespace as NS
        import time
        obj=StackGestureRuntime.__new__(StackGestureRuntime)
        obj.config=NS(STACK_SEARCH_TIMEOUT_SECONDS=30,STACK_CHECKS_PER_FRAME=2,
                      STACK_FRAME_BUDGET_SECONDS=1)
        obj.search_started=time.monotonic()
        obj.search=iter([{'phase':'travel'}]*3)
        obj.search_report={'phase_counts':{}}
        obj.state='planning'
        reports=[]
        obj.save_search_report=lambda:reports.append(dict(obj.search_report))
        obj.advance_search()
        self.assertEqual(obj.state,'planning')
        self.assertEqual(obj.search_report['phase_counts']['travel'],2)
        self.assertEqual(reports,[])
        obj.advance_search()
        self.assertEqual(obj.state,'arrival_pending')
        self.assertEqual(len(reports),1)

    def test_destination_overlap_is_reported_before_route_search(self):
        from scripts.warehouse_stack_gesture import path_search_steps,PathSearchError
        box=OrientedBox('moving',(0,0,1),(.2,.2,.2),0)
        steps=path_search_steps((0,0,1),(2,0,1),box,
            [OrientedBox('cargo',(2,0,1),(.3,.3,.3),0)],.03)
        with self.assertRaises(PathSearchError) as error:
            list(steps)
        self.assertEqual(error.exception.phase,'destination')
        self.assertEqual(error.exception.blockers,('cargo',))

    def test_search_yields_and_honors_check_limit(self):
        from scripts.warehouse_stack_gesture import path_search_steps,PathSearchError
        box=OrientedBox('moving',(0,0,1),(.2,.2,.2),0)
        steps=path_search_steps((0,0,1),(2,0,1),box,
            [OrientedBox('wall',(1,0,1),(.3,.3,.8),0)],.03,max_checks=2)
        self.assertIsInstance(next(steps),dict)
        with self.assertRaises(PathSearchError) as error:
            list(steps)
        self.assertEqual(error.exception.phase,'search_budget')
    def test_detours_around_box_that_blocks_straight_transfer(self):
        from scripts.warehouse_stack_gesture import clear_transfer_path
        box=OrientedBox('moving',(0,0,1),(.2,.2,.2),0)
        obstacles=[OrientedBox('other',(1,0,1.2),(.3,.3,.6),0)]
        path=clear_transfer_path((0,0,1),(2,0,1),box,obstacles,.03)
        self.assertEqual(path[0],(0,0,1))
        self.assertEqual(path[-1],(2,0,1))
        self.assertEqual(collisions(path,box,obstacles),())

    def test_overhead_box_requires_sideways_extraction_before_lift(self):
        from scripts.warehouse_stack_gesture import clear_transfer_path
        box=OrientedBox('moving',(0,0,1),(.2,.2,.2),0)
        obstacles=[OrientedBox('overhead',(0,0,1.6),(.25,.25,.2),0)]
        path=clear_transfer_path((0,0,1),(2,0,2),box,obstacles,.03)
        self.assertNotEqual(path[1][:2],(0,0))
        self.assertEqual(collisions(path,box,obstacles),())

    def test_no_path_does_not_silently_move_through_obstacle(self):
        from scripts.warehouse_stack_gesture import clear_transfer_path
        box=OrientedBox('moving',(0,0,1),(.2,.2,.2),0)
        with self.assertRaisesRegex(RuntimeError,'enclosing'):
            clear_transfer_path((0,0,1),(2,0,1),box,
                [OrientedBox('enclosing',(0,0,1),(2,2,2),0)],.03)


class RuntimeUSDTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd
        except ImportError:
            raise unittest.SkipTest('Bundled OpenUSD required')

    def test_selected_three_load_and_fourth_is_untouched(self):
        from pxr import Usd,UsdGeom,Gf
        from scripts import setup_warehouse_stack_gesture as setup
        from scripts import warehouse_multi_box_config as base
        from scripts.warehouse_box_only_stack import BoxSequence,stack_centers,bounds
        self.assertTrue(hasattr(setup,'stack_configuration'))
        config=setup.stack_configuration(base)
        stage=Usd.Stage.CreateInMemory()
        for i,path in enumerate(base.BOX_PATHS):
            cube=UsdGeom.Cube.Define(stage,path)
            cube.CreateSizeAttr(.5)
            cube.AddTranslateOp().Set(Gf.Vec3d(i,0,1))
        original=stage.GetRootLayer().ExportToString()
        centers=stack_centers((0,4),1,[(.5,.5,.5)]*len(config.BOX_PATHS),.01)
        seq=BoxSequence(stage,config.BOX_PATHS,centers,1,.03)
        for now in range(5):
            seq.update(now)
        self.assertEqual([t.box_path.split('/')[-2] for t in seq.transfers],
                         ['Box_26000','Box_26002','Box_26004'])
        self.assertEqual(seq.index,3)
        self.assertTrue(all(t.state=='loaded' for t in seq.transfers))
        self.assertEqual(tuple(bounds(stage,base.BOX_PATHS[3]).GetMidpoint()),(3,0,1))
        self.assertEqual(len(base.BOX_PATHS),4)
        seq.restore()
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths),[])
        self.assertEqual(stage.GetRootLayer().ExportToString(),original)

    def test_each_source_selected_only_after_previous_gesture_finishes(self):
        from pxr import Usd,UsdGeom,Gf
        from types import SimpleNamespace as NS
        from unittest.mock import patch
        from scripts.warehouse_box_only_stack import BoxSequence
        from scripts.warehouse_stack_gesture import StackGestureRuntime
        from scripts.warehouse_worker_face_box import FaceBoxRuntime
        stage=Usd.Stage.CreateInMemory()
        paths=[]
        for i in range(4):
            p='/Box%d'%i
            c=UsdGeom.Cube.Define(stage,p)
            c.CreateSizeAttr(.5)
            c.AddTranslateOp().Set(Gf.Vec3d(i,0,1))
            paths.append(p)
        original=stage.GetRootLayer().ExportToString()
        seq=BoxSequence(stage,paths,[(0,4,1+i*.51) for i in range(4)],3,.03)
        obj=StackGestureRuntime.__new__(StackGestureRuntime)
        obj.stage,obj.sequence,obj.box_index=stage,seq,0
        obj.config=NS(ARM_RAISE_SECONDS=1,STACK_TURN_RATE_DEG_S=45)
        obj.forward_yaw=-90
        obj.gesture=NS(done=False,reset=lambda:None,follow_transfer=lambda *a:None)
        obj.timeline=NS(is_playing=lambda:True)
        obj.state='facing'
        obj.select_transfer()
        seq.transfers[0].state='loaded'
        usd=NS(get_context=lambda:NS(get_stage=lambda:stage))
        with patch.dict('sys.modules',{'omni':NS(usd=usd),'omni.usd':usd}), \
                patch.object(FaceBoxRuntime,'_on_update',lambda *a:None):
            obj._on_update(None)
            self.assertEqual(obj.box_index,0)
            obj.gesture.done=True
            obj._on_update(None)
            self.assertEqual(obj.box_index,1)
            self.assertEqual(obj.transfer.box_path,'/Box1')
            self.assertEqual(obj.state,'arrival_pending')
        # Partial motion in multiple owned layers must all restore on Stop.
        for transfer in seq.transfers[:2]:
            transfer.state='ready'
            transfer.path_builder=lambda source,dest,*a,**k:[source,dest]
            transfer.start(0,(0,0,0)); transfer.update(2)
        obj._stop_type=2
        with patch.object(FaceBoxRuntime,'_on_timeline',lambda *a:None):
            obj._on_timeline(NS(type=2))
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths),[])
        self.assertEqual(stage.GetRootLayer().ExportToString(),original)
        self.assertIsNone(obj.sequence)
