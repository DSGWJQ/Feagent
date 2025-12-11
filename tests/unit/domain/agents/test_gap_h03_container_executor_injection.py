"""GAP-H03: 容器执行器自动注入测试

测试目标：验证 WorkflowAgent 自动注入容器执行器
- 默认 container_executor 工厂
- 懒加载机制
- 容器执行集成

TDD 阶段：Red（测试先行）
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.agents.node_definition import NodeDefinition, NodeType
from src.domain.services.event_bus import EventBus


class TestContainerExecutorAutoInjection:
    """容器执行器自动注入测试"""

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    @pytest.fixture
    def workflow_agent(self, event_bus):
        """创建 WorkflowAgent 实例"""
        return WorkflowAgent(event_bus=event_bus)

    def test_workflow_agent_has_container_executor_factory(self, workflow_agent):
        """测试 WorkflowAgent 有容器执行器工厂方法"""
        assert hasattr(workflow_agent, "get_container_executor"), \
            "WorkflowAgent 应该有 get_container_executor 方法"

    def test_container_executor_lazy_loaded(self, workflow_agent):
        """测试容器执行器是懒加载的"""
        # 通过工厂调用计数验证懒加载行为
        call_count = 0
        original_create = None

        def counting_factory():
            nonlocal call_count
            call_count += 1
            if original_create:
                return original_create()
            return Mock()

        # 保存原始方法（如果存在）
        if hasattr(workflow_agent, '_create_container_executor'):
            original_create = workflow_agent._create_container_executor

        with patch.object(
            workflow_agent,
            '_create_container_executor',
            side_effect=counting_factory
        ):
            # 初始化后，工厂不应被调用
            assert call_count == 0, "初始化时不应创建执行器（懒加载）"

            # 首次调用 get_container_executor
            workflow_agent.get_container_executor()
            assert call_count == 1, "首次调用应触发工厂创建"

            # 再次调用不应再次创建
            workflow_agent.get_container_executor()
            assert call_count == 1, "第二次调用不应再次创建（单例）"

    def test_get_container_executor_creates_on_first_call(self, workflow_agent):
        """测试首次调用 get_container_executor 时创建执行器"""
        executor1 = workflow_agent.get_container_executor()
        executor2 = workflow_agent.get_container_executor()

        # 验证返回相同实例（单例行为）
        assert executor1 is executor2, "应该返回相同的执行器实例"
        assert executor1 is not None, "执行器不应为 None"

    def test_get_container_executor_returns_instance(self, workflow_agent):
        """测试 get_container_executor 返回执行器实例"""
        executor = workflow_agent.get_container_executor()

        assert executor is not None, "应该返回容器执行器实例"
        # 验证执行器接口
        assert hasattr(executor, "execute_async"), "执行器应该有 execute_async 方法"

    def test_container_executor_singleton_per_agent(self, workflow_agent):
        """测试容器执行器是单例（每个 Agent）"""
        executor1 = workflow_agent.get_container_executor()
        executor2 = workflow_agent.get_container_executor()

        assert executor1 is executor2, "同一 Agent 应该返回相同的执行器实例"

    def test_container_executor_can_be_overridden(self, event_bus):
        """测试容器执行器可以被覆盖"""
        custom_executor = Mock()
        custom_executor.execute_async = AsyncMock(return_value={"success": True})

        agent = WorkflowAgent(
            event_bus=event_bus,
            container_executor=custom_executor
        )

        executor = agent.get_container_executor()
        assert executor is custom_executor, "应该使用传入的自定义执行器"


class TestContainerNodeExecution:
    """容器节点执行测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def workflow_agent(self, event_bus):
        return WorkflowAgent(event_bus=event_bus)

    @pytest.fixture
    def container_node(self):
        """创建容器节点"""
        return NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="test_container",
            code="print('Hello from container')",
            is_container=True,
            container_config={
                "image": "python:3.11-slim",
                "timeout": 30,
                "memory_limit": "128m"
            }
        )

    @pytest.mark.asyncio
    async def test_execute_container_node_uses_auto_injected_executor(
        self, workflow_agent, container_node
    ):
        """测试执行容器节点使用自动注入的执行器"""
        workflow_agent.add_node(container_node)

        # 模拟执行器
        mock_executor = Mock()
        mock_executor.execute_async = AsyncMock(return_value=Mock(
            success=True,
            output={"result": "test"},
            to_dict=Mock(return_value={"success": True, "output": {"result": "test"}})
        ))

        with patch.object(workflow_agent, "get_container_executor", return_value=mock_executor):
            result = await workflow_agent.execute_container_node(container_node.id)

        assert result is not None, "应该返回执行结果"
        mock_executor.execute_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_container_node_without_external_executor(
        self, workflow_agent, container_node
    ):
        """测试不传入外部执行器也能执行容器节点"""
        workflow_agent.add_node(container_node)

        # 不应该报 "No container executor configured" 错误
        result = await workflow_agent.execute_container_node(container_node.id)

        # 即使执行失败（无 Docker），也不应该是配置错误
        if not result.get("success", True):
            assert "No container executor configured" not in result.get("error", ""), \
                "不应该报配置错误，执行器应该自动注入"


class TestContainerExecutorFactory:
    """容器执行器工厂测试"""

    def test_default_executor_factory_exists(self):
        """测试默认执行器工厂存在"""
        from src.domain.agents.workflow_agent import create_default_container_executor

        executor = create_default_container_executor()
        assert executor is not None, "默认工厂应该返回执行器"

    def test_default_executor_has_required_interface(self):
        """测试默认执行器有必需接口"""
        from src.domain.agents.workflow_agent import create_default_container_executor

        executor = create_default_container_executor()

        # 验证接口
        assert hasattr(executor, "execute_async"), "应该有 execute_async"
        assert hasattr(executor, "is_available"), "应该有 is_available"

    def test_executor_availability_check(self):
        """测试执行器可用性检查"""
        from src.domain.agents.workflow_agent import create_default_container_executor

        executor = create_default_container_executor()

        # 应该能检查是否可用（Docker 是否安装）
        is_available = executor.is_available()
        assert isinstance(is_available, bool), "is_available 应该返回布尔值"


class TestContainerExecutorFallback:
    """容器执行器回退机制测试"""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    def test_fallback_to_sandbox_when_docker_unavailable(self, event_bus):
        """测试 Docker 不可用时回退到沙箱执行"""
        agent = WorkflowAgent(event_bus=event_bus)

        executor = agent.get_container_executor()

        # 如果 Docker 不可用，应该有回退机制
        if not executor.is_available():
            assert hasattr(executor, "fallback_executor") or \
                   hasattr(agent, "get_sandbox_executor"), \
                "Docker 不可用时应该有回退机制"

    @pytest.mark.asyncio
    async def test_container_node_uses_sandbox_fallback(self, event_bus):
        """测试容器节点使用沙箱回退"""
        agent = WorkflowAgent(event_bus=event_bus)

        node = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="test_fallback",
            code="result = 1 + 1",
            is_container=True,
            container_config={"image": "python:3.11-slim"}
        )

        agent.add_node(node)

        # 执行应该成功（使用沙箱回退）
        result = await agent.execute_container_node(node.id)

        # 不应该完全失败
        assert result is not None
        # 如果有回退执行结果
        if result.get("fallback_used"):
            assert result.get("executor_type") == "sandbox"
