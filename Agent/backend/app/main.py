"""
ARIA FastAPI Backend Application (main.py)

Exposes REST APIs connecting the React Frontend with the Communication Agent,
FastMCP Study Tools, and the Basic RAG Pipeline.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project paths are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import Communication Agent, RAG Pipeline, and Sample Curriculum
from app.agent.communication_agent import (
    CommunicationAgent,
    BasicRAGPipeline,
    SAMPLE_OS_DOCUMENT,
    run_all_tests,
)

# Initialize FastAPI App
app = FastAPI(
    title="ARIA — AI Study Assistant API",
    description="Backend service powering ARIA with FastMCP, RAG, and Communication Agent.",
    version="1.0.0",
)

# Enable CORS for React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Agent and RAG instances
rag_pipeline = BasicRAGPipeline()
# Seed RAG pipeline with initial curriculum notes
initial_chunks = rag_pipeline.ingest_document(
    document_id="doc_os_core",
    text=SAMPLE_OS_DOCUMENT,
    title="Operating Systems Core Curriculum"
)
agent = CommunicationAgent(rag_pipeline=rag_pipeline)


# ------------------------------------------------------------------------------
# Request & Response Models
# ------------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Student's query or study request.")
    thread_id: Optional[str] = Field("thread-1", description="Conversation thread identifier.")
    user_id: Optional[str] = Field("student-1", description="User identifier.")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User learning preferences.")


class DocumentIngestRequest(BaseModel):
    text: str = Field(..., description="Raw text of study notes or lecture transcript.")
    title: Optional[str] = Field("Uploaded Study Notes", description="Document title.")
    document_id: Optional[str] = Field(None, description="Unique document ID.")


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Health status and service availability."""
    model_name = agent.llm.groq_model if agent.llm.provider == "groq" else agent.llm.openai_model
    return {
        "status": "ok",
        "service": "ARIA Backend",
        "indexed_chunks": len(rag_pipeline.retriever.chunks),
        "llm_provider": agent.llm.provider,
        "llm_model": model_name,
        "llm_api_active": agent.llm.is_api_active(),
    }


@app.post("/api/v1/chat/threads/{thread_id}/messages")
@app.post("/api/chat")
def handle_chat_message(payload: ChatMessageRequest, thread_id: Optional[str] = None):
    """
    Primary chat endpoint:
    Processes user messages through the Communication Agent, RAG pipeline, and MCP tools.
    """
    resolved_thread_id = thread_id or payload.thread_id or "thread-1"
    user_id = payload.user_id or "student-1"
    message_text = payload.message.strip()

    if not message_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        response = agent.handle_message(
            message=message_text,
            user_id=user_id,
            thread_id=resolved_thread_id,
            user_preferences=payload.preferences,
        )

        user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"

        return {
            "thread_id": resolved_thread_id,
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
    """Dynamically ingests custom notes into the RAG pipeline."""
    doc_id = payload.document_id or f"doc_{uuid.uuid4().hex[:6]}"
    chunks = rag_pipeline.ingest_document(
        document_id=doc_id,
        text=payload.text,
        title=payload.title or "Custom Notes"
    )
    return {
        "status": "success",
        "document_id": doc_id,
        "chunks_indexed": len(chunks),
        "total_index_size": len(rag_pipeline.retriever.chunks),
    }


@app.get("/api/v1/documents/chunks")
def list_indexed_chunks():
    """Returns the list of chunks currently in the RAG retrieval index."""
    return {
        "total_chunks": len(rag_pipeline.retriever.chunks),
        "chunks": [c.to_dict() for c in rag_pipeline.retriever.chunks[:20]],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
