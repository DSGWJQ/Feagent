from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///./agent_data.db")
conn = engine.connect()

result = conn.execute(text("SELECT id, name FROM workflows"))
rows = result.fetchall()

print("数据库中的 Workflows:")
for row in rows:
    print(f"  ID={row[0]!r} (type={type(row[0]).__name__}), name={row[1]}")

conn.close()
