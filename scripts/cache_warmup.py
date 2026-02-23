#!/usr/bin/env python3
from __future__ import annotations

"""
Zxyphorz AI Cache Warmup & Precompile Script (offline, no API)

What this script does:
1) Precompiles Python code into bytecode caches (.pyc) to make imports faster.
2) Optionally directs caches to a clean folder (data/pycache) so repo stays tidy.
3) Warms up Zxyphorz AI KnowledgeBase (loads docs/packs and runs sample queries)
   so large knowledge packs feel faster and "smarter" at runtime.
4) Produces a JSON report with timings and environment info.

Usage:
    python scripts/cache_warmup.py precompile
    python scripts/cache_warmup.py warmup
    python scripts/cache_warmup.py all

Notes:
- You should NOT commit __pycache__ or .pyc to GitHub.
- This script is safe to run multiple times.
"""

import argparse
import compileall
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------
# Utilities
# ---------------------------

def repo_root() -> Path:
    # scripts/cache_warmup.py -> repo root is parent of scripts/
    return Path(__file__).resolve().parents[1]


def now_iso() -> str:
    # Simple timestamp, no external deps
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    safe_mkdir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for u in units:
        if size < 1024.0:
            return f"{size:.2f}{u}"
        size /= 1024.0
    return f"{size:.2f}PB"


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def set_pycache_prefix(prefix: Optional[Path]) -> None:
    """
    PYTHONPYCACHEPREFIX redirects __pycache__ into a dedicated folder.
    This keeps backend/tests folders clean.
    """
    if prefix is None:
        return
    safe_mkdir(prefix)
    os.environ["PYTHONPYCACHEPREFIX"] = str(prefix.resolve())


@dataclass
class StepResult:
    name: str
    ok: bool
    seconds: float
    details: Dict[str, Any]


# ---------------------------
# Precompile
# ---------------------------

def precompile_python(
    rr: Path,
    targets: List[Path],
    optimize: int = 0,
    quiet: int = 1
) -> StepResult:
    """
    Precompile source .py files into .pyc caches.

    optimize:
      0 -> default
      1 -> remove assert statements
      2 -> more aggressive

    quiet:
      0 -> verbose
      1 -> less output
      2 -> almost silent
    """
    t0 = time.perf_counter()
    details: Dict[str, Any] = {
        "optimize": optimize,
        "targets": [str(t) for t in targets],
        "compiled": 0,
        "failed": 0,
    }

    ok = True
    compiled = 0
    failed = 0

    for t in targets:
        if not t.exists():
            continue
        # compile_dir returns True if all files compiled successfully
        res = compileall.compile_dir(
            str(t),
            maxlevels=20,
            quiet=quiet,
            optimize=optimize,
            force=True,
            legacy=False
        )
        if res:
            # best-effort count (not exact, but informative)
            compiled += sum(1 for _ in t.rglob("*.py"))
        else:
            ok = False
            failed += 1

    details["compiled"] = compiled
    details["failed"] = failed
    dt = time.perf_counter() - t0
    return StepResult("precompile", ok, dt, details)


# ---------------------------
# Warmup (KnowledgeBase + Engine)
# ---------------------------

def _import_engine_components(rr: Path):
    """
    Import backend components in a controlled way.
    If imports fail, we return (None, error_string).
    """
    try:
        sys.path.insert(0, str(rr))
        from backend.core.config import AppConfig
        from backend.core.rag import KnowledgeBase
        return AppConfig, KnowledgeBase, None
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def warmup_kb(rr: Path, queries: List[Tuple[str, str]], k: int = 3) -> StepResult:
    """
    Warm up KnowledgeBase:
    - loads curated KB + processed packs
    - runs a set of queries (multi-language)
    """
    t0 = time.perf_counter()
    details: Dict[str, Any] = {
        "kb_loaded": False,
        "hits": [],
        "errors": [],
        "k": k,
    }

    AppConfig, KnowledgeBase, err = _import_engine_components(rr)
    if err:
        dt = time.perf_counter() - t0
        details["errors"].append({"stage": "import", "error": err})
        return StepResult("warmup_kb", False, dt, details)

    ok = True
    try:
        cfg = AppConfig.from_repo_root(rr)
        kb = KnowledgeBase(cfg.knowledge_base_dir, packs_processed_dir=cfg.knowledge_packs_processed_dir)
        kb.load()
        details["kb_loaded"] = True

        for q, lang in queries:
            try:
                hits = kb.search(q, k=k, lang_hint=lang)
                # Store only lightweight metadata to keep report small
                hit_summaries = []
                for chunk, score in hits[:k]:
                    hit_summaries.append({
                        "title": getattr(chunk, "title", ""),
                        "score": float(score),
                        "preview": (getattr(chunk, "text", "")[:140] + "...") if getattr(chunk, "text", "") else "",
                    })
                details["hits"].append({"q": q, "lang": lang, "top": hit_summaries})
            except Exception as e:
                ok = False
                details["errors"].append({"stage": "search", "q": q, "error": f"{type(e).__name__}: {e}"})

    except Exception as e:
        ok = False
        details["errors"].append({"stage": "load", "error": f"{type(e).__name__}: {e}"})

    dt = time.perf_counter() - t0
    return StepResult("warmup_kb", ok, dt, details)


# ---------------------------
# Reports
# ---------------------------

def build_report_base(rr: Path) -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "repo_root": str(rr),
        "python": sys.version.splitlines()[0],
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "env": {
            "PYTHONPYCACHEPREFIX": os.environ.get("PYTHONPYCACHEPREFIX", ""),
        },
        "sizes": {
            "backend_folder": human_bytes(folder_size(rr / "backend")),
            "tests_folder": human_bytes(folder_size(rr / "tests")),
            "data_folder": human_bytes(folder_size(rr / "data")),
            "knowledge_base": human_bytes(folder_size(rr / "data" / "knowledge_base")),
            "packs_processed": human_bytes(folder_size(rr / "data" / "knowledge_packs" / "processed")),
        }
    }


def run_all(pycache_prefix: Optional[Path]) -> int:
    rr = repo_root()

    # Redirect caches to keep repo clean (optional but recommended)
    set_pycache_prefix(pycache_prefix)

    report: Dict[str, Any] = build_report_base(rr)
    steps: List[StepResult] = []

    # Precompile targets
    targets = [
        rr / "backend",
        rr / "tests",
        rr / "scripts",
    ]

    # Run precompile twice: optimize=0 and optimize=1
    steps.append(precompile_python(rr, targets, optimize=0, quiet=1))
    steps.append(precompile_python(rr, targets, optimize=1, quiet=1))

    # Warmup KB with multilingual queries (7 languages)
    warm_queries = [
        ("What is RAG and how does it work?", "en"),
        ("Explain BM25 ranking briefly.", "en"),
        ("Apa itu RAG dan bagaimana cara kerjanya?", "id"),
        ("量子力学とは何ですか？", "ja"),
        ("你好，什么是信息检索？", "zh"),
        ("Explique la recherche sémantique.", "fr"),
        ("Explique busca vetorial.", "pt"),
        ("¿Qué es recuperación de información?", "es"),
    ]
    steps.append(warmup_kb(rr, warm_queries, k=3))

    report["steps"] = [
        {
            "name": s.name,
            "ok": s.ok,
            "seconds": round(s.seconds, 4),
            "details": s.details,
        }
        for s in steps
    ]
    report["overall_ok"] = all(s.ok for s in steps)

    out_dir = rr / "data" / "cache"
    safe_mkdir(out_dir)
    out_path = out_dir / "cache_report.json"
    write_json(out_path, report)

    # Print summary
    print("=== Zxyphorz AI Cache Warmup ===")
    print(f"Report: {out_path}")
    for s in steps:
        status = "OK" if s.ok else "FAIL"
        print(f"- {s.name:12s}: {status} ({s.seconds:.2f}s)")
    print(f"Overall: {'OK' if report['overall_ok'] else 'FAIL'}")

    return 0 if report["overall_ok"] else 2


def run_precompile_only(pycache_prefix: Optional[Path]) -> int:
    rr = repo_root()
    set_pycache_prefix(pycache_prefix)

    targets = [rr / "backend", rr / "tests", rr / "scripts"]
    s0 = precompile_python(rr, targets, optimize=0, quiet=1)
    s1 = precompile_python(rr, targets, optimize=1, quiet=1)

    print("=== Precompile Results ===")
    print(f"Optimize=0: {'OK' if s0.ok else 'FAIL'} ({s0.seconds:.2f}s)")
    print(f"Optimize=1: {'OK' if s1.ok else 'FAIL'} ({s1.seconds:.2f}s)")

    return 0 if (s0.ok and s1.ok) else 2


def run_warmup_only(pycache_prefix: Optional[Path]) -> int:
    rr = repo_root()
    set_pycache_prefix(pycache_prefix)

    warm_queries = [
        ("What is RAG and how does it work?", "en"),
        ("Apa itu RAG dan bagaimana cara kerjanya?", "id"),
        ("你好，什么是信息检索？", "zh"),
        ("こんにちは、量子力学は何ですか？", "ja"),
        ("Explique la recherche sémantique.", "fr"),
        ("Explique busca vetorial.", "pt"),
        ("¿Qué es recuperación de información?", "es"),
    ]
    s = warmup_kb(rr, warm_queries, k=3)

    out_dir = rr / "data" / "cache"
    safe_mkdir(out_dir)
    out_path = out_dir / "warmup_report.json"
    write_json(out_path, {
        "generated_at": now_iso(),
        "repo_root": str(rr),
        "ok": s.ok,
        "seconds": round(s.seconds, 4),
        "details": s.details
    })

    print("=== Warmup KB ===")
    print(f"Report: {out_path}")
    print(f"Status: {'OK' if s.ok else 'FAIL'} ({s.seconds:.2f}s)")
    return 0 if s.ok else 2


# ---------------------------
# CLI
# ---------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zxyphorz AI cache warmup/precompile (offline).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["precompile", "warmup", "all"],
        help="Which action to run.",
    )
    parser.add_argument(
        "--pycache-prefix",
        default="data/pycache",
        help="Where to place Python bytecode caches (recommended). "
             "Use empty string '' to generate __pycache__ folders in-place.",
    )

    args = parser.parse_args(argv)

    pycache_prefix: Optional[Path]
    if args.pycache_prefix.strip() == "":
        pycache_prefix = None
    else:
        pycache_prefix = repo_root() / args.pycache_prefix

    if args.command == "precompile":
        return run_precompile_only(pycache_prefix)
    if args.command == "warmup":
        return run_warmup_only(pycache_prefix)
    return run_all(pycache_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
