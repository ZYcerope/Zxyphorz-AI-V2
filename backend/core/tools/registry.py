from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .base import Tool, ToolResult


@dataclass
class ToolRegistry:
    tools: List[Tool]

    def run_first(self, user_text: str, session_id: str) -> Optional[ToolResult]:
        for tool in self.tools:
            try:
                if tool.match(user_text):
                    result = tool.run(user_text, session_id)
                    if result.handled:
                        return result
            except Exception as e:
                # Defensive: tools should never crash the whole assistant
                return ToolResult(
                    handled=True,
                    text=(
                        f"I tried to use '{tool.name}', but it hit an internal error. "
                        f"Try rephrasing your request. (Tool error: {e.__class__.__name__})"
                    ),
                    meta={"tool": tool.name, "error": str(e)},
                )
        return None

    def help_text(self) -> str:
        lines = ["Here are my built-in commands and tools:", ""]
        for t in self.tools:
            lines.append(f"- **{t.name}** — {t.description}")
            if t.examples:
                lines.append(f"  - Example: {t.examples}")

        lines.append("")
        lines.append("Commands:")
        lines.append("- `/help` — show this message")
        lines.append("- `/memory` — show saved session facts")
        lines.append("- `/lang` — show current language")
        lines.append("- `/lang <code>` — set language (en/zh/ja/fr/pt/es/id)")
        lines.append("- `/reset` — clear session memory")
        lines.append("- `/export` — export your session as JSON")
        lines.append("- `/packs` — quick help for offline knowledge packs")
        return "\n".join(lines)
