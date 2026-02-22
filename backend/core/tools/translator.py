from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..i18n import SUPPORTED_LANGS, normalize_lang
from .base import Tool, ToolResult
from .utils import strip_prefix


# A tiny offline phrasebook (not a full translator).
# Designed for demo + utility without external APIs.
PHRASES: Dict[str, Dict[str, str]] = {
    "hello": {"en": "hello", "id": "halo", "es": "hola", "fr": "bonjour", "pt": "olá", "zh": "你好", "ja": "こんにちは"},
    "thank you": {"en": "thank you", "id": "terima kasih", "es": "gracias", "fr": "merci", "pt": "obrigado", "zh": "谢谢", "ja": "ありがとう"},
    "good morning": {"en": "good morning", "id": "selamat pagi", "es": "buenos días", "fr": "bonjour", "pt": "bom dia", "zh": "早上好", "ja": "おはようございます"},
    "good night": {"en": "good night", "id": "selamat malam", "es": "buenas noches", "fr": "bonne nuit", "pt": "boa noite", "zh": "晚安", "ja": "おやすみなさい"},
    "please": {"en": "please", "id": "tolong", "es": "por favor", "fr": "s'il vous plaît", "pt": "por favor", "zh": "请", "ja": "お願いします"},
    "sorry": {"en": "sorry", "id": "maaf", "es": "lo siento", "fr": "désolé", "pt": "desculpa", "zh": "对不起", "ja": "ごめんなさい"},
}


def _reverse_lookup(text: str) -> Optional[Tuple[str, str]]:
    """Return (canonical_key, detected_lang) if the phrase is in our phrasebook."""
    t = (text or "").strip().lower()
    for key, mapping in PHRASES.items():
        for lang, phrase in mapping.items():
            if t == phrase.strip().lower():
                return key, lang
    return None


class TranslatorTool(Tool):
    name = "translator"
    description = "Tiny offline phrase translator (7 languages)."
    examples = "translate to spanish: hello / translate to english: selamat pagi"

    def match(self, user_text: str) -> bool:
        t = user_text.strip().lower()
        return t.startswith("translate") or t.startswith("translate to")

    def run(self, user_text: str, session_id: str) -> ToolResult:
        t = user_text.strip()
        lower = t.lower()

        # Parse: "translate to <lang>: <text>"
        payload = strip_prefix(
            t,
            "translate to english:",
            "translate to indonesian:",
            "translate to spanish:",
            "translate to french:",
            "translate to portuguese:",
            "translate to mandarin:",
            "translate to chinese:",
            "translate to japanese:",
            "translate to en:",
            "translate to id:",
            "translate to es:",
            "translate to fr:",
            "translate to pt:",
            "translate to zh:",
            "translate to ja:",
            "translate:",
            "translate",
        )

        if not payload:
            return ToolResult(
                True,
                "Examples:\n"
                "- `translate to english: selamat pagi`\n"
                "- `translate to japanese: thank you`\n"
                "- `translate to indonesian: hello`",
                {"tool": self.name},
            )

        # Determine target language
        target: Optional[str] = None
        if "to english" in lower or "to en" in lower:
            target = "en"
        elif "to indonesian" in lower or "to bahasa" in lower or "to id" in lower:
            target = "id"
        elif "to spanish" in lower or "to es" in lower:
            target = "es"
        elif "to french" in lower or "to fr" in lower:
            target = "fr"
        elif "to portuguese" in lower or "to pt" in lower:
            target = "pt"
        elif "to chinese" in lower or "to mandarin" in lower or "to zh" in lower:
            target = "zh"
        elif "to japanese" in lower or "to ja" in lower:
            target = "ja"

        if not target:
            return ToolResult(True, "Say `translate to <en|id|es|fr|pt|zh|ja>: ...`", {"tool": self.name})

        phrase = payload.strip()
        # If user provided canonical key (English), map directly
        canonical_key = phrase.lower()
        if canonical_key in PHRASES and target in PHRASES[canonical_key]:
            return ToolResult(True, f"{SUPPORTED_LANGS[target]}: **{PHRASES[canonical_key][target]}**", {"tool": self.name, "target": target})

        # Reverse lookup (phrase in any language -> canonical -> target)
        rev = _reverse_lookup(phrase)
        if rev:
            key, detected = rev
            out = PHRASES.get(key, {}).get(target)
            if out:
                return ToolResult(
                    True,
                    f"Detected ({SUPPORTED_LANGS.get(detected, detected)}). {SUPPORTED_LANGS[target]}: **{out}**",
                    {"tool": self.name, "target": target, "detected": detected},
                )

        return ToolResult(
            True,
            "Offline translator is intentionally small (phrasebook). Try common phrases like "
            "`hello`, `thank you`, `good morning`, `please`, `sorry`.",
            {"tool": self.name, "target": target},
        )
