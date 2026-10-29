from sqlalchemy import text
from app.db.session import engine

with engine.connect() as c:
    rows = c.execute(text(
        "select session_id, role, left(content, 60) from aria.chat_messages order by created_at"
    )).all()
    for r in rows:
        print(r)
