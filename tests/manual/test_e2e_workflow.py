"""端到端测试：工作流完整流程

测试内容：
1. 创建工作流
2. 添加节点（Start → HTTP → End）
3. 执行工作流
4. 验证结果

运行方式：
1. 确保数据库已初始化：alembic upgrade head
2. 运行测试：python tests/manual/test_e2e_workflow.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.models import Base
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.application.use_cases.execute_workflow import (
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)


async def test_e2e_workflow():
    """端到端测试：完整工作流"""
    print("\n🚀 开始端到端测试...")

    # 1. 创建数据库连接
    engine = create_engine("sqlite:///./test_workflow.db")

    # 创建所有表
    Base.metadata.create_all(engine)

    session = Session(engine)

    try:
        # 2. 创建工作流
        print("\n📝 步骤 1: 创建工作流")
        workflow = Workflow(
            id="e2e-test-workflow",
            name="E2E Test Workflow",
            description="端到端测试工作流",
            nodes=[],
            edges=[],
        )

        # 3. 添加节点
        print("📝 步骤 2: 添加节点")
        start_node = Node(
            id="start-1",
            type=NodeType.START,
            name="Start",
            config={},
            position=Position(x=100, y=100),
        )

        http_node = Node(
            id="http-1",
            type=NodeType.HTTP_REQUEST,
            name="Get Post",
            config={
                "url": "https://jsonplaceholder.typicode.com/posts/1",
                "method": "GET",
                "headers": "{}",
                "body": "{}",
            },
            position=Position(x=300, y=100),
        )

        end_node = Node(
            id="end-1",
            type=NodeType.END,
            name="End",
            config={},
            position=Position(x=500, y=100),
        )

        workflow.add_node(start_node)
        workflow.add_node(http_node)
        workflow.add_node(end_node)

        # 4. 添加边
        print("📝 步骤 3: 连接节点")
        edge1 = Edge(id="e1", source_node_id="start-1", target_node_id="http-1")
        edge2 = Edge(id="e2", source_node_id="http-1", target_node_id="end-1")

        workflow.add_edge(edge1)
        workflow.add_edge(edge2)

        # 5. 保存工作流到数据库
        print("📝 步骤 4: 保存工作流到数据库")
        repository = SQLAlchemyWorkflowRepository(session)
        
        # 删除已存在的工作流（如果有）
        try:
            existing = repository.get_by_id("e2e-test-workflow")
            if existing:
                session.query(type(repository._to_orm(existing))).filter_by(id="e2e-test-workflow").delete()
                session.commit()
        except:
            pass

        repository.save(workflow)
        session.commit()
        print("✅ 工作流已保存")

        # 6. 执行工作流
        print("\n📝 步骤 5: 执行工作流")
        registry = create_executor_registry()
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=repository,
            executor_registry=registry,
        )

        input_data = ExecuteWorkflowInput(
            workflow_id="e2e-test-workflow",
            initial_input={"message": "Hello from E2E test"},
        )

        result = await use_case.execute(input_data)

        # 7. 验证结果
        print("\n📝 步骤 6: 验证结果")
        print(f"✅ 执行日志: {len(result['execution_log'])} 个节点")
        for log in result["execution_log"]:
            print(f"  - {log['node_type']}: {log.get('output', 'N/A')}")

        print(f"\n✅ 最终结果:")
        final_result = result["final_result"]
        if isinstance(final_result, dict):
            print(f"  - userId: {final_result.get('userId')}")
            print(f"  - id: {final_result.get('id')}")
            print(f"  - title: {final_result.get('title')}")
        else:
            print(f"  - {final_result}")

        # 8. 测试流式执行
        print("\n📝 步骤 7: 测试流式执行")
        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)
            print(f"  📡 事件: {event['type']}")

        print(f"✅ 收到 {len(events)} 个事件")

        print("\n✅ 端到端测试完成！")

    finally:
        session.close()


async def test_conditional_workflow():
    """测试条件分支工作流"""
    print("\n🚀 测试条件分支工作流...")

    engine = create_engine("sqlite:///./test_workflow.db")
    Base.metadata.create_all(engine)
    session = Session(engine)

    try:
        # 创建工作流
        workflow = Workflow(
            id="conditional-test",
            name="Conditional Test",
            description="测试条件分支",
            nodes=[],
            edges=[],
        )

        # 添加节点
        start_node = Node(
            id="start-2",
            type=NodeType.START,
            name="Start",
            config={},
            position=Position(x=100, y=100),
        )

        prompt_node = Node(
            id="prompt-1",
            type=NodeType.PROMPT,
            name="Prompt",
            config={"content": "test"},
            position=Position(x=300, y=100),
        )

        conditional_node = Node(
            id="cond-1",
            type=NodeType.CONDITIONAL,
            name="Check",
            config={"condition": "'test' in str(input1)"},
            position=Position(x=500, y=100),
        )

        end_node = Node(
            id="end-2",
            type=NodeType.END,
            name="End",
            config={},
            position=Position(x=700, y=100),
        )

        workflow.add_node(start_node)
        workflow.add_node(prompt_node)
        workflow.add_node(conditional_node)
        workflow.add_node(end_node)

        # 添加边
        workflow.add_edge(Edge(id="e1", source_node_id="start-2", target_node_id="prompt-1"))
        workflow.add_edge(Edge(id="e2", source_node_id="prompt-1", target_node_id="cond-1"))
        workflow.add_edge(Edge(id="e3", source_node_id="cond-1", target_node_id="end-2"))

        # 保存
        repository = SQLAlchemyWorkflowRepository(session)
        try:
            existing = repository.get_by_id("conditional-test")
            if existing:
                session.query(type(repository._to_orm(existing))).filter_by(id="conditional-test").delete()
                session.commit()
        except:
            pass

        repository.save(workflow)
        session.commit()

        # 执行
        registry = create_executor_registry()
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=repository,
            executor_registry=registry,
        )

        result = await use_case.execute(
            ExecuteWorkflowInput(workflow_id="conditional-test", initial_input={})
        )

        print(f"✅ 条件分支结果: {result['final_result']}")

    finally:
        session.close()


async def main():
    """运行所有测试"""
    await test_e2e_workflow()
    await test_conditional_workflow()
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    asyncio.run(main())

