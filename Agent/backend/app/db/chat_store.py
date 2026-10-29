"""
app/db/chat_store.py

Persistent Chat History & Conversation Store for ARIA.
Backed by local SQLite (aria_rag.db) with WAL mode for zero-configuration,
robust persistence across server restarts and browser reloads.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("RAG_DB_PATH", str(BACKEND_DIR / "aria_rag.db")))


class ChatStore:
    """Thread-safe SQLite store for conversations and message history."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create conversations and chat_messages tables if they don't exist."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                    ON conversations (user_id, updated_at DESC);
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        intent TEXT,
                        detected_language TEXT,
                        sources TEXT,
                        actions TEXT,
                        structured_data TEXT,
                        latency_ms INTEGER,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_user
                    ON chat_messages (thread_id, user_id, created_at ASC);
                """)
                conn.commit()

    def list_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns list of conversations for user_id, ordered by most recently updated."""
        resolved_limit = limit if isinstance(limit, int) else 50
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM chat_messages m WHERE m.thread_id = c.id AND m.user_id = c.user_id) as message_count
                    FROM conversations c
                    WHERE c.user_id = ?
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, resolved_limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r["id"],
                        "user_id": r["user_id"],
                        "title": r["title"],
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                        "message_count": r["message_count"],
                    }
                    for r in rows
                ]

    def get_conversation(self, thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single conversation record."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT id, user_id, title, created_at, updated_at FROM conversations WHERE id = ? AND user_id = ?",
                    (thread_id, user_id),
                )
                r = cur.fetchone()
                if not r:
                    return None
                return {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "title": r["title"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }

    def get_or_create_conversation(
        self, thread_id: str, user_id: str, default_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ensures a conversation exists; creates it with default_title if missing."""
        with self._lock:
            existing = self.get_conversation(thread_id, user_id)
            if existing:
                return existing

            now_iso = datetime.now(timezone.utc).isoformat()
            title = (default_title or f"Chat {thread_id}").strip()
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO conversations (id, user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (thread_id, user_id, title, now_iso, now_iso),
                )
                conn.commit()

            return {
                "id": thread_id,
                "user_id": user_id,
                "title": title,
                "created_at": now_iso,
                "updated_at": now_iso,
            }

    def update_conversation_title(self, thread_id: str, user_id: str, new_title: str) -> bool:
        """Updates the title of a conversation thread."""
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    UPDATE conversations
                    SET title = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (new_title.strip(), now_iso, thread_id, user_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def touch_conversation(self, thread_id: str, user_id: str) -> None:
        """Updates updated_at timestamp on conversation."""
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
                    (now_iso, thread_id, user_id),
                )
                conn.commit()

    def delete_conversation(self, thread_id: str, user_id: str) -> bool:
        """Deletes a conversation and all its messages."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM chat_messages WHERE thread_id = ? AND user_id = ?",
                    (thread_id, user_id),
                )
                cur = conn.execute(
                    "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                    (thread_id, user_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def add_message(
        self,
        thread_id: str,
        user_id: str,
        role: str,
        content: str,
        *,
        message_id: Optional[str] = None,
        intent: Optional[str] = None,
        language: Optional[str] = None,
        sources: Optional[List[Any]] = None,
        actions: Optional[List[Any]] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> str:
        """Inserts a single chat message into the store."""
        msg_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        now_iso = created_at or datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps(sources or [], default=str)
        actions_json = json.dumps(actions or [], default=str)
        struct_json = json.dumps(structured_data, default=str) if structured_data else None

        with self._lock:
            # Ensure conversation exists
            self.get_or_create_conversation(thread_id, user_id)
            self.touch_conversation(thread_id, user_id)

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO chat_messages (
                        id, thread_id, user_id, role, content, intent,
                        detected_language, sources, actions, structured_data,
                        latency_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg_id,
                        thread_id,
                        user_id,
                        role,
                        content,
                        intent,
                        language,
                        sources_json,
                        actions_json,
                        struct_json,
                        latency_ms,
                        now_iso,
                    ),
                )
                conn.commit()

        return msg_id

    def list_messages(
        self, thread_id: str, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Returns messages in chronological order for thread_id and user_id."""
        resolved_limit = limit if isinstance(limit, int) else 100
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT id, thread_id, user_id, role, content, intent,
                           detected_language, sources, actions, structured_data,
                           latency_ms, created_at
                    FROM chat_messages
                    WHERE thread_id = ? AND user_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (thread_id, user_id, resolved_limit),
                )
                rows = cur.fetchall()

                formatted = []
                for r in rows:
                    raw_sources = r["sources"]
                    parsed_sources = []
                    if raw_sources:
                        try:
                            parsed_sources = json.loads(raw_sources)
                        except Exception:
                            parsed_sources = []

                    raw_actions = r["actions"]
                    parsed_actions = []
                    if raw_actions:
                        try:
                            parsed_actions = json.loads(raw_actions)
                        except Exception:
                            parsed_actions = []

                    raw_struct = r["structured_data"]
                    parsed_struct = None
                    if raw_struct:
                        try:
                            parsed_struct = json.loads(raw_struct)
                        except Exception:
                            parsed_struct = None

                    # Format display timestamp (e.g. 06:30 PM)
                    ts_display = None
                    try:
                        dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                        ts_display = dt.strftime("%I:%M %p")
                    except Exception:
                        ts_display = ""

                    formatted.append({
                        "id": r["id"],
                        "thread_id": r["thread_id"],
                        "user_id": r["user_id"],
                        "role": r["role"],
                        "content": r["content"],
                        "intent": r["intent"],
                        "language": r["detected_language"],
                        "sources": parsed_sources,
                        "actions": parsed_actions,
                        "structured_data": parsed_struct,
                        "latency_ms": r["latency_ms"],
                        "created_at": r["created_at"],
                        "timestamp": ts_display,
                    })

                return formatted

    def clear_messages(self, thread_id: str, user_id: str) -> int:
        """Deletes all messages for a thread while keeping the conversation entry."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "DELETE FROM chat_messages WHERE thread_id = ? AND user_id = ?",
                    (thread_id, user_id),
                )
                deleted = cur.rowcount
                conn.commit()
                self.touch_conversation(thread_id, user_id)
                return deleted

    def count_messages(self, thread_id: str, user_id: str) -> int:
        """Returns the number of messages in a thread."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM chat_messages WHERE thread_id = ? AND user_id = ?",
                    (thread_id, user_id),
                )
                return cur.fetchone()[0]


# Global ChatStore instance
chat_store = ChatStore()
