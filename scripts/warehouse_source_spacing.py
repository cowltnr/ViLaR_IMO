"""User-approved temporary source-stack separation; never saves USD."""
import math


def separation_offset(fixed,moving,distance):
    dx,dy=moving[0]-fixed[0],moving[1]-fixed[1]
    length=math.hypot(dx,dy)
    if not all(math.isfinite(v) for v in (*fixed,*moving,distance)) or length<1e-6 or not 0<distance<=.1:
        raise ValueError('Invalid source separation')
    return (dx/length*distance,dy/length*distance,0.)


class SourceSpacing:
    def __init__(self,stage):
        self.stage,self.layer=stage,None
        self.verified=False

    def apply(self,config):
        from pxr import Usd,UsdGeom,Sdf,Gf,Vt,UsdPhysics
        from scripts.warehouse_oriented_clearance import from_stage,collisions,axes,dot
        fixed=from_stage(self.stage,config.BOX_PATHS[2])
        moving=from_stage(self.stage,config.BOX_PATHS[3])
        delta=separation_offset(fixed.center,moving.center,config.SOURCE_SEPARATION_M)
        prepared=[]
        for path in (config.BOX_PATHS[3],config.BOX_PATHS[1]):
            prim=self.stage.GetPrimAtPath(path)
            if not prim or prim.IsInstance() or prim.IsInstanceProxy():
                raise RuntimeError('Unsupported source prim: '+path)
            cursor=prim
            while cursor and not cursor.IsPseudoRoot():
                if cursor.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(cursor).GetRigidBodyEnabledAttr().Get() is not False:
                    raise RuntimeError('Active source physics: '+str(cursor.GetPath()))
                cursor=cursor.GetParent()
            xf=UsdGeom.Xformable(prim)
            if xf.TransformMightBeTimeVarying():
                raise RuntimeError('Animated source prim: '+path)
            matrix=Gf.Matrix4d(xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
            origin=matrix.ExtractTranslation()
            matrix.SetTranslateOnly(Gf.Vec3d(*(origin[k]+delta[k] for k in range(3))))
            prepared.append((prim,matrix))
        layer=Sdf.Layer.CreateAnonymous('warehouse_source_spacing.usda')
        self.layer=layer
        session=self.stage.GetSessionLayer()
        session.subLayerPaths=[*session.subLayerPaths,layer.identifier]
        try:
            with Usd.EditContext(self.stage,layer):
                for prim,matrix in prepared:
                    op='xformOp:transform:warehouseSourceSpacing'
                    prim.CreateAttribute('xformOpOrder',Sdf.ValueTypeNames.TokenArray).Set(Vt.TokenArray(['!resetXformStack!',op]))
                    prim.CreateAttribute(op,Sdf.ValueTypeNames.Matrix4d).Set(matrix)
            shifted=from_stage(self.stage,config.BOX_PATHS[3])
            if collisions([shifted.center,shifted.center],shifted,[fixed]):
                raise RuntimeError('Source stacks still overlap after temporary spacing')
            pallet=from_stage(self.stage,config.SOURCE_PALLET_PATH)
            for k,axis in enumerate(axes(pallet)[:2]):
                offset=abs(dot(tuple(shifted.center[i]-pallet.center[i] for i in range(3)),axis))
                radius=sum(h*abs(dot(a,axis)) for h,a in zip(shifted.half,axes(shifted)))
                if offset+radius>pallet.half[k]+1e-5:
                    raise RuntimeError('Temporary spacing would leave the source pallet')
            self.verified=True
            print('[Multi-box] SOURCE_SPACING:',delta,'temporary; Stop restores both boxes')
        except BaseException:
            self.restore()
            raise

    def restore(self):
        self.verified=False
        if self.layer is not None:
            session=self.stage.GetSessionLayer()
            session.subLayerPaths=[p for p in session.subLayerPaths if p!=self.layer.identifier]
            self.layer=None
