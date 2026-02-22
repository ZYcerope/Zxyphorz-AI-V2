from __future__ import annotations

import re
from collections import Counter
from typing import List

from .base import Tool, ToolResult
from .utils import strip_prefix


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # naive sentence split
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _word_tokens(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    toks = [t for t in text.split() if len(t) > 2]
    return toks


def _summarize(text: str, max_sentences: int = 4) -> str:
    sents = _split_sentences(text)
    if len(sents) <= max_sentences:
        return " ".join(sents)

    freq = Counter(_word_tokens(text))
    if not freq:
        return " ".join(sents[:max_sentences])

    scored = []
    for i, s in enumerate(sents):
        toks = _word_tokens(s)
        score = sum(freq[t] for t in toks)
        length_penalty = max(1.0, len(toks) / 18.0)
        scored.append((score / length_penalty, i, s))

    scored.sort(reverse=True)
    chosen = sorted(scored[:max_sentences], key=lambda x: x[1])
    return " ".join(s for _, _, s in chosen)


class SummarizeTool(Tool):
    name = "summarize"
    description = "Create a short summary (extractive, local)."
    examples = "summarize: <paste text>"

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return t.startswith("summarize") or t.startswith("tldr") or t.startswith("tl;dr")

    def run(self, user_text: str, session_id: str) -> ToolResult:
        payload = strip_prefix(user_text, "summarize:", "summarize", "tldr:", "tldr", "tl;dr:", "tl;dr")
        if not payload:
            return ToolResult(True, "Paste text after `summarize:` and I’ll shorten it.", {"tool": self.name})

        summary = _summarize(payload, max_sentences=4)
        return ToolResult(True, f"**Summary:** {summary}", {"tool": self.name, "len": len(payload), "sentences": 4})
