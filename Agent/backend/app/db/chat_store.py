"""
app/db/chat_store.py

Persistent Chat History & Conversation Store for ARIA.
Primary Storage: Neon Cloud PostgreSQL (schema 'aria') when DATABASE_URL is configured.
Resilient Fallback: Local SQLite (aria_store.db) with WAL mode for offline development.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Search parent directories for .env
for p in [
    Path.cwd() / ".env",
    Path.cwd() / "Agent" / ".env",
    Path.cwd() / "Agent" / "backend" / ".env",
    Path(__file__).resolve().parent.parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]:
    if p.exists() and p.is_file():
        load_dotenv(p, override=True)
        break

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("RAG_DB_PATH", str(BACKEND_DIR / "aria_store.db")))
DATABASE_URL = os.getenv("DATABASE_URL")

log = logging.getLogger("aria.chat_store")


class ChatStore:
    """Thread-safe store for conversations and message history (PostgreSQL primary, SQLite fallback)."""

    def __init__(self, db_path: Path = DB_PATH, database_url: Optional[str] = DATABASE_URL) -> None:
        self.db_path = db_path
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._lock = threading.RLock()
        self.is_pg_active = False
        self._pg_engine = None

        self._init_db()

    def _get_pg_url(self) -> Optional[str]:
        if not self.database_url:
            return None
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=30000;")
            except Exception:
                pass
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.DatabaseError as e:
            if "malformed" in str(e).lower():
                log.warning(f"[ChatStore] SQLite file {self.db_path} is malformed. Resetting...")
                import time
                try:
                    os.rename(str(self.db_path), str(self.db_path) + f".bak_{int(time.time())}")
                except Exception:
                    pass
                conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                return conn
            raise

    def _init_db(self) -> None:
        """Create conversations and chat_messages tables in PostgreSQL or SQLite."""
        with self._lock:
            pg_url = self._get_pg_url()
            if pg_url:
                try:
                    from sqlalchemy import create_engine, text
                    engine = create_engine(pg_url, pool_pre_ping=True)
                    with engine.begin() as conn:
                        conn.execute(text("CREATE SCHEMA IF NOT EXISTS aria;"))
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS aria.conversations (
                                id VARCHAR(64) PRIMARY KEY,
                                user_id VARCHAR(64) NOT NULL,
                                title TEXT NOT NULL,
                                created_at TIMESTAMPTZ DEFAULT NOW(),
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE INDEX IF NOT EXISTS idx_aria_conversations_user_updated
                            ON aria.conversations (user_id, updated_at DESC);
                        """))
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS aria.chat_messages (
                                id VARCHAR(64) PRIMARY KEY,
                                session_id VARCHAR(100) NOT NULL,
                                user_id VARCHAR(64) NOT NULL,
                                role VARCHAR(20) NOT NULL,
                                content TEXT NOT NULL,
                                intent VARCHAR(50),
                                detected_language VARCHAR(10),
                                sources JSONB,
                                actions JSONB,
                                structured_data JSONB,
                                latency_ms INTEGER,
                                created_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE INDEX IF NOT EXISTS idx_aria_chat_messages_session_user
                            ON aria.chat_messages (session_id, user_id, created_at ASC);
                        """))
                        # Ensure columns exist on legacy tables
                        conn.execute(text("ALTER TABLE aria.chat_messages DROP CONSTRAINT IF EXISTS chat_messages_user_id_fkey;"))
                        conn.execute(text("ALTER TABLE aria.chat_messages ALTER COLUMN user_id TYPE VARCHAR(64);"))
                        conn.execute(text("ALTER TABLE aria.chat_messages ALTER COLUMN id TYPE VARCHAR(64);"))
                        conn.execute(text("ALTER TABLE aria.chat_messages ADD COLUMN IF NOT EXISTS actions JSONB;"))
                        conn.execute(text("ALTER TABLE aria.chat_messages ADD COLUMN IF NOT EXISTS structured_data JSONB;"))

                    self._pg_engine = engine
                    self.is_pg_active = True
                    log.info("[ChatStore] Connected to Neon Cloud PostgreSQL.")
                    return
                except Exception as e:
                    log.warning(f"[ChatStore] PostgreSQL initialization warning: {e}. Falling back to SQLite.")

            # SQLite fallback
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_sqlite_connection() as conn:
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

    # --------------------------------------------------------------------------
    # Conversation Methods
    # --------------------------------------------------------------------------

    def list_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        resolved_limit = limit if isinstance(limit, int) else 50
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.connect() as conn:
                        rows = conn.execute(text("""
                            SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                                   (SELECT COUNT(*) FROM aria.chat_messages m WHERE m.session_id = c.id AND m.user_id = c.user_id) as message_count
                            FROM aria.conversations c
                            WHERE c.user_id = :uid
                            ORDER BY c.updated_at DESC
                            LIMIT :lim
                        """), {"uid": user_id, "lim": resolved_limit}).mappings().all()
                        return [
                            {
                                "id": r["id"],
                                "user_id": r["user_id"],
                                "title": r["title"],
                                "created_at": str(r["created_at"]),
                                "updated_at": str(r["updated_at"]),
                                "message_count": r["message_count"] or 0,
                            }
                            for r in rows
                        ]
                except Exception as e:
                    log.warning(f"[ChatStore] PG list_conversations error: {e}. Falling back to SQLite.")

            # SQLite fallback
            try:
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute("""
                        SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                               (SELECT COUNT(*) FROM chat_messages m WHERE m.thread_id = c.id AND m.user_id = c.user_id) as message_count
                        FROM conversations c
                        WHERE c.user_id = ?
                        ORDER BY c.updated_at DESC
                        LIMIT ?
                    """, (user_id, resolved_limit))
                    return [
                        {
                            "id": r["id"],
                            "user_id": r["user_id"],
                            "title": r["title"],
                            "created_at": r["created_at"],
                            "updated_at": r["updated_at"],
                            "message_count": r["message_count"],
                        }
                        for r in cur.fetchall()
                    ]
            except Exception as e:
                log.warning(f"[ChatStore] SQLite list_conversations error: {e}")
                return []

    def get_conversation(self, thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.connect() as conn:
                        row = conn.execute(text("""
                            SELECT id, user_id, title, created_at, updated_at
                            FROM aria.conversations
                            WHERE id = :tid AND user_id = :uid
                        """), {"tid": thread_id, "uid": user_id}).mappings().first()
                        if row:
                            return {
                                "id": row["id"],
                                "user_id": row["user_id"],
                                "title": row["title"],
                                "created_at": str(row["created_at"]),
                                "updated_at": str(row["updated_at"]),
                            }
                except Exception as e:
                    log.warning(f"[ChatStore] PG get_conversation error: {e}")

            # SQLite fallback
            try:
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute(
                        "SELECT id, user_id, title, created_at, updated_at FROM conversations WHERE id = ? AND user_id = ?",
                        (thread_id, user_id),
                    )
                    r = cur.fetchone()
                    if r:
                        return {
                            "id": r["id"],
                            "user_id": r["user_id"],
                            "title": r["title"],
                            "created_at": r["created_at"],
                            "updated_at": r["updated_at"],
                        }
            except Exception:
                pass
            return None

    def get_or_create_conversation(
        self, thread_id: str, user_id: str, default_title: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._lock:
            existing = self.get_conversation(thread_id, user_id)
            if existing:
                return existing

            now_iso = datetime.now(timezone.utc).isoformat()
            title = (default_title or f"Chat {thread_id}").strip()

            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO aria.conversations (id, user_id, title, created_at, updated_at)
                            VALUES (:id, :uid, :title, NOW(), NOW())
                            ON CONFLICT (id) DO NOTHING;
                        """), {"id": thread_id, "uid": user_id, "title": title})
                    return {
                        "id": thread_id,
                        "user_id": user_id,
                        "title": title,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                except Exception as e:
                    log.warning(f"[ChatStore] PG get_or_create_conversation error: {e}")

            # SQLite fallback
            try:
                with self._get_sqlite_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO conversations (id, user_id, title, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (thread_id, user_id, title, now_iso, now_iso))
                    conn.commit()
            except Exception:
                pass

            return {
                "id": thread_id,
                "user_id": user_id,
                "title": title,
                "created_at": now_iso,
                "updated_at": now_iso,
            }

    def update_conversation_title(self, thread_id: str, user_id: str, new_title: str) -> bool:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        res = conn.execute(text("""
                            UPDATE aria.conversations
                            SET title = :title, updated_at = NOW()
                            WHERE id = :tid AND user_id = :uid
                        """), {"title": new_title.strip(), "tid": thread_id, "uid": user_id})
                        if res.rowcount > 0:
                            return True
                except Exception as e:
                    log.warning(f"[ChatStore] PG update_conversation_title error: {e}")

            # SQLite fallback
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute("""
                        UPDATE conversations
                        SET title = ?, updated_at = ?
                        WHERE id = ? AND user_id = ?
                    """, (new_title.strip(), now_iso, thread_id, user_id))
                    conn.commit()
                    return cur.rowcount > 0
            except Exception:
                return False

    def touch_conversation(self, thread_id: str, user_id: str) -> None:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE aria.conversations SET updated_at = NOW() WHERE id = :tid AND user_id = :uid
                        """), {"tid": thread_id, "uid": user_id})
                    return
                except Exception:
                    pass

            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                with self._get_sqlite_connection() as conn:
                    conn.execute(
                        "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
                        (now_iso, thread_id, user_id),
                    )
                    conn.commit()
            except Exception:
                pass

    def delete_conversation(self, thread_id: str, user_id: str) -> bool:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        conn.execute(text("DELETE FROM aria.chat_messages WHERE session_id = :tid AND user_id = :uid"), {"tid": thread_id, "uid": user_id})
                        res = conn.execute(text("DELETE FROM aria.conversations WHERE id = :tid AND user_id = :uid"), {"tid": thread_id, "uid": user_id})
                        return res.rowcount > 0
                except Exception as e:
                    log.warning(f"[ChatStore] PG delete_conversation error: {e}")

            try:
                with self._get_sqlite_connection() as conn:
                    conn.execute("DELETE FROM chat_messages WHERE thread_id = ? AND user_id = ?", (thread_id, user_id))
                    cur = conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (thread_id, user_id))
                    conn.commit()
                    return cur.rowcount > 0
            except Exception:
                return False

    # --------------------------------------------------------------------------
    # Message Methods
    # --------------------------------------------------------------------------

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
        msg_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        now_iso = created_at or datetime.now(timezone.utc).isoformat()
        src_json = json.dumps(sources or [], default=str)
        act_json = json.dumps(actions or [], default=str)
        struct_json = json.dumps(structured_data, default=str) if structured_data else None

        with self._lock:
            self.touch_conversation(thread_id, user_id)

            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        # Auto-create conversation if missing
                        conn.execute(text("""
                            INSERT INTO aria.conversations (id, user_id, title, created_at, updated_at)
                            VALUES (:id, :uid, 'Study Chat', NOW(), NOW())
                            ON CONFLICT (id) DO UPDATE SET updated_at = NOW();
                        """), {"id": thread_id, "uid": user_id})

                        conn.execute(text("""
                            INSERT INTO aria.chat_messages (
                                id, session_id, user_id, role, content, intent,
                                detected_language, sources, actions, structured_data, latency_ms, created_at
                            ) VALUES (
                                :id, :session_id, :user_id, :role, :content, :intent,
                                :language, :sources, :actions, :structured_data, :latency_ms, NOW()
                            )
                        """), {
                            "id": msg_id,
                            "session_id": thread_id,
                            "user_id": user_id,
                            "role": role,
                            "content": content,
                            "intent": intent,
                            "language": language or "en",
                            "sources": src_json,
                            "actions": act_json,
                            "structured_data": struct_json,
                            "latency_ms": latency_ms,
                        })
                    return msg_id
                except Exception as e:
                    log.warning(f"[ChatStore] PG add_message error: {e}")

            # SQLite fallback
            try:
                with self._get_sqlite_connection() as conn:
                    conn.execute("""
                        INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                        VALUES (?, ?, 'Study Chat', ?, ?)
                        ON CONFLICT (id) DO UPDATE SET updated_at = ?
                    """, (thread_id, user_id, now_iso, now_iso, now_iso))
                    conn.execute("""
                        INSERT INTO chat_messages (
                            id, thread_id, user_id, role, content, intent,
                            detected_language, sources, actions, structured_data,
                            latency_ms, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        msg_id, thread_id, user_id, role, content, intent,
                        language, src_json, act_json, struct_json, latency_ms, now_iso
                    ))
                    conn.commit()
            except Exception as e:
                log.warning(f"[ChatStore] SQLite add_message error: {e}")

        return msg_id

    def list_messages(
        self, thread_id: str, user_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        resolved_limit = limit if isinstance(limit, int) else 100
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.connect() as conn:
                        rows = conn.execute(text("""
                            SELECT id, session_id, user_id, role, content, intent,
                                   detected_language, sources, actions, structured_data,
                                   latency_ms, created_at
                            FROM aria.chat_messages
                            WHERE session_id = :tid AND user_id = :uid
                            ORDER BY created_at ASC
                            LIMIT :lim
                        """), {"tid": thread_id, "uid": user_id, "lim": resolved_limit}).mappings().all()

                        formatted = []
                        for r in rows:
                            raw_sources = r["sources"]
                            parsed_sources = []
                            if raw_sources:
                                parsed_sources = json.loads(raw_sources) if isinstance(raw_sources, str) else raw_sources

                            raw_actions = r["actions"]
                            parsed_actions = []
                            if raw_actions:
                                parsed_actions = json.loads(raw_actions) if isinstance(raw_actions, str) else raw_actions

                            raw_struct = r["structured_data"]
                            parsed_struct = None
                            if raw_struct:
                                parsed_struct = json.loads(raw_struct) if isinstance(raw_struct, str) else raw_struct

                            formatted.append({
                                "id": r["id"],
                                "thread_id": r["session_id"],
                                "user_id": r["user_id"],
                                "role": r["role"],
                                "content": r["content"],
                                "intent": r["intent"],
                                "language": r["detected_language"] or "en",
                                "sources": parsed_sources,
                                "actions": parsed_actions,
                                "structured_data": parsed_struct,
                                "latency_ms": r["latency_ms"],
                                "created_at": str(r["created_at"]),
                            })
                        return formatted
                except Exception as e:
                    log.warning(f"[ChatStore] PG list_messages error: {e}")

            # SQLite fallback
            try:
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute("""
                        SELECT id, thread_id, user_id, role, content, intent,
                               detected_language, sources, actions, structured_data,
                               latency_ms, created_at
                        FROM chat_messages
                        WHERE thread_id = ? AND user_id = ?
                        ORDER BY created_at ASC
                        LIMIT ?
                    """, (thread_id, user_id, resolved_limit))
                    rows = cur.fetchall()

                    formatted = []
                    for r in rows:
                        raw_sources = r["sources"]
                        parsed_sources = json.loads(raw_sources) if raw_sources else []
                        raw_actions = r["actions"]
                        parsed_actions = json.loads(raw_actions) if raw_actions else []
                        raw_struct = r["structured_data"]
                        parsed_struct = json.loads(raw_struct) if raw_struct else None

                        formatted.append({
                            "id": r["id"],
                            "thread_id": r["thread_id"],
                            "user_id": r["user_id"],
                            "role": r["role"],
                            "content": r["content"],
                            "intent": r["intent"],
                            "language": r["detected_language"] or "en",
                            "sources": parsed_sources,
                            "actions": parsed_actions,
                            "structured_data": parsed_struct,
                            "latency_ms": r["latency_ms"],
                            "created_at": r["created_at"],
                        })
                    return formatted
            except Exception as e:
                log.warning(f"[ChatStore] SQLite list_messages error: {e}")
                return []

    def clear_messages(self, thread_id: str, user_id: str) -> int:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.begin() as conn:
                        res = conn.execute(text("DELETE FROM aria.chat_messages WHERE session_id = :tid AND user_id = :uid"), {"tid": thread_id, "uid": user_id})
                        return res.rowcount
                except Exception:
                    pass

            try:
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute("DELETE FROM chat_messages WHERE thread_id = ? AND user_id = ?", (thread_id, user_id))
                    conn.commit()
                    return cur.rowcount
            except Exception:
                return 0

    def count_messages(self, thread_id: str, user_id: str) -> int:
        with self._lock:
            if self.is_pg_active and self._pg_engine:
                try:
                    from sqlalchemy import text
                    with self._pg_engine.connect() as conn:
                        val = conn.execute(text("SELECT COUNT(*) FROM aria.chat_messages WHERE session_id = :tid AND user_id = :uid"), {"tid": thread_id, "uid": user_id}).scalar()
                        return val or 0
                except Exception:
                    pass

            try:
                with self._get_sqlite_connection() as conn:
                    cur = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE thread_id = ? AND user_id = ?", (thread_id, user_id))
                    row = cur.fetchone()
                    return row[0] if row else 0
            except Exception:
                return 0


# Global singleton instance
chat_store = ChatStore()
