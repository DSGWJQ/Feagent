from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)

engine = create_engine("sqlite:///./agent_data.db")
session = Session(engine)

repo = SQLAlchemyWorkflowRepository(session)

try:
    w = repo.get_by_id("1")
    print(f"✅ Success: {w.id}, nodes={len(w.nodes)}, edges={len(w.edges)}")
    print(f"   Name: {w.name}")
    print(f"   Status: {w.status}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
