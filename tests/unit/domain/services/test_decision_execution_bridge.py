"""决策执行桥接器测试 - Phase 8.4

TDD RED阶段：测试 DecisionExecutionBridge 服务
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestDecisionExecutionBridge:
    """DecisionExecutionBridge 基础测试"""

    def test_create_bridge(self):
        """应能创建桥接器"""
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        bridge = DecisionExecutionBridge(event_bus=event_bus)

        assert bridge is not None
        assert bridge.event_bus is event_bus

    def test_bridge_with_validator(self):
        """应能配置决策验证器"""
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        validator = MagicMock()

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
        )

        assert bridge.decision_validator is validator


class TestBridgeSubscription:
    """桥接器事件订阅测试"""

    @pytest.mark.asyncio
    async def test_bridge_subscribes_to_decision_events(self):
        """桥接器应订阅决策事件"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        bridge = DecisionExecutionBridge(event_bus=event_bus)

        await bridge.start()

        # 验证已订阅
        assert DecisionMadeEvent in event_bus._subscribers
        assert len(event_bus._subscribers[DecisionMadeEvent]) > 0

    @pytest.mark.asyncio
    async def test_bridge_stop_unsubscribes(self):
        """停止桥接器应取消订阅"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        bridge = DecisionExecutionBridge(event_bus=event_bus)

        await bridge.start()
        await bridge.stop()

        # 验证已取消订阅
        assert (
            DecisionMadeEvent not in event_bus._subscribers
            or len(event_bus._subscribers[DecisionMadeEvent]) == 0
        )


class TestBridgeValidation:
    """桥接器验证测试"""

    @pytest.mark.asyncio
    async def test_bridge_validates_decision_before_execution(self):
        """执行前应验证决策"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        # Mock 验证器
        validator = MagicMock()
        validator.validate = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="approved"),
                violations=[],
            )
        )

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
        )

        await bridge.start()

        # 发布决策事件
        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
            decision_id="dec_1",
            payload={"plan": {"nodes": [], "edges": []}},
        )
        await event_bus.publish(event)

        # 验证器应被调用
        validator.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_bridge_handles_validation_rejection(self):
        """处理验证拒绝情况"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        # Mock 验证器返回拒绝
        validator = MagicMock()
        validator.validate = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="rejected"),
                violations=["危险操作"],
            )
        )

        # Mock WorkflowAgent 工厂
        workflow_agent = MagicMock()
        workflow_agent.execute_plan = AsyncMock()

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        # 发布决策事件
        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
            decision_id="dec_1",
            payload={"plan": {"nodes": [], "edges": []}},
        )
        await event_bus.publish(event)

        # WorkflowAgent 不应被调用（因为验证失败）
        workflow_agent.execute_plan.assert_not_called()


class TestBridgeExecution:
    """桥接器执行测试"""

    @pytest.mark.asyncio
    async def test_bridge_forwards_to_workflow_agent(self):
        """验证通过后转发给 WorkflowAgent"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        # Mock 验证器返回通过
        validator = MagicMock()
        validator.validate = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="approved"),
                violations=[],
            )
        )

        # Mock WorkflowAgent - 注意现在使用 execute_plan_from_dict
        workflow_agent = MagicMock()
        workflow_agent.execute_plan_from_dict = AsyncMock(
            return_value={"status": "completed", "results": {}}
        )

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        # 发布工作流规划决策
        plan_data = {
            "id": "plan_1",
            "name": "Test Plan",
            "nodes": [{"name": "N1", "node_type": "python", "code": "pass"}],
            "edges": [],
        }
        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
            decision_id="dec_1",
            payload=plan_data,
        )
        await event_bus.publish(event)

        # WorkflowAgent 应被调用
        workflow_agent.execute_plan_from_dict.assert_called_once()

    @pytest.mark.asyncio
    async def test_bridge_publishes_execution_result(self):
        """应发布执行结果事件"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import (
            DecisionExecutionBridge,
            ExecutionResultEvent,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_results = []

        async def result_handler(event):
            received_results.append(event)

        event_bus.subscribe(ExecutionResultEvent, result_handler)

        # Mock 验证器
        validator = MagicMock()
        validator.validate = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="approved"),
                violations=[],
            )
        )

        # Mock WorkflowAgent - 注意现在使用 execute_plan_from_dict
        workflow_agent = MagicMock()
        workflow_agent.execute_plan_from_dict = AsyncMock(
            return_value={"status": "completed", "results": {"node_1": "done"}}
        )

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            decision_validator=validator,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        # 发布决策
        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
            decision_id="dec_1",
            payload={"nodes": [], "edges": []},
        )
        await event_bus.publish(event)

        # 应收到执行结果事件
        assert len(received_results) >= 1
        assert received_results[0].status == "completed"


class TestBridgeDecisionTypes:
    """桥接器决策类型处理测试"""

    @pytest.mark.asyncio
    async def test_bridge_handles_create_node_decision(self):
        """应处理 CREATE_NODE 决策"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        workflow_agent = MagicMock()
        workflow_agent.handle_decision = AsyncMock(
            return_value={"success": True, "node_id": "node_123"}
        )

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_NODE.value,
            decision_id="dec_1",
            payload={"node_type": "python", "config": {"code": "pass"}},
        )
        await event_bus.publish(event)

        workflow_agent.handle_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_bridge_handles_execute_workflow_decision(self):
        """应处理 EXECUTE_WORKFLOW 决策"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        workflow_agent = MagicMock()
        workflow_agent.handle_decision = AsyncMock(
            return_value={"success": True, "status": "completed"}
        )

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.EXECUTE_WORKFLOW.value,
            decision_id="dec_1",
            payload={"workflow_id": "wf_123"},
        )
        await event_bus.publish(event)

        workflow_agent.handle_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_bridge_ignores_non_actionable_decisions(self):
        """应忽略非可执行决策（如 RESPOND）"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        workflow_agent = MagicMock()
        workflow_agent.handle_decision = AsyncMock()

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        # RESPOND 类型不应触发执行
        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.RESPOND.value,
            decision_id="dec_1",
            payload={"response": "Hello"},
        )
        await event_bus.publish(event)

        workflow_agent.handle_decision.assert_not_called()


class TestBridgeErrorHandling:
    """桥接器错误处理测试"""

    @pytest.mark.asyncio
    async def test_bridge_handles_execution_error(self):
        """应处理执行错误"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import (
            DecisionExecutionBridge,
            ExecutionResultEvent,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_results = []

        async def result_handler(event):
            received_results.append(event)

        event_bus.subscribe(ExecutionResultEvent, result_handler)

        # Mock WorkflowAgent 抛出异常
        workflow_agent = MagicMock()
        workflow_agent.handle_decision = AsyncMock(side_effect=Exception("执行失败"))

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        event = DecisionMadeEvent(
            source="test",
            decision_type=DecisionType.CREATE_NODE.value,
            decision_id="dec_1",
            payload={"node_type": "python"},
        )
        await event_bus.publish(event)

        # 应收到失败结果
        assert len(received_results) >= 1
        assert received_results[0].status == "failed"
        assert "执行失败" in received_results[0].error

    @pytest.mark.asyncio
    async def test_bridge_continues_after_error(self):
        """错误后应继续处理后续决策"""
        from src.domain.agents.conversation_agent import DecisionMadeEvent, DecisionType
        from src.domain.services.decision_execution_bridge import DecisionExecutionBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        call_count = 0

        workflow_agent = MagicMock()

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("第一次失败")
            return {"success": True}

        workflow_agent.handle_decision = AsyncMock(side_effect=side_effect)

        bridge = DecisionExecutionBridge(
            event_bus=event_bus,
            workflow_agent_factory=lambda: workflow_agent,
        )

        await bridge.start()

        # 发布两个决策
        for i in range(2):
            event = DecisionMadeEvent(
                source="test",
                decision_type=DecisionType.CREATE_NODE.value,
                decision_id=f"dec_{i}",
                payload={"node_type": "python"},
            )
            await event_bus.publish(event)

        # 应调用两次（即使第一次失败）
        assert workflow_agent.handle_decision.call_count == 2
