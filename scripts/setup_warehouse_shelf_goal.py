#!/usr/bin/env python3
"""Manual Script Editor entry: existing NavMesh -> shelf goal -> wait. No Play/save."""

import asyncio
import builtins
import json
import math
from pathlib import Path

from scripts import setup_warehouse_runtime as runtime
from scripts import warehouse_shelf_goal_config as config
from scripts.configure_warehouse_worker_behavior import configure_worker_behavior

COMMAND_FILE = Path(__file__).resolve().parent.parent / "artifacts" / "warehouse_shelf_commands.txt"


def _world_pose(stage, path):
    from pxr import Usd, UsdGeom
    from scripts.warehouse_worker_cart_pose_sync import IsaacSimPoseSynchronizer

    matrix = UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    # The existing Cart synchronizer supports rigid transforms, not scaled parents.
    rows = [tuple(float(matrix[i][j]) for j in range(3)) for i in range(3)]
    if any(abs(sum(x*x for x in row) - 1) > 1e-4 for row in rows):
        raise RuntimeError(f"Non-unit World scale is unsupported: {path}")
    if any(abs(sum(rows[i][k]*rows[j][k] for k in range(3))) > 1e-4
           for i in range(3) for j in range(i)) or matrix.GetDeterminant() < 0:
        raise RuntimeError(f"Sheared or reflected World transform is unsupported: {path}")
    pose = IsaacSimPoseSynchronizer._matrix_to_pose(matrix)
    if abs(pose[1][0]) > 1e-4 or abs(pose[1][1]) > 1e-4:
        raise RuntimeError(f"Only upright planar actors are supported: {path}")
    return pose


async def start():
    import carb.settings
    import omni.usd
    import omni.anim.navigation.core as nav
    from pxr import UsdGeom

    runtime._precheck_live()
    previous = getattr(builtins, runtime._RUNTIME_SESSION_NAME, None)
    if previous is not None and previous.active:
        raise RuntimeError("Existing runtime active. Stop, then call shutdown_warehouse_runtime() before switching modes.")
    stage = omni.usd.get_context().get_stage()
    if UsdGeom.GetStageUpAxis(stage) != "Z" or abs(UsdGeom.GetStageMetersPerUnit(stage) - 1) > 1e-6:
        raise RuntimeError("Shelf goal requires a meter-scale Z-up Stage")
    worker_pose = _world_pose(stage, runtime.WORKER_SKELROOT_PATH)
    cart_pose = _world_pose(stage, runtime.CART_PATH)
    _world_pose(stage, str(stage.GetPrimAtPath(runtime.CART_PATH).GetParent().GetPath()))
    separation = math.dist(worker_pose[0], cart_pose[0])
    if not 0.1 <= separation <= config.MAX_WORKER_CART_DISTANCE_M:
        raise RuntimeError(f"Worker/Cart separation {separation:.3f} m invalid; restore their pushing arrangement first")
    worker_goal = config.worker_goal_for_cart(worker_pose[0], cart_pose[0], config.CART_GOAL_WORLD)
    yaw = math.degrees(2 * math.atan2(worker_pose[1][2], worker_pose[1][3]))
    from scripts.warehouse_worker_face_box import box_center, FaceBoxRuntime, target_yaw
    target = box_center(stage, config.BOX_TARGET_PATH) if config.FACE_BOX_ENABLED else None
    if target is not None:
        target_yaw(worker_goal, target, config.WORKER_FORWARD_YAW_DEG)
    transfer = None
    approach = None
    gesture = None
    if config.WORKER_FORWARD_AFTER_TURN and config.WORKER_APPROACH_ENABLED:
        raise RuntimeError('Select forward-after-turn OR legacy approach')
    if config.WORKER_REACH_ENABLED and config.WORKER_APPROACH_ENABLED:
        raise RuntimeError('Select approach OR in-place reach, not both')
    if target is not None and config.WORKER_REACH_ENABLED:
        from scripts.warehouse_worker_reach_gesture import ReachGesture, BoxSynchronizedReach
        if config.WORKER_REACH_MODE not in ("timed", "box_synced"):
            raise ValueError('Unknown WORKER_REACH_MODE')
        gesture_class = BoxSynchronizedReach if config.WORKER_REACH_MODE == "box_synced" else ReachGesture
        gesture = gesture_class(stage, runtime.WORKER_SKELROOT_PATH,
                               reach=config.WORKER_REACH_SECONDS,
                               hold=config.BOX_TRANSFER_DURATION_SECONDS,
                               lower=config.WORKER_REACH_LOWER_SECONDS,
                               distance=config.WORKER_REACH_DISTANCE_M)
    if target is not None and (config.WORKER_APPROACH_ENABLED or config.WORKER_FORWARD_AFTER_TURN):
        from scripts.warehouse_worker_approach import WorkerApproach
        approach = WorkerApproach(config.WORKER_APPROACH_DISTANCES_M, config.WORKER_APPROACH_ANGLES_DEG,
                                  config.MAX_SNAP_M, config.WORKER_APPROACH_MAX_DISTANCE_M,
                                  config.WORKER_APPROACH_TIMEOUT_SECONDS,
                                  after_turn=config.WORKER_FORWARD_AFTER_TURN,
                                  forward_step=config.WORKER_FORWARD_STEP_M)
    if target is not None and config.BOX_TRANSFER_ENABLED and (approach is None or approach.after_turn):
        from scripts.warehouse_box_transfer import BoxTransfer
        transfer = BoxTransfer(
            stage, config.BOX_TARGET_PATH, config.PALLET_TARGET_PATH, config.RACK_TARGET_PATH,
            delay=(config.WORKER_REACH_SECONDS if gesture is not None else config.BOX_TRANSFER_DELAY_SECONDS),
            duration=config.BOX_TRANSFER_DURATION_SECONDS,
            edge_margin=config.BOX_PALLET_EDGE_MARGIN_M, gap=config.BOX_PLACEMENT_GAP_M,
            pull_margin=config.BOX_PULL_MARGIN_M, lift_clearance=config.BOX_LIFT_CLEARANCE_M,
            max_pull=config.BOX_MAX_PULL_M,
            max_center_height_offset=(min(gesture.shoulders[side][2] + gesture.arm_lengths[side] * .9 * .95
                                          for side in gesture.shoulders)
                                      if gesture is not None and config.BOX_LIMIT_TO_ARM_REACH else None))
    if gesture is not None and config.WORKER_REACH_MODE == "box_synced":
        gesture.follow_transfer(transfer, config.WORKER_FORWARD_YAW_DEG, config.WORKER_BOX_TURN_RATE_DEG_S)
        gesture.configure_height_feedback(config.WORKER_HAND_HEIGHT_FEEDBACK,
                                           config.WORKER_HAND_HEIGHT_MAX_CORRECTION_M,
                                           config.WORKER_HAND_HEIGHT_RESPONSE_SECONDS)
    worker_result = {}

    async def reuse_navmesh():
        interface = nav.acquire_interface()
        mesh = interface.get_navmesh()
        count = (sum(len(mesh.get_draw_triangles(i)) // 3 for i in range(interface.get_area_count()))
                 if mesh is not None else 0)
        if count <= 0:
            raise RuntimeError("Existing NavMesh missing. Manually Bake with verified 5 cm Step Height first.")
        return {"status": "verified_existing", "triangle_count": count, "reused": True}, runtime.BorrowedNavMeshHandle()

    def snapshot():
        return runtime.WorkerRuntimeSnapshot.capture(
            settings=carb.settings.get_settings(), setting_paths=runtime.PEOPLE_SETTING_PATHS,
            command_file=COMMAND_FILE)

    async def worker_setup():
        result = await configure_worker_behavior(
            runtime.WORKER_PATH, COMMAND_FILE, destination=worker_goal,
            final_yaw=yaw, wait_seconds=config.WAIT_SECONDS, max_snap_m=config.MAX_SNAP_M)
        result.update(cart_start_world=cart_pose[0], cart_goal_world=config.CART_GOAL_WORLD,
                      worker_goal_requested=worker_goal, final_worker_yaw_deg=yaw,
                      cart_collision_checked=False)
        result.update(face_box_enabled=config.FACE_BOX_ENABLED, box_target_world=target)
        result.update(box_transfer_enabled=transfer is not None)
        result.update(box_target_path=config.BOX_TARGET_PATH, pallet_target_path=config.PALLET_TARGET_PATH)
        result.update(worker_approach_enabled=approach is not None)
        result.update(worker_forward_after_turn=config.WORKER_FORWARD_AFTER_TURN)
        result.update(worker_reach_enabled=gesture is not None, physical_grasp=False)
        result.update(worker_reach_mode=config.WORKER_REACH_MODE if gesture is not None else None)
        worker_result.update(result)
        return result

    def setup_cart():
        sync = runtime._setup_cart_live()
        if target is None:
            return sync
        try:
            if gesture is not None:
                gesture.install()
            from scripts.configure_warehouse_worker_behavior import build_destination_commands
            expected = build_destination_commands("Worker_01", worker_result["goal"],
                                                   yaw, config.WAIT_SECONDS)[1]
            return FaceBoxRuntime(sync, expected, worker_result["goal"], config.CART_GOAL_WORLD,
                                  target, config.TURN_DURATION_SECONDS,
                                  config.WORKER_FORWARD_YAW_DEG, config.ARRIVAL_TOLERANCE_M,
                                  transfer=transfer, approach=approach, gesture=gesture)
        except BaseException:
            if gesture is not None:
                gesture.shutdown()
            sync.shutdown()
            raise

    session = await runtime.RuntimeBootstrap(
        precheck=runtime._precheck_live, setup_navmesh=reuse_navmesh,
        capture_worker_state=snapshot, setup_worker=worker_setup,
        setup_cart=setup_cart).start()
    setattr(builtins, runtime._RUNTIME_SESSION_NAME, session)
    print("WAREHOUSE_SHELF_READY=" + json.dumps(session.result, sort_keys=True))
    print("[Shelf Goal] Review coordinates, then press Play manually. No USD save or Bake performed.")
    return session


def run():
    previous = getattr(builtins, runtime._RUNTIME_TASK_NAME, None)
    if previous is not None and not previous.done():
        raise RuntimeError("Another Warehouse setup is still running")
    task = asyncio.ensure_future(start())
    setattr(builtins, runtime._RUNTIME_TASK_NAME, task)
    task.add_done_callback(runtime._report_task_result)
    return task


if __name__ == "__main__":
    run()
