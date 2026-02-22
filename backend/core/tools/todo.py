from __future__ import annotations

import re
from typing import Optional

from ..memory_store import MemoryStore
from .base import Tool, ToolResult
from .utils import strip_prefix


class TodoTool(Tool):
    name = "todo"
    description = "A tiny local todo manager: add/list/done."
    examples = "add todo: finish README / list todos / done 3"

    def __init__(self, store: MemoryStore):
        self.store = store

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return (
            t.startswith("todo")
            or t.startswith("add todo")
            or t.startswith("list todos")
            or t.startswith("done ")
            or t.startswith("mark ")
            or t.startswith("complete ")
        )

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip()
        lower = t.lower()

        if lower.startswith("list todos") or lower == "todo" or lower == "todos":
            todos = self.store.list_todos(session_id, include_done=True)
            if not todos:
                return ToolResult(True, "No todos yet. Add one with: `add todo: ...`", {"tool": self.name, "count": 0})
            lines = ["Your todos:"]
            for td in todos[:50]:
                status = "✅" if td["is_done"] else "⬜"
                lines.append(f"- {status} **{td['id']}** — {td['item']}")
            return ToolResult(True, "\n".join(lines), {"tool": self.name, "count": len(todos)})

        item = strip_prefix(t, "add todo:", "add todo", "todo:", "todo")
        if item:
            todo_id = self.store.add_todo(session_id, item)
            return ToolResult(True, f"Added todo **{todo_id}**: {item}", {"tool": self.name, "id": todo_id, "item": item})

        m = re.match(r"^(done|mark|complete)\s+(\d+)\s*$", lower)
        if m:
            todo_id = int(m.group(2))
            ok = self.store.set_todo_done(session_id, todo_id, True)
            if ok:
                return ToolResult(True, f"Marked todo **{todo_id}** as done ✅", {"tool": self.name, "id": todo_id, "done": True})
            return ToolResult(True, f"I couldn't find todo **{todo_id}** in this session.", {"tool": self.name, "id": todo_id, "done": False})

        return ToolResult(True, "Todo commands: `add todo: ...`, `list todos`, `done <id>`.", {"tool": self.name})
