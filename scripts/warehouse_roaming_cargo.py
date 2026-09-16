"""Reversible Cart-relative load following, in an owned anonymous USD layer."""

class CargoFollower:
    OP='xformOp:transform:warehouseRoamingCargo'

    def __init__(self,stage,cart_path,box_paths):
        if not box_paths or len(set(box_paths))!=len(box_paths):
            raise ValueError('Expected unique loaded boxes')
        self.stage,self.cart_path,self.box_paths=stage,cart_path,tuple(box_paths)
        self.layer=None
        self.relative={}

    def matrix(self,path):
        from pxr import Usd,UsdGeom
        prim=self.stage.GetPrimAtPath(path)
        if not prim:
            raise RuntimeError('Missing cargo/cart prim: '+path)
        return UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())

    def attach(self):
        from pxr import Sdf,Usd,Vt
        if self.layer is not None:
            raise RuntimeError('Cargo already attached')
        inverse=self.matrix(self.cart_path).GetInverse()
        self.relative={p:self.matrix(p)*inverse for p in self.box_paths}
        self.layer=Sdf.Layer.CreateAnonymous('warehouse_roaming_cargo.usda')
        session=self.stage.GetSessionLayer()
        session.subLayerPaths=[self.layer.identifier,*session.subLayerPaths]
        try:
            with Usd.EditContext(self.stage,self.layer):
                for path in self.box_paths:
                    prim=self.stage.GetPrimAtPath(path)
                    prim.CreateAttribute('xformOpOrder',Sdf.ValueTypeNames.TokenArray).Set(
                        Vt.TokenArray(['!resetXformStack!',self.OP]))
                    prim.CreateAttribute(self.OP,Sdf.ValueTypeNames.Matrix4d)
            self.update()
        except BaseException:
            self.restore()
            raise

    def update(self):
        from pxr import Usd
        if self.layer is None:
            return
        cart=self.matrix(self.cart_path)
        with Usd.EditContext(self.stage,self.layer):
            for path,relative in self.relative.items():
                if not self.stage.GetPrimAtPath(path).GetAttribute(self.OP).Set(relative*cart):
                    raise RuntimeError('Cargo follow write failed: '+path)

    def restore(self):
        if self.layer is not None:
            session=self.stage.GetSessionLayer()
            session.subLayerPaths=[p for p in session.subLayerPaths if p!=self.layer.identifier]
            self.layer=None
        self.relative={}
