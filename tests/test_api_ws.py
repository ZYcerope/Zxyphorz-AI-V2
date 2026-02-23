from __future__ import annotations

import json
import unittest


try:
    # FastAPI provides a TestClient wrapper (Starlette under the hood)
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    TestClient = None  # type: ignore


@unittest.skipUnless(TestClient is not None, "FastAPI TestClient not available in this environment")
class TestAPIAndWebSocket(unittest.TestCase):
    """API-level tests (no real network required).

    These tests are extremely valuable for your GitHub repo because they prove:
    - the FastAPI app imports cleanly
    - core endpoints return expected shapes
    - WebSocket streaming protocol is consistent

    They also help you avoid regressions when you add new features.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Importing backend.app will create the global engine and SQLite file in data/storage.
        # That's OK for tests; we also use /api/reset to keep sessions clean.
        from backend.app import app

        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("assistant"), "Zxyphorz AI")
        self.assertIn("version", data)

    def test_chat_endpoint_creates_session_and_replies(self) -> None:
        payload = {"message": "hello", "session_id": None, "language": "en"}
        r = self.client.post("/api/chat", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("session_id", data)
        self.assertIn("reply", data)
        self.assertIn("meta", data)
        self.assertTrue(len(data["session_id"]) >= 8)
        self.assertTrue(len(data["reply"]) > 0)

    def test_reset_and_export_roundtrip(self) -> None:
        # Create a session
        r1 = self.client.post(
            "/api/chat",
            json={"message": "remember this: api test note", "session_id": None},
        )
        sid = r1.json()["session_id"]

        # Export should contain messages
        r2 = self.client.get("/api/export", params={"session_id": sid})
        self.assertEqual(r2.status_code, 200)
        data = r2.json()
        self.assertEqual(data["session_id"], sid)
        self.assertIn("messages", data)

        # Reset
        r3 = self.client.post("/api/reset", json={"message": "x", "session_id": sid})
        self.assertEqual(r3.status_code, 200)
        self.assertTrue(r3.json().get("ok"))

        # Export after reset should show a fresh session structure
        r4 = self.client.get("/api/export", params={"session_id": sid})
        self.assertEqual(r4.status_code, 200)
        data2 = r4.json()
        self.assertEqual(data2["session_id"], sid)
        self.assertIn("facts", data2)
        self.assertIn("todos", data2)

    def test_kb_search_endpoint(self) -> None:
        r = self.client.get("/api/kb/search", params={"q": "BM25", "k": 3, "language": "en"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["q"], "BM25")
        hits = data.get("hits")
        self.assertIsInstance(hits, list)
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("text", hits[0])
        self.assertIn("score", hits[0])

    def test_websocket_streaming_protocol(self) -> None:
        # WebSocket should stream: start -> delta... -> end
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"message": "What is RAG?", "session_id": None, "language": "en"}))

            start = json.loads(ws.receive_text())
            self.assertEqual(start.get("type"), "start")
            sid = start.get("session_id")
            self.assertTrue(sid)

            # Collect deltas until end
            text_parts = []
            while True:
                msg = json.loads(ws.receive_text())
                if msg.get("type") == "delta":
                    text_parts.append(msg.get("text", ""))
                elif msg.get("type") == "end":
                    break
                elif msg.get("type") == "error":
                    self.fail(f"WebSocket error: {msg}")

            full = "".join(text_parts).strip()
            self.assertGreater(len(full), 20)
            self.assertIn("rag", full.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
