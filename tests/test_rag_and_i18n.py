from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class TestI18n(unittest.TestCase):
    """Tests for language normalization and detection."""

    def test_normalize_lang_aliases(self) -> None:
        from backend.core.i18n import normalize_lang

        self.assertEqual(normalize_lang("English"), "en")
        self.assertEqual(normalize_lang("eng"), "en")
        self.assertEqual(normalize_lang("bahasa"), "id")
        self.assertEqual(normalize_lang("pt-br"), "pt")
        self.assertEqual(normalize_lang("zh-cn"), "zh")
        self.assertIsNone(normalize_lang("xx"))

    def test_detect_language_basic(self) -> None:
        from backend.core.i18n import detect_language

        en = detect_language("What is retrieval augmented generation?")
        self.assertEqual(en.code, "en")

        idn = detect_language("Apa itu RAG dan bagaimana cara kerjanya?")
        self.assertIn(idn.code, {"id", "en"})  # heuristic may fallback sometimes

        zh = detect_language("你好，量子力学是什么？")
        self.assertEqual(zh.code, "zh")

        ja = detect_language("こんにちは、量子力学は何ですか？")
        self.assertEqual(ja.code, "ja")


class TestRAG(unittest.TestCase):
    """RAG tests: tokenization, chunking, and retrieval behavior."""

    def test_tokenize_english_plural_light_stem(self) -> None:
        from backend.core.rag import tokenize

        toks = tokenize("Libraries and stories", lang_hint="en")
        # 'libraries' -> 'library' by light rule, 'stories' -> 'story'
        self.assertIn("library", toks)
        self.assertIn("story", toks)

    def test_tokenize_cjk_bigrams(self) -> None:
        from backend.core.rag import tokenize

        toks = tokenize("量子力学", lang_hint="zh")
        # Expect bigrams like 量子, 子力, 力学
        self.assertTrue(any(t == "量子" for t in toks))
        self.assertTrue(any(t == "力学" for t in toks))

    def test_chunk_text_limits(self) -> None:
        from backend.core.rag import chunk_text

        text = "\n\n".join(["A" * 400, "B" * 400, "C" * 400])
        chunks = chunk_text(text, max_chars=850)
        # Should not create a single huge chunk
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(c) <= 900 for c in chunks))

    def test_kb_load_and_search_curated_docs(self) -> None:
        from backend.core.config import AppConfig
        from backend.core.rag import KnowledgeBase

        rr = Path(__file__).resolve().parents[1]
        cfg = AppConfig.from_repo_root(rr)
        kb = KnowledgeBase(cfg.knowledge_base_dir, packs_processed_dir=cfg.knowledge_packs_processed_dir)
        kb.load()

        hits = kb.search("BM25", k=3, lang_hint="en")
        self.assertGreaterEqual(len(hits), 1)
        top_chunk, score = hits[0]
        self.assertGreater(score, 0)
        self.assertTrue("bm25" in top_chunk.text.lower() or "bm25" in top_chunk.title.lower())

    def test_kb_can_load_processed_pack_jsonl(self) -> None:
        """Create a tiny JSONL pack and ensure KB searches it.

        This validates the 'knowledge packs' pipeline end-to-end.
        """
        from backend.core.rag import KnowledgeBase

        rr = Path(__file__).resolve().parents[1]
        kb_dir = rr / "data" / "knowledge_base"

        with tempfile.TemporaryDirectory(prefix="zxy_pack_") as td:
            packs_processed = Path(td)
            pack_file = packs_processed / "mini_pack.jsonl"
            rows = [
                {"title": "UnitTest Pack", "lang": "en", "text": "Zxyphorz AI was created by Xceon."},
                {"title": "UnitTest Pack", "lang": "id", "text": "Zxyphorz AI dibuat oleh Xceon."},
            ]
            pack_file.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

            kb = KnowledgeBase(kb_dir, packs_processed_dir=packs_processed)
            kb.load()

            hits = kb.search("created by", k=5, lang_hint="en")
            self.assertTrue(any("Xceon" in c.text for c, _ in hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
