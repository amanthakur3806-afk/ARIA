from datetime import datetime

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk, created_at_col, fk


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = fk("users")
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    tone_applied: Mapped[str | None] = mapped_column(String(50))
    direct_answer: Mapped[str | None] = mapped_column(Text)
    analogy_or_intuition: Mapped[str | None] = mapped_column(Text)
    total_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = created_at_col()

    user = relationship("User", back_populates="study_plans")
    phases = relationship(
        "StudyPlanPhase",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="StudyPlanPhase.phase_number",
    )


class StudyPlanPhase(Base):
    __tablename__ = "study_plan_phases"
    __table_args__ = (UniqueConstraint("plan_id", "phase_number"),)

    id: Mapped[str] = uuid_pk()
    plan_id: Mapped[str] = fk("study_plans")
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    key_focus: Mapped[str | None] = mapped_column(Text)

    plan = relationship("StudyPlan", back_populates="phases")
