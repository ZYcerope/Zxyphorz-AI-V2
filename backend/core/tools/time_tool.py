from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .base import Tool, ToolResult


class TimeTool(Tool):
    name = "time"
    description = "Show the current time (supports timezones)."
    examples = "what time is it? / time in Asia/Jakarta"

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return (
            "what time" in t
            or t.startswith("time")
            or "current time" in t
            or "time in" in t
        )

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip()
        tz = "Asia/Jakarta"
        lower = t.lower()
        if "time in" in lower:
            # naive parse: everything after "time in"
            tz = t.lower().split("time in", 1)[1].strip() or tz
        try:
            now = datetime.now(ZoneInfo(tz))
            return ToolResult(
                handled=True,
                text=f"It's **{now.strftime('%A, %B %d, %Y — %H:%M:%S')}** ({tz}).",
                meta={"tool": self.name, "tz": tz},
            )
        except Exception:
            now = datetime.now()
            return ToolResult(
                handled=True,
                text=f"I couldn't load that timezone. Server time is **{now.strftime('%A, %B %d, %Y — %H:%M:%S')}**.",
                meta={"tool": self.name, "tz": tz, "fallback": True},
            )
