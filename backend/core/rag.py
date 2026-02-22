from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .i18n import detect_language, normalize_lang
from .utils import normalize_ws, safe_read_text


STOPWORDS_BY_LANG: Dict[str, set[str]] = {
    "en": {
        "a","an","the","and","or","but","if","then","else","when","while",
        "for","to","of","in","on","at","by","with","as","is","are","was","were","be","been",
        "this","that","these","those","it","its","you","your","i","me","my","we","our","they","them",
        "from","into","over","under","about","above","below","up","down","out","off",
    },
    "id": {
        "yang","dan","atau","tapi","jika","maka","ketika","sementara",
        "untuk","ke","dari","di","pada","oleh","dengan","sebagai","adalah",
        "ini","itu","tersebut","saya","aku","kamu","anda","kita","kami","mereka",
    },
    "es": {"el","la","los","las","y","o","pero","si","entonces","cuando","mientras","para","de","en","con","como","es","son","soy"},
    "fr": {"le","la","les","et","ou","mais","si","donc","quand","pendant","pour","de","en","avec","comme","est","sont","je","tu","nous","vous"},
    "pt": {"o","a","os","as","e","ou","mas","se","então","quando","enquanto","para","de","em","com","como","é","são","eu","você","nós"},
}


def _has_hiragana_katakana(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30FF\u31F0-\u31FF]", text))


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4E00-\u9FFF]", text))


def tokenize(text: str, lang_hint: Optional[str] = None) -> List[str]:
    """Tokenize text for retrieval.

    - For CJK (zh/ja): use character bigrams (plus some single chars) for usable search.
    - For Latin languages: use word tokens with minimal normalization.
    """
    t = (text or "").strip()
    if not t:
        return []

    lang = normalize_lang(lang_hint)
    if lang in {"zh", "ja"} or _has_hiragana_katakana(t) or _has_cjk(t):
        # Keep only CJK + kana characters; ignore punctuation/whitespace.
        chars = [c for c in t if re.match(r"[\u3040-\u30FF\u31F0-\u31FF\u4E00-\u9FFF]", c)]
        if len(chars) < 2:
            return chars
        bigrams = [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
        # Add some singles for rare queries
        singles = chars[::3]
        return bigrams + singles

    # Latin-ish tokenization (keeps accents)
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+", t.lower())
    if not words:
        return []

    sw = STOPWORDS_BY_LANG.get(lang or "en", STOPWORDS_BY_LANG["en"])

    out: List[str] = []
    for w in words:
        if len(w) <= 1:
            continue
        if w in sw:
            continue

        # very light normalization for English plural; safe for other langs too
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("s") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return out


def chunk_text(text: str, max_chars: int = 850) -> List[str]:
    """Split text into readable retrieval chunks."""
    raw_blocks = re.split(r"\n\s*\n", (text or "").strip())
    chunks: List[str] = []
    buf = ""
    for block in raw_blocks:
        b = block.strip()
        if not b:
            continue
        if len(buf) + len(b) + 2 <= max_chars:
            buf = (buf + "\n\n" + b).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = b
    if buf:
        chunks.append(buf)
    return [normalize_ws(c.replace("\n", " ")) for c in chunks if c.strip()]


@dataclass(frozen=True)
class KBChunk:
    chunk_id: str
    title: str
    source_file: str
    lang: str
    text: str
    tokens: Tuple[str, ...]
    tf: Dict[str, int]


class KnowledgeBase:
    """A local knowledge base with BM25-style retrieval (pure Python).

    Sources:
    - `data/knowledge_base/*.md` (small curated docs)
    - `data/knowledge_packs/processed/*.jsonl` (large downloaded corpora; optional)
    """

    def __init__(self, kb_dir: Path, packs_processed_dir: Optional[Path] = None):
        self.kb_dir = kb_dir
        self.packs_processed_dir = packs_processed_dir

        self.chunks: List[KBChunk] = []
        self.df: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.avgdl: float = 0.0
        self._is_ready = False

    def load(self) -> None:
        self.kb_dir.mkdir(parents=True, exist_ok=True)

        chunks: List[KBChunk] = []
        df: Dict[str, int] = {}

        # 1) Markdown docs
        for fp in sorted(self.kb_dir.glob("*.md")):
            text = safe_read_text(fp)
            if not text.strip():
                continue

            # Guess language from content (best-effort)
            guess = detect_language(text)
            lang = guess.code if guess.confidence >= 0.6 else "en"

            title = fp.stem.replace("_", " ").title()
            for idx, ch in enumerate(chunk_text(text)):
                toks = tokenize(ch, lang_hint=lang)
                if not toks:
                    continue
                tf: Dict[str, int] = {}
                for t in toks:
                    tf[t] = tf.get(t, 0) + 1
                # document frequency update (unique tokens per chunk)
                for t in set(toks):
                    df[t] = df.get(t, 0) + 1

                chunks.append(
                    KBChunk(
                        chunk_id=f"md:{fp.stem}:{idx}",
                        title=title,
                        source_file=fp.name,
                        lang=lang,
                        text=ch,
                        tokens=tuple(toks),
                        tf=tf,
                    )
                )

        # 2) Processed knowledge packs (.jsonl)
        if self.packs_processed_dir and self.packs_processed_dir.exists():
            for fp in sorted(self.packs_processed_dir.glob("*.jsonl")):
                self._load_jsonl_pack(fp, chunks, df)

        self.chunks = chunks
        self.df = df

        # BM25 stats
        n_docs = max(1, len(self.chunks))
        total_len = sum(len(c.tokens) for c in self.chunks)
        self.avgdl = max(1.0, total_len / n_docs)

        # IDF
        idf: Dict[str, float] = {}
        for term, dfi in self.df.items():
            # BM25 idf smoothing
            idf[term] = math.log(1 + (n_docs - dfi + 0.5) / (dfi + 0.5))
        self.idf = idf
        self._is_ready = True

    def _load_jsonl_pack(self, fp: Path, chunks: List[KBChunk], df: Dict[str, int]) -> None:
        try:
            raw = fp.read_text(encoding="utf-8")
        except Exception:
            return

        for line_no, line in enumerate(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            text = str(obj.get("text", "")).strip()
            if not text:
                continue

            lang = normalize_lang(str(obj.get("lang", ""))) or "en"
            title = str(obj.get("title", "Knowledge Pack")).strip() or "Knowledge Pack"
            source_file = fp.name

            for idx, ch in enumerate(chunk_text(text)):
                toks = tokenize(ch, lang_hint=lang)
                if not toks:
                    continue
                tf: Dict[str, int] = {}
                for t in toks:
                    tf[t] = tf.get(t, 0) + 1
                for t in set(toks):
                    df[t] = df.get(t, 0) + 1

                chunks.append(
                    KBChunk(
                        chunk_id=f"pack:{fp.stem}:{line_no}:{idx}",
                        title=title,
                        source_file=source_file,
                        lang=lang,
                        text=ch,
                        tokens=tuple(toks),
                        tf=tf,
                    )
                )

    def search(self, query: str, k: int = 4, lang_hint: Optional[str] = None) -> List[Tuple[KBChunk, float]]:
        if not self._is_ready:
            self.load()

        q_tokens = tokenize(query, lang_hint=lang_hint)
        if not q_tokens:
            return []

        scores: List[Tuple[int, float]] = []
        for i, c in enumerate(self.chunks):
            s = self._bm25_score(q_tokens, c)
            if s > 0:
                scores.append((i, s))

        scores.sort(key=lambda x: x[1], reverse=True)
        out: List[Tuple[KBChunk, float]] = []
        for i, s in scores[: max(1, k)]:
            out.append((self.chunks[i], float(s)))
        return out

    def _bm25_score(self, q_tokens: Sequence[str], doc: KBChunk, k1: float = 1.4, b: float = 0.75) -> float:
        if self.avgdl <= 0:
            return 0.0

        score = 0.0
        dl = max(1, len(doc.tokens))
        for t in q_tokens:
            tf = doc.tf.get(t, 0)
            if tf <= 0:
                continue
            idf = self.idf.get(t, 0.0)
            denom = tf + k1 * (1.0 - b + b * (dl / self.avgdl))
            score += idf * (tf * (k1 + 1.0)) / denom
        return score
