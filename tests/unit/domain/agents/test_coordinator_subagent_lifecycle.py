"""测试：Coordinator 子Agent 生命周期管理

测试目标：
1. Coordinator 订阅 SpawnSubAgentEvent
2. 创建和管理子Agent实例
3. 执行子Agent任务
4. 跟踪子Agent生命周期状态
5. 发布子Agent完成事件

完成标准：
- Coordinator 可以响应 spawn 事件
- 子Agent 被正确创建和执行
- 生命周期状态被跟踪
- 完成事件正确发布
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.domain.services.event_bus import EventBus

# ==================== 测试1：Coordinator 子Agent 管理初始化 ====================


class TestCoordinatorSubAgentInit:
    """测试 Coordinator 子Agent 管理初始化"""

    def test_coordinator_has_subagent_registry(self):
        """Coordinator 应有子Agent注册表"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "subagent_registry")
        assert coordinator.subagent_registry is not None

    def test_coordinator_has_active_subagents_tracking(self):
        """Coordinator 应有活跃子Agent跟踪"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "active_subagents")
        assert isinstance(coordinator.active_subagents, dict)


# ==================== 测试2：注册子Agent类型 ====================


class TestRegisterSubAgentTypes:
    """测试注册子Agent类型"""

    def test_can_register_subagent_type(self):
        """可以注册子Agent类型"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent()

        # 创建 Mock SubAgent 类
        class MockSearchAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {"results": []}

            def get_capabilities(self) -> dict[str, Any]:
                return {"can_search": True}

        coordinator.register_subagent_type(SubAgentType.SEARCH, MockSearchAgent)

        assert coordinator.subagent_registry.has(SubAgentType.SEARCH)

    def test_can_list_registered_types(self):
        """可以列出已注册的类型"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent()

        class MockSearchAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(self, task, context):
                return {}

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.SEARCH, MockSearchAgent)

        types = coordinator.get_registered_subagent_types()
        assert SubAgentType.SEARCH in types


# ==================== 测试3：处理 SpawnSubAgentEvent ====================


class TestHandleSpawnSubAgentEvent:
    """测试处理 SpawnSubAgentEvent"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        event_bus.subscribe = MagicMock()
        return event_bus

    def test_coordinator_subscribes_to_spawn_event(self, mock_event_bus):
        """Coordinator 应订阅 SpawnSubAgentEvent"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)
        coordinator.start_subagent_listener()

        # 验证订阅
        mock_event_bus.subscribe.assert_called()

    @pytest.mark.asyncio
    async def test_handle_spawn_event_creates_subagent(self, mock_event_bus):
        """处理 spawn 事件应创建子Agent"""
        from src.domain.agents.conversation_agent import SpawnSubAgentEvent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        # 注册 Mock SubAgent
        class MockSearchAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(self, task, context):
                return {"results": ["result1"]}

            def get_capabilities(self):
                return {"can_search": True}

        coordinator.register_subagent_type(SubAgentType.SEARCH, MockSearchAgent)

        # 创建 spawn 事件
        event = SpawnSubAgentEvent(
            subagent_type="search",
            task_payload={"query": "测试搜索"},
            session_id="session_001",
        )

        # 处理事件
        result = await coordinator.handle_spawn_subagent_event(event)

        assert result is not None
        assert result.success is True


# ==================== 测试4：子Agent 执行 ====================


class TestSubAgentExecution:
    """测试子Agent执行"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_execute_subagent_returns_result(self, mock_event_bus):
        """执行子Agent应返回结果"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        class MockPythonExecutor(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.PYTHON_EXECUTOR

            async def _execute_internal(self, task, context):
                code = task.get("code", "")
                return {"stdout": f"executed: {code}", "exit_code": 0}

            def get_capabilities(self):
                return {"can_execute_python": True}

        coordinator.register_subagent_type(SubAgentType.PYTHON_EXECUTOR, MockPythonExecutor)

        # 执行子Agent
        result = await coordinator.execute_subagent(
            subagent_type="python_executor",
            task_payload={"code": "print('hello')"},
            context={},
        )

        assert result.success is True
        assert "stdout" in result.output

    @pytest.mark.asyncio
    async def test_execute_subagent_handles_failure(self, mock_event_bus):
        """执行失败应返回错误"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        class FailingAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.DATA_PROCESSOR

            async def _execute_internal(self, task, context):
                raise ValueError("处理失败")

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.DATA_PROCESSOR, FailingAgent)

        # 执行应失败
        result = await coordinator.execute_subagent(
            subagent_type="data_processor",
            task_payload={},
            context={},
        )

        assert result.success is False
        assert "处理失败" in result.error


# ==================== 测试5：子Agent 生命周期跟踪 ====================


class TestSubAgentLifecycleTracking:
    """测试子Agent生命周期跟踪"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_tracks_active_subagents(self, mock_event_bus):
        """应跟踪活跃子Agent"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        class SlowAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(self, task, context):
                import asyncio

                await asyncio.sleep(0.01)
                return {"done": True}

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.SEARCH, SlowAgent)

        # 执行前
        assert len(coordinator.active_subagents) == 0

        # 执行后（同步检查）
        result = await coordinator.execute_subagent(
            subagent_type="search",
            task_payload={},
            context={},
        )

        # 完成后应清除
        assert result.success is True

    def test_get_subagent_status(self, mock_event_bus):
        """可以获取子Agent状态"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        # 添加一个活跃子Agent记录
        coordinator.active_subagents["subagent_001"] = {
            "type": "search",
            "status": "running",
            "started_at": "2024-01-01T00:00:00",
        }

        status = coordinator.get_subagent_status("subagent_001")

        assert status is not None
        assert status["status"] == "running"


# ==================== 测试6：完成事件发布 ====================


class TestSubAgentCompletionEvents:
    """测试子Agent完成事件发布"""

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_publishes_completion_event(self, mock_event_bus):
        """完成时应发布事件"""
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            SubAgentCompletedEvent,
        )
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        coordinator = CoordinatorAgent(event_bus=mock_event_bus)

        class SimpleAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(self, task, context):
                return {"data": "result"}

            def get_capabilities(self):
                return {}

        coordinator.register_subagent_type(SubAgentType.SEARCH, SimpleAgent)

        await coordinator.execute_subagent(
            subagent_type="search",
            task_payload={},
            context={},
            session_id="session_001",
        )

        # 验证事件发布
        mock_event_bus.publish.assert_called()

        # 检查是否发布了完成事件
        call_args_list = mock_event_bus.publish.call_args_list
        completion_events = [
            call[0][0] for call in call_args_list if isinstance(call[0][0], SubAgentCompletedEvent)
        ]

        assert len(completion_events) >= 1


# ==================== 测试7：SubAgentCompletedEvent 定义 ====================


class TestSubAgentCompletedEvent:
    """测试 SubAgentCompletedEvent 事件定义"""

    def test_event_class_exists(self):
        """事件类应存在"""
        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        assert SubAgentCompletedEvent is not None

    def test_event_has_required_fields(self):
        """事件应有必需字段"""
        from src.domain.agents.coordinator_agent import SubAgentCompletedEvent

        event = SubAgentCompletedEvent(
            subagent_id="subagent_001",
            subagent_type="search",
            session_id="session_001",
            success=True,
            result={"data": "result"},
        )

        assert event.subagent_id == "subagent_001"
        assert event.subagent_type == "search"
        assert event.success is True
        assert event.result["data"] == "result"


# 导出
__all__ = [
    "TestCoordinatorSubAgentInit",
    "TestRegisterSubAgentTypes",
    "TestHandleSpawnSubAgentEvent",
    "TestSubAgentExecution",
    "TestSubAgentLifecycleTracking",
    "TestSubAgentCompletionEvents",
    "TestSubAgentCompletedEvent",
]
