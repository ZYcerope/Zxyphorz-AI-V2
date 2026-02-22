from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .i18n import detect_language, lang_name, normalize_lang, tr
from .memory_store import MemoryStore
from .persona import Persona
from .rag import KnowledgeBase
from .tools.registry import ToolRegistry
from .tools.summarize import _summarize
from .utils import Timer, normalize_ws


@dataclass
class ChatResponse:
    session_id: str
    reply: str
    meta: Dict[str, Any]


class ChatEngine:
    """A deterministic, tool-using assistant.

    NOTE:
    This is not an LLM. It's a well-engineered local assistant:
    - commands
    - tools
    - retrieval (KB + optional knowledge packs)
    - memory (SQLite)
    - basic language routing
    """

    def __init__(
        self,
        persona: Persona,
        store: MemoryStore,
        kb: KnowledgeBase,
        tools: ToolRegistry,
        seed_facts: Optional[Dict[str, Any]] = None,
    ):
        self.persona = persona
        self.store = store
        self.kb = kb
        self.tools = tools
        self.seed_facts = seed_facts or {}

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex[:16]

    def handle(self, user_text: str, session_id: Optional[str], language: Optional[str] = None) -> ChatResponse:
        t_total = Timer.start_now()
        session_id = session_id or self.new_session_id()
        user_text = (user_text or "").strip()
        if not user_text:
            return ChatResponse(session_id, "Say something and I’ll respond.", {"ms": t_total.ms()})

        # Seed stable identity and preferences (idempotent)
        self._ensure_seeded(session_id)

        # Language preference: request > stored fact > auto-detect
        effective_lang = self._resolve_language(session_id, user_text, language)

        # Save user message early
        self.store.add_message(session_id, "user", user_text)
        self._extract_facts(session_id, user_text)

        # Commands (slash)
        if user_text.startswith("/"):
            reply = self._handle_command(session_id, user_text, effective_lang)
            self.store.add_message(session_id, "assistant", reply)
            return ChatResponse(session_id, reply, {"ms": t_total.ms(), "mode": "command", "lang": effective_lang})

        # Tools
        tool_res = self.tools.run_first(user_text, session_id)
        if tool_res is not None:
            reply = tool_res.text
            self.store.add_message(session_id, "assistant", reply)
            self._maybe_refresh_summary_fact(session_id)
            meta = {"ms": t_total.ms(), "mode": "tool", "lang": effective_lang, **tool_res.meta}
            return ChatResponse(session_id, reply, meta)

        # KB + conversational response
        reply, meta = self._chat_reply(session_id, user_text, effective_lang)
        self.store.add_message(session_id, "assistant", reply)
        self._maybe_refresh_summary_fact(session_id)
        meta["ms"] = t_total.ms()
        meta["mode"] = "chat"
        meta["lang"] = effective_lang
        return ChatResponse(session_id, reply, meta)

    # ---------------------- Seed memory ----------------------
    def _ensure_seeded(self, session_id: str) -> None:
        facts = self.store.list_facts(session_id)
        if (facts.get("__seeded__") or {}).get("value") == "1":
            return

        for k, v in self.seed_facts.items():
            if isinstance(v, (list, dict)):
                val = str(v)
            else:
                val = str(v)
            self.store.upsert_fact(session_id, k, val, confidence=1.0)

        self.store.upsert_fact(session_id, "__seeded__", "1", confidence=1.0)

    # ---------------------- Language ----------------------
    def _resolve_language(self, session_id: str, user_text: str, language: Optional[str]) -> str:
        # Explicit request
        req_lang = normalize_lang(language)
        if req_lang:
            self.store.upsert_fact(session_id, "preferred_language", req_lang, confidence=1.0)
            return req_lang

        # Stored preference
        facts = self.store.list_facts(session_id)
        pref = (facts.get("preferred_language") or {}).get("value")
        pref = normalize_lang(pref)
        if pref:
            return pref

        # Auto-detect
        guess = detect_language(user_text)
        if guess.confidence >= 0.75:
            return guess.code
        return "en"

    # ---------------------- Commands ----------------------
    def _handle_command(self, session_id: str, cmd: str, lang: str) -> str:
        raw = cmd.strip()
        c = raw.strip().lower()

        if c in {"/help", "/?"}:
            return self.tools.help_text()

        if c == "/reset":
            self.store.reset_session(session_id)
            return tr(lang, "session_cleared")

        if c == "/export":
            return "Use the UI button 'Export' or open `/api/export?session_id=...` to download JSON."

        if c == "/memory":
            facts = self.store.list_facts(session_id)
            user_facts = {k: v for k, v in facts.items() if not k.startswith("__")}
            if not user_facts:
                return tr(lang, "no_facts")
            lines = [tr(lang, "saved_facts")]
            for k, v in user_facts.items():
                lines.append(f"- **{k}**: {v['value']} _(confidence {v['confidence']:.2f})_")
            return "\n".join(lines)

        if c.startswith("/lang"):
            # /lang or /lang en
            parts = raw.split()
            if len(parts) == 1:
                cur = normalize_lang((self.store.list_facts(session_id).get("preferred_language") or {}).get("value")) or "en"
                return tr(lang, "language_show", lang_name=lang_name(cur), lang_code=cur) + "\n" + tr(lang, "language_help")
            target = normalize_lang(parts[1])
            if not target:
                return tr(lang, "language_help")
            self.store.upsert_fact(session_id, "preferred_language", target, confidence=1.0)
            return tr(lang, "language_set", lang_name=lang_name(target), lang_code=target)

        # Aliases for knowledge pack help
        if c in {"/packs", "/knowledge"}:
            return (
                "To manage offline knowledge packs, use:\n"
                "- `packs list`\n"
                "- `packs status`\n"
                "- `packs howto`\n"
                "Or run: `python scripts/packs.py list`"
            )

        return tr(lang, "unknown_command")

    # ---------------------- Facts ----------------------
    def _extract_facts(self, session_id: str, user_text: str) -> None:
        text = user_text.strip()
        lower = text.lower()

        # English patterns
        m = re.search(r"\bmy name is\s+([A-Za-z0-9_\- ]{2,40})\b", text, flags=re.I)
        if m:
            self.store.upsert_fact(session_id, "user_name", m.group(1).strip(), confidence=0.95)

        m = re.search(r"\bcall me\s+([A-Za-z0-9_\- ]{2,40})\b", text, flags=re.I)
        if m:
            self.store.upsert_fact(session_id, "preferred_name", m.group(1).strip(), confidence=0.9)

        # Indonesian patterns
        m = re.search(r"\bnama\s+saya\s+([A-Za-z0-9_\- ]{2,40})\b", text, flags=re.I)
        if m:
            self.store.upsert_fact(session_id, "user_name", m.group(1).strip(), confidence=0.95)

        m = re.search(r"\baku\s+bernama\s+([A-Za-z0-9_\- ]{2,40})\b", text, flags=re.I)
        if m:
            self.store.upsert_fact(session_id, "user_name", m.group(1).strip(), confidence=0.95)

        # If user says "timezone: ..."
        m = re.search(r"\btimezone\s*(?:is|:)\s*([A-Za-z_\-/]+)\b", text, flags=re.I)
        if m:
            self.store.upsert_fact(session_id, "timezone", m.group(1).strip(), confidence=0.8)

        # If user wants the assistant name/persona
        if "zxyphorz ai" in lower:
            self.store.upsert_fact(session_id, "assistant_name", "Zxyphorz AI", confidence=1.0)

        # Language preference phrases (best-effort)
        m = re.search(r"\b(speak|respond|reply)\s+in\s+(english|indonesian|bahasa|spanish|french|portuguese|chinese|mandarin|japanese)\b", lower)
        if m:
            target = normalize_lang(m.group(2))
            if target:
                self.store.upsert_fact(session_id, "preferred_language", target, confidence=0.9)

    def _maybe_refresh_summary_fact(self, session_id: str) -> None:
        recent = self.store.recent_messages(session_id, limit=30)
        if len(recent) < 12:
            return
        assistant_turns = sum(1 for m in recent if m.role == "assistant")
        if assistant_turns % 10 != 0:
            return

        transcript = []
        for m in recent[-18:]:
            transcript.append(f"{m.role.upper()}: {m.content}")
        summary = _summarize(" ".join(transcript), max_sentences=3)
        if summary:
            self.store.upsert_fact(session_id, "conversation_summary", summary, confidence=0.65)

    # ---------------------- Chat mode ----------------------
    def _chat_reply(self, session_id: str, user_text: str, lang: str) -> Tuple[str, Dict[str, Any]]:
        facts = self.store.list_facts(session_id)
        preferred_name = (facts.get("preferred_name") or {}).get("value") or (facts.get("user_name") or {}).get("value")
        user_name_line = tr(lang, "greeting_named", name=preferred_name) if preferred_name else tr(lang, "greeting_generic")

        hits = self.kb.search(user_text, k=4, lang_hint=lang)
        sources = []
        context_bits = []
        for c, score in hits:
            sources.append({"title": c.title, "file": c.source_file, "lang": c.lang, "score": round(score, 4)})
            context_bits.append(f"- {c.text} (Source: {c.title})")

        summary = (facts.get("conversation_summary") or {}).get("value")

        # Simple intent heuristics (works across languages reasonably well)
        lower = user_text.lower()
        is_question = user_text.strip().endswith("?") or lower.startswith(("what", "why", "how", "can", "could", "do ", "does ", "apa", "bagaimana", "kenapa"))
        wants_project = any(k in lower for k in ["project", "repo", "github", "portfolio", "build", "buatkan"])
        wants_help = any(k in lower for k in ["help", "guide", "steps", "how to", "tolong", "cara"])

        lines: List[str] = []
        lines.append(user_name_line)
        lines.append("")

        if wants_project:
            # Keep this in English by design (portfolio guidance is usually written in English)
            lines.append("If you're building a portfolio repo, here’s a strong path:")
            lines.append("- Pick one core feature and make it polished (docs, tests, clean UI).")
            lines.append("- Add 2–4 supporting features that show engineering depth.")
            lines.append("- Keep everything runnable with one command.")
        elif is_question or wants_help:
            lines.append("Here’s what I can tell you:")
        else:
            lines.append("Got it. Here’s my best response:")

        if context_bits:
            lines.append("")
            lines.append(f"### {tr(lang, 'context_title')}")
            lines.extend(context_bits[:4])

            lines.append("")
            lines.append(f"### {tr(lang, 'answer_title')}")
            lines.append(self._compose_answer(user_text, context_bits, summary=summary))
        else:
            lines.append("")
            lines.append(self._fallback_answer(user_text))

        lines.append("")
        lines.append(f"### {tr(lang, 'next_actions_title')}")
        lines.append(f"- {tr(lang, 'next_action_1')}")
        lines.append(f"- {tr(lang, 'next_action_2')}")

        return "\n".join(lines), {"sources": sources, "has_kb": bool(context_bits)}

    def _compose_answer(self, user_text: str, context_bits: List[str], summary: Optional[str]) -> str:
        q = normalize_ws(user_text)

        intro = (
            f"Based on what you asked — **{q}** — the key idea is to use the most relevant information "
            f"and apply it in a clear, step-by-step way."
        )
        if summary:
            intro += f" (Quick context from our earlier chat: {summary})"

        tips = [
            "Start small, then iterate—clean structure beats random complexity.",
            "Keep inputs/outputs explicit so behavior stays predictable.",
            "Use retrieval (your knowledge packs) when you need real-world coverage offline.",
            "Add lightweight checks and clear error messages for reliability.",
        ]

        return intro + "\n\n" + "\n".join(f"- {t}" for t in tips)

    def _fallback_answer(self, user_text: str) -> str:
        t = user_text.strip()
        lower = t.lower()

        if any(k in lower for k in ["hello", "hi", "halo"]):
            return "Hello! Tell me what you want to build or learn, and I’ll guide you."

        if "?" in t:
            return (
                "I might need a tiny bit more detail to answer precisely.\n\n"
                "Try adding:\n"
                "- what you’re trying to achieve\n"
                "- any constraints (offline, speed, UI, etc.)\n"
                "- what you’ve tried so far"
            )

        return (
            "I understand. If you tell me your exact goal, I can respond with a concrete plan.\n"
            "Example: “I want a local AI assistant with notes + todo + modern web UI.”"
        )
