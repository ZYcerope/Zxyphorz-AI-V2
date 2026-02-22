from __future__ import annotations

from typing import Optional

from ..memory_store import MemoryStore
from .base import Tool, ToolResult
from .utils import strip_prefix


class NotesTool(Tool):
    name = "notes"
    description = "Save and list quick notes (stored locally in SQLite)."
    examples = "remember this: buy milk / list notes"

    def __init__(self, store: MemoryStore):
        self.store = store

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return (
            t.startswith("remember")
            or t.startswith("note:")
            or t.startswith("save note")
            or t.startswith("list notes")
            or t == "notes"
        )

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip()
        lower = t.lower()

        if lower == "notes" or lower.startswith("list notes"):
            notes = self.store.list_notes(session_id, limit=30)
            if not notes:
                return ToolResult(True, "You don't have any notes yet.", {"tool": self.name, "count": 0})
            lines = ["Here are your latest notes:"]
            for n in notes:
                lines.append(f"- {n['note']} _(saved {n['created_at']})_")
            return ToolResult(True, "\n".join(lines), {"tool": self.name, "count": len(notes)})

        note = strip_prefix(t, "note:", "remember this:", "remember:", "save note:", "save note")
        if note is None:
            # allow: "remember <something>"
            if lower.startswith("remember "):
                note = t[len("remember "):].strip()
        if not note:
            return ToolResult(True, "Tell me what to remember. Example: `remember this: my GitHub is ...`", {"tool": self.name})

        self.store.add_note(session_id, note)
        return ToolResult(True, f"Saved. I’ll remember: **{note}**", {"tool": self.name, "note": note})
