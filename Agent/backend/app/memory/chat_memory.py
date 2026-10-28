"""Conversation memory persisted in aria.chat_messages.

The agent calls remember() after each turn and recall() / as_llm_messages()
before building the next prompt, so context survives restarts.
"""
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChatMessage
from app.db.repositories import ChatMessageRepository, ToolExecutionRepository


class ChatMemory:
    def __init__(self, db: Session):
        self.messages = ChatMessageRepository(db)
        self.tools = ToolExecutionRepository(db)

    def remember(
        self,
        user_id: str,
        role: str,
        content: str,
        *,
        detected_language: str | None = None,
        intent: str | None = None,
        latency_ms: int | None = None,
        sources: list[Any] | None = None,
        tool_executions: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Save one message plus any tool runs (ActionSummary dicts with
        tool_name, parameters, result_summary, execution_time_ms)."""
        msg = self.messages.create(
            user_id=user_id,
            role=role,
            content=content,
            detected_language=detected_language,
            intent=intent,
            latency_ms=latency_ms,
            sources=sources or [],
        )
        for t in tool_executions or []:
            self.tools.create(message_id=msg.id, **t)
        return msg

    def recall(self, user_id: str, limit: int = 20) -> list[ChatMessage]:
        return self.messages.list_by_user(user_id, limit=limit)

    def as_llm_messages(self, user_id: str, limit: int = 20) -> list[dict[str, str]]:
        """History in the {"role", "content"} shape most LLM APIs expect."""
        return [{"role": m.role, "content": m.content} for m in self.recall(user_id, limit)]

    def forget(self, user_id: str) -> int:
        """Delete a user's stored conversation. Returns messages removed."""
        return self.messages.delete_by_user(user_id)
