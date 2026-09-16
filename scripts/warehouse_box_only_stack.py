"""Independent visual stack preview; reuses shelf BoxTransfer session restoration.

Not a physical grasp, stable-load proof, or full warehouse collision planner.
"""
import math
from scripts.warehouse_box_transfer import BoxTransfer


def stack_centers(xy,top,sizes,gap):
    if (len(xy)!=2 or not all(math.isfinite(v) for v in (*xy,top,gap)) or gap<0
            or not sizes or any(len(s)!=3 or not all(math.isfinite(v) and v>0 for v in s) for s in sizes)):
        raise ValueError('Invalid stack dimensions')
    result=[]
    for size in sizes:
        result.append((*xy,top+gap+size[2]/2))
        top+=gap+size[2]
    return result


def bounds(stage,path):
    from pxr import Usd,UsdGeom
    prim=stage.GetPrimAtPath(path)
    if not prim:
        raise RuntimeError('Missing prim: '+path)
    result=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy']).ComputeWorldBound(prim).ComputeAlignedRange()
    if result.IsEmpty():
        raise RuntimeError('Unloaded geometry: '+path)
    return result


class VisualTransfer(BoxTransfer):
    def __init__(self,stage,path,destination,height,duration):
        self.destination,self.travel_height=tuple(destination),height
        super().__init__(stage,path,path,path,delay=0,duration=duration,
            edge_margin=0,gap=0,pull_margin=0,lift_clearance=0,max_pull=1)

    def _geometry(self):
        r=bounds(self.stage,self.box_path)
        return tuple(r.GetMidpoint()),self.destination,tuple(r.GetMin()),tuple(r.GetMax()),tuple(r.GetSize())

    def path_builder(self,source,destination,*args,**kwargs):
        return [source,(*source[:2],self.travel_height),
                (*destination[:2],self.travel_height),destination]


class BoxSequence:
    def __init__(self,stage,paths,destinations,duration,clearance):
        if len(paths)!=len(destinations) or len(set(paths))!=len(paths) or not paths:
            raise ValueError('Invalid box sequence')
        if not math.isfinite(clearance) or clearance<0:
            raise ValueError('Invalid clearance')
        geometry=[bounds(stage,p) for p in paths]
        # Lift above all source/target boxes before traversing horizontally.
        top=max(max(r.GetMax()[2] for r in geometry),
                max(d[2]+r.GetSize()[2]/2 for r,d in zip(geometry,destinations)))
        self.transfers=[VisualTransfer(stage,p,d,top+r.GetSize()[2]/2+clearance,duration)
                        for p,d,r in zip(paths,destinations,geometry)]
        self.index=0

    def update(self,now):
        if self.index>=len(self.transfers):
            return
        current=self.transfers[self.index]
        if current.state=='ready':
            current.start(now,(0,0,0))
            print('[Box-only] MOVING',self.index+1,'of',len(self.transfers),current.box_path)
        current.update(now)
        if current.state=='loaded':
            self.index+=1
            print('[Box-only] LOADED',self.index,'of',len(self.transfers))
            if self.index<len(self.transfers):
                self.transfers[self.index].start(now,(0,0,0))
            else:
                print('[Box-only] COMPLETE: Stop restores all boxes')

    def restore(self):
        errors=[]
        for transfer in self.transfers:
            try:
                transfer.restore()
            except Exception as error:
                errors.append(str(error))
        self.index=0
        if errors:
            raise RuntimeError('; '.join(errors))


def prepare(stage,config):
    from pxr import UsdGeom
    from scripts.warehouse_multi_box_inspection import collect_lid_meshes
    from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report,plan_on_lids
    if abs(UsdGeom.GetStageMetersPerUnit(stage)-1)>1e-6 or UsdGeom.GetStageUpAxis(stage)!='Z':
        raise RuntimeError('Meter-scale Z-up stage required')
    sizes=[tuple(bounds(stage,p).GetSize()) for p in config.BOX_PATHS]
    lids=lid_surfaces_from_mesh_report(collect_lid_meshes(stage,config.PALLET_PATH),
                                     verified_ids=config.COMPOSITE_VERIFIED_LID_PATHS)
    # Whole stack footprint must stay above the selected existing lids.
    footprint=tuple(max(s[k] for s in sizes) for k in range(3))
    placement=plan_on_lids('box_only_stack',footprint,lids,[],
        max_gap=config.COMPOSITE_MAX_GAP_M,max_height_delta=config.COMPOSITE_MAX_HEIGHT_DELTA_M,
        min_coverage=config.COMPOSITE_MIN_COVERAGE,edge_margin=config.EDGE_MARGIN_M,
        placement_gap=config.PLACEMENT_GAP_M,max_top=1e6)
    if placement is None:
        raise RuntimeError('No verified lid footprint fits the stack; no motion configured')
    xy=tuple((placement.bounds.lower[k]+placement.bounds.upper[k])/2 for k in (0,1))
    centers=stack_centers(xy,placement.bounds.lower[2]-config.PLACEMENT_GAP_M,sizes,config.PLACEMENT_GAP_M)
    sequence=BoxSequence(stage,config.BOX_PATHS,centers,config.BOX_ONLY_SECONDS,config.LIFT_CLEARANCE_M)
    for transfer in sequence.transfers:
        transfer.pallet_path=config.PALLET_PATH  # Destination label; geometry is overridden.
    print('[Box-only] PLAN:',list(zip(config.BOX_PATHS,centers)))
    return sequence


class Preview:
    def __init__(self,stage,sequence,config):
        import omni.timeline
        import omni.kit.app
        from pxr import Sdf,Usd,UsdPhysics,Gf
        self.stage,self.sequence=stage,sequence
        self.active=True
        self.update_sub=self.stop_sub=None
        self.timeline=omni.timeline.get_timeline_interface()
        self.layer=Sdf.Layer.CreateAnonymous('box_only_freeze.usda')
        stage.GetSessionLayer().subLayerPaths=[self.layer.identifier,*stage.GetSessionLayer().subLayerPaths]
        try:
            with Usd.EditContext(stage,self.layer):
                # Suppress authored People commands during this isolated test.
                worker=stage.GetPrimAtPath('/World/Characters/Worker_01')
                if worker:
                    for prim in Usd.PrimRange(worker):
                        attr=prim.GetAttribute('omni:scripting:scripts')
                        if attr:
                            attr.Set([])
                cart=stage.GetPrimAtPath(config.CART_PATH)
                if not cart:
                    raise RuntimeError('Cart missing')
                for prim in Usd.PrimRange(cart):
                    if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                        body=UsdPhysics.RigidBodyAPI(prim)
                        body.CreateKinematicEnabledAttr(True)
                        body.CreateVelocityAttr(Gf.Vec3f(0))
                        body.CreateAngularVelocityAttr(Gf.Vec3f(0))
            self.update_sub=omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(self.update,name='BoxOnlyStack')
            self.stop_sub=self.timeline.get_timeline_event_stream().create_subscription_to_pop(self.on_timeline,name='BoxOnlyStop')
        except BaseException:
            self.shutdown()
            raise

    def update(self,event):
        import omni.usd
        if not self.active:
            return
        if omni.usd.get_context().get_stage()!=self.stage:
            self.shutdown()
            return
        if self.timeline.is_playing():
            try:
                self.sequence.update(self.timeline.get_current_time())
            except Exception as error:
                self.timeline.pause()
                print('[Box-only] FAILED:',error,'; press Stop to restore')

    def on_timeline(self,event):
        import omni.timeline
        if event.type==int(omni.timeline.TimelineEventType.STOP):
            self.shutdown()

    def shutdown(self):
        self.active=False
        self.update_sub=self.stop_sub=None
        try:
            self.sequence.restore()
        finally:
            session=self.stage.GetSessionLayer()
            session.subLayerPaths=[p for p in session.subLayerPaths if p!=self.layer.identifier]
        print('[Box-only] RESTORED; Run again to prepare another test')


def run():
    import builtins
    import omni.usd
    import omni.timeline
    from scripts import setup_warehouse_runtime as runtime
    from scripts import warehouse_multi_box_config as config
    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError('Press Stop first')
    task=getattr(builtins,runtime._RUNTIME_TASK_NAME,None)
    if task is not None and not task.done():
        raise RuntimeError('Previous setup is still running')
    for key in (runtime._RUNTIME_SESSION_NAME,'_warehouse_multi_box_source_session','_warehouse_box_only_preview'):
        previous=getattr(builtins,key,None)
        if previous is not None and previous.active:
            previous.shutdown()
    stage=omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError('Open warehouse USD first')
    sequence=prepare(stage,config)
    preview=Preview(stage,sequence,config)
    setattr(builtins,'_warehouse_box_only_preview',preview)
    print('[Box-only] READY: 4-tier visual stack; manual Play; USD not saved')
    return preview
