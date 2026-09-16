"""Retry missing Behavior instantiation without changing saved USD or security policy."""


async def ensure_instance(read_instance,set_paths,next_update,paths,max_frames=120):
    instance=read_instance()
    if instance is not None:
        return instance
    if not paths or max_frames<1:
        raise ValueError('Missing behavior paths or invalid wait bound')
    try:
        set_paths([])
        # ScriptManager processes USD notices asynchronously; do not coalesce edits.
        for _ in range(3):
            await next_update()
        set_paths(paths)
        for _ in range(max_frames):
            await next_update()
            instance=read_instance()
            if instance is not None:
                return instance
        raise RuntimeError('Behavior instance was not created; inspect ScriptManager import/on_init errors and script permission dialog')
    finally:
        set_paths(paths)


async def verify_worker_behavior(path):
    import omni.usd
    import omni.timeline
    import omni.kit.app
    from pxr import Usd,Sdf
    from omni.kit.scripting.scripts.script_manager import ScriptManager
    from isaacsim.replicator.metropolis.utils.simulation_util import SimulationUtil
    timeline=omni.timeline.get_timeline_interface()
    stage=omni.usd.get_context().get_stage()
    if not timeline.is_stopped() or stage is None:
        raise RuntimeError('Behavior rebind requires an open stage and Stop')
    manager=ScriptManager.get_instance()
    if manager is None:
        raise RuntimeError('ScriptManager unavailable; enable omni.kit.scripting')
    future=getattr(manager,'_future',None)
    if future is not None and not future.done():
        raise RuntimeError('Script execution permission dialog is pending; review it manually, then Run again')
    if future is not None and future.done() and (future.cancelled() or future.result() is False):
        raise RuntimeError('Script execution was not approved; review Isaac Sim script permissions manually')
    prim=stage.GetPrimAtPath(path)
    if not prim:
        raise RuntimeError('Worker SkelRoot missing: '+path)
    attr=prim.GetAttribute('omni:scripting:scripts')
    paths=list(attr.Get() or []) if attr else []
    if not paths:
        raise RuntimeError('Worker Behavior path is empty')
    def read_instance():
        inst=SimulationUtil.get_agent_script_instance_by_path(path)
        if inst is not None and type(inst).__name__!='CharacterBehavior':
            raise RuntimeError('Unexpected Behavior class on Worker: '+type(inst).__name__)
        return inst
    existing=read_instance()
    if existing is not None:
        print('[Worker Behavior] INSTANCE_VERIFIED: existing',path)
        return {'instance_verified':True,'rebound':False}
    layer=Sdf.Layer.CreateAnonymous('worker_behavior_rebind.usda')
    session=stage.GetSessionLayer()
    session.subLayerPaths=[layer.identifier,*session.subLayerPaths]
    def set_paths(values):
        with Usd.EditContext(stage,layer):
            if not attr.Set(values):
                raise RuntimeError('Cannot set temporary Behavior paths')
        if list(attr.Get() or [])!=list(values):
            raise RuntimeError('Stronger Behavior override prevents rebind')
    async def next_update():
        await omni.kit.app.get_app().next_update_async()
        if not timeline.is_stopped() or omni.usd.get_context().get_stage()!=stage:
            raise RuntimeError('Keep the same stage stopped until INSTANCE_VERIFIED')
    try:
        print('[Worker Behavior] REBIND: missing instance; Worker-only detach/attach')
        await ensure_instance(read_instance,set_paths,next_update,paths)
    finally:
        session.subLayerPaths=[p for p in session.subLayerPaths if p!=layer.identifier]
    await next_update()
    if read_instance() is None:
        raise RuntimeError('Behavior instance disappeared after rebind layer cleanup')
    print('[Worker Behavior] INSTANCE_VERIFIED: rebound',path)
    return {'instance_verified':True,'rebound':True}
