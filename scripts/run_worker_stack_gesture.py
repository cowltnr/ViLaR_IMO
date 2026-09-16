"""Script Editor Open/Run while stopped, then manual Play. Separate candidate."""
import asyncio
import builtins
from pathlib import Path
import sys
import importlib
import omni.timeline

PROJECT=Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
if str(PROJECT) not in sys.path:
    sys.path.insert(0,str(PROJECT))
if not omni.timeline.get_timeline_interface().is_stopped():
    raise RuntimeError('Press Stop first')
from scripts import setup_warehouse_runtime as runtime
pending=getattr(builtins,runtime._RUNTIME_TASK_NAME,None)
if pending is not None and not pending.done():
    raise RuntimeError('Previous warehouse setup still running')
# Close the previous owner before reloading its module globals.
for key in (runtime._RUNTIME_SESSION_NAME,'_warehouse_multi_box_source_session','_warehouse_box_only_preview'):
    previous=getattr(builtins,key,None)
    if previous is not None and previous.active:
        previous.shutdown()
importlib.invalidate_caches()
for name in ('configure_warehouse_worker_behavior','warehouse_box_transfer',
             'warehouse_worker_cart_pose_sync',
             'warehouse_worker_behavior_rebind',
             'warehouse_multi_box_config','warehouse_oriented_clearance',
             'warehouse_box_only_stack','warehouse_worker_face_box',
             'warehouse_worker_reach_gesture',
             'warehouse_roaming_config','warehouse_roaming_geometry',
             'warehouse_roaming_cargo','warehouse_roaming_goals',
             'warehouse_loaded_cart_roaming','warehouse_roaming_actions',
             'warehouse_stack_gesture',
             'setup_warehouse_stack_gesture'):
    module=importlib.import_module('scripts.'+name)
    path=PROJECT/'scripts'/(name+'.py')
    if Path(module.__file__).resolve()!=path.resolve():
        raise RuntimeError('Wrong project module: '+str(module.__file__))
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
task=asyncio.ensure_future(module.start())
setattr(builtins,runtime._RUNTIME_TASK_NAME,task)
task.add_done_callback(runtime._report_task_result)
