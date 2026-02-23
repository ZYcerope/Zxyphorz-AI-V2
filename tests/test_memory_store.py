from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class TestMemoryStore(unittest.TestCase):
    """MemoryStore is the foundation for long-term persistence.

    These tests are useful because:
    - they catch schema regressions
    - they verify export format (used by the UI)
    - they verify notes/todos/facts behave consistently
    """

    def setUp(self) -> None:
        from backend.core.memory_store import MemoryStore

        self._tmp = tempfile.TemporaryDirectory(prefix="zxy_mem_")
        self.db = Path(self._tmp.name) / "mem.sqlite3"
        self.store = MemoryStore(self.db)
        self.session_id = "unit-test-session"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_session_touch_and_reset(self) -> None:
        # Touch should create a session row without error.
        self.store.touch_session(self.session_id, title="My Session")

        # Reset should remove session data and not throw.
        self.store.reset_session(self.session_id)

        # After reset, the store should still be usable.
        self.store.touch_session(self.session_id)
        facts = self.store.list_facts(self.session_id)
        self.assertIsInstance(facts, dict)

    def test_messages_roundtrip(self) -> None:
        self.store.add_message(self.session_id, "user", "Hello")
        self.store.add_message(self.session_id, "assistant", "Hi there")

        msgs = self.store.recent_messages(self.session_id, limit=10)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].role, "user")
        self.assertEqual(msgs[0].content, "Hello")
        self.assertEqual(msgs[1].role, "assistant")
        self.assertEqual(msgs[1].content, "Hi there")

    def test_facts_upsert_and_list(self) -> None:
        self.store.upsert_fact(self.session_id, "assistant_name", "Zxyphorz AI", confidence=1.0)
        self.store.upsert_fact(self.session_id, "assistant_creator", "Xceon", confidence=1.0)
        # Update existing key
        self.store.upsert_fact(self.session_id, "assistant_creator", "Xceon", confidence=0.9)

        facts = self.store.list_facts(self.session_id)
        self.assertIn("assistant_name", facts)
        self.assertIn("assistant_creator", facts)
        self.assertEqual(facts["assistant_creator"]["value"], "Xceon")
        self.assertGreaterEqual(float(facts["assistant_creator"]["confidence"]), 0.8)

    def test_notes_add_and_list(self) -> None:
        self.store.add_note(self.session_id, "First note")
        self.store.add_note(self.session_id, "Second note")

        notes = self.store.list_notes(self.session_id)
        self.assertGreaterEqual(len(notes), 2)
        # Notes are returned newest-first
        self.assertEqual(notes[0]["note"], "Second note")
        self.assertEqual(notes[1]["note"], "First note")

    def test_todos_add_list_and_done(self) -> None:
        id1 = self.store.add_todo(self.session_id, "Write README")
        id2 = self.store.add_todo(self.session_id, "Add tests")
        self.assertIsInstance(id1, int)
        self.assertIsInstance(id2, int)

        todos = self.store.list_todos(self.session_id, include_done=True)
        self.assertEqual(len(todos), 2)
        self.assertTrue(any(t["item"] == "Write README" for t in todos))

        # Mark done
        ok = self.store.set_todo_done(self.session_id, id1, True)
        self.assertTrue(ok)

        todos2 = self.store.list_todos(self.session_id, include_done=True)
        done = [t for t in todos2 if t["id"] == id1][0]
        self.assertTrue(done["is_done"])

        # Hide done
        open_only = self.store.list_todos(self.session_id, include_done=False)
        self.assertEqual(len(open_only), 1)
        self.assertEqual(open_only[0]["item"], "Add tests")

    def test_export_session_contract(self) -> None:
        self.store.add_message(self.session_id, "user", "remember this: hello")
        self.store.upsert_fact(self.session_id, "foo", "bar", confidence=0.7)
        self.store.add_note(self.session_id, "Note A")
        tid = self.store.add_todo(self.session_id, "Todo A")
        self.store.set_todo_done(self.session_id, tid, True)

        data = self.store.export_session(self.session_id)
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("facts", data)
        self.assertIn("notes", data)
        self.assertIn("todos", data)
        self.assertIn("messages", data)

        self.assertEqual(data["facts"]["foo"]["value"], "bar")
        self.assertGreaterEqual(len(data["notes"]), 1)
        self.assertGreaterEqual(len(data["todos"]), 1)
        self.assertGreaterEqual(len(data["messages"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
