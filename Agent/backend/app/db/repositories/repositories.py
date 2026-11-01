from sqlalchemy import select

from app.db.models import (
    AgentToolExecution,
    ChatMessage,
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

    def list_by_user(self, user_id: str, *, limit: int = 50) -> list[ChatMessage]:
        """Oldest-first, last `limit` messages for the user."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(self.db.scalars(stmt))))

    def delete_by_user(self, user_id: str) -> int:
        rows = list(self.db.scalars(select(ChatMessage).where(ChatMessage.user_id == user_id)))
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
