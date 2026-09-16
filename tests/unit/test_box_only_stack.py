import unittest


class StackMathTest(unittest.TestCase):
    def test_four_centers_use_previous_top_not_same_destination(self):
        from scripts.warehouse_box_only_stack import stack_centers
        result=stack_centers((2,3),1,[(.5,.5,.25)]*4,.01)
        self.assertEqual(len(result),4)
        for p,z in zip(result,[1.135,1.395,1.655,1.915]):
            self.assertEqual(p[:2],(2,3))
            self.assertAlmostEqual(p[2],z)

    def test_invalid_size_rejected(self):
        from scripts.warehouse_box_only_stack import stack_centers
        with self.assertRaises(ValueError):
            stack_centers((0,0),1,[(.5,.5,-1)],.01)


class StackUSDTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from pxr import Usd
        except ImportError:
            raise unittest.SkipTest('Bundled OpenUSD required')

    def test_sequential_motion_and_full_restore_preserve_root(self):
        from pxr import Usd,UsdGeom,Gf
        from scripts.warehouse_box_only_stack import BoxSequence
        stage=Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(stage,1)
        UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
        paths=[]
        for i in range(4):
            path='/Box%d'%i
            cube=UsdGeom.Cube.Define(stage,path)
            cube.CreateSizeAttr(.5)
            cube.AddTranslateOp().Set(Gf.Vec3d(i,0,.25))
            paths.append(path)
        root=stage.GetRootLayer().ExportToString()
        sequence=BoxSequence(stage,paths,[(0,4,1.25+i*.51) for i in range(4)],3,.03)
        sequence.update(0)
        sequence.update(1.5)
        cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default'])
        self.assertGreater(cache.ComputeWorldBound(stage.GetPrimAtPath(paths[0])).ComputeAlignedRange().GetMidpoint()[2],.25)
        self.assertEqual(tuple(cache.ComputeWorldBound(stage.GetPrimAtPath(paths[1])).ComputeAlignedRange().GetMidpoint()),(1.,0.,.25))
        for t in [3,6,9,12]:
            sequence.update(t)
        self.assertEqual(sequence.index,4)
        sequence.restore()
        self.assertEqual(stage.GetRootLayer().ExportToString(),root)
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths),[])

    def test_preview_suppresses_worker_commands_and_restores_cart_physics(self):
        from pxr import Usd,UsdGeom,UsdPhysics,Sdf
        from types import SimpleNamespace as NS
        from unittest.mock import patch
        from scripts.warehouse_box_only_stack import Preview,BoxSequence
        stage=Usd.Stage.CreateInMemory()
        worker=UsdGeom.Xform.Define(stage,'/World/Characters/Worker_01').GetPrim()
        worker.CreateAttribute('omni:scripting:scripts',Sdf.ValueTypeNames.AssetArray).Set([Sdf.AssetPath('/original.py')])
        cart=UsdGeom.Xform.Define(stage,'/Cart').GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(cart).CreateKinematicEnabledAttr(False)
        UsdGeom.Cube.Define(stage,'/Box').CreateSizeAttr(.5)
        root=stage.GetRootLayer().ExportToString()
        stream=NS(create_subscription_to_pop=lambda *a,**k:object())
        timeline=NS(get_timeline_event_stream=lambda:stream)
        timeline_module=NS(get_timeline_interface=lambda:timeline)
        app_module=NS(get_app=lambda:NS(get_update_event_stream=lambda:stream))
        omni=NS(timeline=timeline_module,kit=NS(app=app_module))
        with patch.dict('sys.modules',{'omni':omni,'omni.timeline':timeline_module,
                                      'omni.kit':omni.kit,'omni.kit.app':app_module}):
            sequence=BoxSequence(stage,['/Box'],[(0,4,1)],3,.03)
            preview=Preview(stage,sequence,NS(CART_PATH='/Cart'))
            self.assertEqual(list(worker.GetAttribute('omni:scripting:scripts').Get()),[])
            self.assertTrue(UsdPhysics.RigidBodyAPI(cart).GetKinematicEnabledAttr().Get())
            sequence.update(0)
            sequence.update(1)
            preview.shutdown()
        self.assertEqual(worker.GetAttribute('omni:scripting:scripts').Get()[0].path,'/original.py')
        self.assertFalse(UsdPhysics.RigidBodyAPI(cart).GetKinematicEnabledAttr().Get())
        self.assertEqual(stage.GetRootLayer().ExportToString(),root)
        self.assertEqual(list(stage.GetSessionLayer().subLayerPaths),[])
