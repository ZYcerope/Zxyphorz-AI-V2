from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ToolResult:
    handled: bool
    text: str
    meta: Dict[str, Any]


class Tool:
    """Base class for all tools.

    Tools are deterministic functions that can assist the chat engine.
    """

    name: str = "tool"
    description: str = ""
    examples: str = ""

    def match(self, user_text: str) -> bool:
        raise NotImplementedError

    def run(self, user_text: str, session_id: str) -> ToolResult:
        raise NotImplementedError
