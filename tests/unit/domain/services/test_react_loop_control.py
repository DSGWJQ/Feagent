"""ReAct 循环控制与熔断器测试 - 阶段 5

TDD 驱动：先写测试定义期望行为，再实现功能

测试场景：
1. ReAct 循环限制配置（max_iterations, timeout, token/cost limit）
2. 熔断器（Circuit Breaker）在 Coordinator 中的实现
3. 超过阈值时的告警和终止机制

完成标准：
- 测试覆盖"超过上限→循环停止→返回告警"
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestReActLoopLimits:
    """测试 ReAct 循环限制配置"""

    def test_conversation_agent_has_timeout_config(self):
        """测试：ConversationAgent 应该有 timeout 配置

        场景：设置最大执行时间，超时后自动终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        llm = MagicMock()

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=10,
            timeout_seconds=30,  # 新增：超时配置
        )

        assert agent.timeout_seconds == 30

    def test_conversation_agent_has_token_limit_config(self):
        """测试：ConversationAgent 应该有 token/cost 限制配置

        场景：设置最大 token 消耗，超过后终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        llm = MagicMock()

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=10,
            max_tokens=4000,  # 新增：token 限制
            max_cost=0.5,  # 新增：成本限制（美元）
        )

        assert agent.max_tokens == 4000
        assert agent.max_cost == 0.5

    @pytest.mark.asyncio
    async def test_loop_stops_on_iteration_limit(self):
        """测试：达到最大迭代次数时循环停止

        验收标准：iterations 达到 max_iterations 后终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM 永远不结束
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考中...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=3,
        )

        result = await agent.run_async("测试输入")

        assert result.iterations == 3
        assert result.terminated_by_limit is True
        assert result.limit_type == "max_iterations"  # 新增：限制类型

    @pytest.mark.asyncio
    async def test_loop_stops_on_timeout(self):
        """测试：超时后循环停止

        验收标准：执行时间超过 timeout_seconds 后终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM 每次调用耗时 0.5 秒
        async def slow_think(context):
            await asyncio.sleep(0.5)
            return "慢速思考..."

        llm = MagicMock()
        llm.think = slow_think
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=100,
            timeout_seconds=1,  # 1秒超时
        )

        result = await agent.run_async("测试输入")

        assert result.terminated_by_limit is True
        assert result.limit_type == "timeout"
        assert result.iterations <= 3  # 大约能执行2-3次

    @pytest.mark.asyncio
    async def test_loop_stops_on_token_limit(self):
        """测试：超过 token 限制后循环停止

        验收标准：累计 token 超过 max_tokens 后终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM 每次消耗 1000 tokens
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)
        llm.get_token_usage = MagicMock(return_value=1000)  # 新增：获取 token 消耗

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=100,
            max_tokens=2500,  # 最多 2500 tokens
        )

        result = await agent.run_async("测试输入")

        assert result.terminated_by_limit is True
        assert result.limit_type == "token_limit"
        assert result.total_tokens <= 3000  # 约 2-3 次迭代

    @pytest.mark.asyncio
    async def test_loop_stops_on_cost_limit(self):
        """测试：超过成本限制后循环停止

        验收标准：累计成本超过 max_cost 后终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM 每次消耗 $0.1
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)
        llm.get_cost = MagicMock(return_value=0.1)  # 新增：获取成本

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=100,
            max_cost=0.25,  # 最多 $0.25
        )

        result = await agent.run_async("测试输入")

        assert result.terminated_by_limit is True
        assert result.limit_type == "cost_limit"
        assert result.total_cost <= 0.35  # 约 2-3 次迭代（浮点精度）


class TestCircuitBreaker:
    """测试 Coordinator 中的熔断器"""

    def test_coordinator_has_circuit_breaker(self):
        """测试：CoordinatorAgent 应该有熔断器配置

        熔断器配置：
        - failure_threshold: 连续失败阈值
        - recovery_timeout: 恢复超时时间
        - half_open_requests: 半开状态请求数
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.circuit_breaker import CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60,
            half_open_requests=3,
        )

        agent = CoordinatorAgent(
            circuit_breaker_config=config,
        )

        assert agent.circuit_breaker is not None
        assert agent.circuit_breaker.config.failure_threshold == 5

    def test_circuit_breaker_opens_on_failures(self):
        """测试：连续失败后熔断器打开

        场景：连续 5 次决策验证失败后，熔断器打开
        """
        from src.domain.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # 模拟连续失败
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.state == "open"

    def test_circuit_breaker_blocks_requests_when_open(self):
        """测试：熔断器打开时阻止请求

        场景：熔断器打开后，新请求被拒绝
        """
        from src.domain.services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitBreakerOpenError,
        )

        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # 打开熔断器
        for _ in range(3):
            breaker.record_failure()

        # 尝试执行请求
        with pytest.raises(CircuitBreakerOpenError, match="熔断器已打开"):
            breaker.check_state()

    def test_circuit_breaker_half_open_after_timeout(self):
        """测试：超时后熔断器进入半开状态

        场景：recovery_timeout 后允许有限请求通过
        """
        from src.domain.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1,  # 1秒恢复
        )
        breaker = CircuitBreaker(config)

        # 打开熔断器
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True

        # 等待恢复
        import time

        time.sleep(1.1)

        # 应该进入半开状态
        assert breaker.state == "half_open"
        assert breaker.is_open is False

    def test_circuit_breaker_closes_on_success(self):
        """测试：半开状态成功后熔断器关闭

        场景：半开状态下成功请求后恢复正常
        """
        from src.domain.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0,  # 立即恢复
            half_open_requests=2,
        )
        breaker = CircuitBreaker(config)

        # 打开熔断器
        for _ in range(3):
            breaker.record_failure()

        # 进入半开状态
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)
        assert breaker.state == "half_open"

        # 成功请求
        for _ in range(2):
            breaker.record_success()

        assert breaker.state == "closed"
        assert breaker.is_open is False

    @pytest.mark.asyncio
    async def test_coordinator_triggers_alert_on_circuit_open(self):
        """测试：熔断器打开时触发告警

        验收标准：熔断器打开后发布告警事件
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.circuit_breaker import CircuitBreakerConfig
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        alerts = []

        # 订阅告警事件
        from src.domain.agents.coordinator_agent import CircuitBreakerAlertEvent

        async def capture_alert(event):
            alerts.append(event)

        event_bus.subscribe(CircuitBreakerAlertEvent, capture_alert)

        config = CircuitBreakerConfig(failure_threshold=2)
        agent = CoordinatorAgent(
            event_bus=event_bus,
            circuit_breaker_config=config,
        )

        # 模拟连续失败
        for _ in range(2):
            agent.circuit_breaker.record_failure()

        # 触发告警检查
        await agent.check_circuit_breaker_state()

        assert len(alerts) == 1
        assert alerts[0].state == "open"

    @pytest.mark.asyncio
    async def test_coordinator_terminates_loop_on_circuit_open(self):
        """测试：熔断器打开时终止 ReAct 循环

        验收标准：当熔断器打开时，正在执行的循环应该立即终止
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.circuit_breaker import CircuitBreakerConfig
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        config = CircuitBreakerConfig(failure_threshold=2)
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            circuit_breaker_config=config,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考...")
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=100,
            coordinator=coordinator,  # 新增：关联协调者
        )

        # 打开熔断器
        for _ in range(2):
            coordinator.circuit_breaker.record_failure()

        result = await agent.run_async("测试输入")

        assert result.terminated_by_limit is True
        assert result.limit_type == "circuit_breaker"


class TestLoopControlResult:
    """测试循环控制结果"""

    def test_react_result_includes_limit_info(self):
        """测试：ReActResult 应包含限制相关信息"""
        from src.domain.agents.conversation_agent import ReActResult

        result = ReActResult(
            completed=False,
            terminated_by_limit=True,
            limit_type="timeout",
            total_tokens=5000,
            total_cost=0.3,
            execution_time=30.5,
        )

        assert result.limit_type == "timeout"
        assert result.total_tokens == 5000
        assert result.total_cost == 0.3
        assert result.execution_time == 30.5

    def test_react_result_has_alert_message(self):
        """测试：终止时 ReActResult 应包含告警消息"""
        from src.domain.agents.conversation_agent import ReActResult

        result = ReActResult(
            completed=False,
            terminated_by_limit=True,
            limit_type="max_iterations",
            alert_message="已达到最大迭代次数限制 (10 次)，循环已终止",
        )

        assert "最大迭代次数" in result.alert_message


class TestRealWorldScenario:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_complete_loop_control_scenario(self):
        """测试：完整的循环控制场景

        场景：
        1. 配置循环限制（iterations=5, timeout=10s, tokens=10000）
        2. 配置熔断器（failure_threshold=3）
        3. 运行 ReAct 循环
        4. 模拟超过 token 限制
        5. 验证循环停止并返回告警

        这是阶段 5 的完整验收场景！
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.circuit_breaker import CircuitBreakerConfig
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        # === 步骤 1 & 2：配置 ===
        event_bus = EventBus()
        config = CircuitBreakerConfig(failure_threshold=3)
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            circuit_breaker_config=config,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        # Mock LLM
        iteration_count = 0

        async def mock_think(context):
            nonlocal iteration_count
            iteration_count += 1
            return f"第 {iteration_count} 次思考"

        llm = MagicMock()
        llm.think = mock_think
        llm.decide_action = AsyncMock(return_value={"action_type": "continue"})
        llm.should_continue = AsyncMock(return_value=True)
        llm.get_token_usage = MagicMock(return_value=3000)  # 每次 3000 tokens

        agent = ConversationAgent(
            session_context=session_ctx,
            llm=llm,
            max_iterations=10,
            timeout_seconds=30,
            max_tokens=8000,  # 最多 8000 tokens
            coordinator=coordinator,
        )

        # === 步骤 3 & 4：运行并触发限制 ===
        result = await agent.run_async("分析一段很长的文本")

        # === 步骤 5：验证 ===
        assert result.terminated_by_limit is True
        assert result.limit_type == "token_limit"
        assert result.total_tokens <= 12000  # 约 3 次迭代
        assert result.iterations <= 4

        # 验证告警消息
        assert result.alert_message is not None
        assert "token" in result.alert_message.lower() or "限制" in result.alert_message

        print("✅ 验收通过：完整循环控制场景测试成功！")
        print(f"   - 迭代次数: {result.iterations}")
        print(f"   - 总 Tokens: {result.total_tokens}")
        print(f"   - 限制类型: {result.limit_type}")
        print(f"   - 告警消息: {result.alert_message}")
