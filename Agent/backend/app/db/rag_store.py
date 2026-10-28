"""
app/db/rag_store.py

User-scoped, session-aware RAG store with persistent DB backing (SQLite)
and fast in-memory indexing for semantic retrieval.

Features:
1. User & Session isolation: Each chunk is stamped with user_id and session_id.
2. DB persistence: Automatically initializes and persists to 'aria_rag.db' (SQLite),
   matching the document/chunk schema.
3. Fast in-memory retrieval: Indexes chunks into BasicRetriever on startup and ingestion.
4. Fallback gracefully: If a user has not uploaded any documents, optionally
   falls back to core curriculum notes so learning chat continues seamlessly.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


class UserScopedRagStore:
    """
    Thread-safe, user-isolated, session-scoped RAG store backed by SQLite.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._extractor = ChunkExtractor(
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        self._chunks_by_user: Dict[str, List[DocumentChunk]] = defaultdict(list)
        self._chunk_sessions: Dict[str, str] = {}  # chunk_id -> session_id
        self._docs_by_user: Dict[str, Dict[str, dict]] = defaultdict(dict)
        
        # Initialize SQLite tables and load existing state
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
    # DB Initialization & Hydration
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create documents and chunks tables in SQLite if they don't exist."""
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        text TEXT NOT NULL,
                        chunk_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_docs_user_session
                    ON documents (user_id, session_id)
                    """
                )
                conn.execute(
                    """
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
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunks_user_session
                    ON chunks (user_id, session_id)
                    """
                )
                conn.commit()

    def _load_from_db(self) -> None:
        """Hydrate in-memory index from DB on startup."""
        with self._lock:
            with self._get_connection() as conn:
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

                chunk_rows = conn.execute(
                    """
                    SELECT c.id, c.document_id, c.user_id, c.session_id, c.section, c.text,
                           c.word_count, c.language, d.title
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    ORDER BY c.user_id, c.document_id, c.chunk_index
                    """
                ).fetchall()

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
    # Ingest (Write to DB + Memory)
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
        if not text or not text.strip():
            return 0

        # Extract structured chunks
        new_chunks = self._extractor.extract_chunks(
            document_id=doc_id, text=text, title=title
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # 1. Update SQLite DB
            with self._get_connection() as conn:
                # Delete existing chunks and doc for this doc_id
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

                # Insert document
                conn.execute(
                    """
                    INSERT INTO documents (id, user_id, session_id, title, text, chunk_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (doc_id, user_id, session_id, title, text, len(new_chunks), now_iso),
                )

                # Insert chunks
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
                conn.executemany(
                    """
                    INSERT INTO chunks (id, document_id, user_id, session_id, chunk_index, section, text, word_count, language, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    chunk_tuples,
                )
                conn.commit()

            # 2. Update In-Memory Structures
            # Filter out old chunks for this doc
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
        Search chunks owned by user_id.
        If session_id is provided, only searches chunks in that session.
        If user has no indexed chunks and allow_curriculum_fallback is True,
        searches the default core curriculum.
        Returns: (matched_chunks, scores, retrieval_latency_ms)
        """
        with self._lock:
            candidates = list(self._chunks_by_user.get(user_id, []))

            # Filter by session_id if specified
            if session_id is not None and candidates:
                allowed_docs = {
                    d_id
                    for d_id, meta in self._docs_by_user.get(user_id, {}).items()
                    if meta.get("session_id") == session_id
                }
                candidates = [c for c in candidates if c.document_id in allowed_docs]

            # Fallback to default curriculum if no candidates found
            if not candidates and allow_curriculum_fallback:
                candidates = list(self._chunks_by_user.get("default_curriculum", []))

        if not candidates:
            return [], [], 0.0

        retriever = BasicRetriever()
        retriever.index_chunks(candidates)
        return retriever.retrieve(query=query, top_k=top_k)

    # ------------------------------------------------------------------
    # Query Helpers & Metadata
    # ------------------------------------------------------------------

    def list_documents(
        self, user_id: str, session_id: Optional[str] = None
    ) -> List[dict]:
        """List all documents for a user, optionally filtered by session."""
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
        """List chunk details for inspection and UI display."""
        with self._lock:
            candidates = self._chunks_by_user.get(user_id, [])
            results = []
            for c in candidates:
                c_sess = self._chunk_sessions.get(c.chunk_id, "default")
                if session_id and c_sess != session_id:
                    continue
                results.append(
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "title": c.title,
                        "section": c.section,
                        "text": c.text,
                        "user_id": user_id,
                        "session_id": c_sess,
                        "word_count": c.word_count,
                        "language": c.language,
                    }
                )
                if len(results) >= limit:
                    break
            return results

    def delete_document(self, user_id: str, doc_id: str) -> bool:
        """Deletes a document and its chunks from both DB and memory."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM chunks WHERE document_id = ? AND user_id = ?",
                    (doc_id, user_id),
                )
                conn.execute(
                    "DELETE FROM documents WHERE id = ? AND user_id = ?",
                    (doc_id, user_id),
                )
                conn.commit()

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
            return len(
                [
                    c
                    for c in self._chunks_by_user.get(user_id, [])
                    if self._chunk_sessions.get(c.chunk_id) == session_id
                ]
            )

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            per_user = {uid: len(c) for uid, c in self._chunks_by_user.items()}
            return {
                "total_chunks_in_db": sum(per_user.values()),
                "total_users": len(per_user),
                "chunks_per_user": per_user,
                "db_path": str(self.db_path),
            }


# Singleton instance
rag_store = UserScopedRagStore()
