from __future__ import annotations

"""One-command test runner.

Why this exists:
- Beginners can run: `python tests/run_all.py`
- CI can run: `python -m unittest discover -s tests -p "test_*.py" -v`

This runner also executes the original smoke-test in `tests/run.py`.
"""

import sys
from pathlib import Path
import unittest

# Ensure repo root is importable even when running `python tests/run_all.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._helpers import ensure_import_paths, set_cwd_repo_root


def run_smoke() -> None:
    """Run the original smoke-test script (kept for compatibility)."""
    ensure_import_paths()
    set_cwd_repo_root()

    from tests import run as smoke
    smoke.main()


def run_unittests(argv: list[str]) -> int:
    """Run unittest discovery and return process exit code."""
    ensure_import_paths()
    set_cwd_repo_root()

    verbosity = 1
    if "-v" in argv or "--verbose" in argv:
        verbosity = 2

    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> None:
    argv = sys.argv[1:]

    print("\n=== Zxyphorz AI: Smoke tests ===")
    run_smoke()

    print("\n=== Zxyphorz AI: Unit tests ===")
    code = run_unittests(argv)
    if code == 0:
        print("\nAll tests passed ✅")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
