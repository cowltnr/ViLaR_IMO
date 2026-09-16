import importlib
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


class LauncherImportTest(unittest.TestCase):
    def test_discovers_new_module_despite_cached_directory_listing(self):
        launcher = Path(__file__).resolve().parents[2] / 'scripts/run_shelf_goal.py'
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'scripts'
            package.mkdir()
            (package / '__init__.py').write_text('')
            for name in ('configure_warehouse_worker_behavior', 'warehouse_shelf_goal_config',
                         'warehouse_worker_cart_pose_sync', 'warehouse_worker_face_box',
                         'warehouse_box_transfer', 'warehouse_worker_reach_gesture'):
                (package / (name + '.py')).write_text('')
            (package / 'setup_warehouse_runtime.py').write_text(
                '_RUNTIME_SESSION_NAME = "_test_nonexistent_shelf_session"\n')
            (package / 'setup_warehouse_shelf_goal.py').write_text('def run(): return 42\n')
            omni = ModuleType('omni')
            timeline = ModuleType('omni.timeline')
            timeline.get_timeline_interface = lambda: SimpleNamespace(is_stopped=lambda: True)
            omni.timeline = timeline
            with patch.dict(sys.modules), patch.object(sys, 'path', [directory, *sys.path]):
                for name in list(sys.modules):
                    if name == 'scripts' or name.startswith('scripts.'):
                        del sys.modules[name]
                sys.modules.update({'omni': omni, 'omni.timeline': timeline})
                importlib.import_module('scripts')
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module('scripts.warehouse_worker_approach')
                old = package.stat()
                (package / 'warehouse_worker_approach.py').write_text('')
                os.utime(package, ns=(old.st_atime_ns, old.st_mtime_ns))
                result = runpy.run_path(str(launcher), run_name='__main__')
                self.assertEqual(result['task'], 42)
