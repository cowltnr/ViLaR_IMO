"""Open/Run while stopped, then manual Play. No Worker or NavMesh planning."""
from pathlib import Path
import sys
import importlib

PROJECT=Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
if str(PROJECT) not in sys.path:
    sys.path.insert(0,str(PROJECT))
importlib.invalidate_caches()
for name in ('warehouse_box_transfer','warehouse_multi_box_config','warehouse_box_only_stack'):
    module=importlib.import_module('scripts.'+name)
    path=PROJECT/'scripts'/(name+'.py')
    if Path(module.__file__).resolve()!=path.resolve():
        raise RuntimeError('Wrong scripts package: '+str(module.__file__))
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)

preview=module.run()
