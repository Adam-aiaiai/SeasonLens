"""Run SeasonLens and the existing dependency-free backend-core smoke checks."""
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/backend-core/src"),
                str(ROOT / "extensions/seasonlens/backend/src")]


def main() -> None:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "extensions/seasonlens/backend/tests"))
    # These existing tests are plain functions with assertions; no fixtures or pytest dependency.
    core = runpy.run_path(str(ROOT / "packages/backend-core/tests/test_policy_and_state.py"))
    for name, function in sorted(core.items()):
        if name.startswith("test_") and callable(function):
            suite.addTest(unittest.FunctionTestCase(function, description=f"backend-core: {name}"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
