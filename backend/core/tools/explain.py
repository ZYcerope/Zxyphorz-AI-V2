from __future__ import annotations

from typing import List, Optional

from ..rag import KnowledgeBase
from .base import Tool, ToolResult
from .utils import strip_prefix


class ExplainTool(Tool):
    name = "explain"
    description = "Explain a topic with examples (uses local knowledge base when available)."
    examples = "explain: retrieval augmented generation"

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return t.startswith("explain") or t.startswith("what is") or t.startswith("how does")

    def run(self, user_text: str, session_id: str) -> ToolResult:
        topic = strip_prefix(user_text, "explain:", "explain", "what is", "how does")
        topic = (topic or "").strip(" :?-")
        if not topic:
            return ToolResult(True, "Tell me what to explain. Example: `explain: BM25`", {"tool": self.name})

        hits = self.kb.search(topic, k=3)
        sources: List[str] = []
        snippets: List[str] = []
        for c, _s in hits:
            sources.append(c.title)
            snippets.append(f"- {c.text} (Source: {c.title})")

        # A deterministic, readable explanation template.
        lines: List[str] = []
        lines.append(f"Here’s a clear explanation of **{topic}**:")
        lines.append("")
        lines.append("### Intuition")
        lines.append(
            f"{topic} is best understood as a set of simple ideas working together. "
            f"I’ll give you the big picture first, then a concrete example."
        )
        lines.append("")
        lines.append("### Key points")
        lines.append("- What it is")
        lines.append("- Why it matters")
        lines.append("- A small example")
        lines.append("")
        lines.append("### Example")
        lines.append(
            "Imagine you have a folder of notes. When you ask a question, the system searches the notes, "
            "picks the most relevant parts, and uses them to craft the answer."
        )

        if snippets:
            lines.append("")
            lines.append("### Local references (from your knowledge base)")
            lines.extend(snippets[:6])

        lines.append("")
        lines.append("### Next step")
        lines.append("If you tell me your goal (study, build a feature, or write a blog post), I’ll tailor the explanation.")

        return ToolResult(True, "\n".join(lines), {"tool": self.name, "topic": topic, "sources": sources})
