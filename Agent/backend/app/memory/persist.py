"""
Best-effort persistence of chat turns to persistent SQLite store (aria_rag.db)
and PostgreSQL (aria schema if DATABASE_URL is configured).

Never raises: a database problem must not break the chat endpoint.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.db.chat_store import chat_store

log = logging.getLogger("aria.memory")


def _clean(value: Any) -> Any:
    """Make sources/parameters JSON-safe."""
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return str(value)


def persist_turn(
    user_id: str,
    user_text: str,
    assistant_text: str,
    *,
    thread_id: str = "thread-1",
    intent: Optional[str] = None,
    language: Optional[str] = None,
    sources: Optional[List[Any]] = None,
    actions: Optional[List[Any]] = None,
    structured_data: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
) -> bool:
    """
    Saves a complete conversation turn (user query and assistant response)
    to persistent SQLite storage (and mirrors to PostgreSQL if configured).
    """
    try:
        # 1. Primary Persistent Store: Local SQLite (aria_rag.db)
        # Store user query
        chat_store.add_message(
            thread_id=thread_id,
            user_id=user_id,
            role="user",
            content=user_text,
        )

        # Store assistant response
        chat_store.add_message(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content=assistant_text,
            intent=intent,
            language=language,
            sources=_clean(sources or []),
            actions=_clean(actions or []),
            structured_data=_clean(structured_data) if structured_data else None,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        log.warning("Could not save chat turn to ChatStore: %s", exc)

    # 2. Secondary Sync: PostgreSQL if DATABASE_URL is configured
    try:
        from app.db.session import SessionLocal, session_scope
        if SessionLocal is not None:
            from app.db.repositories import UserRepository
            from app.memory import ChatMemory

            with session_scope() as db:
                user = UserRepository(db).get_or_create(f"{user_id}@aria.local", user_id)
                memory = ChatMemory(db)
                memory.remember(user.id, "user", user_text)

                tools = []
                for a in actions or []:
                    name = a.get("tool_name") or a.get("name")
                    if name:
                        tools.append({
                            "tool_name": name,
                            "parameters": _clean(a.get("parameters") or {}),
                            "result_summary": a.get("result_summary") or a.get("summary"),
                            "execution_time_ms": a.get("execution_time_ms"),
                        })

                memory.remember(
                    user.id, "assistant", assistant_text,
                    detected_language=language, intent=intent,
                    latency_ms=latency_ms, sources=_clean(sources or []),
                    tool_executions=tools,
                )
    except Exception as exc:
        log.debug("PostgreSQL mirror skip: %s", exc)

    return True
