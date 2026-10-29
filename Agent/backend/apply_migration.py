import sys
from app.db.session import engine

path = sys.argv[1]
sql = open(path, encoding="utf-8").read()

raw = engine.raw_connection()
try:
    cur = raw.cursor()
    cur.execute(sql)
    raw.commit()
    print("applied:", path)
    cur.execute("select table_name from information_schema.tables where table_schema='aria' order by 1")
    print("aria tables:", [r[0] for r in cur.fetchall()])
    cur.execute("select column_name from information_schema.columns where table_schema='aria' and table_name='chat_messages' order by ordinal_position")
    print("chat_messages columns:", [r[0] for r in cur.fetchall()])
finally:
    raw.close()
