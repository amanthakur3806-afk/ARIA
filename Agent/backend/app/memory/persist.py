"""Best-effort persistence of chat turns to PostgreSQL (aria schema).

Never raises: a database problem must not break the chat endpoint.
"""
import json
import logging

log = logging.getLogger("aria.memory")


def _clean(value):
    """Make sources/parameters JSON-safe."""
    return json.loads(json.dumps(value, default=str))


def persist_turn(
    user_id: str,
    user_text: str,
    assistant_text: str,
    *,
    session_id=None,
    intent=None,
    language=None,
    sources=None,
    actions=None,
    latency_ms=None,
) -> bool:
    try:
        from app.db.session import session_scope
        from app.db.repositories import UserRepository
        from app.memory import ChatMemory

        with session_scope() as db:
            user = UserRepository(db).get_or_create(f"{user_id}@aria.local", user_id)
            memory = ChatMemory(db)
            memory.remember(user.id, "user", user_text, session_id=session_id)

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
                session_id=session_id,
                detected_language=language, intent=intent,
                latency_ms=latency_ms, sources=_clean(sources or []),
                tool_executions=tools,
            )
        return True
    except Exception as exc:
        log.warning("Could not save chat turn to PostgreSQL: %s", exc)
        return False
