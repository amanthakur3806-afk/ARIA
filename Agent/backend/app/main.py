"""
ARIA FastAPI Backend Application (main.py)

Exposes REST APIs connecting the React Frontend with the Communication Agent,
FastMCP Study Tools, and the Persistent User-Scoped RAG Store.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project paths are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import Communication Agent and persistent RAG store
from app.agent.communication_agent import CommunicationAgent
from app.db.rag_store import rag_store

# Initialize FastAPI App
app = FastAPI(
    title="ARIA — AI Study Assistant API",
    description="Backend service powering ARIA with FastMCP, User-Scoped RAG, and Communication Agent.",
    version="1.1.0",
)

# Enable CORS for React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Agent instance
agent = CommunicationAgent()


# ------------------------------------------------------------------------------
# Request & Response Models
# ------------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Student's query or study request.")
    thread_id: Optional[str] = Field("thread-1", description="Conversation thread / session identifier.")
    user_id: Optional[str] = Field("student-1", description="User identifier.")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User learning preferences.")


class DocumentIngestRequest(BaseModel):
    text: str = Field(..., description="Raw text of study notes or lecture transcript.")
    title: Optional[str] = Field("Uploaded Study Notes", description="Document title.")
    document_id: Optional[str] = Field(None, description="Unique document ID.")
    user_id: Optional[str] = Field("student-1", description="User identifier.")
    session_id: Optional[str] = Field("thread-1", description="Session identifier.")


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Health status, LLM availability, and RAG database stats."""
    model_name = agent.llm.groq_model if agent.llm.provider == "groq" else agent.llm.openai_model
    store_stats = rag_store.stats()
    return {
        "status": "ok",
        "service": "ARIA Backend",
        "llm_provider": agent.llm.provider,
        "llm_model": model_name,
        "llm_api_active": agent.llm.is_api_active(),
        "rag_store": store_stats,
    }


@app.post("/api/v1/chat/threads/{thread_id}/messages")
@app.post("/api/chat")
def handle_chat_message(payload: ChatMessageRequest, thread_id: Optional[str] = None):
    """
    Primary chat endpoint:
    Processes user messages through the Communication Agent, scoped to the user and session RAG store.
    """
    resolved_thread_id = thread_id or payload.thread_id or "thread-1"
    user_id = payload.user_id or "student-1"
    message_text = payload.message.strip()

    if not message_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        user_total = rag_store.total_chunks(user_id=user_id)
        session_total = rag_store.total_chunks(user_id=user_id, session_id=resolved_thread_id)

        # When no data is ingested: reply with NO answers, just a greeting and prompt to upload data
        if user_total == 0 or session_total == 0:
            user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            if user_total == 0:
                default_reply = (
                    f"Hello! 👋 I'm ARIA, your AI Study Assistant.\n\n"
                    f"Currently, there is no knowledge base or study data uploaded for student **{user_id}**.\n\n"
                    f"Please upload a knowledge base or data file (such as your lecture notes, textbook chapters, or revision materials) "
                    f"using the **📥 Ingest Notes / Knowledge Base** button to begin!"
                )
            else:
                default_reply = (
                    f"Hello! 👋 I'm ARIA, your AI Study Assistant.\n\n"
                    f"No study materials have been uploaded for session **{resolved_thread_id}** yet.\n\n"
                    f"Please upload a knowledge base or data file for this session using the **📥 Ingest Notes / Knowledge Base** button, or switch to an active session with materials."
                )

            return {
                "thread_id": resolved_thread_id,
                "user_id": user_id,
                "user_message": {
                    "id": user_msg_id,
                    "role": "user",
                    "content": message_text,
                },
                "assistant_message": {
                    "id": assistant_msg_id,
                    "role": "assistant",
                    "content": default_reply,
                    "intent": "no_data_prompt",
                    "language": "en",
                    "sources": [],
                    "actions": [],
                    "structured_data": None,
                    "latency_profile": None,
                },
            }

        # Retrieve chunks specifically scoped to user_id and session_id (NO dummy fallback)
        matched_chunks, scores, ret_lat = rag_store.search(
            user_id=user_id,
            query=message_text,
            top_k=4,
            session_id=resolved_thread_id,
            allow_curriculum_fallback=False,
        )

        response = agent.handle_message(
            message=message_text,
            user_id=user_id,
            thread_id=resolved_thread_id,
            context_chunks=matched_chunks if matched_chunks else None,
            user_preferences=payload.preferences,
        )

        user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"

        return {
            "thread_id": resolved_thread_id,
            "user_id": user_id,
            "user_message": {
                "id": user_msg_id,
                "role": "user",
                "content": message_text,
            },
            "assistant_message": {
                "id": assistant_msg_id,
                "role": "assistant",
                "content": response.content,
                "intent": response.intent,
                "language": response.language,
                "sources": response.sources,
                "actions": [a.to_dict() for a in response.actions],
                "structured_data": response.structured_data,
                "latency_profile": response.latency_profile.to_dict() if response.latency_profile else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/v1/documents/ingest")
def ingest_document(payload: DocumentIngestRequest):
    """
    Ingests notes into the persistent DB, stamped with user_id and session_id.
    """
    doc_id = payload.document_id or f"doc_{uuid.uuid4().hex[:8]}"
    user_id = payload.user_id or "student-1"
    session_id = payload.session_id or "thread-1"
    title = payload.title or "Uploaded Notes"

    chunk_count = rag_store.ingest(
        user_id=user_id,
        doc_id=doc_id,
        text=payload.text,
        title=title,
        session_id=session_id,
    )

    return {
        "status": "success",
        "document_id": doc_id,
        "user_id": user_id,
        "session_id": session_id,
        "title": title,
        "chunks_indexed": chunk_count,
        "user_total_chunks": rag_store.total_chunks(user_id=user_id),
        "session_total_chunks": rag_store.total_chunks(user_id=user_id, session_id=session_id),
    }


@app.get("/api/v1/documents/chunks")
def list_indexed_chunks(
    user_id: str = Query("student-1", description="User ID"),
    session_id: Optional[str] = Query(None, description="Optional session filter"),
    limit: int = Query(50, description="Max chunks to return"),
):
    """
    Returns chunks stored in DB for the given user and session.
    """
    chunks = rag_store.list_chunks(user_id=user_id, session_id=session_id, limit=limit)
    return {
        "user_id": user_id,
        "session_id": session_id,
        "total_chunks": rag_store.total_chunks(user_id=user_id, session_id=session_id),
        "chunks": chunks,
    }


@app.get("/api/v1/documents")
def list_documents(
    user_id: str = Query("student-1", description="User ID"),
    session_id: Optional[str] = Query(None, description="Optional session filter"),
):
    """
    Returns list of ingested documents for the given user and session.
    """
    docs = rag_store.list_documents(user_id=user_id, session_id=session_id)
    return {
        "user_id": user_id,
        "session_id": session_id,
        "documents": docs,
    }


@app.delete("/api/v1/documents/{document_id}")
def delete_document(
    document_id: str,
    user_id: str = Query("student-1", description="User ID"),
):
    """
    Deletes a document and all its chunks for the user from both DB and memory index.
    """
    deleted = rag_store.delete_document(user_id=user_id, doc_id=document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or does not belong to user.")
    return {"status": "success", "deleted_document_id": document_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
