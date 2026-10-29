"""
app/db/rag_store.py

User-scoped, session-aware RAG store with persistent DB backing
(PostgreSQL cloud database if DATABASE_URL is configured, with automatic SQLite fallback)
and fast in-memory indexing for sub-millisecond semantic retrieval.

Features:
1. User & Session isolation: Each chunk is stamped with user_id and session_id.
2. PostgreSQL Cloud Persistence: Automatically persists documents and chunks to
   'aria.documents' and 'aria.chunks' in Neon/PostgreSQL when DATABASE_URL is set.
3. Resilient Fallback: If PostgreSQL is unreachable or DATABASE_URL is missing,
   transparently persists to local SQLite ('aria_rag.db').
4. Sub-millisecond in-memory indexing: Re-indexes chunks into BasicRetriever on startup and ingestion.
5. Cross-session & curriculum fallback: Intelligently surfaces user or curriculum chunks if a session is fresh.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections import defaultdict
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

from app.agent.communication_agent import (
    BasicRetriever,
    ChunkExtractor,
    DocumentChunk,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_TOP_K,
    SAMPLE_OS_DOCUMENT,
)

# Database path defaults to Agent/backend/aria_rag.db
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("RAG_DB_PATH", str(BACKEND_DIR / "aria_rag.db")))
DATABASE_URL = os.getenv("DATABASE_URL")


class UserScopedRagStore:
    """
    Thread-safe, user-isolated, session-scoped RAG store backed by PostgreSQL (cloud)
    or SQLite (local fallback).
    """

    def __init__(self, db_path: Path = DB_PATH, database_url: Optional[str] = DATABASE_URL) -> None:
        self.db_path = db_path
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._lock = threading.RLock()
        self._extractor = ChunkExtractor(
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        self._chunks_by_user: Dict[str, List[DocumentChunk]] = defaultdict(list)
        self._chunk_sessions: Dict[str, str] = {}  # chunk_id -> session_id
        self._docs_by_user: Dict[str, Dict[str, dict]] = defaultdict(dict)
        self.is_pg_active = False

        # Initialize tables and load existing state
        self._init_db()
        self._load_from_db()

        # Seed global sample OS document if database is completely fresh
        if not self._chunks_by_user:
            self.ingest(
                user_id="default_curriculum",
                doc_id="doc_os_core",
                text=SAMPLE_OS_DOCUMENT,
                title="Operating Systems Core Curriculum",
                session_id="global_curriculum",
            )

    # ------------------------------------------------------------------
    # DB Connections & Initialization
    # ------------------------------------------------------------------

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _get_pg_connection(self):
        import psycopg
        clean_url = self.database_url
        if clean_url.startswith("postgresql+psycopg://"):
            clean_url = clean_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return psycopg.connect(clean_url, connect_timeout=10)

    def _init_db(self) -> None:
        """Create documents and chunks tables in PostgreSQL or SQLite."""
        with self._lock:
            if self.database_url:
                try:
                    with self._get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("CREATE SCHEMA IF NOT EXISTS aria;")
                            cur.execute("""
                                CREATE TABLE IF NOT EXISTS aria.documents (
                                    id VARCHAR(64) PRIMARY KEY,
                                    user_id VARCHAR(64) NOT NULL,
                                    session_id VARCHAR(64) NOT NULL,
                                    title TEXT NOT NULL,
                                    text TEXT NOT NULL,
                                    chunk_count INTEGER NOT NULL,
                                    created_at TIMESTAMPTZ DEFAULT NOW()
                                );
                            """)
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_aria_docs_user_session
                                ON aria.documents (user_id, session_id);
                            """)
                            cur.execute("""
                                CREATE TABLE IF NOT EXISTS aria.chunks (
                                    id VARCHAR(64) PRIMARY KEY,
                                    document_id VARCHAR(64) NOT NULL REFERENCES aria.documents(id) ON DELETE CASCADE,
                                    user_id VARCHAR(64) NOT NULL,
                                    session_id VARCHAR(64) NOT NULL,
                                    chunk_index INTEGER NOT NULL,
                                    section TEXT,
                                    text TEXT NOT NULL,
                                    word_count INTEGER NOT NULL,
                                    language VARCHAR(16),
                                    created_at TIMESTAMPTZ DEFAULT NOW()
                                );
                            """)
                            cur.execute("""
                                CREATE INDEX IF NOT EXISTS idx_aria_chunks_user_session
                                ON aria.chunks (user_id, session_id);
                            """)
                            conn.commit()
                            self.is_pg_active = True
                            return
                except Exception as e:
                    print(f"[RAG Store] PostgreSQL connection notice: {e}. Falling back to SQLite.", flush=True)

            # SQLite local fallback
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_sqlite_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        text TEXT NOT NULL,
                        chunk_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_user_session ON documents (user_id, session_id)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chunks (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        section TEXT,
                        text TEXT NOT NULL,
                        word_count INTEGER NOT NULL,
                        language TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_user_session ON chunks (user_id, session_id)")
                conn.commit()

    def _load_from_db(self) -> None:
        """Hydrate in-memory index from PostgreSQL or SQLite on startup."""
        with self._lock:
            if self.is_pg_active:
                try:
                    with self._get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT id, user_id, session_id, title, chunk_count, created_at FROM aria.documents;")
                            doc_rows = cur.fetchall()
                            for d in doc_rows:
                                uid = d[1]
                                doc_id = d[0]
                                self._docs_by_user[uid][doc_id] = {
                                    "doc_id": doc_id,
                                    "user_id": uid,
                                    "session_id": d[2],
                                    "title": d[3],
                                    "chunk_count": d[4],
                                    "created_at": str(d[5]),
                                }

                            cur.execute("""
                                SELECT c.id, c.document_id, c.user_id, c.session_id, c.section, c.text,
                                       c.word_count, c.language, d.title
                                FROM aria.chunks c
                                JOIN aria.documents d ON c.document_id = d.id
                                ORDER BY c.user_id, c.document_id, c.chunk_index;
                            """)
                            chunk_rows = cur.fetchall()
                            for cr in chunk_rows:
                                uid = cr[2]
                                chunk = DocumentChunk(
                                    chunk_id=cr[0],
                                    document_id=cr[1],
                                    title=cr[8],
                                    section=cr[4] or "General",
                                    text=cr[5],
                                    char_start=0,
                                    char_end=len(cr[5]),
                                    word_count=cr[6],
                                    language=cr[7] or "en",
                                )
                                self._chunks_by_user[uid].append(chunk)
                                self._chunk_sessions[cr[0]] = cr[3]
                            return
                except Exception as e:
                    print(f"[RAG Store] Error loading from PostgreSQL: {e}. Falling back to SQLite cache.", flush=True)

            # SQLite local fallback
            if self.db_path.exists():
                with self._get_sqlite_connection() as conn:
                    doc_rows = conn.execute(
                        "SELECT id, user_id, session_id, title, chunk_count, created_at FROM documents"
                    ).fetchall()
                    for d in doc_rows:
                        uid = d["user_id"]
                        doc_id = d["id"]
                        self._docs_by_user[uid][doc_id] = {
                            "doc_id": doc_id,
                            "user_id": uid,
                            "session_id": d["session_id"],
                            "title": d["title"],
                            "chunk_count": d["chunk_count"],
                            "created_at": d["created_at"],
                        }

                    chunk_rows = conn.execute("""
                        SELECT c.id, c.document_id, c.user_id, c.session_id, c.section, c.text,
                               c.word_count, c.language, d.title
                        FROM chunks c
                        JOIN documents d ON c.document_id = d.id
                        ORDER BY c.user_id, c.document_id, c.chunk_index
                    """).fetchall()

                    for cr in chunk_rows:
                        uid = cr["user_id"]
                        chunk = DocumentChunk(
                            chunk_id=cr["id"],
                            document_id=cr["document_id"],
                            title=cr["title"],
                            section=cr["section"] or "General",
                            text=cr["text"],
                            char_start=0,
                            char_end=len(cr["text"]),
                            word_count=cr["word_count"],
                            language=cr["language"] or "en",
                        )
                        self._chunks_by_user[uid].append(chunk)
                        self._chunk_sessions[cr["id"]] = cr["session_id"]

    # ------------------------------------------------------------------
    # Ingest (Write to PostgreSQL / SQLite + Memory)
    # ------------------------------------------------------------------

    def ingest(
        self,
        user_id: str,
        doc_id: str,
        text: str,
        title: str = "Notes",
        session_id: str = "default",
    ) -> int:
        """
        Ingest text for a user and session.
        Idempotent: Replaces existing document and chunks if doc_id already exists.
        """
        if not user_id:
            raise ValueError("user_id is required")
        if not session_id:
            session_id = "default"

        text = (text or "").replace("\x00", "").strip()
        title = (title or "").replace("\x00", "").strip() or "Notes"
        if not text:
            return 0

        new_chunks = self._extractor.extract_chunks(
            document_id=doc_id, text=text, title=title
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # 1. Update PostgreSQL (if active)
            if self.is_pg_active:
                try:
                    with self._get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM aria.chunks WHERE document_id = %s;", (doc_id,))
                            cur.execute("DELETE FROM aria.documents WHERE id = %s;", (doc_id,))
                            cur.execute("""
                                INSERT INTO aria.documents (id, user_id, session_id, title, text, chunk_count, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s);
                            """, (doc_id, user_id, session_id, title, text, len(new_chunks), now_iso))
                            chunk_tuples = [
                                (
                                    c.chunk_id,
                                    doc_id,
                                    user_id,
                                    session_id,
                                    idx,
                                    c.section,
                                    c.text,
                                    c.word_count,
                                    c.language,
                                    now_iso,
                                )
                                for idx, c in enumerate(new_chunks)
                            ]
                            cur.executemany("""
                                INSERT INTO aria.chunks (id, document_id, user_id, session_id, chunk_index, section, text, word_count, language, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """, chunk_tuples)
                            conn.commit()
                except Exception as e:
                    print(f"[RAG Store] PostgreSQL ingest write warning: {e}", flush=True)

            # 2. Also mirror into local SQLite cache
            try:
                with self._get_sqlite_connection() as conn:
                    conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
                    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                    conn.execute("""
                        INSERT INTO documents (id, user_id, session_id, title, text, chunk_count, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (doc_id, user_id, session_id, title, text, len(new_chunks), now_iso))
                    chunk_tuples_sq = [
                        (
                            c.chunk_id,
                            doc_id,
                            user_id,
                            session_id,
                            idx,
                            c.section,
                            c.text,
                            c.word_count,
                            c.language,
                            now_iso,
                        )
                        for idx, c in enumerate(new_chunks)
                    ]
                    conn.executemany("""
                        INSERT INTO chunks (id, document_id, user_id, session_id, chunk_index, section, text, word_count, language, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, chunk_tuples_sq)
                    conn.commit()
            except Exception:
                pass

            # 3. Update In-Memory Structures for sub-millisecond retrieval
            self._chunks_by_user[user_id] = [
                c for c in self._chunks_by_user[user_id] if c.document_id != doc_id
            ]
            self._chunks_by_user[user_id].extend(new_chunks)
            for c in new_chunks:
                self._chunk_sessions[c.chunk_id] = session_id

            self._docs_by_user[user_id][doc_id] = {
                "doc_id": doc_id,
                "user_id": user_id,
                "session_id": session_id,
                "title": title,
                "chunk_count": len(new_chunks),
                "created_at": now_iso,
            }

        return len(new_chunks)

    # ------------------------------------------------------------------
    # Search (Read with User & Session Isolation)
    # ------------------------------------------------------------------

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
        session_id: Optional[str] = None,
        allow_curriculum_fallback: bool = False,
    ) -> Tuple[List[DocumentChunk], List[float], float]:
        """
        Search chunks owned by user_id with sub-millisecond in-memory speed.
        If session_id is provided, checks that session first, then falls back to all user documents.
        """
        with self._lock:
            candidates = list(self._chunks_by_user.get(user_id, []))

            if session_id is not None and candidates:
                allowed_docs = {
                    d_id
                    for d_id, meta in self._docs_by_user.get(user_id, {}).items()
                    if meta.get("session_id") == session_id
                }
                session_candidates = [
                    c for c in candidates if c.document_id in allowed_docs
                ]
                if session_candidates:
                    candidates = session_candidates

            if not candidates and allow_curriculum_fallback:
                candidates = list(self._chunks_by_user.get("default_curriculum", []))

        if not candidates:
            return [], [], 0.0

        retriever = BasicRetriever()
        retriever.index_chunks(candidates)
        matched_chunks, scores, retrieval_latency_ms = retriever.retrieve(query=query, top_k=top_k)

        # Cross-session fallback: If session filter was applied and yielded nothing or score < 0.15,
        # search across ALL documents owned by this verified Clerk user
        if session_id is not None and (not matched_chunks or (scores and max(scores) < 0.15)):
            with self._lock:
                all_user_candidates = list(self._chunks_by_user.get(user_id, []))
            if all_user_candidates and len(all_user_candidates) != len(candidates):
                retriever_all = BasicRetriever()
                retriever_all.index_chunks(all_user_candidates)
                m_all, s_all, _ = retriever_all.retrieve(query=query, top_k=top_k)
                if m_all and s_all and max(s_all) >= 0.15:
                    matched_chunks, scores = m_all, s_all

        # Curriculum fallback
        if allow_curriculum_fallback and (not matched_chunks or (scores and max(scores) < 0.15)):
            with self._lock:
                curr_candidates = list(self._chunks_by_user.get("default_curriculum", []))
            if curr_candidates:
                retriever_curr = BasicRetriever()
                retriever_curr.index_chunks(curr_candidates)
                m_curr, s_curr, _ = retriever_curr.retrieve(query=query, top_k=top_k)
                if m_curr and s_curr and max(s_curr) >= 0.15:
                    matched_chunks, scores = m_curr, s_curr

        return matched_chunks, scores, retrieval_latency_ms

    # ------------------------------------------------------------------
    # Query Helpers & Metadata
    # ------------------------------------------------------------------

    def list_documents(
        self, user_id: str, session_id: Optional[str] = None
    ) -> List[dict]:
        with self._lock:
            docs = list(self._docs_by_user.get(user_id, {}).values())
            if session_id:
                docs = [d for d in docs if d.get("session_id") == session_id]
            return docs

    def list_chunks(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        safe_limit = limit if isinstance(limit, int) else 100
        with self._lock:
            candidates = self._chunks_by_user.get(user_id, [])
            results = []
            for c in candidates:
                c_sess = self._chunk_sessions.get(c.chunk_id, "default")
                if session_id and c_sess != session_id:
                    continue
                results.append({
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "title": c.title,
                    "section": c.section,
                    "text": c.text,
                    "user_id": user_id,
                    "session_id": c_sess,
                    "word_count": c.word_count,
                    "language": c.language,
                })
                if len(results) >= safe_limit:
                    break
            return results

    def delete_document(self, user_id: str, doc_id: str) -> bool:
        """Deletes a document and its chunks from both PostgreSQL/SQLite and memory."""
        with self._lock:
            if self.is_pg_active:
                try:
                    with self._get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM aria.chunks WHERE document_id = %s AND user_id = %s;", (doc_id, user_id))
                            cur.execute("DELETE FROM aria.documents WHERE id = %s AND user_id = %s;", (doc_id, user_id))
                            conn.commit()
                except Exception as e:
                    print(f"[RAG Store] PostgreSQL delete warning: {e}", flush=True)

            try:
                with self._get_sqlite_connection() as conn:
                    conn.execute("DELETE FROM chunks WHERE document_id = ? AND user_id = ?", (doc_id, user_id))
                    conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
                    conn.commit()
            except Exception:
                pass

            if user_id in self._chunks_by_user:
                self._chunks_by_user[user_id] = [
                    c for c in self._chunks_by_user[user_id] if c.document_id != doc_id
                ]
            if user_id in self._docs_by_user and doc_id in self._docs_by_user[user_id]:
                del self._docs_by_user[user_id][doc_id]
                return True
            return False

    def total_chunks(self, user_id: str, session_id: Optional[str] = None) -> int:
        with self._lock:
            if session_id is None:
                return len(self._chunks_by_user.get(user_id, []))
            return len([
                c for c in self._chunks_by_user.get(user_id, [])
                if self._chunk_sessions.get(c.chunk_id) == session_id
            ])

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            per_user = {uid: len(c) for uid, c in self._chunks_by_user.items()}
            return {
                "total_chunks_in_db": sum(per_user.values()),
                "total_users": len(per_user),
                "chunks_per_user": per_user,
                "db_backend": "PostgreSQL (Neon Cloud)" if self.is_pg_active else "SQLite (Local File)",
                "db_path": str(self.db_path) if not self.is_pg_active else "Neon Serverless",
            }


# Singleton instance
rag_store = UserScopedRagStore()
