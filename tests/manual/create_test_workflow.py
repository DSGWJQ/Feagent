"""Utility script to create a sample workflow for manual testing."""
# ruff: noqa: E402

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.engine import sync_engine
from src.infrastructure.database.models import Base, WorkflowModel
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)


def create_test_workflow() -> None:
    print("Creating sample workflow...")

    engine = sync_engine
    Base.metadata.create_all(engine)
    session = Session(engine)

    try:
        workflow = Workflow(
            id="1",
            name="Sample Workflow",
            description="Workflow used for manual UI tests",
            nodes=[],
            edges=[],
        )

        start_node = Node(
            id="start-1",
            type=NodeType.START,
            name="Start",
            config={},
            position=Position(x=100, y=200),
        )

        http_node = Node(
            id="http-1",
            type=NodeType.HTTP_REQUEST,
            name="Fetch Data",
            config={
                "url": "https://jsonplaceholder.typicode.com/posts/1",
                "method": "GET",
                "headers": "{}",
                "body": "{}",
            },
            position=Position(x=400, y=200),
        )

        end_node = Node(
            id="end-1",
            type=NodeType.END,
            name="End",
            config={},
            position=Position(x=700, y=200),
        )

        workflow.add_node(start_node)
        workflow.add_node(http_node)
        workflow.add_node(end_node)
        workflow.add_edge(Edge(id="e1", source_node_id="start-1", target_node_id="http-1"))
        workflow.add_edge(Edge(id="e2", source_node_id="http-1", target_node_id="end-1"))

        repository = SQLAlchemyWorkflowRepository(session)

        try:
            existing = repository.get_by_id("1")
            if existing:
                session.query(WorkflowModel).filter_by(id="1").delete()
                session.commit()
        except Exception:
            pass

        repository.save(workflow)
        session.commit()

        print("Sample workflow created: id=1")

    finally:
        session.close()


if __name__ == "__main__":
    create_test_workflow()
