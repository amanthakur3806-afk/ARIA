from sqlalchemy import select

from app.db.models import (
    AgentToolExecution,
    ChatMessage,
    Flashcard,
    QuizQuestion,
    StudyFlowchart,
    StudyPlan,
    StudyPlanPhase,
    User,
)
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_or_create(self, email: str, full_name: str) -> User:
        return self.get_by_email(email) or self.create(email=email, full_name=full_name)


class ChatMessageRepository(BaseRepository[ChatMessage]):
    model = ChatMessage

    def list_by_user(
        self, user_id: str, *, session_id: str | None = None, limit: int = 50
    ) -> list[ChatMessage]:
        """Oldest-first, last `limit` messages for the user (optionally one session)."""
        stmt = select(ChatMessage).where(ChatMessage.user_id == user_id)
        if session_id is not None:
            stmt = stmt.where(ChatMessage.session_id == session_id)
        stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)
        return list(reversed(list(self.db.scalars(stmt))))

    def delete_by_user(self, user_id: str, session_id: str | None = None) -> int:
        stmt = select(ChatMessage).where(ChatMessage.user_id == user_id)
        if session_id is not None:
            stmt = stmt.where(ChatMessage.session_id == session_id)
        rows = list(self.db.scalars(stmt))
        for row in rows:
            self.db.delete(row)
        self.db.commit()
        return len(rows)


class ToolExecutionRepository(BaseRepository[AgentToolExecution]):
    model = AgentToolExecution

    def list_by_message(self, message_id: str) -> list[AgentToolExecution]:
        stmt = (
            select(AgentToolExecution)
            .where(AgentToolExecution.message_id == message_id)
            .order_by(AgentToolExecution.created_at)
        )
        return list(self.db.scalars(stmt))


class StudyPlanRepository(BaseRepository[StudyPlan]):
    model = StudyPlan

    def create_with_phases(self, phases: list[dict], **plan_data) -> StudyPlan:
        """Create a plan and its StudyPhase rows in one transaction.
        Each phase dict uses: phase_number, phase_name, duration_minutes, description, key_focus."""
        plan = StudyPlan(**plan_data)
        plan.phases = [StudyPlanPhase(**p) for p in phases]
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def list_by_user(self, user_id: str, *, limit: int = 50) -> list[StudyPlan]:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id)
            .order_by(StudyPlan.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))


class FlashcardRepository(BaseRepository[Flashcard]):
    model = Flashcard

    def list_by_user(self, user_id: str, *, topic: str | None = None, limit: int = 200) -> list[Flashcard]:
        stmt = select(Flashcard).where(Flashcard.user_id == user_id)
        if topic:
            stmt = stmt.where(Flashcard.topic == topic)
        return list(self.db.scalars(stmt.order_by(Flashcard.created_at.desc()).limit(limit)))


class QuizQuestionRepository(BaseRepository[QuizQuestion]):
    model = QuizQuestion

    def list_by_user(self, user_id: str, *, limit: int = 200) -> list[QuizQuestion]:
        stmt = (
            select(QuizQuestion)
            .where(QuizQuestion.user_id == user_id)
            .order_by(QuizQuestion.created_at.desc(), QuizQuestion.question_order)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))


class FlowchartRepository(BaseRepository[StudyFlowchart]):
    model = StudyFlowchart

    def list_by_user(self, user_id: str, *, limit: int = 50) -> list[StudyFlowchart]:
        stmt = (
            select(StudyFlowchart)
            .where(StudyFlowchart.user_id == user_id)
            .order_by(StudyFlowchart.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
