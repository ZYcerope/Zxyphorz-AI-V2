from __future__ import annotations

from .base import Tool, ToolResult


class CodeTemplatesTool(Tool):
    name = "code_templates"
    description = "Generate small code templates/snippets locally (no AI model)."
    examples = "generate a python class / create a fastapi endpoint / template: react component"

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return (
            ("generate" in t and "template" in t)
            or t.startswith("template:")
            or t.startswith("generate a ")
            or t.startswith("create a ")
        )

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip()
        lower = t.lower()

        # Extract requested template type
        req = lower
        if ":" in lower:
            req = lower.split(":", 1)[1].strip()

        def block(code: str) -> str:
            return f"```\n{code.rstrip()}\n```"

        if "fastapi" in req and ("endpoint" in req or "route" in req or "api" in req):
            code = """from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    qty: int = 1

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/items")
def create_item(item: Item):
    return {"message": "created", "item": item.model_dump()}
"""
            return ToolResult(True, "Here’s a clean FastAPI endpoint template:\n" + block(code), {"tool": self.name, "type": "fastapi_endpoint"})

        if "python class" in req or ("class" in req and "python" in req):
            code = """from dataclasses import dataclass

@dataclass
class UserProfile:
    username: str
    email: str
    points: int = 0

    def add_points(self, n: int) -> None:
        if n < 0:
            raise ValueError("n must be >= 0")
        self.points += n
"""
            return ToolResult(True, "Python class template:\n" + block(code), {"tool": self.name, "type": "python_class"})

        if "react" in req and "component" in req:
            code = """export default function Card({ title, children }) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className="card-body">{children}</div>
    </div>
  );
}
"""
            return ToolResult(True, "React component template:\n" + block(code), {"tool": self.name, "type": "react_component"})

        if "sql" in req and ("table" in req or "schema" in req):
            code = """CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""
            return ToolResult(True, "SQL table template:\n" + block(code), {"tool": self.name, "type": "sql_table"})

        return ToolResult(
            True,
            "Tell me the exact template you want, e.g.:\n"
            "- `create a fastapi endpoint for login`\n"
            "- `generate template: python class for a bank account`\n"
            "- `template: sql schema for notes`",
            {"tool": self.name, "type": "unknown"},
        )

