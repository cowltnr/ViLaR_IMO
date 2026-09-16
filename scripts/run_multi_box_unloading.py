"""Open/Run in Script Editor while stopped. Configure unloading; manual Play."""
import sys
import importlib
import hashlib
from pathlib import Path

PROJECT = Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
if str(PROJECT) not in sys.path:
    sys.path.insert(0,str(PROJECT))
importlib.invalidate_caches()


def reload_project_module(name):
    """Read current source directly; reject another project's scripts package."""
    module=importlib.import_module('scripts.'+name)
    expected=(PROJECT/'scripts'/(name+'.py')).resolve()
    if Path(module.__file__).resolve()!=expected:
        raise RuntimeError('Wrong project module: '+str(module.__file__))
    source=expected.read_bytes()
    exec(compile(source,str(expected),'exec'),module.__dict__)
    print('[Multi-box] MODULE:',name,hashlib.sha256(source).hexdigest()[:12],str(expected))
    return module


def run():
    import asyncio
    import builtins
    import omni.timeline
    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError('Press Stop first')
    from scripts import setup_warehouse_runtime as runtime
    previous = getattr(builtins,runtime._RUNTIME_TASK_NAME,None)
    if previous is not None and not previous.done():
        raise RuntimeError('Warehouse setup still running')
    # Resolve dependencies before cleaning the previous stopped session.
    names = ('configure_warehouse_worker_behavior', 'warehouse_box_transfer',
             'warehouse_composite_support',
             'warehouse_oriented_clearance','warehouse_source_spacing',
             'warehouse_work_position',
             'warehouse_worker_reach_gesture','warehouse_walking_carry',
             'warehouse_multi_box_config','warehouse_unloading_live','setup_multi_box_unloading')
    modules = [reload_project_module(name) for name in names]
    for key in (runtime._RUNTIME_SESSION_NAME,'_warehouse_multi_box_source_session'):
        session = getattr(builtins,key,None)
        if session is not None and session.active:
            session.shutdown(restore_navmesh=False)
    task = asyncio.ensure_future(modules[-1].start())
    setattr(builtins,runtime._RUNTIME_TASK_NAME,task)
    task.add_done_callback(runtime._report_task_result)
    return task


if __name__ == '__main__':
    task = run()
