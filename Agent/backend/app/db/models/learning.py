from datetime import datetime
from typing import Any

from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk, created_at_col, fk


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = fk("users")
    card_id: Mapped[str | None] = mapped_column(String(50))
    topic: Mapped[str | None] = mapped_column(String(255))
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    format: Mapped[str | None] = mapped_column(String(30))
    key_points: Mapped[list[Any] | None] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    created_at: Mapped[datetime | None] = created_at_col()

    user = relationship("User", back_populates="flashcards")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = fk("users")
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option_index: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = created_at_col()

    user = relationship("User", back_populates="quiz_questions")


class StudyFlowchart(Base):
    __tablename__ = "study_flowcharts"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = fk("users")
    topic: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    mermaid_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    nodes: Mapped[list[Any] | None] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    edges: Mapped[list[Any] | None] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    steps_walkthrough: Mapped[list[Any] | None] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime | None] = created_at_col()

    user = relationship("User", back_populates="flowcharts")
