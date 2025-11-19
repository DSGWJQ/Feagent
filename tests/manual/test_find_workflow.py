from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.infrastructure.database.repositories.workflow_repository import SQLAlchemyWorkflowRepository

engine = create_engine('sqlite:///./agent_data.db')
session = Session(engine)

repo = SQLAlchemyWorkflowRepository(session)

print("测试 find_by_id('1')...")
w = repo.find_by_id('1')

if w is None:
    print("❌ 返回 None")
else:
    print(f"✅ 找到: {w.id}, name={w.name}, nodes={len(w.nodes)}, edges={len(w.edges)}")

print("\n测试 find_by_id('999')...")
w2 = repo.find_by_id('999')
if w2 is None:
    print("✅ 正确返回 None")
else:
    print(f"❌ 不应该找到: {w2.id}")

