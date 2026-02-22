from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Supported languages (ISO-ish)
# - en: English
# - zh: Mandarin Chinese (Simplified/Traditional mixed)
# - ja: Japanese
# - fr: French
# - pt: Portuguese
# - es: Spanish
# - id: Indonesian
SUPPORTED_LANGS: Dict[str, str] = {
    "en": "English",
    "zh": "Mandarin Chinese",
    "ja": "Japanese",
    "fr": "French",
    "pt": "Portuguese",
    "es": "Spanish",
    "id": "Indonesian",
}


def normalize_lang(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    c = code.strip().lower()
    aliases = {
        "eng": "en", "english": "en",
        "cn": "zh", "zh-cn": "zh", "zh-hans": "zh", "mandarin": "zh", "chinese": "zh",
        "jp": "ja", "jpn": "ja", "japanese": "ja",
        "fra": "fr", "french": "fr",
        "por": "pt", "pt-br": "pt", "portuguese": "pt",
        "spa": "es", "spanish": "es",
        "indo": "id", "bahasa": "id", "indonesian": "id",
    }
    c = aliases.get(c, c)
    return c if c in SUPPORTED_LANGS else None


@dataclass(frozen=True)
class LangGuess:
    code: str
    confidence: float


# Small stopword seeds for rough language detection (offline, heuristic)
_STOPWORDS = {
    "en": {"the", "and", "is", "are", "what", "how", "why", "can", "do", "with", "from"},
    "id": {"yang", "dan", "atau", "itu", "ini", "apa", "bagaimana", "kenapa", "bisa", "dengan", "dari"},
    "es": {"el", "la", "y", "o", "que", "cómo", "por", "para", "con", "desde"},
    "fr": {"le", "la", "et", "ou", "que", "comment", "pour", "avec", "depuis"},
    "pt": {"o", "a", "e", "ou", "que", "como", "por", "para", "com", "desde"},
}


def _contains_hiragana_katakana(text: str) -> bool:
    # Hiragana: 3040–309F, Katakana: 30A0–30FF, Katakana Phonetic Extensions: 31F0–31FF
    return bool(re.search(r"[\u3040-\u30FF\u31F0-\u31FF]", text))


def _contains_cjk(text: str) -> bool:
    # CJK Unified Ideographs: 4E00–9FFF
    return bool(re.search(r"[\u4E00-\u9FFF]", text))


def detect_language(text: str) -> LangGuess:
    """Very small heuristic detector.

    It is intentionally simple and deterministic. The goal is not perfect
    classification—only a good-enough guess for UX.

    Returns: (lang_code, confidence)
    """
    t = (text or "").strip()
    if not t:
        return LangGuess("en", 0.1)

    # Japanese first (hiragana/katakana is a strong signal)
    if _contains_hiragana_katakana(t):
        return LangGuess("ja", 0.95)

    # Chinese next (CJK without kana often means Chinese)
    if _contains_cjk(t):
        return LangGuess("zh", 0.85)

    # Latin languages: stopword scoring
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", t.lower())
    if not words:
        return LangGuess("en", 0.2)

    scores: Dict[str, int] = {k: 0 for k in _STOPWORDS.keys()}
    for w in words[:120]:
        for lang, sw in _STOPWORDS.items():
            if w in sw:
                scores[lang] += 1

    best = max(scores.items(), key=lambda kv: kv[1])
    best_lang, best_score = best
    total = sum(scores.values())

    # Confidence heuristic
    if best_score == 0:
        return LangGuess("en", 0.35)
    conf = min(0.9, 0.45 + (best_score / max(1, len(words))) * 4.0)
    # Bias to English if tie-ish
    if total > 0 and best_score / total < 0.4:
        conf = min(conf, 0.6)
    return LangGuess(best_lang, conf)


# UI/response strings
_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "greeting_generic": "Hi,",
        "greeting_named": "Hi {name},",
        "context_title": "Relevant context I found",
        "answer_title": "Answer",
        "next_actions_title": "Next actions",
        "next_action_1": "If you want, paste your goal in 1 sentence and I’ll propose a step-by-step plan.",
        "next_action_2": "Type `/help` to see built-in tools (notes, todo, summaries, language settings, knowledge packs).",
        "unknown_command": "Unknown command. Try `/help`.",
        "session_cleared": "Session memory cleared. Start fresh whenever you’re ready.",
        "no_facts": "I don't have any saved facts for this session yet.",
        "saved_facts": "Saved session facts:",
        "language_set": "Language set to **{lang_name}** ({lang_code}).",
        "language_show": "Current language: **{lang_name}** ({lang_code}).",
        "language_help": "Use `/lang <code>` (en/zh/ja/fr/pt/es/id) or set it in the UI dropdown.",
    },
    "id": {
        "greeting_generic": "Halo,",
        "greeting_named": "Halo {name},",
        "context_title": "Konteks relevan yang aku temukan",
        "answer_title": "Jawaban",
        "next_actions_title": "Langkah selanjutnya",
        "next_action_1": "Kalau mau, tulis tujuanmu dalam 1 kalimat dan aku buatkan rencana langkah demi langkah.",
        "next_action_2": "Ketik `/help` untuk melihat tools (catatan, todo, ringkasan, bahasa, knowledge packs).",
        "unknown_command": "Perintah tidak dikenal. Coba `/help`.",
        "session_cleared": "Memori sesi dibersihkan. Kita mulai dari nol ya.",
        "no_facts": "Aku belum menyimpan fakta apa pun untuk sesi ini.",
        "saved_facts": "Fakta sesi yang tersimpan:",
        "language_set": "Bahasa diatur ke **{lang_name}** ({lang_code}).",
        "language_show": "Bahasa saat ini: **{lang_name}** ({lang_code}).",
        "language_help": "Gunakan `/lang <kode>` (en/zh/ja/fr/pt/es/id) atau pilih di dropdown UI.",
    },
    "es": {
        "greeting_generic": "Hola,",
        "greeting_named": "Hola {name},",
        "context_title": "Contexto relevante que encontré",
        "answer_title": "Respuesta",
        "next_actions_title": "Próximos pasos",
        "next_action_1": "Si quieres, escribe tu objetivo en 1 frase y haré un plan paso a paso.",
        "next_action_2": "Escribe `/help` para ver herramientas (notas, tareas, resúmenes, idioma, paquetes de conocimiento).",
        "unknown_command": "Comando desconocido. Prueba `/help`.",
        "session_cleared": "Memoria de sesión borrada. Empecemos de nuevo.",
        "no_facts": "Aún no tengo hechos guardados para esta sesión.",
        "saved_facts": "Hechos guardados de la sesión:",
        "language_set": "Idioma configurado a **{lang_name}** ({lang_code}).",
        "language_show": "Idioma actual: **{lang_name}** ({lang_code}).",
        "language_help": "Usa `/lang <código>` (en/zh/ja/fr/pt/es/id) o selecciónalo en la UI.",
    },
    "fr": {
        "greeting_generic": "Bonjour,",
        "greeting_named": "Bonjour {name},",
        "context_title": "Contexte pertinent trouvé",
        "answer_title": "Réponse",
        "next_actions_title": "Prochaines actions",
        "next_action_1": "Si tu veux, écris ton objectif en 1 phrase et je proposerai un plan étape par étape.",
        "next_action_2": "Tape `/help` pour voir les outils (notes, tâches, résumés, langue, packs de connaissances).",
        "unknown_command": "Commande inconnue. Essaie `/help`.",
        "session_cleared": "Mémoire de session effacée. On recommence.",
        "no_facts": "Je n'ai pas encore de faits enregistrés pour cette session.",
        "saved_facts": "Faits enregistrés de la session :",
        "language_set": "Langue définie sur **{lang_name}** ({lang_code}).",
        "language_show": "Langue actuelle : **{lang_name}** ({lang_code}).",
        "language_help": "Utilise `/lang <code>` (en/zh/ja/fr/pt/es/id) ou choisis dans l’interface.",
    },
    "pt": {
        "greeting_generic": "Olá,",
        "greeting_named": "Olá {name},",
        "context_title": "Contexto relevante que encontrei",
        "answer_title": "Resposta",
        "next_actions_title": "Próximas ações",
        "next_action_1": "Se quiser, escreva seu objetivo em 1 frase e eu monto um plano passo a passo.",
        "next_action_2": "Digite `/help` para ver as ferramentas (notas, tarefas, resumos, idioma, pacotes de conhecimento).",
        "unknown_command": "Comando desconhecido. Tente `/help`.",
        "session_cleared": "Memória da sessão apagada. Vamos recomeçar.",
        "no_facts": "Ainda não tenho fatos salvos para esta sessão.",
        "saved_facts": "Fatos salvos da sessão:",
        "language_set": "Idioma definido para **{lang_name}** ({lang_code}).",
        "language_show": "Idioma atual: **{lang_name}** ({lang_code}).",
        "language_help": "Use `/lang <código>` (en/zh/ja/fr/pt/es/id) ou escolha na interface.",
    },
    "zh": {
        "greeting_generic": "你好，",
        "greeting_named": "你好 {name}，",
        "context_title": "我找到的相关上下文",
        "answer_title": "回答",
        "next_actions_title": "下一步",
        "next_action_1": "如果你愿意，用一句话写下你的目标，我会给你一步一步的计划。",
        "next_action_2": "输入 `/help` 查看工具（笔记、待办、摘要、语言、知识包）。",
        "unknown_command": "未知命令。试试 `/help`。",
        "session_cleared": "会话记忆已清除。我们可以重新开始。",
        "no_facts": "这个会话还没有保存任何事实。",
        "saved_facts": "已保存的会话事实：",
        "language_set": "语言已设置为 **{lang_name}**（{lang_code}）。",
        "language_show": "当前语言：**{lang_name}**（{lang_code}）。",
        "language_help": "使用 `/lang <code>`（en/zh/ja/fr/pt/es/id）或在界面下拉框选择。",
    },
    "ja": {
        "greeting_generic": "こんにちは、",
        "greeting_named": "こんにちは {name}、",
        "context_title": "見つかった関連コンテキスト",
        "answer_title": "回答",
        "next_actions_title": "次のアクション",
        "next_action_1": "よければ、目標を1文で書いてください。手順付きの計画を提案します。",
        "next_action_2": "`/help` でツール（メモ、ToDo、要約、言語、知識パック）を確認できます。",
        "unknown_command": "不明なコマンドです。`/help` を試してください。",
        "session_cleared": "セッションの記憶を消去しました。最初からやり直せます。",
        "no_facts": "このセッションにはまだ保存された情報がありません。",
        "saved_facts": "保存されたセッション情報：",
        "language_set": "言語を **{lang_name}**（{lang_code}）に設定しました。",
        "language_show": "現在の言語：**{lang_name}**（{lang_code}）。",
        "language_help": "`/lang <code>`（en/zh/ja/fr/pt/es/id）か、UIのドロップダウンで設定できます。",
    },
}


def tr(lang: str, key: str, **kwargs: str) -> str:
    l = normalize_lang(lang) or "en"
    table = _STRINGS.get(l) or _STRINGS["en"]
    s = table.get(key) or _STRINGS["en"].get(key) or key
    return s.format(**kwargs)


def lang_name(code: str) -> str:
    return SUPPORTED_LANGS.get(code, code)
