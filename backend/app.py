from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core.config import AppConfig
from .core.engine import ChatEngine
from .core.memory_store import MemoryStore
from .core.persona import ZXYPHORZ_AI
from .core.rag import KnowledgeBase
from .core.tools.calculator import CalculatorTool
from .core.tools.code_templates import CodeTemplatesTool
from .core.tools.explain import ExplainTool
from .core.tools.notes import NotesTool
from .core.tools.packs_tool import KnowledgePacksTool
from .core.tools.registry import ToolRegistry
from .core.tools.summarize import SummarizeTool
from .core.tools.time_tool import TimeTool
from .core.tools.todo import TodoTool
from .core.tools.translator import TranslatorTool


REPO_ROOT = Path(__file__).resolve().parents[1]
CFG = AppConfig.from_repo_root(REPO_ROOT)

# Seed facts (stable identity / preferences)
_seed_facts: Dict[str, Any] = {}
if CFG.seed_facts_path.exists():
    try:
        _seed_facts = json.loads(CFG.seed_facts_path.read_text(encoding="utf-8"))
    except Exception:
        _seed_facts = {}

store = MemoryStore(CFG.sqlite_path)

kb = KnowledgeBase(CFG.knowledge_base_dir, packs_processed_dir=CFG.knowledge_packs_processed_dir)
kb.load()

tools = ToolRegistry(
    tools=[
        # Order matters: more "specific" tools first, generic last
        TimeTool(),
        CalculatorTool(),
        SummarizeTool(),
        NotesTool(store),
        TodoTool(store),
        KnowledgePacksTool(CFG.knowledge_packs_dir),
        ExplainTool(kb),
        TranslatorTool(),
        CodeTemplatesTool(),
    ]
)

engine = ChatEngine(persona=ZXYPHORZ_AI, store=store, kb=kb, tools=tools, seed_facts=_seed_facts)

app = FastAPI(title="Zxyphorz AI", version="1.1.0")

# Serve frontend
app.mount("/static", StaticFiles(directory=str(CFG.frontend_dir), html=False), name="static")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = None
    language: Optional[str] = Field(default=None, description="Preferred language code (en/zh/ja/fr/pt/es/id)")


class ChatReply(BaseModel):
    session_id: str
    reply: str
    meta: Dict[str, Any]


@app.get("/", response_class=HTMLResponse)
def index() -> Any:
    return FileResponse((CFG.frontend_dir / "index.html").as_posix())


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "assistant": ZXYPHORZ_AI.name, "version": "1.1.0"}


@app.post("/api/chat", response_model=ChatReply)
def chat(req: ChatRequest) -> Any:
    resp = engine.handle(req.message, req.session_id, language=req.language)
    return {"session_id": resp.session_id, "reply": resp.reply, "meta": resp.meta}


@app.post("/api/reset")
def reset(req: ChatRequest) -> Dict[str, Any]:
    session_id = req.session_id or engine.new_session_id()
    store.reset_session(session_id)
    return {"ok": True, "session_id": session_id}


@app.get("/api/export")
def export(session_id: str) -> Any:
    data = store.export_session(session_id)
    return JSONResponse(content=data)


@app.get("/api/kb/search")
def kb_search(q: str, k: int = 4, language: Optional[str] = None) -> Dict[str, Any]:
    hits = kb.search(q, k=min(max(k, 1), 10), lang_hint=language)
    return {
        "q": q,
        "hits": [
            {
                "chunk_id": c.chunk_id,
                "title": c.title,
                "file": c.source_file,
                "lang": c.lang,
                "text": c.text,
                "score": score,
            }
            for c, score in hits
        ],
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
                message = str(payload.get("message", "")).strip()
                session_id = payload.get("session_id")
                language = payload.get("language")
            except Exception:
                await ws.send_text(json.dumps({"type": "error", "message": "Invalid JSON payload."}))
                continue

            if not message:
                await ws.send_text(json.dumps({"type": "error", "message": "Empty message."}))
                continue

            resp = engine.handle(message, session_id, language=language)

            # Streaming: send words in small chunks
            await ws.send_text(json.dumps({"type": "start", "session_id": resp.session_id, "meta": resp.meta}))
            words = resp.reply.split(" ")
            buf = []
            for w in words:
                buf.append(w)
                if len(buf) >= 14:
                    await ws.send_text(json.dumps({"type": "delta", "text": " ".join(buf) + " "}))
                    buf = []
            if buf:
                await ws.send_text(json.dumps({"type": "delta", "text": " ".join(buf)}))
            await ws.send_text(json.dumps({"type": "end"}))
    except WebSocketDisconnect:
        return
