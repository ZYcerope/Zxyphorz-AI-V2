from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .utils import utc_now_iso


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  title TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_created
ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.5,
  updated_at TEXT NOT NULL,
  UNIQUE(session_id, key),
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS todos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  item TEXT NOT NULL,
  is_done INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
"""


@dataclass
class Message:
    role: str
    content: str
    created_at: str


class MemoryStore:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path.as_posix(), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # --- sessions ---
    def touch_session(self, session_id: str, title: Optional[str] = None) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            exists = cur.fetchone() is not None
            if not exists:
                conn.execute(
                    "INSERT INTO sessions(session_id, created_at, updated_at, title) VALUES(?,?,?,?)",
                    (session_id, now, now, title),
                )
            else:
                if title is not None:
                    conn.execute(
                        "UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                        (now, title, session_id),
                    )
                else:
                    conn.execute(
                        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                        (now, session_id),
                    )

    def reset_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM facts WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM notes WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM todos WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    # --- messages ---
    def add_message(self, session_id: str, role: str, content: str) -> None:
        self.touch_session(session_id)
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
                (session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def recent_messages(self, session_id: str, limit: int = 20) -> List[Message]:
        self.touch_session(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        rows = list(reversed(rows))
        return [Message(role=r["role"], content=r["content"], created_at=r["created_at"]) for r in rows]

    # --- facts ---
    def upsert_fact(self, session_id: str, key: str, value: str, confidence: float = 0.7) -> None:
        self.touch_session(session_id)
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO facts(session_id, key, value, confidence, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(session_id, key)
                DO UPDATE SET value=excluded.value, confidence=excluded.confidence, updated_at=excluded.updated_at
                """,
                (session_id, key, value, float(confidence), now),
            )

    def list_facts(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        self.touch_session(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, confidence, updated_at FROM facts WHERE session_id = ? ORDER BY key ASC",
                (session_id,),
            ).fetchall()
        return {r["key"]: {"value": r["value"], "confidence": r["confidence"], "updated_at": r["updated_at"]} for r in rows}

    # --- notes ---
    def add_note(self, session_id: str, note: str) -> None:
        self.touch_session(session_id)
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO notes(session_id, note, created_at) VALUES(?,?,?)",
                (session_id, note, now),
            )

    def list_notes(self, session_id: str, limit: int = 50) -> List[Dict[str, str]]:
        self.touch_session(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT note, created_at FROM notes WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"note": r["note"], "created_at": r["created_at"]} for r in rows]

    # --- todo ---
    def add_todo(self, session_id: str, item: str) -> int:
        self.touch_session(session_id)
        now = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO todos(session_id, item, is_done, created_at, updated_at) VALUES(?,?,?,?,?)",
                (session_id, item, 0, now, now),
            )
            return int(cur.lastrowid)

    def list_todos(self, session_id: str, include_done: bool = True) -> List[Dict[str, Any]]:
        self.touch_session(session_id)
        q = "SELECT id, item, is_done, created_at, updated_at FROM todos WHERE session_id = ?"
        params: List[Any] = [session_id]
        if not include_done:
            q += " AND is_done = 0"
        q += " ORDER BY is_done ASC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(q, params).fetchall()
        return [
            {
                "id": int(r["id"]),
                "item": r["item"],
                "is_done": bool(r["is_done"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def set_todo_done(self, session_id: str, todo_id: int, is_done: bool) -> bool:
        self.touch_session(session_id)
        now = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE todos SET is_done = ?, updated_at = ? WHERE session_id = ? AND id = ?",
                (1 if is_done else 0, now, session_id, int(todo_id)),
            )
            return cur.rowcount > 0

    # --- export ---
    def export_session(self, session_id: str) -> Dict[str, Any]:
        self.touch_session(session_id)
        return {
            "session_id": session_id,
            "facts": self.list_facts(session_id),
            "notes": self.list_notes(session_id),
            "todos": self.list_todos(session_id, include_done=True),
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at}
                for m in self.recent_messages(session_id, limit=5000)
            ],
        }
