"""Manual bootstrap: existing shelf navigation, parked visual stack gesture."""
import builtins
import math
from pathlib import Path


def stack_configuration(base):
    """Copy the stack-only selection; keep four-box baseline launchers unchanged."""
    from types import SimpleNamespace
    config=SimpleNamespace(**{k:v for k,v in vars(base).items() if k.isupper()})
    selected=tuple(base.STACK_BOX_PATHS)
    if not selected or len(set(selected))!=len(selected) or any(p not in base.BOX_PATHS for p in selected):
        raise ValueError('Invalid stack box selection')
    config.OBSTACLE_BOX_PATHS=tuple(base.BOX_PATHS)
    config.BOX_PATHS=selected
    config.ARM_RAISE_SECONDS=base.STACK_ARM_RAISE_SECONDS
    config.ARM_LOWER_SECONDS=base.STACK_ARM_LOWER_SECONDS
    return config


async def start():
    import carb.settings
    import omni.usd
    import omni.anim.navigation.core as nav
    from scripts import setup_warehouse_runtime as runtime
    from scripts import warehouse_shelf_goal_config as shelf
    from scripts import warehouse_multi_box_config as base_config
    from scripts.setup_warehouse_shelf_goal import _world_pose
    from scripts.configure_warehouse_worker_behavior import configure_worker_behavior,build_destination_commands
    from scripts.warehouse_worker_reach_gesture import BoxSynchronizedReach
    from scripts.warehouse_stack_gesture import StackGestureRuntime
    from scripts.warehouse_box_only_stack import bounds
    config=stack_configuration(base_config)
    runtime._precheck_live()
    stage=omni.usd.get_context().get_stage()
    for path in config.BOX_PATHS:
        bounds(stage,path)
    worker=_world_pose(stage,runtime.WORKER_SKELROOT_PATH)
    cart=_world_pose(stage,runtime.CART_PATH)
    if not .1<=math.dist(worker[0],cart[0])<=shelf.MAX_WORKER_CART_DISTANCE_M:
        raise RuntimeError('Restore Worker/Cart pushing arrangement')
    goal=shelf.worker_goal_for_cart(worker[0],cart[0],shelf.CART_GOAL_WORLD)
    yaw=math.degrees(2*math.atan2(worker[1][2],worker[1][3]))
    gesture = None
    if config.STACK_GESTURES_ENABLED:
        gesture = BoxSynchronizedReach(
            stage,
            runtime.WORKER_SKELROOT_PATH,
            reach=config.ARM_RAISE_SECONDS,
            hold=config.BOX_ONLY_SECONDS,
            lower=config.ARM_LOWER_SECONDS,
            distance=shelf.WORKER_REACH_DISTANCE_M,
        )

        # 생성이 끝난 다음 설정해야 합니다.
        gesture.hand_height_offset = config.STACK_HAND_HEIGHT_OFFSET_M

        gesture.configure_height_feedback(
            shelf.WORKER_HAND_HEIGHT_FEEDBACK,
            shelf.WORKER_HAND_HEIGHT_MAX_CORRECTION_M,
            shelf.WORKER_HAND_HEIGHT_RESPONSE_SECONDS,
        )

    command_file=Path(__file__).resolve().parent.parent/'artifacts/warehouse_stack_gesture_commands.txt'
    result={}
    async def mesh_setup():
        if nav.acquire_interface().get_navmesh() is None:
            raise RuntimeError('Bake NavMesh manually first')
        return {'reused':True},runtime.BorrowedNavMeshHandle()
    def snapshot():
        return runtime.WorkerRuntimeSnapshot.capture(settings=carb.settings.get_settings(),
            setting_paths=runtime.PEOPLE_SETTING_PATHS,command_file=command_file)
    async def worker_setup():
        result.update(await configure_worker_behavior(runtime.WORKER_PATH,command_file,
            destination=goal,final_yaw=yaw,wait_seconds=0,initial_wait=0))
        from scripts.warehouse_worker_behavior_rebind import verify_worker_behavior
        result.update(await verify_worker_behavior(runtime.WORKER_SKELROOT_PATH))
        return result
    def controller_setup():
        sync=runtime._setup_cart_live()
        try:
            if gesture is not None:
                gesture.install()
            expected=build_destination_commands('Worker_01',result['goal'],yaw,0,initial_wait=0)[0]
            return StackGestureRuntime(sync,expected,result['goal'],shelf.CART_GOAL_WORLD,
                tuple(bounds(stage,config.BOX_PATHS[0]).GetMidpoint()),config.STACK_FACE_SECONDS,
                shelf.WORKER_FORWARD_YAW_DEG,shelf.ARRIVAL_TOLERANCE_M,
                gesture=gesture,stage=stage,config=config)
        except BaseException:
            if gesture is not None:
                gesture.shutdown()
            sync.shutdown()
            raise
    session=await runtime.RuntimeBootstrap(precheck=runtime._precheck_live,
        setup_navmesh=mesh_setup,capture_worker_state=snapshot,
        setup_worker=worker_setup,setup_cart=controller_setup).start()
    setattr(builtins,runtime._RUNTIME_SESSION_NAME,session)
    print('[Worker Stack] READY: manual Play; parking then sequential boxes; gestures=',
          config.STACK_GESTURES_ENABLED,'; boxes=',len(config.BOX_PATHS),'; USD not saved')
    from scripts import warehouse_roaming_config
    print('[Loaded Roaming] AFTER_STACK_ENABLED=',warehouse_roaming_config.ENABLED)
    return session
