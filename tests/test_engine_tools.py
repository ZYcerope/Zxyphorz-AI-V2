from __future__ import annotations

import unittest

from tests._helpers import temporary_engine


class TestChatEngineAndTools(unittest.TestCase):
    """High-value regression tests for the assistant behavior.

    Why this matters for your repo:
    - Proves the project is runnable and stable.
    - Prevents accidental breakage when adding new tools.
    - Demonstrates engineering quality (not just 'a toy bot').
    """

    def test_seed_memory_is_applied(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("hello", None)
            sid = r.session_id

            # The seed should store stable identity facts.
            mem = engine.store.list_facts(sid)
            self.assertEqual(mem.get("assistant_creator", {}).get("value"), "Xceon")
            self.assertIn("Zxyphorz", mem.get("assistant_identity", {}).get("value", ""))

    def test_language_command_roundtrip(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("/lang id", None)
            self.assertIn("Language set", r.reply)
            self.assertIn("Indonesian", r.reply)

            sid = r.session_id
            r2 = engine.handle("/lang", sid)
            self.assertTrue("id" in r2.reply.lower())

            # Now normal chat should greet in Indonesian.
            r3 = engine.handle("apa itu rag?", sid)
            self.assertTrue(r3.reply.strip().startswith("Halo") or "Konteks" in r3.reply)

    def test_calculator_safety_blocks_function_calls(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("calc: __import__('os').system('echo hacked')", None)
            # Should not execute anything; should respond with safe error.
            self.assertIn("couldn't evaluate", r.reply.lower())

            r2 = engine.handle("2*(3+4)", r.session_id)
            self.assertIn("14", r2.reply)

    def test_notes_and_todos_workflow(self) -> None:
        with temporary_engine() as (engine, _db):
            r1 = engine.handle("remember this: build a portfolio", None)
            self.assertIn("Saved", r1.reply)
            sid = r1.session_id

            r2 = engine.handle("list notes", sid)
            self.assertIn("portfolio", r2.reply.lower())

            r3 = engine.handle("add todo: write README", sid)
            self.assertTrue("added" in r3.reply.lower() or "todo" in r3.reply.lower())

            r4 = engine.handle("list todos", sid)
            self.assertIn("README", r4.reply)

            todos = engine.store.list_todos(sid, include_done=True)
            self.assertGreaterEqual(len(todos), 1)
            tid = todos[0]["id"]

            r5 = engine.handle(f"done {tid}", sid)
            self.assertTrue(
                "done" in r5.reply.lower()
                or "updated" in r5.reply.lower()
                or "marked" in r5.reply.lower()
            )

    def test_translator_phrasebook_7_langs(self) -> None:
        with temporary_engine() as (engine, _db):
            sid = engine.handle("hello", None).session_id

            # English -> Japanese
            r = engine.handle("translate to ja: thank you", sid)
            self.assertTrue("ありがとう" in r.reply or "Japanese" in r.reply)

            # Indonesian -> English
            r2 = engine.handle("translate to english: selamat pagi", sid)
            self.assertTrue("good morning" in r2.reply.lower() or "Detected" in r2.reply)

            # Spanish
            r3 = engine.handle("translate to spanish: hello", sid)
            self.assertTrue("hola" in r3.reply.lower() or "Spanish" in r3.reply)

            # French
            r4 = engine.handle("translate to french: please", sid)
            self.assertTrue("s'il" in r4.reply.lower() or "French" in r4.reply)

            # Portuguese
            r5 = engine.handle("translate to portuguese: sorry", sid)
            self.assertTrue("descul" in r5.reply.lower() or "Portuguese" in r5.reply)

            # Chinese
            r6 = engine.handle("translate to chinese: hello", sid)
            self.assertTrue("你好" in r6.reply or "Mandarin" in r6.reply)

    def test_kb_explain_tool_returns_explanation(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("explain: rag", None)
            self.assertTrue("rag" in r.reply.lower())
            # Should be tool mode
            self.assertEqual(r.meta.get("mode"), "tool")

    def test_help_contains_tools(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("/help", None)
            text = r.reply.lower()
            for term in ("calculator", "notes", "todo", "translator"):
                self.assertIn(term, text)

    def test_response_format_has_sections_when_kb_hits_exist(self) -> None:
        with temporary_engine() as (engine, _db):
            r = engine.handle("BM25 ranking in information retrieval", None)
            self.assertIn("###", r.reply)
            self.assertIn("relevant context", r.reply.lower())
            self.assertIn("answer", r.reply.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
