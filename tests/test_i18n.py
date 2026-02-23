from __future__ import annotations

import unittest
from tests._helpers import ensure_import_paths


class TestI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_import_paths()

    def test_normalize_lang_aliases(self) -> None:
        from backend.core.i18n import normalize_lang

        self.assertEqual(normalize_lang("english"), "en")
        self.assertEqual(normalize_lang("bahasa"), "id")
        self.assertEqual(normalize_lang("zh-cn"), "zh")
        self.assertEqual(normalize_lang("jpn"), "ja")
        self.assertEqual(normalize_lang("pt-br"), "pt")
        self.assertIsNone(normalize_lang("xx"))

    def test_detect_language_basic(self) -> None:
        from backend.core.i18n import detect_language

        self.assertEqual(detect_language("こんにちは").code, "ja")
        self.assertEqual(detect_language("你好").code, "zh")
        self.assertEqual(detect_language("apa itu RAG dan bagaimana cara kerja nya").code, "id")
        self.assertEqual(detect_language("what is retrieval augmented generation").code, "en")

    def test_tr_fallback(self) -> None:
        from backend.core.i18n import tr

        s = tr("xx", "unknown_command")
        self.assertIn("Unknown command", s)
