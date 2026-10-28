"""Import every model here so Base.metadata knows about all tables."""
from app.db.models.user import User
from app.db.models.chat import ChatMessage, AgentToolExecution
from app.db.models.study_plan import StudyPlan, StudyPlanPhase
from app.db.models.learning import Flashcard, QuizQuestion, StudyFlowchart

__all__ = [
    "User",
    "ChatMessage",
    "AgentToolExecution",
    "StudyPlan",
    "StudyPlanPhase",
    "Flashcard",
    "QuizQuestion",
    "StudyFlowchart",
]
