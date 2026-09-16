import math
import unittest


class RoamingControllerTest(unittest.TestCase):
    def test_rejected_clearance_never_issues_move(self):
        from scripts.warehouse_loaded_cart_roaming import LoadedCartRoaming
        class Actions:
            def route_check_steps(self,points):
                yield None
                return False
            def begin_move(self,goal):
                raise AssertionError('Unsafe route must not move')
        runtime=LoadedCartRoaming(Actions())
        runtime.state='validating'
        runtime.goal=(3,0,0)
        runtime.validation=runtime.actions.route_check_steps([])
        runtime._advance_validation(1)
        self.assertEqual(runtime.state,'retry_wait')
        self.assertIsNone(runtime.validation)

    def test_checks_are_sliced_before_any_move_and_close_restores(self):
        from scripts.warehouse_loaded_cart_roaming import LoadedCartRoaming
        from scripts import warehouse_roaming_config as cfg
        from unittest.mock import patch
        class Actions:
            def __init__(self):
                self.moves=[]
                self.attached=False
                self.stopped=False
            def begin_return(self): pass
            def return_complete(self): return True
            def attach_loaded_boxes(self): self.attached=True
            def resume_cart(self): pass
            def worker_position(self): return (0,0,0)
            def update_loaded_boxes(self): pass
            def route_check_steps(self,points):
                for _ in range(5): yield None
                return True
            def begin_move(self,goal): self.moves.append(goal)
            def stop_owned_motion(self): self.stopped=True
            def restore_loaded_boxes(self): self.attached=False
        a=Actions()
        runtime=LoadedCartRoaming(a)
        class Picker:
            def candidate_steps(self,start):
                yield dict(accepted=True,goal=(3,0,0),points=[start,(3,0,0)])
        runtime.picker=Picker()
        runtime.start(0)
        runtime.update(.1)
        runtime.update(.2)
        self.assertEqual(runtime.state,'validating')
        with patch.object(cfg,'GUARD_STEPS_PER_FRAME',2):
            runtime.update(.3)
            self.assertEqual(a.moves,[])
            runtime.update(.4)
            self.assertEqual(a.moves,[])
            runtime.update(.5)
        self.assertEqual(a.moves,[(3,0,0)])
        runtime.close()
        self.assertTrue(a.stopped)
        self.assertFalse(a.attached)


class RoamingGeometryTest(unittest.TestCase):
    def test_guard_rolls_worker_back_holds_cart_and_cancels_owned_command_in_both_orders(self):
        from types import SimpleNamespace as NS
        from scripts.warehouse_roaming_actions import IsaacRoamingActions,OwnedPeopleCommand
        from scripts.warehouse_worker_cart_pose_sync import PoseSyncController
        from scripts.warehouse_loaded_cart_roaming import LoadedCartRoaming
        for subscriber_first in (False,True):
            with self.subTest(subscriber_first=subscriber_first):
                worker=[((0.,0.,0.),(0.,0.,0.,1.))]
                cart=((0.,1.,0.),(0.,0.,0.,1.))
                writes=[]
                sync=PoseSyncController(read_worker_pose=lambda:worker[0],read_cart_pose=lambda:cart,
                    write_cart_pose=writes.append,clear_cart_override=lambda:None,is_playing=lambda:True)
                sync.update()
                a=IsaacRoamingActions.__new__(IsaacRoamingActions)
                a.last_safe=worker[0]
                a.guard_error=None
                a._pose_safe=lambda pose:pose[0][0]<=.1
                a._set_pose=lambda pose:worker.__setitem__(0,pose)
                a.guard_callback=a._guard_motion
                sync.motion_guard=a.guard_callback
                a.sync=NS(_controller=sync,relative_transform=sync.relative_transform,hold=sync.hold)
                a.owner=NS(timeline=NS(is_playing=lambda:True))
                behavior=NS(commands=[('ours',['GoTo','2','0','0','0'])],
                    current_command=NS(command_id='ours'),end_current_command=lambda **k:None)
                a.command=OwnedPeopleCommand(behavior)
                a.command.key='ours'
                a.cargo=NS(update=lambda:None,restore=lambda:None)
                runtime=LoadedCartRoaming(a)
                runtime.state='moving'
                runtime.cargo_attached=True
                worker[0]=((.2,0.,0.),(0.,0.,0.,1.))
                if subscriber_first:
                    with self.assertRaises(RuntimeError):
                        sync.update()
                runtime.update(1)
                self.assertEqual(runtime.state,'failed')
                self.assertEqual(worker[0][0],(0.,0.,0.))
                self.assertEqual(len(writes),1)
                self.assertEqual(sync.held_pose,cart)
                self.assertEqual(behavior.commands,[])
                self.assertIsNone(behavior.current_command)

    def test_completed_queue_waits_for_delayed_command_end_event(self):
        from types import SimpleNamespace as NS
        from scripts.warehouse_roaming_actions import OwnedPeopleCommand
        command=OwnedPeopleCommand(NS(commands=[],current_command=None))
        command.key='finished-but-event-pending'
        self.assertFalse(command.complete())
        command.on_event(NS(payload=dict(command_id=command.key,status='default')))
        self.assertTrue(command.complete())

    def test_actual_cart_footprint_can_fail_while_worker_is_on_mesh(self):
        from scripts.warehouse_roaming_actions import IsaacRoamingActions
        actions=IsaacRoamingActions.__new__(IsaacRoamingActions)
        actions.relative=((0,1,0),(0,0,0,1))
        actions.cart_points=((.6,0,0),(-.6,0,0))
        actions._closest=lambda p:p if abs(p[0])<=.5 else None
        self.assertFalse(actions._pose_safe(((0,0,0),(0,0,0,1))))
        actions._closest=lambda p:p
        self.assertTrue(actions._pose_safe(((0,0,0),(0,0,0,1))))

    def test_cancel_removes_only_owned_people_command(self):
        from scripts.warehouse_roaming_actions import OwnedPeopleCommand
        from types import SimpleNamespace as NS
        class Behavior:
            def __init__(self):
                self.commands=[]
                self.current_command=None
            def inject_command(self,pairs,executeImmediately=False):
                self.commands.extend((key,text.split()[1:]) for key,text in pairs)
            def end_current_command(self,set_status=True):
                self.current_command.finished=True
        behavior=Behavior()
        command=OwnedPeopleCommand(behavior)
        command.send((1,2,0),90)
        behavior.current_command=NS(command_id=command.key,finished=False)
        behavior.commands.append(('other',['Idle','10']))
        command.cancel()
        self.assertEqual(behavior.commands,[('other',['Idle','10'])])
        self.assertIsNone(behavior.current_command)

    def test_turn_sweep_includes_cart_corner_off_walkable_area(self):
        from scripts import warehouse_roaming_geometry as g
        self.assertTrue(hasattr(g,'route_poses'))
        poses=list(g.route_poses([(0,0,0),(0,2,0)],0,0,.25,10))
        self.assertEqual(poses[0][0],(0,0,0))
        self.assertAlmostEqual(g.yaw_degrees(poses[-1]),90)
        # A cart corner 2m to Worker's right sweeps past the x=1.5 boundary.
        points=[g.footprint_world(p,((2,0,0),))[0] for p in poses]
        self.assertTrue(any(p[0]>1.5 for p in points))
        self.assertTrue(any(abs(p[1]-2)<.01 for p in points))

    def test_sampling_covers_interior_and_rejects_invalid_step(self):
        from scripts import warehouse_roaming_geometry as g
        points=g.footprint_grid((-1,-1),(1,1),1)
        self.assertIn((0.,0.,0.),points)
        with self.assertRaises(ValueError):
            g.footprint_grid((-1,-1),(1,1),0)


class CargoUSDTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd
        except ImportError:
            raise unittest.SkipTest('Bundled OpenUSD required')

    def test_cargo_restore_keeps_loaded_transfer_until_stack_restore(self):
        from pxr import Usd,UsdGeom,Gf
        from scripts.warehouse_box_only_stack import BoxSequence
        from scripts.warehouse_roaming_cargo import CargoFollower
        stage=Usd.Stage.CreateInMemory()
        UsdGeom.Xform.Define(stage,'/Cart')
        box=UsdGeom.Cube.Define(stage,'/Box')
        box.CreateSizeAttr(.5)
        box.AddTranslateOp().Set(Gf.Vec3d(0,0,1))
        original=stage.GetRootLayer().ExportToString()
        stack=BoxSequence(stage,['/Box'],[(2,0,1)],1,.03)
        stack.update(0)
        stack.update(1)
        transfer_layer=stack.transfers[0].layer.identifier
        cargo=CargoFollower(stage,'/Cart',['/Box'])
        cargo.attach()
        cargo.restore()
        self.assertIn(transfer_layer,stage.GetSessionLayer().subLayerPaths)
        position=UsdGeom.Xformable(box).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation()
        self.assertAlmostEqual(position[0],2)
        stack.restore()
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths),[])
        self.assertEqual(stage.GetRootLayer().ExportToString(),original)

    def test_box_tracks_cart_rotation_then_owned_layer_restores(self):
        from pxr import Usd,UsdGeom,Gf
        from scripts import warehouse_roaming_cargo as c
        stage=Usd.Stage.CreateInMemory()
        cart=UsdGeom.Xform.Define(stage,'/Cart')
        op=cart.AddTransformOp()
        op.Set(Gf.Matrix4d(1))
        box=UsdGeom.Cube.Define(stage,'/Box')
        box.AddTranslateOp().Set(Gf.Vec3d(1,0,1))
        before=stage.GetRootLayer().ExportToString()
        cargo=c.CargoFollower(stage,'/Cart',('/Box',))
        cargo.attach()
        # Simulate runtime Cart motion in a separate external layer.
        from pxr import Sdf
        layer=Sdf.Layer.CreateAnonymous()
        stage.GetSessionLayer().subLayerPaths.append(layer.identifier)
        with Usd.EditContext(stage,layer):
            matrix=Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),90))
            matrix.SetTranslateOnly(Gf.Vec3d(3,2,0))
            op.Set(matrix)
        cargo.update()
        position=UsdGeom.Xformable(box).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation()
        for actual,expected in zip(position,(3,3,1)):
            self.assertAlmostEqual(actual,expected)
        cargo.restore()
        self.assertIn(layer.identifier,stage.GetSessionLayer().subLayerPaths)
        self.assertEqual(stage.GetRootLayer().ExportToString(),before)
