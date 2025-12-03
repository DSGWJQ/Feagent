"""执行总结端到端集成测试 - Phase 5

测试目标：
1. WorkflowAgent 执行完成后结果返回给 ConversationAgent
2. ConversationAgent 生成执行总结（含日志、成功/失败、错误）
3. 总结传给 Coordinator 记录
4. Coordinator 触发 WorkflowAgent 推送最终状态给前端
5. 验证总结包含必要字段（规则、知识引用、工具使用）

运行命令：
    pytest tests/integration/test_execution_summary_e2e.py -v -s
"""

import asyncio
from datetime import datetime

import pytest

# === Mock WebSocket ===


class MockWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages: list[dict] = []
        self.receive_queue: asyncio.Queue = asyncio.Queue()

    async def accept(self):
        self.accepted = True

    async def close(self):
        self.closed = True

    async def send_json(self, data: dict):
        self.sent_messages.append(data)

    async def receive_json(self) -> dict:
        return await self.receive_queue.get()

    def put_message(self, data: dict):
        """模拟客户端发送消息"""
        self.receive_queue.put_nowait(data)


# === 端到端集成测试 ===


class TestExecutionSummaryE2E:
    """执行总结端到端测试"""

    @pytest.mark.asyncio
    async def test_complete_summary_flow_success(self):
        """测试：完整总结流程 - 成功场景"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import (
            SummaryGenerator,
        )
        from src.domain.services.event_bus import EventBus

        # 设置组件
        event_bus = EventBus()
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.set_channel_bridge(bridge)
        generator = SummaryGenerator()

        # 建立 WebSocket 连接
        ws = MockWebSocket()
        await channel.register_session("session_e2e", ws, "user_1")

        # 模拟 WorkflowAgent 执行结果
        workflow_result = {
            "workflow_id": "wf_sales_analysis",
            "success": True,
            "node_results": {
                "fetch_data": {
                    "success": True,
                    "output": {"rows": 1000},
                    "tool_id": "http_tool",
                    "duration": 0.5,
                },
                "analyze": {
                    "success": True,
                    "output": {"insights": ["trend_up"]},
                    "tool_id": "llm_tool",
                    "duration": 1.2,
                },
                "generate_report": {
                    "success": True,
                    "output": {"report": "Sales Report"},
                    "duration": 0.3,
                },
            },
            "execution_time": 2.0,
        }

        # 模拟协调者上下文
        coordinator_context = {
            "rules": [
                {
                    "id": "rule_data_validation",
                    "name": "数据验证规则",
                    "description": "验证输入数据",
                },
                {"id": "rule_security", "name": "安全检查规则", "description": "检查安全性"},
            ],
            "knowledge": [
                {
                    "source_id": "kb_sales",
                    "title": "销售数据分析指南",
                    "relevance_score": 0.92,
                },
            ],
            "tools": [
                {"id": "http_tool", "name": "HTTP 请求工具"},
                {"id": "llm_tool", "name": "LLM 分析工具"},
            ],
        }

        # 1. ConversationAgent 生成总结
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_e2e",
            coordinator_context=coordinator_context,
        )

        # 2. Coordinator 记录并推送
        await coordinator.record_and_push_summary(summary)

        # 验证总结已记录
        recorded = coordinator.get_execution_summary("wf_sales_analysis")
        assert recorded is not None
        assert recorded.success is True

        # 验证 WebSocket 推送
        assert len(ws.sent_messages) == 1
        sent = ws.sent_messages[0]
        assert sent["type"] == "execution_summary"
        assert sent["payload"]["workflow_id"] == "wf_sales_analysis"
        assert sent["payload"]["success"] is True

        # 验证总结包含必要字段
        assert len(summary.rules_applied) == 2
        assert len(summary.knowledge_references) == 1
        assert len(summary.tools_used) >= 1
        assert summary.knowledge_references[0].title == "销售数据分析指南"

    @pytest.mark.asyncio
    async def test_complete_summary_flow_failure(self):
        """测试：完整总结流程 - 失败场景"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import SummaryGenerator
        from src.domain.services.event_bus import EventBus

        # 设置组件
        event_bus = EventBus()
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.set_channel_bridge(bridge)
        generator = SummaryGenerator()

        # 建立 WebSocket 连接
        ws = MockWebSocket()
        await channel.register_session("session_fail", ws, "user_2")

        # 模拟失败的工作流结果
        workflow_result = {
            "workflow_id": "wf_failed_task",
            "success": False,
            "failed_node_id": "node_api_call",
            "error_message": "API 响应超时 (timeout after 30s)",
            "node_results": {
                "node_prepare": {"success": True, "output": {}},
                "node_api_call": {
                    "success": False,
                    "error": "API 响应超时 (timeout after 30s)",
                    "error_code": "HTTP_TIMEOUT",
                    "retryable": True,
                },
            },
        }

        coordinator_context = {
            "rules": [{"id": "r1", "name": "超时重试规则", "description": "处理超时"}],
            "knowledge": [],
            "tools": [],
        }

        # 生成总结
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_fail",
            coordinator_context=coordinator_context,
        )

        # 记录并推送
        await coordinator.record_and_push_summary(summary)

        # 验证失败状态
        assert summary.success is False
        assert len(summary.errors) >= 1
        assert "超时" in summary.errors[0].error_message

        # 验证推送的消息
        sent = ws.sent_messages[0]
        assert sent["payload"]["success"] is False
        assert len(sent["payload"]["errors"]) >= 1

    @pytest.mark.asyncio
    async def test_summary_event_published(self):
        """测试：总结记录事件发布"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import (
            ExecutionSummary,
            ExecutionSummaryRecordedEvent,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 订阅事件
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(ExecutionSummaryRecordedEvent, handler)

        # 创建并记录总结
        summary = ExecutionSummary(
            workflow_id="wf_event_test",
            session_id="session_event",
            success=True,
        )

        await coordinator.record_execution_summary_async(summary)

        # 验证事件发布
        assert len(received_events) == 1
        event = received_events[0]
        assert event.workflow_id == "wf_event_test"
        assert event.success is True

    @pytest.mark.asyncio
    async def test_human_readable_summary_generation(self):
        """测试：人类可读总结生成"""
        from src.domain.agents.execution_summary import (
            ExecutionError,
            ExecutionLogEntry,
            ExecutionSummary,
            KnowledgeRef,
            RuleApplication,
            ToolUsage,
        )

        # 创建包含完整信息的总结
        summary = ExecutionSummary(
            workflow_id="wf_readable",
            session_id="session_1",
            success=False,
            execution_logs=[
                ExecutionLogEntry(
                    node_id="n1",
                    action="completed",
                    timestamp=datetime.now(),
                    message="步骤1完成",
                ),
                ExecutionLogEntry(
                    node_id="n2",
                    action="failed",
                    timestamp=datetime.now(),
                    message="步骤2失败",
                ),
            ],
            errors=[
                ExecutionError(
                    node_id="n2",
                    error_code="VALIDATION_ERROR",
                    error_message="数据格式不正确",
                    retryable=False,
                ),
            ],
            rules_applied=[
                RuleApplication(
                    rule_id="r1",
                    rule_name="格式验证",
                    applied=True,
                    result="失败",
                ),
            ],
            knowledge_references=[
                KnowledgeRef(
                    source_id="kb1",
                    title="数据格式规范",
                    relevance_score=0.88,
                ),
            ],
            tools_used=[
                ToolUsage(
                    tool_id="t1",
                    tool_name="验证器",
                    invocations=2,
                    total_time=0.5,
                ),
            ],
        )

        readable = summary.to_human_readable()

        # 验证可读摘要包含关键信息
        assert "wf_readable" in readable
        assert "失败" in readable
        assert "错误" in readable
        assert "格式验证" in readable
        assert "数据格式规范" in readable
        assert "验证器" in readable

    @pytest.mark.asyncio
    async def test_multiple_workflows_summary_tracking(self):
        """测试：多工作流总结跟踪"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import SummaryGenerator
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        generator = SummaryGenerator()

        # 执行多个工作流
        workflow_configs = [
            ("wf_1", True),
            ("wf_2", False),
            ("wf_3", True),
            ("wf_4", True),
            ("wf_5", False),
        ]

        for wf_id, success in workflow_configs:
            result = {
                "workflow_id": wf_id,
                "success": success,
                "node_results": {},
            }

            summary = await generator.generate(
                workflow_result=result,
                session_id=f"session_{wf_id}",
            )

            coordinator.record_execution_summary(summary)

        # 验证统计
        stats = coordinator.get_summary_statistics()
        assert stats["total"] == 5
        assert stats["successful"] == 3
        assert stats["failed"] == 2

        # 验证可以获取每个总结
        assert coordinator.get_execution_summary("wf_1").success is True
        assert coordinator.get_execution_summary("wf_2").success is False

    @pytest.mark.asyncio
    async def test_summary_includes_execution_timing(self):
        """测试：总结包含执行时间信息"""
        from src.domain.agents.execution_summary import SummaryGenerator

        generator = SummaryGenerator()

        result = {
            "workflow_id": "wf_timing",
            "success": True,
            "node_results": {
                "fast_node": {"success": True, "duration": 0.1},
                "slow_node": {"success": True, "duration": 2.5},
            },
            "execution_time": 2.6,
        }

        summary = await generator.generate(
            workflow_result=result,
            session_id="session_timing",
        )

        assert summary.total_duration > 0
        assert summary.completed_at is not None

        # 检查日志中有节点执行记录
        assert len(summary.execution_logs) == 2

    @pytest.mark.asyncio
    async def test_websocket_push_with_full_payload(self):
        """测试：WebSocket 推送包含完整负载"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )
        from src.domain.agents.execution_summary import (
            ExecutionLogEntry,
            ExecutionSummary,
            KnowledgeRef,
            RuleApplication,
            ToolUsage,
        )

        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_full", ws, "user_full")

        # 创建包含所有字段的总结
        summary = ExecutionSummary(
            workflow_id="wf_full_push",
            session_id="session_full",
            success=True,
            execution_logs=[
                ExecutionLogEntry(
                    node_id="n1",
                    action="completed",
                    timestamp=datetime.now(),
                    message="Done",
                ),
            ],
            rules_applied=[
                RuleApplication(rule_id="r1", rule_name="Rule 1", result="pass"),
            ],
            knowledge_references=[
                KnowledgeRef(source_id="k1", title="Doc 1", relevance_score=0.9),
            ],
            tools_used=[
                ToolUsage(tool_id="t1", tool_name="Tool 1", invocations=1, total_time=0.5),
            ],
        )

        # 推送
        await bridge.push_execution_summary("session_full", summary)

        # 验证负载
        sent = ws.sent_messages[0]
        payload = sent["payload"]

        assert "execution_logs" in payload
        assert "rules_applied" in payload
        assert "knowledge_references" in payload
        assert "tools_used" in payload
        assert len(payload["execution_logs"]) == 1
        assert len(payload["rules_applied"]) == 1
        assert len(payload["knowledge_references"]) == 1
        assert len(payload["tools_used"]) == 1

    @pytest.mark.asyncio
    async def test_summary_serialization_roundtrip(self):
        """测试：总结序列化往返"""
        from src.domain.agents.execution_summary import (
            ExecutionError,
            ExecutionLogEntry,
            ExecutionSummary,
            KnowledgeRef,
            RuleApplication,
            ToolUsage,
        )

        # 创建完整总结
        original = ExecutionSummary(
            workflow_id="wf_serial",
            session_id="session_serial",
            success=True,
            execution_logs=[
                ExecutionLogEntry(
                    node_id="n1",
                    action="completed",
                    timestamp=datetime.now(),
                    message="Done",
                    duration=0.5,
                ),
            ],
            errors=[
                ExecutionError(
                    node_id="n2",
                    error_code="ERR",
                    error_message="Error msg",
                    retryable=True,
                ),
            ],
            rules_applied=[
                RuleApplication(rule_id="r1", rule_name="Rule", applied=True, result="OK"),
            ],
            knowledge_references=[
                KnowledgeRef(source_id="k1", title="Title", relevance_score=0.8),
            ],
            tools_used=[
                ToolUsage(tool_id="t1", tool_name="Tool", invocations=2, total_time=1.0),
            ],
        )

        # 序列化
        data = original.to_dict()

        # 验证字典包含所有字段
        assert data["workflow_id"] == "wf_serial"
        assert data["success"] is True
        assert len(data["execution_logs"]) == 1
        assert len(data["errors"]) == 1
        assert len(data["rules_applied"]) == 1
        assert len(data["knowledge_references"]) == 1
        assert len(data["tools_used"]) == 1


class TestSummaryOrderVerification:
    """验证总结流程顺序"""

    @pytest.mark.asyncio
    async def test_correct_order_task_summary_coordinator_push(self):
        """测试：正确顺序（任务总结 → 协调者记录 → 推送前端）"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import (
            ExecutionSummaryRecordedEvent,
            SummaryGenerator,
        )
        from src.domain.services.event_bus import EventBus

        # 跟踪执行顺序
        execution_order = []

        # 设置组件
        event_bus = EventBus()
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.set_channel_bridge(bridge)
        generator = SummaryGenerator()

        # 监听事件
        async def on_summary_recorded(event):
            execution_order.append("coordinator_recorded")

        event_bus.subscribe(ExecutionSummaryRecordedEvent, on_summary_recorded)

        # Mock WebSocket
        ws = MockWebSocket()
        original_send = ws.send_json

        async def tracked_send(data):
            execution_order.append("frontend_push")
            await original_send(data)

        ws.send_json = tracked_send

        await channel.register_session("session_order", ws, "user_order")

        # 执行流程
        workflow_result = {
            "workflow_id": "wf_order_test",
            "success": True,
            "node_results": {},
        }

        # Step 1: 生成总结
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_order",
        )
        execution_order.append("summary_generated")

        # Step 2: 协调者记录并推送
        await coordinator.record_and_push_summary(summary)

        # 验证顺序
        assert len(execution_order) >= 3
        assert execution_order[0] == "summary_generated"
        assert "coordinator_recorded" in execution_order
        assert "frontend_push" in execution_order

        # 协调者记录应该在推送之前或同时
        recorded_idx = execution_order.index("coordinator_recorded")
        push_idx = execution_order.index("frontend_push")
        assert recorded_idx <= push_idx


# 导出
__all__ = [
    "TestExecutionSummaryE2E",
    "TestSummaryOrderVerification",
]
