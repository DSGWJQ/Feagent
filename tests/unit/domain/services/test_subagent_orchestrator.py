"""SubAgentOrchestrator 单元测试

TDD测试：先写测试，后实现
测试子Agent编排器的所有功能：
- 类型注册与查询
- 事件监听控制
- 子Agent执行生命周期
- 状态查询
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ==================== 初始化测试 ====================


class TestSubAgentOrchestratorInit:
    """初始化测试"""

    def test_init_with_defaults(self) -> None:
        """测试默认初始化"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        assert orchestrator._event_bus is None
        assert orchestrator._log_collector is None
        assert orchestrator._registry is not None
        assert orchestrator._active_subagents == {}
        assert orchestrator._results == {}
        assert orchestrator._is_listening is False

    def test_init_with_event_bus(self) -> None:
        """测试带EventBus初始化"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_event_bus = MagicMock()
        orchestrator = SubAgentOrchestrator(event_bus=mock_event_bus)

        assert orchestrator._event_bus is mock_event_bus

    def test_init_with_log_collector(self) -> None:
        """测试带LogCollector初始化"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_log = MagicMock()
        orchestrator = SubAgentOrchestrator(log_collector=mock_log)

        assert orchestrator._log_collector is mock_log

    def test_init_with_custom_registry(self) -> None:
        """测试自定义Registry初始化"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_registry = MagicMock()
        orchestrator = SubAgentOrchestrator(registry=mock_registry)

        assert orchestrator._registry is mock_registry


# ==================== 类型注册测试 ====================


class TestSubAgentOrchestratorRegistration:
    """类型注册测试"""

    def test_register_type(self) -> None:
        """测试注册子Agent类型"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_registry = MagicMock()
        orchestrator = SubAgentOrchestrator(registry=mock_registry)
        mock_class = MagicMock()

        orchestrator.register_type("test_agent", mock_class)

        # 验证注册到内部registry
        mock_registry.register.assert_called_once_with("test_agent", mock_class)

    def test_list_types(self) -> None:
        """测试列出已注册类型"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_registry = MagicMock()
        mock_registry.list_types.return_value = ["type_a", "type_b"]
        orchestrator = SubAgentOrchestrator(registry=mock_registry)

        result = orchestrator.list_types()

        assert result == ["type_a", "type_b"]
        mock_registry.list_types.assert_called_once()


# ==================== 监听控制测试 ====================


class TestSubAgentOrchestratorListening:
    """事件监听控制测试"""

    def test_start_listening_without_event_bus(self) -> None:
        """测试无EventBus时启动监听"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        # 无EventBus不应报错，只是不订阅
        orchestrator.start_listening()

        assert orchestrator._is_listening is False

    def test_start_listening_with_event_bus(self) -> None:
        """测试有EventBus时启动监听"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_event_bus = MagicMock()
        orchestrator = SubAgentOrchestrator(event_bus=mock_event_bus)

        orchestrator.start_listening()

        assert orchestrator._is_listening is True
        mock_event_bus.subscribe.assert_called_once()

    def test_start_listening_idempotent(self) -> None:
        """测试重复启动监听是幂等的"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_event_bus = MagicMock()
        orchestrator = SubAgentOrchestrator(event_bus=mock_event_bus)

        orchestrator.start_listening()
        orchestrator.start_listening()

        # 只应订阅一次
        assert mock_event_bus.subscribe.call_count == 1

    def test_stop_listening(self) -> None:
        """测试停止监听"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_event_bus = MagicMock()
        orchestrator = SubAgentOrchestrator(event_bus=mock_event_bus)
        orchestrator.start_listening()

        orchestrator.stop_listening()

        assert orchestrator._is_listening is False
        mock_event_bus.unsubscribe.assert_called_once()

    def test_stop_listening_when_not_listening(self) -> None:
        """测试未监听时停止不报错"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        # 不应报错
        orchestrator.stop_listening()
        assert orchestrator._is_listening is False


# ==================== 事件处理测试 ====================


class TestSubAgentOrchestratorEventHandling:
    """事件处理测试"""

    @pytest.mark.asyncio
    async def test_handle_spawn_event(self) -> None:
        """测试处理SpawnSubAgentEvent"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        # 创建mock事件
        mock_event = MagicMock()
        mock_event.subagent_type = "test_type"
        mock_event.task_payload = {"task": "test"}
        mock_event.context_snapshot = {"ctx": "data"}
        mock_event.session_id = "session_123"

        # Mock execute方法
        mock_result = MagicMock()
        orchestrator.execute = AsyncMock(return_value=mock_result)

        result = await orchestrator.handle_spawn_event(mock_event)

        orchestrator.execute.assert_called_once_with(
            subagent_type="test_type",
            task_payload={"task": "test"},
            context={"ctx": "data"},
            session_id="session_123",
        )
        assert result is mock_result


# ==================== 执行生命周期测试 ====================


class TestSubAgentOrchestratorExecution:
    """执行生命周期测试"""

    @pytest.mark.asyncio
    async def test_execute_unknown_type(self) -> None:
        """测试执行未知类型返回错误"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        result = await orchestrator.execute(
            subagent_type="unknown_type",
            task_payload={},
            session_id="session_123",
        )

        assert result.success is False
        assert "Unknown subagent type" in result.error

    @pytest.mark.asyncio
    async def test_execute_unregistered_type(self) -> None:
        """测试执行未注册类型返回错误"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_registry = MagicMock()
        mock_registry.create_instance.return_value = None
        orchestrator = SubAgentOrchestrator(registry=mock_registry)

        with patch(
            "src.domain.services.sub_agent_scheduler.SubAgentType",
            side_effect=lambda x: x,
        ):
            result = await orchestrator.execute(
                subagent_type="registered_but_no_instance",
                task_payload={},
                session_id="session_123",
            )

        assert result.success is False
        assert "not registered" in result.error

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """测试成功执行子Agent"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        # 设置mock
        mock_agent = MagicMock()
        mock_agent.agent_id = "agent_001"
        mock_agent_result = MagicMock()
        mock_agent_result.success = True
        mock_agent_result.output = {"data": "result"}
        mock_agent_result.error = None
        mock_agent_result.execution_time = 100
        mock_agent.execute = AsyncMock(return_value=mock_agent_result)

        mock_registry = MagicMock()
        mock_registry.create_instance.return_value = mock_agent

        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()

        orchestrator = SubAgentOrchestrator(
            event_bus=mock_event_bus,
            registry=mock_registry,
        )

        with patch(
            "src.domain.services.sub_agent_scheduler.SubAgentType",
            side_effect=lambda x: x,
        ):
            result = await orchestrator.execute(
                subagent_type="test_type",
                task_payload={"task": "do_something"},
                context={"key": "value"},
                session_id="session_123",
            )

        assert result is mock_agent_result
        mock_agent.execute.assert_called_once_with({"task": "do_something"}, {"key": "value"})
        mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_stores_result_in_session(self) -> None:
        """测试执行结果存储到会话"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_agent = MagicMock()
        mock_agent.agent_id = "agent_001"
        mock_agent_result = MagicMock()
        mock_agent_result.success = True
        mock_agent_result.output = {"data": "result"}
        mock_agent_result.error = None
        mock_agent_result.execution_time = 100
        mock_agent.execute = AsyncMock(return_value=mock_agent_result)

        mock_registry = MagicMock()
        mock_registry.create_instance.return_value = mock_agent

        orchestrator = SubAgentOrchestrator(registry=mock_registry)

        with patch(
            "src.domain.services.sub_agent_scheduler.SubAgentType",
            side_effect=lambda x: x,
        ):
            await orchestrator.execute(
                subagent_type="test_type",
                task_payload={},
                session_id="session_123",
            )

        # 验证结果存储
        results = orchestrator.get_session_results("session_123")
        assert len(results) == 1
        assert results[0]["subagent_id"] == "agent_001"
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self) -> None:
        """测试执行异常处理"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_agent = MagicMock()
        mock_agent.agent_id = "agent_001"
        mock_agent.execute = AsyncMock(side_effect=Exception("Execution failed"))

        mock_registry = MagicMock()
        mock_registry.create_instance.return_value = mock_agent

        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()

        orchestrator = SubAgentOrchestrator(
            event_bus=mock_event_bus,
            registry=mock_registry,
        )

        with patch(
            "src.domain.services.sub_agent_scheduler.SubAgentType",
            side_effect=lambda x: x,
        ):
            result = await orchestrator.execute(
                subagent_type="test_type",
                task_payload={},
                session_id="session_123",
            )

        assert result.success is False
        assert "Execution failed" in result.error
        # 失败也应发布事件
        mock_event_bus.publish.assert_called_once()


# ==================== 状态查询测试 ====================


class TestSubAgentOrchestratorQueries:
    """状态查询测试"""

    def test_get_status_not_found(self) -> None:
        """测试查询不存在的子Agent状态"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        result = orchestrator.get_status("nonexistent_id")

        assert result is None

    def test_get_status_found(self) -> None:
        """测试查询存在的子Agent状态"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()
        orchestrator._active_subagents["agent_001"] = {
            "type": "test_type",
            "status": "running",
        }

        result = orchestrator.get_status("agent_001")

        assert result is not None
        assert result["type"] == "test_type"
        assert result["status"] == "running"

    def test_get_session_results_empty(self) -> None:
        """测试获取空会话结果"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        result = orchestrator.get_session_results("nonexistent_session")

        assert result == []

    def test_get_session_results_with_data(self) -> None:
        """测试获取有数据的会话结果"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()
        orchestrator._results["session_123"] = [
            {"subagent_id": "agent_001", "success": True},
            {"subagent_id": "agent_002", "success": False},
        ]

        result = orchestrator.get_session_results("session_123")

        assert len(result) == 2
        assert result[0]["subagent_id"] == "agent_001"


# ==================== 日志测试 ====================


class TestSubAgentOrchestratorLogging:
    """日志测试"""

    def test_log_with_collector(self) -> None:
        """测试有LogCollector时记录日志"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        mock_log = MagicMock()
        orchestrator = SubAgentOrchestrator(log_collector=mock_log)

        orchestrator._log("info", "Test message", {"key": "value"})

        mock_log.info.assert_called_once()

    def test_log_without_collector(self) -> None:
        """测试无LogCollector时不报错"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        orchestrator = SubAgentOrchestrator()

        # 不应报错
        orchestrator._log("info", "Test message", {})


# ==================== 集成测试 ====================


class TestSubAgentOrchestratorIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """测试完整生命周期：注册 -> 监听 -> 执行 -> 查询"""
        from src.domain.services.subagent_orchestrator import SubAgentOrchestrator

        # 1. 初始化
        mock_event_bus = MagicMock()
        mock_event_bus.publish = AsyncMock()
        mock_registry = MagicMock()

        mock_agent = MagicMock()
        mock_agent.agent_id = "agent_lifecycle_001"
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"lifecycle": "complete"}
        mock_result.error = None
        mock_result.execution_time = 50
        mock_agent.execute = AsyncMock(return_value=mock_result)
        mock_registry.create_instance.return_value = mock_agent

        orchestrator = SubAgentOrchestrator(
            event_bus=mock_event_bus,
            registry=mock_registry,
        )

        # 2. 注册类型
        mock_class = MagicMock()
        orchestrator.register_type("lifecycle_agent", mock_class)

        # 3. 启动监听
        orchestrator.start_listening()
        assert orchestrator._is_listening is True

        # 4. 执行子Agent
        with patch(
            "src.domain.services.sub_agent_scheduler.SubAgentType",
            side_effect=lambda x: x,
        ):
            result = await orchestrator.execute(
                subagent_type="lifecycle_agent",
                task_payload={"action": "test"},
                session_id="lifecycle_session",
            )

        assert result.success is True

        # 5. 查询结果
        session_results = orchestrator.get_session_results("lifecycle_session")
        assert len(session_results) == 1

        # 6. 停止监听
        orchestrator.stop_listening()
        assert orchestrator._is_listening is False
