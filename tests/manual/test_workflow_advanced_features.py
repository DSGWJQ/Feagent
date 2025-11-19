"""手动测试：工作流高级功能

测试内容：
1. 自定义节点组件
2. 节点配置面板
3. 节点调色板
4. 执行状态显示
5. 代码导出功能
6. 后端节点执行器

运行方式：
1. 启动后端：python -m uvicorn src.interfaces.api.main:app --reload
2. 启动前端：cd web && npm run dev
3. 访问：http://localhost:8000/workflows/1/edit
"""

import asyncio

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_executor import WorkflowExecutor
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors import create_executor_registry


async def test_basic_workflow():
    """测试基础工作流执行"""
    print("\n=== 测试 1: 基础工作流执行 ===")

    # 创建节点
    start_node = Node(
        id="1",
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=0, y=0),
    )

    prompt_node = Node(
        id="2",
        type=NodeType.PROMPT,
        name="Prompt",
        config={"content": "Hello, World!"},
        position=Position(x=200, y=0),
    )

    end_node = Node(
        id="3",
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=400, y=0),
    )

    # 创建边
    edge1 = Edge(id="e1", source_node_id="1", target_node_id="2")
    edge2 = Edge(id="e2", source_node_id="2", target_node_id="3")

    # 创建工作流
    workflow = Workflow(
        id="test-workflow-1",
        name="Test Basic Workflow",
        description="测试基础工作流",
        nodes=[start_node, prompt_node, end_node],
        edges=[edge1, edge2],
    )

    # 创建执行器
    registry = create_executor_registry()
    executor = WorkflowExecutor(executor_registry=registry)

    # 执行工作流
    result = await executor.execute(workflow, initial_input={"message": "test"})

    print(f"✅ 执行结果: {result}")
    print(f"✅ 执行日志: {executor.execution_log}")


async def test_http_workflow():
    """测试 HTTP 工作流"""
    print("\n=== 测试 2: HTTP 工作流 ===")

    # 创建节点
    start_node = Node(
        id="1",
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=0, y=0),
    )

    http_node = Node(
        id="2",
        type=NodeType.HTTP_REQUEST,
        name="HTTP Request",
        config={
            "url": "https://jsonplaceholder.typicode.com/posts/1",
            "method": "GET",
            "headers": "{}",
            "body": "{}",
        },
        position=Position(x=200, y=0),
    )

    end_node = Node(
        id="3",
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=400, y=0),
    )

    # 创建边
    edge1 = Edge(id="e1", source_node_id="1", target_node_id="2")
    edge2 = Edge(id="e2", source_node_id="2", target_node_id="3")

    # 创建工作流
    workflow = Workflow(
        id="test-workflow-2",
        name="Test HTTP Workflow",
        description="测试 HTTP 工作流",
        nodes=[start_node, http_node, end_node],
        edges=[edge1, edge2],
    )

    # 创建执行器
    registry = create_executor_registry()
    executor = WorkflowExecutor(executor_registry=registry)

    # 执行工作流
    try:
        result = await executor.execute(workflow, initial_input={"message": "test"})
        print(f"✅ 执行结果: {result}")
        print(f"✅ 执行日志: {executor.execution_log}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")


async def test_conditional_workflow():
    """测试条件分支工作流"""
    print("\n=== 测试 3: 条件分支工作流 ===")

    # 创建节点
    start_node = Node(
        id="1",
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=0, y=0),
    )

    conditional_node = Node(
        id="2",
        type=NodeType.CONDITIONAL,
        name="Conditional",
        config={"condition": "input1 == 'test'"},
        position=Position(x=200, y=0),
    )

    end_node = Node(
        id="3",
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=400, y=0),
    )

    # 创建边
    edge1 = Edge(id="e1", source_node_id="1", target_node_id="2")
    edge2 = Edge(id="e2", source_node_id="2", target_node_id="3")

    # 创建工作流
    workflow = Workflow(
        id="test-workflow-3",
        name="Test Conditional Workflow",
        description="测试条件分支工作流",
        nodes=[start_node, conditional_node, end_node],
        edges=[edge1, edge2],
    )

    # 创建执行器
    registry = create_executor_registry()
    executor = WorkflowExecutor(executor_registry=registry)

    # 执行工作流
    try:
        result = await executor.execute(workflow, initial_input="test")
        print(f"✅ 执行结果: {result}")
        print(f"✅ 执行日志: {executor.execution_log}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")


async def test_event_callback():
    """测试事件回调（SSE）"""
    print("\n=== 测试 4: 事件回调（SSE） ===")

    events = []

    def event_callback(event_type: str, data: dict):
        events.append({"type": event_type, "data": data})
        print(f"📡 事件: {event_type} - {data}")

    # 创建简单工作流
    start_node = Node(
        id="1",
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=0, y=0),
    )

    prompt_node = Node(
        id="2",
        type=NodeType.PROMPT,
        name="Prompt",
        config={"content": "Test prompt"},
        position=Position(x=200, y=0),
    )

    end_node = Node(
        id="3",
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=400, y=0),
    )

    edge1 = Edge(id="e1", source_node_id="1", target_node_id="2")
    edge2 = Edge(id="e2", source_node_id="2", target_node_id="3")

    workflow = Workflow(
        id="test-workflow-4",
        name="Test Event Callback",
        description="测试事件回调",
        nodes=[start_node, prompt_node, end_node],
        edges=[edge1, edge2],
    )

    # 创建执行器并设置回调
    registry = create_executor_registry()
    executor = WorkflowExecutor(executor_registry=registry)
    executor.set_event_callback(event_callback)

    # 执行工作流
    result = await executor.execute(workflow, initial_input={"message": "test"})

    print(f"\n✅ 执行结果: {result}")
    print(f"✅ 收到 {len(events)} 个事件")


async def main():
    """运行所有测试"""
    print("🚀 开始测试工作流高级功能...")

    await test_basic_workflow()
    await test_http_workflow()
    await test_conditional_workflow()
    await test_event_callback()

    print("\n✅ 所有测试完成！")
    print("\n📝 前端测试步骤：")
    print("1. 启动后端：python -m uvicorn src.interfaces.api.main:app --reload")
    print("2. 启动前端：cd web && npm run dev")
    print("3. 访问：http://localhost:8000/workflows/1/edit")
    print("4. 测试功能：")
    print("   - 从左侧调色板拖拽节点到画布")
    print("   - 点击节点打开配置面板")
    print("   - 连接节点")
    print("   - 点击「导出代码」按钮")
    print("   - 点击「执行」按钮查看实时状态")


if __name__ == "__main__":
    asyncio.run(main())

