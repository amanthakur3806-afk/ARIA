"""
ARIA FastAPI Backend Application (main.py)

Exposes REST APIs connecting the React Frontend with the Communication Agent,
FastMCP Study Tools, and the Persistent User-Scoped RAG Store.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Ensure project paths are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import Communication Agent, persistent RAG store, and Guardrails
from app.agent.communication_agent import CommunicationAgent, StudyIntent
from app.agent.guardrails import (
    ANSWER_POLICY_MODE,
    CROSS_USER_REFUSAL_MESSAGE,
    DEFAULT_TOP_K,
    DecisionPath,
    InputGuard,
    NO_CONTEXT_MESSAGE,
    OutputGuard,
    RAG_MIN_SCORE,
    RetrievalGate,
    SECURITY_REFUSAL_MESSAGE,
    VALIDATION_ERROR_EMPTY,
    VALIDATION_ERROR_TOO_LONG,
    decision_logger,
)
from app.db.rag_store import rag_store
from app.memory.persist import persist_turn

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
    stream: Optional[bool] = Field(False, description="Whether to stream response via SSE.")


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
    model_name = getattr(agent.llm, "groq_model", None) or getattr(agent.llm, "openai_model", "aria-model")
    store_stats = rag_store.stats()
    return {
        "status": "ok",
        "service": "ARIA Backend",
        "llm_provider": getattr(agent.llm, "provider", "groq"),
        "llm_model": model_name,
        "llm_api_active": agent.llm.is_api_active() if hasattr(agent.llm, "is_api_active") else True,
        "rag_store": store_stats,
    }


@app.post("/api/v1/chat/threads/{thread_id}/messages")
@app.post("/api/chat")
def handle_chat_message(
    payload: ChatMessageRequest,
    thread_id: Optional[str] = None,
    on_token: Optional[Callable[[str], None]] = None,
):
    """
    Primary chat endpoint with 4-layer guardrails:
    1. Input Guard: control-character stripping, length capping, hostile injection / credential leak blocking.
    2. User Isolation Gate: verified Clerk user ID enforcement (user ID is never taken from query).
    3. Retrieval Gate: RAG_MIN_SCORE filtering deciding the path BEFORE any model call.
    4. Output Guard: citation verification, source correction, and decision logging.
    """
    if payload.stream and on_token is None:
        return stream_chat_message(payload=payload, thread_id=thread_id)

    resolved_thread_id = thread_id or payload.thread_id or "thread-1"
    _t0 = time.perf_counter()
    user_id = payload.user_id or "student-1"
    raw_message = payload.message

    # 1. Layer 1: Input Guard
    val_res = InputGuard.validate(raw_message, authenticated_user_id=user_id)
    if not val_res.is_valid:
        if val_res.status == "validation_error":
            raise HTTPException(status_code=400, detail=val_res.error_message)
        else:
            decision_logger.log(
                user_id=user_id,
                path=val_res.path,
                chunk_count=0,
                top_score=None,
                status=val_res.status,
                decision_reason=val_res.refusal_reason or "security_refusal",
            )
            return {
                "thread_id": resolved_thread_id,
                "user_id": user_id,
                "user_message": {"id": f"msg_{uuid.uuid4().hex[:8]}", "role": "user", "content": raw_message},
                "assistant_message": {
                    "id": f"msg_{uuid.uuid4().hex[:8]}",
                    "role": "assistant",
                    "content": val_res.error_message or SECURITY_REFUSAL_MESSAGE,
                    "intent": "security_refusal",
                    "language": "en",
                    "sources": [],
                    "actions": [],
                    "structured_data": None,
                    "latency_profile": None,
                },
            }

    message_text = val_res.sanitized_query

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

            persist_turn(user_id, message_text, default_reply, intent="no_data_prompt", language="en")
            if on_token:
                for offset in range(0, len(default_reply), 32):
                    on_token(default_reply[offset:offset + 32])

            return {
                "thread_id": resolved_thread_id,
                "user_id": user_id,
                "user_message": {"id": user_msg_id, "role": "user", "content": message_text},
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

        # Retrieve chunks strictly scoped to user and session
        matched_chunks, scores, ret_lat = rag_store.search(
            user_id=user_id,
            query=message_text,
            top_k=DEFAULT_TOP_K,
            session_id=resolved_thread_id,
            allow_curriculum_fallback=False,
        )

        # 2. Layer 2: Retrieval Gate evaluated BEFORE model call
        intent = agent.detect_intent(message_text)
        gate_res = RetrievalGate.evaluate(matched_chunks, scores, min_score=RAG_MIN_SCORE)
        if gate_res.path == DecisionPath.NO_CONTEXT and intent != StudyIntent.CONVERSATIONAL_GUIDE:
            decision_logger.log(
                user_id=user_id,
                path=DecisionPath.NO_CONTEXT,
                chunk_count=0,
                top_score=gate_res.top_score,
                status="success",
                decision_reason=gate_res.decision_reason,
            )
            persist_turn(user_id, message_text, NO_CONTEXT_MESSAGE, intent="no_context", language="en")
            if on_token:
                for offset in range(0, len(NO_CONTEXT_MESSAGE), 32):
                    on_token(NO_CONTEXT_MESSAGE[offset:offset + 32])

            return {
                "thread_id": resolved_thread_id,
                "user_id": user_id,
                "user_message": {"id": f"msg_{uuid.uuid4().hex[:8]}", "role": "user", "content": message_text},
                "assistant_message": {
                    "id": f"msg_{uuid.uuid4().hex[:8]}",
                    "role": "assistant",
                    "content": NO_CONTEXT_MESSAGE,
                    "intent": "no_context",
                    "language": "en",
                    "sources": [],
                    "actions": [],
                    "structured_data": None,
                    "latency_profile": None,
                },
            }

        streamed_content = []

        def emit_token(token: str):
            if on_token:
                on_token(token)
                streamed_content.append(token)

        response = agent.handle_message(
            message=message_text,
            user_id=user_id,
            thread_id=resolved_thread_id,
            context_chunks=gate_res.filtered_chunks,
            context_scores=gate_res.filtered_scores,
            user_preferences=payload.preferences,
            on_token=emit_token if on_token else None,
        )
        if on_token:
            emitted_text = "".join(streamed_content)
            if response.content.startswith(emitted_text):
                remaining_content = response.content[len(emitted_text):]
            else:
                remaining_content = response.content
            for offset in range(0, len(remaining_content), 32):
                on_token(remaining_content[offset:offset + 32])

        user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"

        persist_turn(
            user_id, message_text, response.content,
            intent=response.intent, language=response.language,
            sources=response.sources,
            actions=[a.to_dict() for a in response.actions],
            latency_ms=int((time.perf_counter() - _t0) * 1000),
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
                "content": response.content,
                "intent": response.intent,
                "language": response.language,
                "sources": response.sources,
                "actions": [a.to_dict() for a in response.actions],
                "structured_data": response.structured_data,
                "latency_profile": response.latency_profile.to_dict() if response.latency_profile else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")


@app.post("/api/v1/chat/threads/{thread_id}/messages/stream")
def stream_chat_message(payload: ChatMessageRequest, thread_id: Optional[str] = None):
    """Streams generated chat text and sends response metadata when the turn completes."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    events: Queue = Queue()

    def generate_events():
        def process_message():
            try:
                result = handle_chat_message(
                    payload,
                    thread_id,
                    on_token=lambda content: events.put(("token", {"content": content})),
                )
                assistant_message = result["assistant_message"]
                metadata = {key: value for key, value in assistant_message.items() if key != "content"}
                events.put(("complete", {
                    "thread_id": result["thread_id"],
                    "user_id": result["user_id"],
                    "assistant_message": metadata,
                }))
            except HTTPException as error:
                events.put(("error", {"detail": error.detail}))
            except Exception as error:
                events.put(("error", {"detail": str(error)}))
            finally:
                events.put(("end", None))

        Thread(target=process_message, daemon=True).start()
        while True:
            event_name, event_data = events.get()
            if event_name == "end":
                break
            encoded_data = json.dumps(event_data, ensure_ascii=False)
            yield f"event: {event_name}\ndata: {encoded_data}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/documents/ingest")
def ingest_document(payload: DocumentIngestRequest):
    """
    Ingests notes into the persistent DB, stamped with user_id and session_id.
    """
    doc_id = payload.document_id or f"doc_{uuid.uuid4().hex[:8]}"
    user_id = payload.user_id or "student-1"
    session_id = payload.session_id or "thread-1"
    title = (payload.title or "Uploaded Notes").replace("\x00", "").strip() or "Uploaded Notes"

    clean_text = (payload.text or "").replace("\x00", "").strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Document text cannot be empty.")

    chunk_count = rag_store.ingest(
        user_id=user_id,
        doc_id=doc_id,
        text=clean_text,
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


@app.post("/api/v1/documents/upload")
def upload_document_file(
    file: UploadFile = File(...),
    user_id: str = Form("student-1"),
    session_id: str = Form("thread-1"),
    title: Optional[str] = Form(None),
    document_id: Optional[str] = Form(None),
):
    """
    Upload and parse study materials (.pdf, .txt, .md, .json, .csv).
    Automatically extracts text (using pypdf for PDFs) and indexes chunks into RAG store.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    filename = file.filename
    raw_user_id = user_id if isinstance(user_id, str) else "student-1"
    raw_session_id = session_id if isinstance(session_id, str) else "thread-1"
    raw_title = title if isinstance(title, str) else None
    raw_doc_id = document_id if isinstance(document_id, str) else None

    clean_title = (raw_title or "").replace("\x00", "").strip()
    if not clean_title:
        clean_title = Path(filename).stem or "Uploaded Document"

    doc_id = raw_doc_id or f"doc_{uuid.uuid4().hex[:8]}"
    resolved_user_id = raw_user_id
    resolved_session_id = raw_session_id

    try:
        contents = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 10MB limit check
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit. Please upload a smaller document.")

    lower_name = filename.lower()
    extracted_text = ""

    if lower_name.endswith(".pdf"):
        try:
            import io
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(contents))
            pages_text = []
            for p_idx, page in enumerate(reader.pages):
                pt = page.extract_text() or ""
                if pt.strip():
                    pages_text.append(f"### Page {p_idx + 1}\n{pt.strip()}")
            extracted_text = "\n\n".join(pages_text)
            if not extracted_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="No selectable text found in PDF. This may be a scanned image or empty PDF. Please upload a PDF with selectable text.",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse PDF document: {str(e)}",
            )
    else:
        # Plain text, Markdown, JSON, CSV
        try:
            extracted_text = contents.decode("utf-8")
        except UnicodeDecodeError:
            try:
                extracted_text = contents.decode("latin-1")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Unsupported file encoding: {str(e)}")

    # Sanitize null bytes and control chars
    extracted_text = extracted_text.replace("\x00", "").strip()
    if not extracted_text:
        raise HTTPException(status_code=400, detail="Extracted document content is empty.")

    try:
        chunk_count = rag_store.ingest(
            user_id=resolved_user_id,
            doc_id=doc_id,
            text=extracted_text,
            title=clean_title,
            session_id=resolved_session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index document: {str(e)}")

    return {
        "status": "success",
        "document_id": doc_id,
        "filename": filename,
        "title": clean_title,
        "user_id": resolved_user_id,
        "session_id": resolved_session_id,
        "chunks_indexed": chunk_count,
        "user_total_chunks": rag_store.total_chunks(user_id=resolved_user_id),
        "session_total_chunks": rag_store.total_chunks(user_id=resolved_user_id, session_id=resolved_session_id),
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
    resolved_uid = user_id if isinstance(user_id, str) else "student-1"
    resolved_sid = session_id if isinstance(session_id, str) else None
    resolved_limit = limit if isinstance(limit, int) else 50

    chunks = rag_store.list_chunks(user_id=resolved_uid, session_id=resolved_sid, limit=resolved_limit)
    return {
        "user_id": resolved_uid,
        "session_id": resolved_sid,
        "total_chunks": rag_store.total_chunks(user_id=resolved_uid, session_id=resolved_sid),
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
    resolved_uid = user_id if isinstance(user_id, str) else "student-1"
    resolved_sid = session_id if isinstance(session_id, str) else None

    docs = rag_store.list_documents(user_id=resolved_uid, session_id=resolved_sid)
    return {
        "user_id": resolved_uid,
        "session_id": resolved_sid,
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
    resolved_uid = user_id if isinstance(user_id, str) else "student-1"
    deleted = rag_store.delete_document(user_id=resolved_uid, doc_id=document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or does not belong to user.")
    return {"status": "success", "deleted_document_id": document_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
