from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root is on PYTHONPATH when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.config import AppConfig
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


def build_engine(tmp_db: Path) -> ChatEngine:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = AppConfig.from_repo_root(repo_root)

    seed_facts = {}
    if cfg.seed_facts_path.exists():
        try:
            seed_facts = json.loads(cfg.seed_facts_path.read_text(encoding="utf-8"))
        except Exception:
            seed_facts = {}

    store = MemoryStore(tmp_db)
    kb = KnowledgeBase(cfg.knowledge_base_dir, packs_processed_dir=cfg.knowledge_packs_processed_dir)
    kb.load()

    tools = ToolRegistry(
        tools=[
            TimeTool(),
            CalculatorTool(),
            SummarizeTool(),
            NotesTool(store),
            TodoTool(store),
            KnowledgePacksTool(cfg.knowledge_packs_dir),
            ExplainTool(kb),
            TranslatorTool(),
            CodeTemplatesTool(),
        ]
    )
    return ChatEngine(persona=ZXYPHORZ_AI, store=store, kb=kb, tools=tools, seed_facts=seed_facts)


def main() -> None:
    tmp_db = Path("tests_tmp.sqlite3")
    if tmp_db.exists():
        tmp_db.unlink()

    engine = build_engine(tmp_db)

    r1 = engine.handle("2*(3+4)", None)
    assert "Result:" in r1.reply and "14" in r1.reply, r1.reply

    sid = r1.session_id
    r2 = engine.handle("remember this: hello world", sid)
    assert "Saved" in r2.reply

    r3 = engine.handle("list notes", sid)
    assert "hello world" in r3.reply

    r4 = engine.handle("/help", sid)
    assert "built-in" in r4.reply.lower() or "tools" in r4.reply.lower()

    r5 = engine.handle("explain: rag", sid)
    assert "explanation" in r5.reply.lower() or "here’s" in r5.reply.lower()

    r6 = engine.handle("/lang id", sid)
    assert "id" in r6.reply.lower()

    print("All tests passed ✅")


if __name__ == "__main__":
    main()
