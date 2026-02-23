from __future__ import annotations

"""
Diagnostics runner for Zxyphorz AI.

This script is very useful when someone clones your repo and says:
"It doesn't work on my machine."

It prints environment info and runs a few quick self-checks.

Run:
    python tests/diagnostics.py
"""

import platform
import sys
from pathlib import Path


def _try_import_versions() -> dict:
    out = {}
    try:
        import fastapi

        out["fastapi"] = getattr(fastapi, "__version__", "?")
    except Exception as e:
        out["fastapi"] = f"IMPORT_ERROR: {e}"

    try:
        import uvicorn

        out["uvicorn"] = getattr(uvicorn, "__version__", "?")
    except Exception as e:
        out["uvicorn"] = f"IMPORT_ERROR: {e}"

    return out


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    print("=== Zxyphorz AI Diagnostics ===")
    print(f"Python: {sys.version.splitlines()[0]}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Repo root: {repo_root}")

    versions = _try_import_versions()
    print("Dependencies:")
    for k, v in versions.items():
        print(f"  - {k}: {v}")

    # Quick engine smoke test
    print("\nSmoke test: engine.handle()")
    try:
        sys.path.insert(0, str(repo_root))

        from tests._helpers import temporary_engine

        with temporary_engine() as (engine, _db):
            r = engine.handle("2*(3+4)", None)
            ok = "14" in r.reply
            print(f"  - calculator: {'OK' if ok else 'FAIL'} -> {r.reply}")
            if not ok:
                return 2

            r2 = engine.handle("explain: rag", r.session_id)
            ok2 = "rag" in r2.reply.lower()
            print(f"  - explain tool: {'OK' if ok2 else 'FAIL'}")
            if not ok2:
                return 2

            _ = engine.handle("/memory", r.session_id)
            print("  - memory command: OK")

    except Exception as e:
        print("  - ERROR during smoke test:")
        print(f"    {type(e).__name__}: {e}")
        return 2

    # Optional: API import check
    print("\nSmoke test: FastAPI app import")
    try:
        from backend.app import app  # noqa: F401

        print("  - app import: OK")
    except Exception as e:
        print("  - app import: FAIL")
        print(f"    {type(e).__name__}: {e}")
        return 2

    print("\nDiagnostics completed ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
