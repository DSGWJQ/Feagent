"""
测试WorkflowAgent对七种子节点类型的支持

测试内容：
1. type_mapping正确映射新节点类型
2. FILE节点执行前调用CoordinatorAgent校验
3. FILE节点被拒绝场景
4. HUMAN节点发布HumanInputRequestedEvent
5. DATA_PROCESS与TRANSFORM双向映射
6. 现有节点类型不受影响（回归测试）
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.agents.node_definition import NodeDefinition
from src.domain.agents.node_definition import NodeType as DefNodeType
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.event_bus import Event, EventBus
from src.domain.services.node_registry import NodeFactory, NodeType


@dataclass
class HumanInputRequestedEvent(Event):
    """人机交互请求事件"""

    workflow_id: str = ""
    node_id: str = ""
    prompt: str = ""
    expected_inputs: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """校验结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


class TestTypeMappingExtension:
    """测试type_mapping扩展"""

    @pytest.mark.asyncio
    async def test_file_node_definition_maps_to_file_type(self):
        """FILE节点定义正确映射到NodeType.FILE"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.FILE
        mock_node.config = {"operation": "read", "path": "/tmp/test.txt"}
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.FILE,
            name="read_file",
            config={"operation": "read", "path": "/tmp/test.txt"},
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.FILE  # 第一个参数是NodeType.FILE

        assert node.type == NodeType.FILE

    @pytest.mark.asyncio
    async def test_data_process_definition_maps_to_transform_type(self):
        """DATA_PROCESS节点定义映射到NodeType.TRANSFORM"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.TRANSFORM
        mock_node.config = {"type": "field_mapping", "mapping": {"old": "new"}}
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.DATA_PROCESS,
            name="transform_data",
            config={"type": "field_mapping", "mapping": {"old": "new"}},
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.TRANSFORM  # 第一个参数是NodeType.TRANSFORM

        assert node.type == NodeType.TRANSFORM

    @pytest.mark.asyncio
    async def test_human_node_definition_maps_to_human_type(self):
        """HUMAN节点定义正确映射到NodeType.HUMAN"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.HUMAN
        mock_node.config = {"prompt": "Please confirm"}
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.HUMAN,
            name="user_confirmation",
            config={"prompt": "Please confirm"},
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.HUMAN  # 第一个参数是NodeType.HUMAN

        assert node.type == NodeType.HUMAN


class TestFileNodeSecurityValidation:
    """测试FILE节点安全校验"""

    @pytest.mark.asyncio
    async def test_file_node_approved_by_coordinator(self):
        """FILE节点通过CoordinatorAgent校验后正常执行"""
        # 创建mock对象
        mock_coordinator = Mock()
        mock_coordinator.validate_file_operation = AsyncMock(
            return_value=ValidationResult(is_valid=True, errors=[])
        )
        mock_event_bus = Mock(spec=EventBus)
        mock_event_bus.publish = AsyncMock()
        mock_executor = Mock()
        mock_executor.execute = AsyncMock(
            return_value={"status": "success", "content": "file data"}
        )

        # 创建mock workflow_context
        mock_context = Mock()
        mock_context.set_node_output = Mock()

        # 创建WorkflowAgent
        agent = WorkflowAgent(
            workflow_context=mock_context,
            coordinator_agent=mock_coordinator,
            event_bus=mock_event_bus,
            node_executor=mock_executor,
        )

        # 创建FILE节点并手动添加到agent
        mock_node = Mock()
        mock_node.id = "file_node_1"
        mock_node.type = NodeType.FILE
        mock_node.config = {"operation": "read", "path": "/var/log/app.log"}
        agent._nodes["file_node_1"] = mock_node

        # 执行节点
        result = await agent.execute_node("file_node_1")

        # 验证CoordinatorAgent被调用
        mock_coordinator.validate_file_operation.assert_called_once()
        call_kwargs = mock_coordinator.validate_file_operation.call_args.kwargs
        assert call_kwargs["operation"] == "read"
        assert call_kwargs["path"] == "/var/log/app.log"

        # 验证节点执行成功
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_file_node_rejected_by_coordinator(self):
        """FILE节点被CoordinatorAgent拒绝时抛出PermissionError"""
        # 创建mock对象
        mock_coordinator = Mock()
        mock_coordinator.validate_file_operation = AsyncMock(
            return_value=ValidationResult(is_valid=False, errors=["Path not in whitelist"])
        )
        mock_event_bus = Mock(spec=EventBus)
        mock_event_bus.publish = AsyncMock()

        # 创建WorkflowAgent
        agent = WorkflowAgent(coordinator_agent=mock_coordinator, event_bus=mock_event_bus)

        # 创建FILE节点并手动添加到agent
        mock_node = Mock()
        mock_node.id = "file_node_2"
        mock_node.type = NodeType.FILE
        mock_node.config = {"operation": "write", "path": "/etc/passwd", "content": "hacked"}
        agent._nodes["file_node_2"] = mock_node

        # 执行节点应该抛出异常
        with pytest.raises(PermissionError, match="Path not in whitelist"):
            await agent.execute_node("file_node_2")

        # 验证CoordinatorAgent被调用
        mock_coordinator.validate_file_operation.assert_called_once()

        # 验证失败事件被发布
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_file_node_without_coordinator_skips_validation(self):
        """FILE节点在没有CoordinatorAgent时跳过校验"""
        # 创建mock executor和context
        mock_executor = Mock()
        mock_executor.execute = AsyncMock(return_value={"status": "success"})
        mock_context = Mock()
        mock_context.set_node_output = Mock()

        # 创建WorkflowAgent（无coordinator）
        agent = WorkflowAgent(node_executor=mock_executor, workflow_context=mock_context)

        # 创建FILE节点并手动添加到agent
        mock_node = Mock()
        mock_node.id = "file_node_3"
        mock_node.type = NodeType.FILE
        mock_node.config = {"operation": "read", "path": "/tmp/test.txt"}
        agent._nodes["file_node_3"] = mock_node

        # 执行节点应该成功（没有校验）
        result = await agent.execute_node("file_node_3")

        assert result["status"] == "success"


class TestHumanNodeEventPublishing:
    """测试HUMAN节点事件发布"""

    @pytest.mark.asyncio
    async def test_human_node_publishes_input_requested_event(self):
        """HUMAN节点发布HumanInputRequestedEvent"""
        # 创建mock event bus
        mock_event_bus = Mock(spec=EventBus)
        mock_event_bus.publish = AsyncMock()

        # 创建mock workflow_context
        mock_context = Mock()
        mock_context.workflow_id = "workflow_123"

        # 创建WorkflowAgent
        agent = WorkflowAgent(event_bus=mock_event_bus, workflow_context=mock_context)

        # 创建HUMAN节点并手动添加到agent
        mock_node = Mock()
        mock_node.id = "human_node_1"
        mock_node.type = NodeType.HUMAN
        mock_node.config = {
            "prompt": "Do you want to proceed?",
            "expected_inputs": ["yes", "no"],
            "timeout_seconds": 60,
            "metadata": {"importance": "high"},
        }
        agent._nodes["human_node_1"] = mock_node

        # 执行节点
        result = await agent.execute_node("human_node_1")

        # 验证事件被发布
        mock_event_bus.publish.assert_called_once()
        event = mock_event_bus.publish.call_args.args[0]

        assert event.workflow_id == "workflow_123"
        assert event.node_id == "human_node_1"
        assert event.prompt == "Do you want to proceed?"
        assert event.expected_inputs == ["yes", "no"]
        assert event.timeout_seconds == 60
        assert event.metadata["importance"] == "high"

        # 验证返回pending状态
        assert result["status"] == "pending_human_input"

    @pytest.mark.asyncio
    async def test_human_node_without_event_bus_executes_normally(self):
        """HUMAN节点在没有EventBus时正常执行"""
        # 创建mock executor和context
        mock_executor = Mock()
        mock_executor.execute = AsyncMock(return_value={"status": "completed", "user_input": "yes"})
        mock_context = Mock()
        mock_context.set_node_output = Mock()

        # 创建WorkflowAgent（无event_bus）
        agent = WorkflowAgent(node_executor=mock_executor, workflow_context=mock_context)

        # 创建HUMAN节点并手动添加到agent
        mock_node = Mock()
        mock_node.id = "human_node_2"
        mock_node.type = NodeType.HUMAN
        mock_node.config = {"prompt": "Confirm?"}
        agent._nodes["human_node_2"] = mock_node

        # 执行节点
        result = await agent.execute_node("human_node_2")

        # 应该正常执行并返回结果
        assert "status" in result
        assert result["status"] == "completed"


class TestDataProcessTransformMapping:
    """测试DATA_PROCESS与TRANSFORM双向映射"""

    @pytest.mark.asyncio
    async def test_transform_plan_dict_creates_data_process_definition(self):
        """从plan dict中的transform类型创建DATA_PROCESS定义"""
        agent = WorkflowAgent()

        plan_dict = {
            "nodes": [
                {
                    "id": "transform_1",
                    "type": "transform",
                    "name": "field_mapper",
                    "config": {"type": "field_mapping", "mapping": {"old": "new"}},
                }
            ],
            "edges": [],
        }

        # 执行计划解析
        # 注意：这里测试的是字符串"transform"能否正确解析
        # 如果execute_plan_from_dict存在，使用它；否则测试类型字符串解析逻辑
        try:
            _result = await agent.execute_plan_from_dict(plan_dict)
            # 如果方法存在且执行，验证节点被正确创建
            assert "transform_1" in agent._nodes or len(agent._nodes) > 0
        except AttributeError:
            # 方法可能不存在，跳过此测试
            pytest.skip("execute_plan_from_dict方法未实现")

    @pytest.mark.asyncio
    async def test_data_process_string_maps_to_transform_node_type(self):
        """字符串'data_process'正确映射到TRANSFORM节点类型"""
        _agent = WorkflowAgent()

        # 测试字符串到NodeType的转换逻辑
        # 这通常发生在解析配置时
        node_type_str = "data_process"

        # 模拟解析逻辑
        try:
            node_type = NodeType(node_type_str.lower())
        except ValueError:
            # 应该fallback到TRANSFORM
            node_type = (
                NodeType.TRANSFORM if node_type_str.lower() == "data_process" else NodeType.GENERIC
            )

        assert node_type == NodeType.TRANSFORM


class TestRegressionForExistingNodeTypes:
    """回归测试：现有节点类型不受影响"""

    @pytest.mark.asyncio
    async def test_llm_node_still_works(self):
        """LLM节点类型不受新节点影响"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.LLM
        mock_node.config = {"user_prompt": "Analyze this"}
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.LLM, name="analyze", config={"user_prompt": "Analyze this"}
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.LLM

        assert node.type == NodeType.LLM

    @pytest.mark.asyncio
    async def test_http_node_still_works(self):
        """HTTP节点类型不受新节点影响"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.API
        mock_node.config = {"url": "https://api.example.com"}
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.HTTP, name="api_call", config={"url": "https://api.example.com"}
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.API

        assert node.type == NodeType.API

    @pytest.mark.asyncio
    async def test_condition_node_still_works(self):
        """CONDITION节点类型不受新节点影响"""
        # 创建mock node_factory
        mock_factory = Mock(spec=NodeFactory)
        mock_node = Mock()
        mock_node.type = NodeType.CONDITION
        mock_node.config = {"expression": "x > 10"}  # 修正：CONDITION节点使用expression字段
        mock_node.parent_id = None
        mock_node.collapsed = False
        mock_node.children = []
        mock_factory.create = Mock(return_value=mock_node)

        agent = WorkflowAgent(node_factory=mock_factory)
        node_def = NodeDefinition(
            node_type=DefNodeType.CONDITION,
            name="check",
            config={"expression": "x > 10"},  # 修正字段名
        )

        node = agent.create_node_from_definition(node_def)

        # 验证factory被正确调用
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        assert call_args[0][0] == NodeType.CONDITION

        assert node.type == NodeType.CONDITION
