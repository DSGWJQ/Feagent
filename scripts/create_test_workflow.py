"""创建测试工作流数据

用于测试工作流编辑器和执行功能
"""

from sqlalchemy.orm import Session

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)


def create_test_workflow():
    """创建测试工作流"""
    # 创建节点
    node1 = Node.create(
        type=NodeType.START,
        name="开始",
        config={},
        position=Position(x=50, y=250),
    )

    node2 = Node.create(
        type=NodeType.HTTP,
        name="HTTP 请求",
        config={"url": "https://api.example.com", "method": "GET"},
        position=Position(x=350, y=250),
    )

    node3 = Node.create(
        type=NodeType.END,
        name="结束",
        config={},
        position=Position(x=650, y=250),
    )

    # 创建边
    edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)
    edge2 = Edge.create(source_node_id=node2.id, target_node_id=node3.id)

    # 创建工作流
    workflow = Workflow.create(
        name="测试工作流",
        description="用于测试工作流编辑器和执行功能",
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
    )

    # 保存到数据库
    db: Session = next(get_db_session())
    try:
        repository = SQLAlchemyWorkflowRepository(db)
        repository.save(workflow)
        db.commit()
        print("✅ 测试工作流创建成功！")
        print(f"   工作流 ID: {workflow.id}")
        print(f"   访问 URL: http://localhost:3000/workflows/{workflow.id}/edit")
        return workflow.id
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_test_workflow()
