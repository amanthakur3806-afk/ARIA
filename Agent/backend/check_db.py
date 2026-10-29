from sqlalchemy import text
from app.db.session import engine

with engine.connect() as c:
    print("server:", c.execute(text(
        "select current_database(), inet_server_addr(), inet_server_port(), current_user"
    )).all())
    print("columns:", c.execute(text(
        "select column_name from information_schema.columns "
        "where table_schema='aria' and table_name='chat_messages' order by ordinal_position"
    )).scalars().all())
