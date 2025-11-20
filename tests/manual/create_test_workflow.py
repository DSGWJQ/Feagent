"""创建测试工作流

运行此脚本创建一个测试工作流，用于前端测试
"""

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
from src.infrastructure.database.models import Base
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)


def create_test_workflow():
    """创建测试工作流"""
    print("🚀 创建测试工作流...")

    # 使用项目正式数据库（与 FastAPI 相同）
    engine = sync_engine
    Base.metadata.create_all(engine)
    session = Session(engine)

    try:
        # 创建工作流
        workflow = Workflow(
            id="1",
            name="测试工作流",
            description="用于前端测试的工作流",
            nodes=[],
            edges=[],
        )

        # 添加节点
        start_node = Node(
            id="start-1",
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=100, y=200),
        )

        http_node = Node(
            id="http-1",
            type=NodeType.HTTP_REQUEST,
            name="获取数据",
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
            name="结束",
            config={},
            position=Position(x=700, y=200),
        )

        workflow.add_node(start_node)
        workflow.add_node(http_node)
        workflow.add_node(end_node)

        # 添加边
        workflow.add_edge(Edge(id="e1", source_node_id="start-1", target_node_id="http-1"))
        workflow.add_edge(Edge(id="e2", source_node_id="http-1", target_node_id="end-1"))

        # 保存
        repository = SQLAlchemyWorkflowRepository(session)

        # 删除已存在的
        try:
            existing = repository.get_by_id("1")
            if existing:
                from src.infrastructure.database.models import WorkflowModel

                session.query(WorkflowModel).filter_by(id="1").delete()
                session.commit()
        except:
            pass

        repository.save(workflow)
        session.commit()

        print("✅ 测试工作流创建成功！")
        print(f"   ID: {workflow.id}")
        print(f"   名称: {workflow.name}")
        print(f"   节点数: {len(workflow.nodes)}")
        print(f"   边数: {len(workflow.edges)}")

    finally:
        session.close()


if __name__ == "__main__":
    create_test_workflow()
