"""Smoke test: run from Agent/backend with  python test_db_layer.py
Needs the aria schema created and DATABASE_URL set in .env."""
from app.db.session import session_scope
from app.db.repositories import UserRepository, FlashcardRepository, StudyPlanRepository
from app.memory import ChatMemory

with session_scope() as db:
    user = UserRepository(db).get_or_create("layer-test@example.com", "Layer Test")

    memory = ChatMemory(db)
    memory.remember(user.id, "user", "Explain recursion", intent="explain")
    memory.remember(
        user.id, "assistant", "Recursion is...", latency_ms=420,
        tool_executions=[{"tool_name": "search", "parameters": {"q": "recursion"},
                          "result_summary": "3 hits", "execution_time_ms": 85}],
    )
    print("history:", memory.as_llm_messages(user.id))

    FlashcardRepository(db).create(user_id=user.id, topic="recursion", front="Base case?",
                                   back="Stops the recursion", tags=["cs", "basics"])
    plan = StudyPlanRepository(db).create_with_phases(
        user_id=user.id, topic="recursion", total_duration_minutes=60,
        phases=[{"phase_number": 1, "phase_name": "Intro", "duration_minutes": 30},
                {"phase_number": 2, "phase_name": "Practice", "duration_minutes": 30}],
    )
    print("plan phases:", [p.phase_name for p in plan.phases])

    UserRepository(db).delete(user.id)  # cascades to everything above
    print("cleaned up")
