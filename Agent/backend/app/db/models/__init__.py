"""Import every model here so Base.metadata knows about all active tables."""
from app.db.models.user import User
from app.db.models.chat import ChatMessage, AgentToolExecution

__all__ = [
    "User",
    "ChatMessage",
    "AgentToolExecution",
]
