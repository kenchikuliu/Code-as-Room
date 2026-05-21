"""Compatibility wrapper for the repository-root run_pipeline.py entrypoint.

This keeps both old usage patterns working:
  - python agent_utils/unified_pipeline.py ...
  - sys.path.insert(0, "agent_utils"); from unified_pipeline import run_full_pipeline
"""

from pathlib import Path
import importlib.util
import runpy


ROOT_ENTRYPOINT = Path(__file__).resolve().parents[1] / "run_pipeline.py"


def _load_root_module():
    spec = importlib.util.spec_from_file_location("_root_run_pipeline", ROOT_ENTRYPOINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    runpy.run_path(str(ROOT_ENTRYPOINT), run_name="__main__")
else:
    _root = _load_root_module()
    for _name in dir(_root):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_root, _name)
    __all__ = [name for name in globals() if not name.startswith("_")]
