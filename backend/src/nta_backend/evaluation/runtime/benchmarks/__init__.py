import glob
import importlib
import os

_dir = os.path.dirname(__file__)

for _path in sorted(glob.glob(os.path.join(_dir, "*.py"))):
    _name = os.path.basename(_path)[:-3]
    if _name.startswith("_"):
        continue
    importlib.import_module(f"{__package__}.{_name}")
