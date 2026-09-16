"""Setup a single owner for multi-box callbacks and stop restoration."""
import builtins
import math
from pathlib import Path


async def start():
    import carb.settings
    import omni.usd
    import omni.anim.navigation.core as nav
    from scripts import setup_warehouse_runtime as runtime
    from scripts import warehouse_shelf_goal_config as shelf
    from scripts import warehouse_multi_box_config as config
    from scripts.setup_warehouse_shelf_goal import _world_pose
    from scripts.configure_warehouse_worker_behavior import configure_worker_behavior, build_destination_commands
    from scripts.warehouse_worker_reach_gesture import BoxSynchronizedReach
    from scripts.warehouse_unloading_live import Unloading
    runtime._precheck_live()
    stage = omni.usd.get_context().get_stage()
    missing = [path for path in config.BOX_PATHS if path not in config.SOURCE_SUPPORT_PATHS]
    if missing:
        raise RuntimeError('Unresolved source support paths; no motion configured: ' + ', '.join(missing))
    for path in (*config.BOX_PATHS, *config.SOURCE_SUPPORT_PATHS.values()):
        if not stage.GetPrimAtPath(path):
            raise RuntimeError('Source prim missing; no motion configured: ' + path)
    for index, path in enumerate(config.BOX_PATHS):
        support = config.SOURCE_SUPPORT_PATHS[path]
        if support in config.BOX_PATHS[:index]:
            raise RuntimeError('Invalid unloading order: supporting box would move first')
    worker = _world_pose(stage,runtime.WORKER_SKELROOT_PATH)
    cart = _world_pose(stage,runtime.CART_PATH)
    if not .1 <= math.dist(worker[0],cart[0]) <= shelf.MAX_WORKER_CART_DISTANCE_M:
        raise RuntimeError('Restore Worker/Cart pushing arrangement')
    goal = shelf.worker_goal_for_cart(worker[0],cart[0],shelf.CART_GOAL_WORLD)
    yaw = math.degrees(2*math.atan2(worker[1][2],worker[1][3]))
    gesture = BoxSynchronizedReach(stage,runtime.WORKER_SKELROOT_PATH,
        reach=config.ARM_RAISE_SECONDS,hold=config.TRANSFER_SECONDS,
        lower=config.ARM_LOWER_SECONDS,distance=.4)
    gesture.configure_height_feedback(shelf.WORKER_HAND_HEIGHT_FEEDBACK,
        shelf.WORKER_HAND_HEIGHT_MAX_CORRECTION_M,shelf.WORKER_HAND_HEIGHT_RESPONSE_SECONDS)
    command_file = Path(__file__).resolve().parent.parent/'artifacts/warehouse_multi_box_commands.txt'
    result = {}
    async def mesh_setup():
        mesh = nav.acquire_interface().get_navmesh()
        if mesh is None:
            raise RuntimeError('Bake NavMesh manually first')
        return {'reused':True},runtime.BorrowedNavMeshHandle()
    def snapshot():
        return runtime.WorkerRuntimeSnapshot.capture(settings=carb.settings.get_settings(),
            setting_paths=runtime.PEOPLE_SETTING_PATHS,command_file=command_file)
    async def worker_setup():
        result.update(await configure_worker_behavior(runtime.WORKER_PATH,command_file,
            destination=goal,final_yaw=yaw,wait_seconds=0,initial_wait=0))
        return result
    def controller_setup():
        from scripts.warehouse_source_spacing import SourceSpacing
        spacing=SourceSpacing(stage)
        sync = runtime._setup_cart_live()
        try:
            if config.SOURCE_SEPARATION_ENABLED:
                spacing.apply(config)
                if not spacing.verified or spacing.layer is None:
                    raise RuntimeError('Source spacing was not verified; configuration refused')
            gesture.install()
            expected = build_destination_commands('Worker_01',result['goal'],yaw,0,initial_wait=0)[0]
            controller=Unloading(sync,stage,gesture,config,expected,result['goal'],shelf.CART_GOAL_WORLD)
            controller.spacing=spacing
            return controller
        except BaseException:
            spacing.restore()
            gesture.shutdown()
            sync.shutdown()
            raise
    session = await runtime.RuntimeBootstrap(precheck=runtime._precheck_live,
        setup_navmesh=mesh_setup,capture_worker_state=snapshot,
        setup_worker=worker_setup,setup_cart=controller_setup).start()
    setattr(builtins,runtime._RUNTIME_SESSION_NAME,session)
    print('[Multi-box] CONFIGURED_V4_WALK: source spacing enabled=',config.SOURCE_SEPARATION_ENABLED,
          '; manual Play; USD not saved.')
    return session
