import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


class LauncherSourceTest(unittest.TestCase):
    def test_reads_new_source_and_rejects_other_project(self):
        entry=runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/run_multi_box_unloading.py'))
        loader=entry['reload_project_module']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'scripts').mkdir()
            source=root/'scripts/_source_probe.py'
            source.write_text('value=2\n')
            module=ModuleType('scripts._source_probe')
            module.__file__=str(source)
            module.value=1
            with patch.dict(sys.modules,{'scripts._source_probe':module}),patch.dict(loader.__globals__,PROJECT=root):
                self.assertEqual(loader('_source_probe').value,2)
                source.write_text('value=3\n')
                self.assertEqual(loader('_source_probe').value,3)
                module.__file__='/different/project/probe.py'
                with self.assertRaises(RuntimeError):
                    loader('_source_probe')
                self.assertEqual(module.value,3)
