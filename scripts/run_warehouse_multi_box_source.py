"""Configure the first multi-box source approach in Isaac Sim.

Open in Script Editor and Run while STOPPED. This is a staged adapter: it
configures Worker/Cart synchronization and the first source GoTo only. It does
not start Play, move a box, save USD, or Bake NavMesh.
"""

import asyncio
import builtins
import glob
import json
import math
from pathlib import Path
import sys
import importlib
import types

PROJECT = Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
# Isaac Sim Script Editor executes a temporary /tmp copy. Register the real
# project before importing any project-owned `scripts.*` module.
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
# Isaac Sim may already have a different package named `scripts` in sys.modules.
# Make the package search path explicitly include this repository before any
# project module is imported, while preserving an existing package object.
project_scripts = str(PROJECT / 'scripts')
cached_scripts = sys.modules.get('scripts')
if cached_scripts is None or not hasattr(cached_scripts, '__path__'):
    cached_scripts = types.ModuleType('scripts')
    cached_scripts.__path__ = [project_scripts]
    cached_scripts.__package__ = 'scripts'
    sys.modules['scripts'] = cached_scripts
elif project_scripts not in cached_scripts.__path__:
    cached_scripts.__path__.insert(0, project_scripts)
importlib.invalidate_caches()

from scripts import setup_warehouse_runtime as runtime
from scripts import warehouse_multi_box_config as config
from scripts.warehouse_multi_box_runtime import WarehouseMultiBoxRuntime

REPORT_PATTERN = str(PROJECT / 'artifacts/runs/warehouse_multi_box_inspection_*/scene_report.json')
COMMAND_FILE = PROJECT / 'artifacts' / 'warehouse_multi_box_commands.txt'
SESSION_NAME = '_warehouse_multi_box_source_session'
TASK_NAME = '_warehouse_multi_box_source_task'


def _latest_report():
    paths = sorted(glob.glob(REPORT_PATTERN))
    if not paths:
        raise RuntimeError('No warehouse multi-box inspection report found. Run the inspector first.')
    with open(paths[-1], encoding='utf-8') as stream:
        report = json.load(stream)
    return Path(paths[-1]), report


def _box_center(stage, path):
    from pxr import Usd, UsdGeom
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        raise RuntimeError('Box prim not found: ' + path)
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render,
                               UsdGeom.Tokens.proxy])
    bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
    low, high = tuple(bounds.GetMin()), tuple(bounds.GetMax())
    return tuple((low[i] + high[i]) / 2 for i in range(3))


def _worker_yaw(stage):
    from pxr import Usd, UsdGeom
    from scripts.warehouse_worker_cart_pose_sync import IsaacSimPoseSynchronizer
    prim = stage.GetPrimAtPath(runtime.WORKER_SKELROOT_PATH)
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    pose = IsaacSimPoseSynchronizer._matrix_to_pose(matrix)
    return math.degrees(2 * math.atan2(pose[1][2], pose[1][3]))


async def start():
    import carb.settings
    import omni.anim.navigation.core as nav
    import omni.timeline
    import omni.usd
    from pxr import UsdGeom

    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError('Press Stop before configuring the multi-box source approach.')
    runtime._precheck_live()
    raise RuntimeError(
        'Source-only launcher retired: this file does not unload four boxes. '
        'Its source probe is a Worker-only point, not a validated Cart parking pose. '
        'Use run_shelf_goal.py only for the existing single-box baseline; '
        'multi-box execution is not yet available.')
    previous = getattr(builtins, SESSION_NAME, None)
    if previous is not None and previous.active:
        raise RuntimeError('Existing multi-box source session is active. Stop it first.')
    stage = omni.usd.get_context().get_stage()
    report_path, report = _latest_report()
    if report.get('stage') != stage.GetRootLayer().identifier:
        raise RuntimeError('Inspection report does not belong to the currently open Stage.')

    source_runtime = WarehouseMultiBoxRuntime(config.BOX_PATHS)
    prepared = source_runtime.prepare(report, {'source': 'CartAssembly parked pose'})
    if isinstance(prepared, dict) and prepared.get('status') == 'blocked':
        raise RuntimeError('Multi-box source preflight blocked: ' + prepared['reason'])
    source = prepared.source_approach
    target = _box_center(stage, prepared.action.box_id)
    dx, dy = target[0] - source.navmesh_point[0], target[1] - source.navmesh_point[1]
    if math.hypot(dx, dy) < 1e-6:
        raise RuntimeError('Source approach point is too close to the box center.')
    box_yaw = math.degrees(math.atan2(dy, dx))
    # Keep the authored heading during the approach. Facing the box is a
    # separate post-arrival action; using box_yaw here makes CartAssembly turn
    # with the Worker at the source point.
    approach_yaw = _worker_yaw(stage)

    worker_result = {}

    async def reuse_navmesh():
        interface = nav.acquire_interface()
        mesh = interface.get_navmesh()
        count = (sum(len(mesh.get_draw_triangles(i)) // 3
                     for i in range(interface.get_area_count())) if mesh is not None else 0)
        if count <= 0:
            raise RuntimeError('Existing NavMesh is unavailable.')
        return {'status': 'verified_existing', 'triangle_count': count, 'reused': True}, runtime.BorrowedNavMeshHandle()

    def snapshot():
        return runtime.WorkerRuntimeSnapshot.capture(
            settings=carb.settings.get_settings(), setting_paths=runtime.PEOPLE_SETTING_PATHS,
            command_file=COMMAND_FILE)

    async def setup_worker():
        from scripts.configure_warehouse_worker_behavior import configure_worker_behavior
        result = await configure_worker_behavior(
            # Pass the Worker character root, not its SkelRoot child. The
            # People command name is derived from this path and must remain
            # `Worker_01`.
            runtime.WORKER_PATH, COMMAND_FILE,
            destination=source.navmesh_point, final_yaw=approach_yaw,
            wait_seconds=0.0, max_snap_m=config.MAX_NAVMESH_SNAP_M)
        result.update(source_box_path=prepared.action.box_id,
                      source_navmesh_point=source.navmesh_point,
                      source_path_points=len(source.path_points),
                      report_path=str(report_path),
                      box_center=target,
                      approach_yaw_deg=approach_yaw,
                      box_yaw_deg=box_yaw,
                      box_transfer_configured=False)
        worker_result.update(result)
        return result

    def setup_cart():
        return runtime._setup_cart_live()

    session = await runtime.RuntimeBootstrap(
        precheck=runtime._precheck_live, setup_navmesh=reuse_navmesh,
        capture_worker_state=snapshot, setup_worker=setup_worker,
        setup_cart=setup_cart).start()
    setattr(builtins, SESSION_NAME, session)
    session.result['source_action'] = {
        'kind': prepared.action.kind, 'box_id': prepared.action.box_id,
        'navmesh_point': source.navmesh_point,
        'box_horizontal_distance_m': source.box_horizontal_distance_m,
    }
    print('WAREHOUSE_MULTI_BOX_SOURCE_READY=' + json.dumps(session.result, sort_keys=True))
    print('[Multi-box Source] First source GoTo configured. Press Play manually to test Worker/Cart approach only.')
    return session


def run():
    previous = getattr(builtins, TASK_NAME, None)
    if previous is not None and not previous.done():
        raise RuntimeError('Another multi-box source setup is still running.')
    task = asyncio.ensure_future(start())
    setattr(builtins, TASK_NAME, task)
    task.add_done_callback(runtime._report_task_result)
    return task


def shutdown():
    """Stop only this staged source session and restore its command settings."""
    session = getattr(builtins, SESSION_NAME, None)
    if session is None or not session.active:
        return {'status': 'already_stopped'}
    session.shutdown(restore_navmesh=False)
    setattr(builtins, SESSION_NAME, None)
    print('[Multi-box Source] SHUTDOWN: source session cleared; NavMesh was borrowed.')
    return {'status': 'stopped'}


if __name__ == '__main__':
    run()
