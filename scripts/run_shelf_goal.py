"""Open this file in Isaac Sim Script Editor and Run while the Timeline is stopped.

Launcher copied from the user-verified warehouse context instructions.
Does not start Play, save USD, or re-bake NavMesh.
The explicit project path is intentional: Script Editor may execute a /tmp copy.
"""

import sys
import importlib
import builtins

import omni.timeline

project = "/home/cowltnr/PycharmProjects/SDV_Robocar"
if project not in sys.path:
    sys.path.insert(0, project)

if not omni.timeline.get_timeline_interface().is_stopped():
    raise RuntimeError("Press Stop first")

# Discover newly added modules in a long-running Isaac Sim process.
importlib.invalidate_caches()

from scripts import setup_warehouse_runtime as runtime

from scripts import configure_warehouse_worker_behavior as behavior
from scripts import warehouse_shelf_goal_config as config
from scripts import warehouse_worker_cart_pose_sync as pose_sync
from scripts import warehouse_worker_face_box as face_box
from scripts import warehouse_box_transfer as box_transfer
from scripts import warehouse_worker_approach as approach
from scripts import warehouse_worker_reach_gesture as reach_gesture
from scripts import setup_warehouse_shelf_goal as shelf

# Resolve every dependency before stopping a working runtime.
session = getattr(builtins, runtime._RUNTIME_SESSION_NAME, None)
if session is not None and session.active:
    runtime.shutdown_warehouse_runtime(restore_navmesh=False)

importlib.reload(behavior)
importlib.reload(config)
importlib.reload(pose_sync)
importlib.reload(face_box)
importlib.reload(box_transfer)
importlib.reload(approach)
importlib.reload(reach_gesture)
importlib.reload(shelf)

task = shelf.run()
