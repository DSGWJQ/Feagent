"""测试：ExecuteWorkflowUseCase

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 用户执行工作流（通过 API 触发）
- Use Case 负责业务编排（获取工作流 → 执行 → 返回结果）
- 支持 SSE 流式返回（实时推送节点执行状态）
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class TestExecuteWorkflowUseCase:
    """测试 ExecuteWorkflowUseCase"""

    @pytest.mark.asyncio
    async def test_execute_workflow_should_succeed(self):
        """测试：执行工作流应该成功

        场景：
        - 用户触发工作流执行

        验收标准：
        - 返回执行结果
        - 包含执行日志
        - 包含最终结果
        """
        # Arrange
        from src.application.use_cases.execute_workflow import (
            ExecuteWorkflowInput,
            ExecuteWorkflowUseCase,
        )

        # 创建工作流
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=100, y=0),
        )

        edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)

        workflow = Workflow.create(
            name="测试工作流",
            description="",
            nodes=[node1, node2],
            edges=[edge1],
        )

        # Mock repository
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = workflow

        # 创建 Use Case
        use_case = ExecuteWorkflowUseCase(workflow_repository=mock_repository)

        # 创建输入
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow.id,
            initial_input={"message": "test"},
        )

        # Act
        result = await use_case.execute(input_data)

        # Assert
        assert result is not None
        assert "execution_log" in result
        assert "final_result" in result
        assert len(result["execution_log"]) == 2  # START 和 END 两个节点
        mock_repository.get_by_id.assert_called_once_with(workflow.id)

    @pytest.mark.asyncio
    async def test_execute_workflow_with_invalid_id_should_raise_error(self):
        """测试：执行不存在的工作流应该抛出异常

        场景：
        - 用户尝试执行不存在的工作流

        验收标准：
        - 抛出 NotFoundError
        """
        # Arrange
        from src.application.use_cases.execute_workflow import (
            ExecuteWorkflowInput,
            ExecuteWorkflowUseCase,
        )

        # Mock repository
        mock_repository = Mock()
        mock_repository.get_by_id.side_effect = NotFoundError("Workflow", "invalid_id")

        # 创建 Use Case
        use_case = ExecuteWorkflowUseCase(workflow_repository=mock_repository)

        # 创建输入
        input_data = ExecuteWorkflowInput(
            workflow_id="invalid_id",
            initial_input={"message": "test"},
        )

        # Act & Assert
        with pytest.raises(NotFoundError, match="Workflow 不存在"):
            await use_case.execute(input_data)

    @pytest.mark.asyncio
    async def test_execute_workflow_with_streaming_should_yield_events(self):
        """测试：流式执行工作流应该生成事件

        场景：
        - 用户触发工作流执行（流式模式）
        - 每个节点执行时生成事件

        验收标准：
        - 生成 node_start 事件
        - 生成 node_complete 事件
        - 生成 workflow_complete 事件
        """
        # Arrange
        from src.application.use_cases.execute_workflow import (
            ExecuteWorkflowInput,
            ExecuteWorkflowUseCase,
        )

        # 创建工作流
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=100, y=0),
        )

        edge1 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)

        workflow = Workflow.create(
            name="测试工作流",
            description="",
            nodes=[node1, node2],
            edges=[edge1],
        )

        # Mock repository
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = workflow

        # 创建 Use Case
        use_case = ExecuteWorkflowUseCase(workflow_repository=mock_repository)

        # 创建输入
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow.id,
            initial_input={"message": "test"},
        )

        # Act
        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # Assert
        assert len(events) >= 1  # 至少有 workflow_complete 事件
        workflow_complete_events = [e for e in events if e["type"] == "workflow_complete"]
        assert len(workflow_complete_events) == 1
        assert "result" in workflow_complete_events[0]
        assert "execution_log" in workflow_complete_events[0]

    @pytest.mark.asyncio
    async def test_execute_workflow_with_error_should_yield_error_event(self):
        """测试：工作流执行失败应该生成错误事件

        场景：
        - 工作流包含环（拓扑排序失败）

        验收标准：
        - 生成 workflow_error 事件
        """
        # Arrange
        from src.application.use_cases.execute_workflow import (
            ExecuteWorkflowInput,
            ExecuteWorkflowUseCase,
        )

        # 创建包含环的工作流
        node1 = Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=0, y=0),
        )
        node2 = Node.create(
            type=NodeType.LLM,
            name="处理",
            config={},
            position=Position(x=100, y=0),
        )

        # 创建环：node2 -> node1
        edge1 = Edge.create(source_node_id=node2.id, target_node_id=node1.id)
        # node1 -> node2
        edge2 = Edge.create(source_node_id=node1.id, target_node_id=node2.id)

        workflow = Workflow.create(
            name="包含环的工作流",
            description="",
            nodes=[node1, node2],
            edges=[edge1, edge2],
        )

        # Mock repository
        mock_repository = Mock()
        mock_repository.get_by_id.return_value = workflow

        # 创建 Use Case
        use_case = ExecuteWorkflowUseCase(workflow_repository=mock_repository)

        # 创建输入
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow.id,
            initial_input={"message": "test"},
        )

        # Act
        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # Assert
        assert len(events) >= 1
        error_events = [e for e in events if e["type"] == "workflow_error"]
        assert len(error_events) == 1
        assert "error" in error_events[0]
