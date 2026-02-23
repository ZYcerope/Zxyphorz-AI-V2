from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RepoPaths:
    """Common repository paths used by tests."""
    repo_root: Path
    scripts_dir: Path
    data_dir: Path
    kb_dir: Path
    packs_dir: Path
    packs_processed_dir: Path
    profile_dir: Path
    seed_facts_path: Path


def get_repo_paths() -> RepoPaths:
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    data_dir = repo_root / "data"
    kb_dir = data_dir / "knowledge_base"
    packs_dir = data_dir / "knowledge_packs"
    packs_processed_dir = packs_dir / "processed"
    profile_dir = data_dir / "profile"
    seed_facts_path = profile_dir / "seed_facts.json"
    return RepoPaths(
        repo_root=repo_root,
        scripts_dir=scripts_dir,
        data_dir=data_dir,
        kb_dir=kb_dir,
        packs_dir=packs_dir,
        packs_processed_dir=packs_processed_dir,
        profile_dir=profile_dir,
        seed_facts_path=seed_facts_path,
    )


def ensure_import_paths() -> RepoPaths:
    """Make sure repo root (and scripts/) are importable."""
    p = get_repo_paths()
    root = str(p.repo_root)
    scripts = str(p.scripts_dir)
    if root not in sys.path:
        sys.path.insert(0, root)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return p


def load_seed_facts(seed_facts_path: Path) -> Dict[str, Any]:
    if not seed_facts_path.exists():
        return {}
    try:
        return json.loads(seed_facts_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def make_temp_db_path(prefix: str = "zxy_test_") -> Path:
    """Create a unique sqlite path in a temporary directory."""
    td = Path(tempfile.mkdtemp(prefix=prefix))
    return td / "test.sqlite3"


def build_engine(
    sqlite_path: Path,
    *,
    kb_dir: Optional[Path] = None,
    packs_processed_dir: Optional[Path] = None,
    seed_facts: Optional[Dict[str, Any]] = None,
):
    """Build a ChatEngine for tests (no network, no external APIs)."""
    ensure_import_paths()

    from backend.core.engine import ChatEngine
    from backend.core.memory_store import MemoryStore
    from backend.core.persona import ZXYPHORZ_AI
    from backend.core.rag import KnowledgeBase
    from backend.core.tools.calculator import CalculatorTool
    from backend.core.tools.code_templates import CodeTemplatesTool
    from backend.core.tools.explain import ExplainTool
    from backend.core.tools.notes import NotesTool
    from backend.core.tools.packs_tool import KnowledgePacksTool
    from backend.core.tools.registry import ToolRegistry
    from backend.core.tools.summarize import SummarizeTool
    from backend.core.tools.time_tool import TimeTool
    from backend.core.tools.todo import TodoTool
    from backend.core.tools.translator import TranslatorTool

    paths = get_repo_paths()
    kb_dir = kb_dir or paths.kb_dir
    packs_processed_dir = packs_processed_dir or paths.packs_processed_dir

    store = MemoryStore(sqlite_path)
    kb = KnowledgeBase(kb_dir, packs_processed_dir=packs_processed_dir)
    kb.load()

    tools = ToolRegistry(
        tools=[
            TimeTool(),
            CalculatorTool(),
            SummarizeTool(),
            NotesTool(store),
            TodoTool(store),
            KnowledgePacksTool(paths.packs_dir),
            ExplainTool(kb),
            TranslatorTool(),
            CodeTemplatesTool(),
        ]
    )

    return ChatEngine(
        persona=ZXYPHORZ_AI,
        store=store,
        kb=kb,
        tools=tools,
        seed_facts=seed_facts or load_seed_facts(paths.seed_facts_path),
    )


def set_cwd_repo_root() -> None:
    """Run tests from anywhere, but use repo-root as the working directory."""
    paths = get_repo_paths()
    os.chdir(paths.repo_root)


def assert_contains_any(haystack: str, *needles: str) -> None:
    """Small helper for readable assertions."""
    h = (haystack or "").lower()
    for n in needles:
        if (n or "").lower() in h:
            return
    raise AssertionError(f"Expected one of {needles} in: {haystack!r}")
