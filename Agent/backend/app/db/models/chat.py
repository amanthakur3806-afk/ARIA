from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk, created_at_col, fk


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = fk("users")
    session_id: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String(10))
    intent: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[list[Any] | None] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime | None] = created_at_col()

    user = relationship("User", back_populates="chat_messages")
    tool_executions = relationship(
        "AgentToolExecution", back_populates="message", cascade="all, delete-orphan"
    )


class AgentToolExecution(Base):
    __tablename__ = "agent_tool_executions"

    id: Mapped[str] = uuid_pk()
    message_id: Mapped[str | None] = fk("chat_messages", nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    result_summary: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = created_at_col()

    message = relationship("ChatMessage", back_populates="tool_executions")
